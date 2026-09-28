"""Tests for SpoofDPITool."""

import asyncio
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


@pytest.mark.usefixtures("fast_ready")
class TestStart:
    """Test SpoofDPITool.start()."""

    @pytest.fixture
    def fast_ready(self, mocker: MockerFixture) -> None:
        """Shrink the readiness wait so a hung poll fails fast instead of hanging."""
        mocker.patch("ocom.core.tools.spoofdpi.READY_TIMEOUT", 0.05)
        mocker.patch("ocom.core.tools.spoofdpi.READY_POLL_INTERVAL", 0.001)

    @pytest.fixture
    def proc(self, mocker: MockerFixture) -> MagicMock:
        """Patch start_process to return a mock process."""
        process = MagicMock(returncode=None)
        mocker.patch(
            "ocom.core.tools.spoofdpi.ProcessManager.start_process",
            new=AsyncMock(return_value=process),
        )
        return process

    @pytest.fixture
    def stop(self, mocker: MockerFixture) -> AsyncMock:
        """Patch stop_process."""
        return mocker.patch(
            "ocom.core.tools.spoofdpi.ProcessManager.stop_process",
            new=AsyncMock(return_value=True),
        )

    @staticmethod
    def _patch_probes(
        mocker: MockerFixture, *, running: bool, ports: list[bool] | bool
    ) -> AsyncMock:
        """Patch liveness and port probes; a list gives successive port results."""
        mocker.patch(
            "ocom.core.tools.spoofdpi.ProcessManager.is_process_running",
            return_value=running,
        )
        if isinstance(ports, list):
            return mocker.patch(
                "ocom.core.tools.spoofdpi.ProcessManager.check_port_in_use",
                new=AsyncMock(side_effect=ports),
            )
        return mocker.patch(
            "ocom.core.tools.spoofdpi.ProcessManager.check_port_in_use",
            new=AsyncMock(return_value=ports),
        )

    @pytest.mark.usefixtures("proc")
    async def test_start_success_port_ready(
        self, tool: SpoofDPITool, mocker: MockerFixture
    ) -> None:
        """A running process with a bound port reports RUNNING."""
        self._patch_probes(mocker, running=True, ports=[False, True])
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

    @pytest.mark.usefixtures("proc")
    async def test_start_waits_for_port(
        self, tool: SpoofDPITool, mocker: MockerFixture
    ) -> None:
        """Status stays STARTING while polling; RUNNING only once the port opens."""
        seen: list[ToolStatus] = []

        async def port_probe(_port: int) -> bool:
            seen.append(tool.status)
            return len(seen) > 3  # pre-check free, then two misses, then bound

        mocker.patch(
            "ocom.core.tools.spoofdpi.ProcessManager.is_process_running",
            return_value=True,
        )
        mocker.patch(
            "ocom.core.tools.spoofdpi.ProcessManager.check_port_in_use", new=port_probe
        )
        result = await tool.start(ToolConfig())
        assert result is True
        assert tool.status == ToolStatus.RUNNING
        assert seen == [ToolStatus.STARTING] * 4

    async def test_start_port_already_in_use(
        self, tool: SpoofDPITool, mocker: MockerFixture
    ) -> None:
        """A port held by another listener fails before spawning anything."""
        spawn = mocker.patch(
            "ocom.core.tools.spoofdpi.ProcessManager.start_process", new=AsyncMock()
        )
        self._patch_probes(mocker, running=True, ports=True)
        result = await tool.start(ToolConfig())
        assert result is False
        assert tool.status == ToolStatus.ERROR
        assert tool.error_message == "Port 127.0.0.1:8080 is already in use"
        spawn.assert_not_awaited()

    async def test_start_port_never_ready(
        self,
        tool: SpoofDPITool,
        mocker: MockerFixture,
        proc: MagicMock,
        stop: AsyncMock,
    ) -> None:
        """A port that never opens times out to ERROR and stops the process."""
        self._patch_probes(mocker, running=True, ports=False)
        result = await tool.start(ToolConfig())
        assert result is False
        assert tool.status == ToolStatus.ERROR
        assert tool.error_message == (
            "Proxy did not listen on 127.0.0.1:8080 within 0.05s"
        )
        stop.assert_awaited_once_with(proc)
        assert tool._process is None

    async def test_abort_detaches_process_before_stopping(
        self, tool: SpoofDPITool, mocker: MockerFixture
    ) -> None:
        """A refresh while the failed process shuts down keeps ERROR."""
        mocker.patch(
            "ocom.core.tools.spoofdpi.ProcessManager.start_process",
            new=AsyncMock(return_value=MagicMock(returncode=None)),
        )
        self._patch_probes(mocker, running=True, ports=False)
        during_stop: list[ToolStatus] = []

        async def slow_stop(_proc: MagicMock) -> bool:
            during_stop.append(await tool.refresh_status())
            return True

        mocker.patch(
            "ocom.core.tools.spoofdpi.ProcessManager.stop_process", new=slow_stop
        )
        assert await tool.start(ToolConfig()) is False
        assert during_stop == [ToolStatus.ERROR]
        assert tool.status == ToolStatus.ERROR

    async def test_start_cancelled_while_waiting(
        self,
        tool: SpoofDPITool,
        mocker: MockerFixture,
        proc: MagicMock,
        stop: AsyncMock,
    ) -> None:
        """Cancelling mid-wait stops the process instead of stranding STARTING."""
        self._patch_probes(mocker, running=True, ports=False)
        mocker.patch("ocom.core.tools.spoofdpi.READY_TIMEOUT", 60.0)
        task = asyncio.create_task(tool.start(ToolConfig()))
        await asyncio.sleep(0.01)
        assert tool.status == ToolStatus.STARTING
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task
        assert tool.status == ToolStatus.STOPPED
        assert tool._process is None
        stop.assert_awaited_once_with(proc)

    async def test_start_process_raises(
        self, tool: SpoofDPITool, mocker: MockerFixture
    ) -> None:
        """A raising start_process should be caught and reported as ERROR."""
        mocker.patch(
            "ocom.core.tools.spoofdpi.ProcessManager.start_process",
            new=AsyncMock(side_effect=RuntimeError("boom")),
        )
        self._patch_probes(mocker, running=False, ports=False)
        result = await tool.start(ToolConfig())
        assert result is False
        assert tool.status == ToolStatus.ERROR
        assert tool.error_message == "boom"

    async def test_start_process_exits(
        self, tool: SpoofDPITool, mocker: MockerFixture, stop: AsyncMock
    ) -> None:
        """A process that exits early should be reported as ERROR."""
        mocker.patch(
            "ocom.core.tools.spoofdpi.ProcessManager.start_process",
            new=AsyncMock(return_value=MagicMock(returncode=3)),
        )
        self._patch_probes(mocker, running=False, ports=False)
        result = await tool.start(ToolConfig())
        assert result is False
        assert tool.status == ToolStatus.ERROR
        assert tool.error_message == "Process exited with code 3"
        stop.assert_awaited_once()
        assert tool._process is None


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

    @pytest.mark.parametrize("status", [ToolStatus.STARTING, ToolStatus.STOPPING])
    async def test_transitioning_left_alone(
        self, tool: SpoofDPITool, mocker: MockerFixture, status: ToolStatus
    ) -> None:
        """A refresh mid-transition must not override start()/stop()'s status."""
        tool._status = status
        tool._process = MagicMock(returncode=None)
        running = mocker.patch(
            "ocom.core.tools.spoofdpi.ProcessManager.is_process_running",
            return_value=True,
        )
        assert await tool.refresh_status() == status
        running.assert_not_called()

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
