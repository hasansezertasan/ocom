"""Tests for SpoofDPITool."""

from typing import TYPE_CHECKING
from unittest.mock import AsyncMock, MagicMock

import pytest

from ocom.core.tool import ToolConfig, ToolStatus
from ocom.core.tools.spoofdpi import SpoofDPITool

if TYPE_CHECKING:
    from pytest_mock import MockerFixture


@pytest.fixture
def tool() -> SpoofDPITool:
    """Create a SpoofDPITool instance."""
    return SpoofDPITool()


class TestConstruction:
    """Test SpoofDPITool attributes and construction."""

    def test_attributes(self, tool: SpoofDPITool) -> None:
        """Class attributes should match the documented tool contract."""
        assert tool.name == "SpoofDPI"
        assert tool.command == "spoofdpi"
        assert tool.requires_sudo is False
        assert tool.supports_configs is False
        assert tool.conflicts_with == ["GoodbyeDPI"]
        assert tool._port == 8080


class TestStart:
    """Test SpoofDPITool.start()."""

    async def test_start_success_port_ready(
        self, tool: SpoofDPITool, mocker: MockerFixture
    ) -> None:
        """A running process with a bound port reports RUNNING."""
        mocker.patch(
            "ocom.core.tools.spoofdpi.ProcessManager.start_process",
            new=AsyncMock(return_value=MagicMock(returncode=None)),
        )
        mocker.patch(
            "ocom.core.tools.spoofdpi.ProcessManager.is_process_running",
            return_value=True,
        )
        mocker.patch(
            "ocom.core.tools.spoofdpi.ProcessManager.check_port_in_use",
            new=AsyncMock(return_value=True),
        )
        mocker.patch("ocom.core.tools.spoofdpi.asyncio.sleep", new=AsyncMock())
        config = ToolConfig(
            options={
                "port": 9090,
                "dns_addr": "1.1.1.1",
                "dns_mode": "dot",
                "system_proxy": True,
            },
            extra_args=["--debug"],
        )
        result = await tool.start(config)
        assert result is True
        assert tool.status == ToolStatus.RUNNING
        assert tool._port == 9090

    async def test_start_success_port_not_ready(
        self, tool: SpoofDPITool, mocker: MockerFixture
    ) -> None:
        """A running process without a bound port still reports RUNNING."""
        mocker.patch(
            "ocom.core.tools.spoofdpi.ProcessManager.start_process",
            new=AsyncMock(return_value=MagicMock(returncode=None)),
        )
        mocker.patch(
            "ocom.core.tools.spoofdpi.ProcessManager.is_process_running",
            return_value=True,
        )
        mocker.patch(
            "ocom.core.tools.spoofdpi.ProcessManager.check_port_in_use",
            new=AsyncMock(return_value=False),
        )
        mocker.patch("ocom.core.tools.spoofdpi.asyncio.sleep", new=AsyncMock())
        result = await tool.start(ToolConfig())
        assert result is True
        assert tool.status == ToolStatus.RUNNING

    async def test_start_process_raises(
        self, tool: SpoofDPITool, mocker: MockerFixture
    ) -> None:
        """A raising start_process should be caught and reported as ERROR."""
        mocker.patch(
            "ocom.core.tools.spoofdpi.ProcessManager.start_process",
            new=AsyncMock(side_effect=RuntimeError("boom")),
        )
        result = await tool.start(ToolConfig())
        assert result is False
        assert tool.status == ToolStatus.ERROR
        assert tool.error_message == "boom"

    async def test_start_process_exits(
        self, tool: SpoofDPITool, mocker: MockerFixture
    ) -> None:
        """A process that exits early should be reported as ERROR."""
        mocker.patch(
            "ocom.core.tools.spoofdpi.ProcessManager.start_process",
            new=AsyncMock(return_value=MagicMock(returncode=3)),
        )
        mocker.patch(
            "ocom.core.tools.spoofdpi.ProcessManager.is_process_running",
            return_value=False,
        )
        mocker.patch("ocom.core.tools.spoofdpi.asyncio.sleep", new=AsyncMock())
        result = await tool.start(ToolConfig())
        assert result is False
        assert tool.status == ToolStatus.ERROR
        assert tool.error_message == "Process exited with code 3"


