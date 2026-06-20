"""Shared test fixtures for ocom tests."""

from collections.abc import Callable

import pytest

from ocom.core.tool import BaseTool, ToolConfig, ToolStatus


class MockTool(BaseTool):
    """A mock tool for testing BaseTool functionality."""

    name = "MockTool"
    description = "A mock tool for testing"
    command = "mock_command"
    requires_sudo = False
    supports_configs = True
    config_extensions = [".conf"]
    install_url = "https://example.com/install"
    conflicts_with = ["OtherTool"]

    def __init__(self, available: bool = True) -> None:
        super().__init__()
        self._available = available
        self._start_success = True
        self._stop_success = True

    async def check_available(self) -> bool:
        if self._available:
            self._status = ToolStatus.STOPPED
            return True
        self._status = ToolStatus.UNAVAILABLE
        return False

    async def start(self, config: ToolConfig) -> bool:
        if not self._start_success:
            self._status = ToolStatus.ERROR
            self._error_message = "Start failed"
            return False
        self._status = ToolStatus.RUNNING
        self._current_config = config.config_file
        self._emit_output("MockTool started")
        return True

    async def stop(self) -> bool:
        if not self._stop_success:
            self._status = ToolStatus.ERROR
            return False
        self._status = ToolStatus.STOPPED
        self._current_config = None
        self._emit_output("MockTool stopped")
        return True

    async def refresh_status(self) -> ToolStatus:
        return self._status


@pytest.fixture
def mock_tool() -> MockTool:
    """Create a mock tool instance."""
    return MockTool(available=True)


@pytest.fixture
def unavailable_tool() -> MockTool:
    """Create an unavailable mock tool instance."""
    return MockTool(available=False)


@pytest.fixture
def tool_config() -> ToolConfig:
    """Create a basic tool configuration."""
    return ToolConfig(
        enabled=True,
        config_file="/path/to/config.conf",
        config_dirs=["/etc/mock", "/home/user/.config/mock"],
        extra_args=["--verbose"],
        options={"timeout": 30, "retries": 3},
    )


@pytest.fixture
def output_collector() -> tuple[list[tuple[str, str]], Callable[[str, str], None]]:
    """Create a collector for tool output messages.

    Returns:
        A tuple of (collected_messages, callback_function).
    """
    messages: list[tuple[str, str]] = []

    def callback(tool_name: str, message: str) -> None:
        messages.append((tool_name, message))

    return messages, callback
