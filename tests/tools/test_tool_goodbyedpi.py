"""Tests for GoodbyeDPITool."""

from typing import TYPE_CHECKING
from unittest.mock import AsyncMock, MagicMock

import pytest

from ocom.core.tool import ToolConfig, ToolStatus
from ocom.tools.goodbyedpi import GoodbyeDPITool

if TYPE_CHECKING:
    from pytest_mock import MockerFixture


@pytest.fixture
def tool() -> GoodbyeDPITool:
    """Create a GoodbyeDPITool instance."""
    return GoodbyeDPITool()


class TestConstruction:
    """Test GoodbyeDPITool attributes."""

    def test_attributes(self, tool: GoodbyeDPITool) -> None:
        """Class attributes should match the documented tool contract."""
        assert tool.name == "GoodbyeDPI"
        assert tool.command == "goodbyedpi"
        assert tool.requires_sudo is False
        assert tool.conflicts_with == ["SpoofDPI"]
        assert tool._mode == 9


class TestStart:
    """Test GoodbyeDPITool.start()."""

    async def test_start_requires_admin(
        self, tool: GoodbyeDPITool, mocker: MockerFixture
    ) -> None:
        """Without admin rights start fails with a clear error."""
        mocker.patch("ocom.tools.goodbyedpi.is_admin", return_value=False)
        result = await tool.start(ToolConfig())
        assert result is False
        assert tool.status == ToolStatus.ERROR
        assert tool.error_message == "Administrator privileges required"

    async def test_start_process_raises(
        self, tool: GoodbyeDPITool, mocker: MockerFixture
    ) -> None:
        """A raising start_process should be caught and reported as ERROR."""
        mocker.patch("ocom.tools.goodbyedpi.is_admin", return_value=True)
        mocker.patch(
            "ocom.tools.goodbyedpi.ProcessManager.start_process",
            new=AsyncMock(side_effect=RuntimeError("boom")),
        )
        result = await tool.start(ToolConfig())
        assert result is False
        assert tool.status == ToolStatus.ERROR
        assert tool.error_message == "boom"

    async def test_start_success_with_options(
        self, tool: GoodbyeDPITool, mocker: MockerFixture
    ) -> None:
        """A running process with a custom mode reaches RUNNING."""
        mocker.patch("ocom.tools.goodbyedpi.is_admin", return_value=True)
        mocker.patch(
            "ocom.tools.goodbyedpi.ProcessManager.start_process",
            new=AsyncMock(return_value=MagicMock(returncode=None)),
        )
        mocker.patch(
            "ocom.tools.goodbyedpi.ProcessManager.is_process_running", return_value=True
        )
        mocker.patch("ocom.tools.goodbyedpi.asyncio.sleep", new=AsyncMock())
        result = await tool.start(
            ToolConfig(options={"mode": 3, "block_quic": False}, extra_args=["-x"])
        )
        assert result is True
        assert tool.status == ToolStatus.RUNNING
        assert tool._mode == 3

    async def test_start_process_exits(
        self, tool: GoodbyeDPITool, mocker: MockerFixture
    ) -> None:
        """A process that exits early should be reported as ERROR."""
        mocker.patch("ocom.tools.goodbyedpi.is_admin", return_value=True)
        mocker.patch(
            "ocom.tools.goodbyedpi.ProcessManager.start_process",
            new=AsyncMock(return_value=MagicMock(returncode=1)),
        )
        mocker.patch(
            "ocom.tools.goodbyedpi.ProcessManager.is_process_running",
            return_value=False,
        )
        mocker.patch("ocom.tools.goodbyedpi.asyncio.sleep", new=AsyncMock())
        result = await tool.start(ToolConfig())
        assert result is False
        assert tool.status == ToolStatus.ERROR
        assert "Process exited unexpectedly" in str(tool.error_message)


class TestStop:
    """Test GoodbyeDPITool.stop()."""

    async def test_stop_without_process(self, tool: GoodbyeDPITool) -> None:
        """Stopping with no process should just report STOPPED."""
        result = await tool.stop()
        assert result is True
        assert tool.status == ToolStatus.STOPPED

    async def test_stop_with_process(
        self, tool: GoodbyeDPITool, mocker: MockerFixture
    ) -> None:
        """Stopping with a process should stop it and clear state."""
        tool._process = MagicMock(returncode=None)
        mocker.patch(
            "ocom.tools.goodbyedpi.ProcessManager.stop_process",
            new=AsyncMock(return_value=True),
        )
        result = await tool.stop()
        assert result is True
        assert tool.status == ToolStatus.STOPPED
        assert tool._process is None


class TestRefreshStatus:
    """Test GoodbyeDPITool.refresh_status()."""

    async def test_unavailable_rechecks(
        self, tool: GoodbyeDPITool, mocker: MockerFixture
    ) -> None:
        """UNAVAILABLE should re-run availability detection."""
        tool._status = ToolStatus.UNAVAILABLE
        mocker.patch(
            "ocom.tools.goodbyedpi.ProcessManager.find_command", return_value=None
        )
        assert await tool.refresh_status() == ToolStatus.UNAVAILABLE

    async def test_process_running(
        self, tool: GoodbyeDPITool, mocker: MockerFixture
    ) -> None:
        """A live process should be reported RUNNING."""
        tool._status = ToolStatus.RUNNING
        tool._process = MagicMock(returncode=None)
        mocker.patch(
            "ocom.tools.goodbyedpi.ProcessManager.is_process_running", return_value=True
        )
        assert await tool.refresh_status() == ToolStatus.RUNNING

    async def test_process_died(
        self, tool: GoodbyeDPITool, mocker: MockerFixture
    ) -> None:
        """A dead process should reset to STOPPED and clear it."""
        tool._status = ToolStatus.RUNNING
        tool._process = MagicMock(returncode=1)
        mocker.patch(
            "ocom.tools.goodbyedpi.ProcessManager.is_process_running",
            return_value=False,
        )
        assert await tool.refresh_status() == ToolStatus.STOPPED
        assert tool._process is None

    async def test_no_process(self, tool: GoodbyeDPITool) -> None:
        """With no process the current status is returned unchanged."""
        tool._status = ToolStatus.STOPPED
        assert await tool.refresh_status() == ToolStatus.STOPPED


class TestGetStatusText:
    """Test GoodbyeDPITool.get_status_text()."""

    def test_running(self, tool: GoodbyeDPITool) -> None:
        """Running status includes the active mode."""
        tool._status = ToolStatus.RUNNING
        tool._mode = 5
        assert tool.get_status_text() == "Mode 5"

    def test_non_running_delegates(self, tool: GoodbyeDPITool) -> None:
        """Non-running status defers to the base implementation."""
        tool._status = ToolStatus.STOPPED
        assert tool.get_status_text() == "Stopped"


class TestHandleOutput:
    """Test GoodbyeDPITool._handle_output()."""

    def test_emits_line(self, tool: GoodbyeDPITool) -> None:
        """Output lines are forwarded to the registered callback."""
        seen: list[tuple[str, str]] = []
        tool.set_output_callback(lambda name, msg: seen.append((name, msg)))
        tool._handle_output("hello")
        assert seen == [("GoodbyeDPI", "hello")]
