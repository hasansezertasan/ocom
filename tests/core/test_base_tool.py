"""Tests for BaseTool abstract base class."""

import asyncio
from typing import TYPE_CHECKING
from unittest.mock import AsyncMock, MagicMock

import pytest

from ocom.core.tool import StartError, ToolConfig, ToolStatus
from tests.conftest import MockTool

if TYPE_CHECKING:
    from collections.abc import Callable

    from pytest_mock import MockerFixture


async def _never_resolves() -> None:
    """Block forever: the test cancels while this is pending."""
    never: asyncio.Future[None] = asyncio.get_running_loop().create_future()
    await never


class TestBaseToolClassAttributes:
    """Test BaseTool class attribute inheritance."""

    def test_mock_tool_has_required_attributes(self, mock_tool: MockTool) -> None:
        """MockTool should have all required class attributes."""
        assert mock_tool.name == "MockTool"
        assert mock_tool.description == "A mock tool for testing"
        assert mock_tool.command == "mock_command"
        assert mock_tool.requires_sudo is False
        assert mock_tool.supports_configs is True
        assert mock_tool.config_extensions == [".conf"]
        assert mock_tool.install_url == "https://example.com/install"
        assert mock_tool.conflicts_with == ["OtherTool"]


class TestBaseToolInitialization:
    """Test BaseTool initialization."""

    def test_initial_status_is_unavailable(self, mock_tool: MockTool) -> None:
        """New tools should start with UNAVAILABLE status."""
        fresh_tool = MockTool(available=True)
        assert fresh_tool.status == ToolStatus.UNAVAILABLE

    def test_initial_error_message_is_none(self, mock_tool: MockTool) -> None:
        """New tools should have no error message."""
        assert mock_tool.error_message is None

    def test_initial_current_config_is_none(self, mock_tool: MockTool) -> None:
        """New tools should have no current config."""
        assert mock_tool.current_config is None


class TestCheckAvailable:
    """Test check_available behavior."""

    async def test_available_tool_sets_stopped_status(
        self, mock_tool: MockTool
    ) -> None:
        """Available tool should transition to STOPPED."""
        result = await mock_tool.check_available()
        assert result is True
        assert mock_tool.status == ToolStatus.STOPPED

    async def test_unavailable_tool_stays_unavailable(
        self, unavailable_tool: MockTool
    ) -> None:
        """Unavailable tool should stay UNAVAILABLE."""
        result = await unavailable_tool.check_available()
        assert result is False
        assert unavailable_tool.status == ToolStatus.UNAVAILABLE


class TestStartStop:
    """Test start and stop operations."""

    async def test_start_sets_running_status(
        self, mock_tool: MockTool, tool_config: ToolConfig
    ) -> None:
        """Starting a tool should set RUNNING status."""
        await mock_tool.check_available()
        result = await mock_tool.start(tool_config)
        assert result is True
        assert mock_tool.status == ToolStatus.RUNNING

    async def test_start_sets_current_config(
        self, mock_tool: MockTool, tool_config: ToolConfig
    ) -> None:
        """Starting should store the config file path."""
        await mock_tool.check_available()
        await mock_tool.start(tool_config)
        assert mock_tool.current_config == tool_config.config_file

    async def test_stop_sets_stopped_status(
        self, mock_tool: MockTool, tool_config: ToolConfig
    ) -> None:
        """Stopping a tool should set STOPPED status."""
        await mock_tool.check_available()
        await mock_tool.start(tool_config)
        result = await mock_tool.stop()
        assert result is True
        assert mock_tool.status == ToolStatus.STOPPED

    async def test_stop_clears_current_config(
        self, mock_tool: MockTool, tool_config: ToolConfig
    ) -> None:
        """Stopping should clear the current config."""
        await mock_tool.check_available()
        await mock_tool.start(tool_config)
        await mock_tool.stop()
        assert mock_tool.current_config is None

    async def test_start_failure_sets_error_status(
        self, mock_tool: MockTool, tool_config: ToolConfig
    ) -> None:
        """Failed start should set ERROR status."""
        mock_tool._start_success = False
        result = await mock_tool.start(tool_config)
        assert result is False
        assert mock_tool.status == ToolStatus.ERROR
        assert mock_tool.error_message == "Start failed"


