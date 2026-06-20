"""Base tool abstraction for network/privacy tools."""

import asyncio
from abc import ABC, abstractmethod
from collections.abc import Callable
from dataclasses import dataclass, field
from enum import Enum

from ocom.core.process import ProcessManager


class ToolStatus(Enum):
    """Status of a network tool."""

    UNAVAILABLE = "unavailable"  # Tool not installed on system
    STOPPED = "stopped"  # Installed but not running
    STARTING = "starting"  # In process of starting
    RUNNING = "running"  # Currently active
    STOPPING = "stopping"  # In process of stopping
    ERROR = "error"  # Failed state

    @property
    def is_transitioning(self) -> bool:
        """Check if status is a transitional state."""
        return self in (ToolStatus.STARTING, ToolStatus.STOPPING)

    @property
    def can_start(self) -> bool:
        """Check if tool can be started from this state."""
        return self in (ToolStatus.STOPPED, ToolStatus.ERROR)

    @property
    def can_stop(self) -> bool:
        """Check if tool can be stopped from this state."""
        return self == ToolStatus.RUNNING


@dataclass
class ToolConfig:
    """Configuration for a specific tool instance."""

    enabled: bool = True
    config_file: str | None = None  # Selected config file (e.g., .ovpn)
    config_dirs: list[str] = field(default_factory=list)  # Directories to scan
    extra_args: list[str] = field(default_factory=list)  # Additional CLI arguments
    options: dict[str, str | bool | int] = field(default_factory=dict)  # Tool-specific options


class BaseTool(ABC):
    """Abstract base class for all network/privacy tools.

    Subclasses must implement all abstract methods to integrate
    a new tool into the ocom TUI.
    """

    # Class attributes to be overridden by subclasses
    name: str = "Unknown Tool"
    description: str = ""
    command: str = ""  # Primary CLI command to check availability
    requires_sudo: bool = False
    supports_configs: bool = False  # Whether tool uses config files (like .ovpn)
    config_extensions: list[str] = []  # File extensions to scan (e.g., [".ovpn"])
    install_url: str = ""  # URL to installation documentation
    conflicts_with: list[str] = []  # Tool names that conflict (will be auto-stopped)

    def __init__(self) -> None:
        self._status = ToolStatus.UNAVAILABLE
        self._process: asyncio.subprocess.Process | None = None
        self._error_message: str | None = None
        self._current_config: str | None = None
        self._output_callback: Callable[[str, str], None] | None = None

    def set_output_callback(self, callback: Callable[[str, str], None] | None) -> None:
        """Set callback for tool output.

        Args:
            callback: Function called with (tool_name, message) for each output line.
        """
        self._output_callback = callback

    def _emit_output(self, message: str) -> None:
        """Emit output to the registered callback.

        Args:
            message: The output message.
        """
        if self._output_callback:
            self._output_callback(self.name, message)

    @property
    def status(self) -> ToolStatus:
        """Current tool status."""
        return self._status

    @property
    def error_message(self) -> str | None:
        """Error message if status is ERROR."""
        return self._error_message

    @property
    def current_config(self) -> str | None:
        """Currently active config file, if any."""
        return self._current_config

    async def check_available(self) -> bool:
        """Check if the tool is installed on the system.

        Default implementation checks if self.command exists in PATH.

        Returns:
            True if the tool is available, False otherwise.
        """
        if ProcessManager.find_command(self.command):
            self._status = ToolStatus.STOPPED
            return True
        self._status = ToolStatus.UNAVAILABLE
        return False

    @abstractmethod
    async def start(self, config: ToolConfig) -> bool:
        """Start the tool with the given configuration.

        Args:
            config: Tool configuration including selected config file and options.

        Returns:
            True if started successfully, False otherwise.
        """

    @abstractmethod
    async def stop(self) -> bool:
        """Stop the tool.

        Returns:
            True if stopped successfully, False otherwise.
        """

    @abstractmethod
    async def refresh_status(self) -> ToolStatus:
        """Refresh and return the current status.

        This is called periodically to update the UI.

        Returns:
            Current ToolStatus.
        """

    def get_config_files(self, config: ToolConfig) -> list[str]:
        """Get list of available config files.

        Override this for tools that use config files.

        Args:
            config: Tool configuration with directories to scan.

        Returns:
            List of config file paths.
        """
        return []

    def get_status_text(self) -> str:
        """Get human-readable status text for display.

        Can be overridden for tool-specific status details.
        """
        if self._status == ToolStatus.ERROR and self._error_message:
            return f"Error: {self._error_message}"
        if self._status == ToolStatus.RUNNING and self._current_config:
            return self._current_config
        return self._status.value.capitalize()