class TestStop:
    """Test SpoofDPITool.stop()."""

    async def test_stop_without_process(self, tool: SpoofDPITool) -> None:
        """Stopping with no process should just report STOPPED."""
        result = await tool.stop()
        assert result is True
        assert tool.status == ToolStatus.STOPPED

    async def test_stop_with_process(
        self, tool: SpoofDPITool, mocker: MockerFixture
    ) -> None:
        """Stopping with a process should stop it and clear state."""
        tool._process = MagicMock(returncode=None)
        mocker.patch(
            "ocom.core.tools.spoofdpi.ProcessManager.stop_process",
            new=AsyncMock(return_value=True),
        )
        result = await tool.stop()
        assert result is True
        assert tool.status == ToolStatus.STOPPED
        assert tool._process is None


class TestRefreshStatus:
    """Test SpoofDPITool.refresh_status() and reconcilers."""

    async def test_unavailable_rechecks(
        self, tool: SpoofDPITool, mocker: MockerFixture
    ) -> None:
        """UNAVAILABLE should re-run availability detection."""
        tool._status = ToolStatus.UNAVAILABLE
        mocker.patch(
            "ocom.core.tools.spoofdpi.ProcessManager.find_command", return_value=None
        )
        assert await tool.refresh_status() == ToolStatus.UNAVAILABLE

    async def test_process_running(
        self, tool: SpoofDPITool, mocker: MockerFixture
    ) -> None:
        """A live tracked process should be reported RUNNING."""
        tool._status = ToolStatus.RUNNING
        tool._process = MagicMock(returncode=None)
        mocker.patch(
            "ocom.core.tools.spoofdpi.ProcessManager.is_process_running",
            return_value=True,
        )
        assert await tool.refresh_status() == ToolStatus.RUNNING

    async def test_process_died(
        self, tool: SpoofDPITool, mocker: MockerFixture
    ) -> None:
        """A dead tracked process should reset to STOPPED and clear it."""
        tool._status = ToolStatus.RUNNING
        tool._process = MagicMock(returncode=1)
        mocker.patch(
            "ocom.core.tools.spoofdpi.ProcessManager.is_process_running",
            return_value=False,
        )
        assert await tool.refresh_status() == ToolStatus.STOPPED
        assert tool._process is None

    async def test_port_still_in_use(
        self, tool: SpoofDPITool, mocker: MockerFixture
    ) -> None:
        """No process but RUNNING: an in-use port keeps it RUNNING."""
        tool._status = ToolStatus.RUNNING
        tool._process = None
        mocker.patch(
            "ocom.core.tools.spoofdpi.ProcessManager.check_port_in_use",
            new=AsyncMock(return_value=True),
        )
        assert await tool.refresh_status() == ToolStatus.RUNNING

    async def test_no_process_not_running(self, tool: SpoofDPITool) -> None:
        """No process and not RUNNING returns the status unchanged."""
        tool._status = ToolStatus.STOPPED
        tool._process = None
        assert await tool.refresh_status() == ToolStatus.STOPPED

    async def test_port_freed(self, tool: SpoofDPITool, mocker: MockerFixture) -> None:
        """No process but RUNNING: a freed port drops it to STOPPED."""
        tool._status = ToolStatus.RUNNING
        tool._process = None
        mocker.patch(
            "ocom.core.tools.spoofdpi.ProcessManager.check_port_in_use",
            new=AsyncMock(return_value=False),
        )
        assert await tool.refresh_status() == ToolStatus.STOPPED


class TestGetStatusText:
    """Test SpoofDPITool.get_status_text()."""

    def test_running(self, tool: SpoofDPITool) -> None:
        """Running status includes the proxy port."""
        tool._status = ToolStatus.RUNNING
        tool._port = 8123
        assert tool.get_status_text() == "Proxy on :8123"

    def test_non_running_delegates(self, tool: SpoofDPITool) -> None:
        """Non-running status defers to the base implementation."""
        tool._status = ToolStatus.STOPPED
        assert tool.get_status_text() == "Stopped"
