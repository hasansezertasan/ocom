"""Tests for BaseTool abstract base class."""

from collections.abc import Callable

from ocom.core.tool import ToolConfig, ToolStatus

from .conftest import MockTool


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

    async def test_available_tool_sets_stopped_status(self, mock_tool: MockTool) -> None:
        """Available tool should transition to STOPPED."""
        result = await mock_tool.check_available()
        assert result is True
        assert mock_tool.status == ToolStatus.STOPPED

    async def test_unavailable_tool_stays_unavailable(self, unavailable_tool: MockTool) -> None:
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
        messages, callback = output_collector
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

    def test_default_returns_empty_list(self, mock_tool: MockTool, tool_config: ToolConfig) -> None:
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
