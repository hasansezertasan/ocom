"""Tests for GoodbyeDPITool."""

import asyncio
from typing import TYPE_CHECKING
from unittest.mock import AsyncMock, MagicMock

import pytest

from ocom.core.tool import ToolConfig, ToolStatus
from ocom.core.tools.goodbyedpi import GoodbyeDPITool

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


@pytest.mark.usefixtures("fast_ready")
class TestStart:
    """Test GoodbyeDPITool.start()."""

    @pytest.fixture
    def fast_ready(self, mocker: MockerFixture) -> None:
        """Run as admin with a short readiness window and a fast poll."""
        mocker.patch("ocom.core.tools.goodbyedpi.is_admin", return_value=True)
        mocker.patch("ocom.core.tools.goodbyedpi.READY_WINDOW", 0.02)
        mocker.patch("ocom.core.tool.READY_POLL_INTERVAL", 0.001)

    @pytest.fixture
    def stop(self, mocker: MockerFixture) -> AsyncMock:
        """Patch stop_process."""
        return mocker.patch(
            "ocom.core.tools.goodbyedpi.ProcessManager.stop_process",
            new=AsyncMock(return_value=True),
        )

    async def test_start_requires_admin(
        self, tool: GoodbyeDPITool, mocker: MockerFixture
    ) -> None:
        """Without admin rights start fails with a clear error."""
        mocker.patch("ocom.core.tools.goodbyedpi.is_admin", return_value=False)
        result = await tool.start(ToolConfig())
        assert result is False
        assert tool.status == ToolStatus.ERROR
        assert tool.error_message == "Administrator privileges required"

    async def test_start_process_raises(
        self, tool: GoodbyeDPITool, mocker: MockerFixture
    ) -> None:
        """A raising start_process should be caught and reported as ERROR."""
        mocker.patch(
            "ocom.core.tools.goodbyedpi.ProcessManager.start_process",
            new=AsyncMock(side_effect=RuntimeError("boom")),
        )
        result = await tool.start(ToolConfig())
        assert result is False
        assert tool.status == ToolStatus.ERROR
        assert tool.error_message == "boom"

    async def test_start_success_with_options(
        self, tool: GoodbyeDPITool, mocker: MockerFixture
    ) -> None:
        """A process that stays up with a custom mode reaches RUNNING."""
        spawn = mocker.patch(
            "ocom.core.tools.goodbyedpi.ProcessManager.start_process",
            new=AsyncMock(return_value=MagicMock(returncode=None)),
        )
        result = await tool.start(
            ToolConfig(options={"mode": 3, "block_quic": False}, extra_args=["-x"])
        )
        assert result is True
        assert tool.status == ToolStatus.RUNNING
        assert tool._mode == 3
        assert spawn.await_args is not None
        assert spawn.await_args.args[0] == ["goodbyedpi", "-3", "-x"]

    async def test_starting_until_window_passes(
        self, tool: GoodbyeDPITool, mocker: MockerFixture
    ) -> None:
        """A refresh during the readiness window must not report RUNNING early."""
        mocker.patch(
            "ocom.core.tools.goodbyedpi.ProcessManager.start_process",
            new=AsyncMock(return_value=MagicMock(returncode=None)),
        )
        mocker.patch("ocom.core.tools.goodbyedpi.READY_WINDOW", 60.0)
        task = asyncio.create_task(tool.start(ToolConfig()))
        await asyncio.sleep(0.01)
        assert await tool.refresh_status() == ToolStatus.STARTING
        task.cancel()
        await asyncio.wait([task])

    async def test_start_process_exits(
        self, tool: GoodbyeDPITool, mocker: MockerFixture, stop: AsyncMock
    ) -> None:
        """A process that exits during the window is ERROR and cleaned up."""
        mocker.patch(
            "ocom.core.tools.goodbyedpi.ProcessManager.start_process",
            new=AsyncMock(return_value=MagicMock(returncode=1)),
        )
        result = await tool.start(ToolConfig())
        assert result is False
        assert tool.status == ToolStatus.ERROR
        assert tool.error_message == (
            "Process exited with code 1 (run as Administrator?)"
        )
        assert tool._process is None
        stop.assert_awaited_once()

    async def test_start_cancelled(
        self, tool: GoodbyeDPITool, mocker: MockerFixture, stop: AsyncMock
    ) -> None:
        """Cancelling mid-window stops the process instead of stranding STARTING."""
        proc = MagicMock(returncode=None)
        mocker.patch(
            "ocom.core.tools.goodbyedpi.ProcessManager.start_process",
            new=AsyncMock(return_value=proc),
        )
        mocker.patch("ocom.core.tools.goodbyedpi.READY_WINDOW", 60.0)
        task = asyncio.create_task(tool.start(ToolConfig()))
        await asyncio.sleep(0.01)
        task.cancel()
        await asyncio.wait([task])
        assert task.cancelled()
        assert tool.status == ToolStatus.STOPPED
        assert tool._process is None
        stop.assert_awaited_once_with(proc)


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
            "ocom.core.tools.goodbyedpi.ProcessManager.stop_process",
            new=AsyncMock(return_value=True),
        )
        result = await tool.stop()
        assert result is True
        assert tool.status == ToolStatus.STOPPED
        assert tool._process is None

    async def test_refresh_during_stop_keeps_stopping(
        self, tool: GoodbyeDPITool, mocker: MockerFixture
    ) -> None:
        """A refresh while stopping must not flip STOPPING back to RUNNING."""
        tool._status = ToolStatus.RUNNING
        tool._process = MagicMock(returncode=None)
        during_stop: list[ToolStatus] = []

        async def slow_stop(_proc: MagicMock) -> bool:
            during_stop.append(await tool.refresh_status())
            return True

        mocker.patch(
            "ocom.core.tools.goodbyedpi.ProcessManager.stop_process", new=slow_stop
        )
        assert await tool.stop() is True
        assert during_stop == [ToolStatus.STOPPING]
        assert tool.status == ToolStatus.STOPPED