class TestOutputCallback:
    """Test output callback functionality."""

    async def test_set_output_callback(
        self,
        mock_tool: MockTool,
        output_collector: tuple[list[tuple[str, str]], Callable[[str, str], None]],
    ) -> None:
        """Output callback should be settable."""
        _messages, callback = output_collector
        mock_tool.set_output_callback(callback)
        # Callback is now registered
        assert mock_tool._output_callback is callback

    async def test_emit_output_calls_callback(
        self,
        mock_tool: MockTool,
        tool_config: ToolConfig,
        output_collector: tuple[list[tuple[str, str]], Callable[[str, str], None]],
    ) -> None:
        """Starting tool should emit output via callback."""
        messages, callback = output_collector
        mock_tool.set_output_callback(callback)

        await mock_tool.check_available()
        await mock_tool.start(tool_config)

        assert len(messages) >= 1
        assert messages[0] == ("MockTool", "MockTool started")

    async def test_emit_output_without_callback(
        self, mock_tool: MockTool, tool_config: ToolConfig
    ) -> None:
        """Emitting output without callback should not raise."""
        # No callback set - should not raise
        await mock_tool.check_available()
        await mock_tool.start(tool_config)

    def test_set_callback_to_none(
        self,
        mock_tool: MockTool,
        output_collector: tuple[list[tuple[str, str]], Callable[[str, str], None]],
    ) -> None:
        """Setting callback to None should clear it."""
        _, callback = output_collector
        mock_tool.set_output_callback(callback)
        mock_tool.set_output_callback(None)
        assert mock_tool._output_callback is None


class TestGetStatusText:
    """Test get_status_text method."""

    def test_status_text_for_unavailable(self, mock_tool: MockTool) -> None:
        """UNAVAILABLE should show 'Unavailable'."""
        assert mock_tool.get_status_text() == "Unavailable"

    async def test_status_text_for_stopped(self, mock_tool: MockTool) -> None:
        """STOPPED should show 'Stopped'."""
        await mock_tool.check_available()
        assert mock_tool.get_status_text() == "Stopped"

    async def test_status_text_for_running_with_config(
        self, mock_tool: MockTool, tool_config: ToolConfig
    ) -> None:
        """RUNNING with config should show config path."""
        await mock_tool.check_available()
        await mock_tool.start(tool_config)
        assert mock_tool.get_status_text() == tool_config.config_file

    async def test_status_text_for_error_with_message(
        self, mock_tool: MockTool, tool_config: ToolConfig
    ) -> None:
        """ERROR with message should show error details."""
        mock_tool._start_success = False
        await mock_tool.start(tool_config)
        assert "Error:" in mock_tool.get_status_text()
        assert "Start failed" in mock_tool.get_status_text()


class TestGetConfigFiles:
    """Test get_config_files method."""

    def test_default_returns_empty_list(
        self, mock_tool: MockTool, tool_config: ToolConfig
    ) -> None:
        """Default implementation returns empty list."""
        result = mock_tool.get_config_files(tool_config)
        assert result == []


class TestRefreshStatus:
    """Test refresh_status method."""

    async def test_refresh_returns_current_status(self, mock_tool: MockTool) -> None:
        """refresh_status should return the current status."""
        await mock_tool.check_available()
        status = await mock_tool.refresh_status()
        assert status == ToolStatus.STOPPED


@pytest.fixture
def stop(mocker: MockerFixture) -> AsyncMock:
    """Patch stop_process."""
    return mocker.patch(
        "ocom.core.tool.ProcessManager.stop_process", new=AsyncMock(return_value=True)
    )


@pytest.fixture
def fast_poll(mocker: MockerFixture) -> None:
    """Shrink the readiness poll so waits finish quickly."""
    mocker.patch("ocom.core.tool.READY_POLL_INTERVAL", 0.001)


class TestRunStart:
    """Test BaseTool._run_start(): every exit path settles."""

    async def test_success_reaches_running(self, mock_tool: MockTool) -> None:
        """The tool is STARTING during launch and RUNNING once it returns."""
        seen: list[ToolStatus] = []

        async def launch() -> None:
            seen.append(mock_tool.status)

        assert await mock_tool._run_start(launch) is True
        assert seen == [ToolStatus.STARTING]
        assert mock_tool.status == ToolStatus.RUNNING

    async def test_start_error_records_and_stops(
        self, mock_tool: MockTool, stop: AsyncMock
    ) -> None:
        """A StartError records ERROR, logs it, and stops the spawned process."""
        proc = MagicMock(returncode=None)
        messages: list[str] = []
        mock_tool.set_output_callback(lambda _name, msg: messages.append(msg))

        async def launch() -> None:
            mock_tool._process = proc
            msg = "no tunnel"
            raise StartError(msg)

        assert await mock_tool._run_start(launch) is False
        assert mock_tool.status == ToolStatus.ERROR
        assert mock_tool.error_message == "no tunnel"
        assert messages == ["Error: no tunnel"]
        assert mock_tool._process is None
        stop.assert_awaited_once_with(proc)

    @pytest.mark.usefixtures("stop")
    async def test_unexpected_error_records(self, mock_tool: MockTool) -> None:
        """Any other exception is reported as ERROR rather than escaping."""

        async def launch() -> None:
            msg = "bad option"
            raise ValueError(msg)

        assert await mock_tool._run_start(launch) is False
        assert mock_tool.status == ToolStatus.ERROR
        assert mock_tool.error_message == "bad option"

    async def test_cancelled_settles_stopped(
        self, mock_tool: MockTool, stop: AsyncMock
    ) -> None:
        """Cancelling mid-launch stops the process instead of stranding STARTING."""
        proc = MagicMock(returncode=None)

        async def launch() -> None:
            mock_tool._process = proc
            await _never_resolves()

        task = asyncio.create_task(mock_tool._run_start(launch))
        await asyncio.sleep(0)
        assert mock_tool.status == ToolStatus.STARTING
        task.cancel()
        await asyncio.wait([task])
        assert task.cancelled()
        assert mock_tool.status == ToolStatus.STOPPED
        assert mock_tool._process is None
        stop.assert_awaited_once_with(proc)

    async def test_abandon_detaches_before_stopping(
        self, mock_tool: MockTool, mocker: MockerFixture
    ) -> None:
        """The outcome is settled before the failed process finishes stopping."""
        during_stop: list[tuple[ToolStatus, object]] = []

        async def slow_stop(_proc: MagicMock) -> bool:
            during_stop.append((mock_tool.status, mock_tool._process))
            return True

        mocker.patch("ocom.core.tool.ProcessManager.stop_process", new=slow_stop)

        async def launch() -> None:
            mock_tool._process = MagicMock(returncode=None)
            msg = "boom"
            raise StartError(msg)

        assert await mock_tool._run_start(launch) is False
        assert during_stop == [(ToolStatus.ERROR, None)]


@pytest.mark.usefixtures("fast_poll")
class TestWaitUntilReady:
    """Test BaseTool._wait_until_ready()."""

    async def test_ready(self, mock_tool: MockTool) -> None:
        """A passing probe returns True."""
        mock_tool._process = MagicMock(returncode=None)
        probes = iter([False, False, True])

        async def is_ready() -> bool:
            return next(probes)

        assert await mock_tool._wait_until_ready(is_ready, within=1.0) is True

    async def test_process_exits(self, mock_tool: MockTool) -> None:
        """An exited process raises StartError with its exit code."""
        mock_tool._process = MagicMock(returncode=3)
        with pytest.raises(StartError, match="Process exited with code 3"):
            await mock_tool._wait_until_ready(None, within=1.0)

    async def test_no_process(self, mock_tool: MockTool) -> None:
        """No tracked process counts as exited."""
        with pytest.raises(StartError, match="Process exited with code None"):
            await mock_tool._wait_until_ready(None, within=1.0)

    async def test_times_out_alive(self, mock_tool: MockTool) -> None:
        """A process alive but never ready returns False at the deadline."""
        mock_tool._process = MagicMock(returncode=None)

        async def is_ready() -> bool:
            return False

        assert await mock_tool._wait_until_ready(is_ready, within=0.02) is False

    async def test_liveness_only(self, mock_tool: MockTool) -> None:
        """Without a probe, surviving the window returns False (still alive)."""
        mock_tool._process = MagicMock(returncode=None)
        assert await mock_tool._wait_until_ready(None, within=0.02) is False


class TestStopTrackedProcess:
    """Test BaseTool._stop_tracked_process()."""

    async def test_no_process(self, mock_tool: MockTool, stop: AsyncMock) -> None:
        """Without a process it settles on STOPPED and logs nothing."""
        messages: list[str] = []
        mock_tool.set_output_callback(lambda _name, msg: messages.append(msg))
        assert await mock_tool._stop_tracked_process("stopped") is True
        assert mock_tool.status == ToolStatus.STOPPED
        assert messages == []
        stop.assert_not_awaited()

    async def test_with_process(self, mock_tool: MockTool, stop: AsyncMock) -> None:
        """A tracked process is stopped, dropped, and the message logged."""
        proc = MagicMock(returncode=None)
        mock_tool._process = proc
        messages: list[str] = []
        mock_tool.set_output_callback(lambda _name, msg: messages.append(msg))
        assert await mock_tool._stop_tracked_process("stopped") is True
        assert mock_tool.status == ToolStatus.STOPPED
        assert mock_tool._process is None
        assert messages == ["stopped"]
        stop.assert_awaited_once_with(proc)

    async def test_cancelled(self, mock_tool: MockTool, mocker: MockerFixture) -> None:
        """Cancelling mid-stop still settles on STOPPED and drops the process."""
        mock_tool._status = ToolStatus.RUNNING
        mock_tool._process = MagicMock(returncode=None)

        async def blocked_stop(_proc: MagicMock) -> bool:
            await _never_resolves()
            return True

        mocker.patch("ocom.core.tool.ProcessManager.stop_process", new=blocked_stop)
        task = asyncio.create_task(mock_tool._stop_tracked_process())
        await asyncio.sleep(0)
        assert mock_tool.status == ToolStatus.STOPPING
        task.cancel()
        await asyncio.wait([task])
        assert task.cancelled()
        assert mock_tool.status == ToolStatus.STOPPED
        assert mock_tool._process is None