class TestRefreshStatus:
    """Test GoodbyeDPITool.refresh_status()."""

    async def test_unavailable_rechecks(
        self, tool: GoodbyeDPITool, mocker: MockerFixture
    ) -> None:
        """UNAVAILABLE should re-run availability detection."""
        tool._status = ToolStatus.UNAVAILABLE
        mocker.patch(
            "ocom.core.tools.goodbyedpi.ProcessManager.find_command", return_value=None
        )
        assert await tool.refresh_status() == ToolStatus.UNAVAILABLE

    async def test_process_running(
        self, tool: GoodbyeDPITool, mocker: MockerFixture
    ) -> None:
        """A live process should be reported RUNNING."""
        tool._status = ToolStatus.RUNNING
        tool._process = MagicMock(returncode=None)
        mocker.patch(
            "ocom.core.tools.goodbyedpi.ProcessManager.is_process_running",
            return_value=True,
        )
        assert await tool.refresh_status() == ToolStatus.RUNNING

    @pytest.mark.parametrize("status", [ToolStatus.STARTING, ToolStatus.STOPPING])
    async def test_transitioning_left_alone(
        self, tool: GoodbyeDPITool, mocker: MockerFixture, status: ToolStatus
    ) -> None:
        """A refresh mid-transition must not override start()/stop()'s status."""
        tool._status = status
        tool._process = MagicMock(returncode=None)
        running = mocker.patch(
            "ocom.core.tools.goodbyedpi.ProcessManager.is_process_running",
            return_value=True,
        )
        assert await tool.refresh_status() == status
        running.assert_not_called()

    async def test_process_died(
        self, tool: GoodbyeDPITool, mocker: MockerFixture
    ) -> None:
        """A dead process should reset to STOPPED and clear it."""
        tool._status = ToolStatus.RUNNING
        tool._process = MagicMock(returncode=1)
        mocker.patch(
            "ocom.core.tools.goodbyedpi.ProcessManager.is_process_running",
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
