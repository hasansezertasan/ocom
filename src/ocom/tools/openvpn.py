"""OpenVPN tool implementation."""

import asyncio
from pathlib import Path
from typing import ClassVar, final, override

from ocom.core.process import IS_WINDOWS, ProcessManager
from ocom.core.tool import BaseTool, ToolConfig, ToolStatus

__all__ = ["OpenVPNTool"]


@final
class OpenVPNTool(BaseTool):
    """OpenVPN connection manager.

    Manages OpenVPN connections using .ovpn configuration files.
    Requires sudo on Unix, Administrator on Windows.
    """

    name = "OpenVPN"
    description = "Secure VPN tunneling"
    command = "openvpn"
    # Unix needs sudo, Windows needs Admin (handled separately)
    requires_sudo = not IS_WINDOWS
    supports_configs = True
    config_extensions: ClassVar[list[str]] = [".ovpn", ".conf"]
    install_url = "https://openvpn.net/community-resources/installing-openvpn/"
    conflicts_with: ClassVar[list[str]] = ["WARP"]  # Both control routing and DNS

    def __init__(self) -> None:
        """Initialize the OpenVPN tool with an empty output buffer."""
        super().__init__()
        self._output_lines: list[str] = []

    @override
    async def start(self, config: ToolConfig) -> bool:
        """Start OpenVPN with the specified config file.

        Args:
            config: Must have config_file set to an .ovpn path.

        Returns:
            True if connection initiated successfully.
        """
        config_path = self._validate_config(config)
        if config_path is None:
            return False

        self._status = ToolStatus.STARTING
        self._current_config = config_path.name
        self._output_lines.clear()

        args, password = self._build_command(config, config_path)

        try:
            self._process = await ProcessManager.start_process(
                args, on_output=self._handle_output, stdin_data=password
            )
        except Exception as e:  # noqa: BLE001  # external CLI can fail many ways
            self._status = ToolStatus.ERROR
            self._error_message = str(e)
            return False

        # Wait briefly for initial connection attempt
        await asyncio.sleep(2)
        return await self._evaluate_start()

    def _validate_config(self, config: ToolConfig) -> Path | None:
        """Validate the selected config file and resolve its path.

        Args:
            config: Tool configuration to validate.

        Returns:
            The resolved config path, or None if it is missing or invalid.
        """
        if not config.config_file:
            self._status = ToolStatus.ERROR
            self._error_message = "No config file selected"
            return None

        config_path = Path(config.config_file).expanduser()
        if not config_path.exists():
            self._status = ToolStatus.ERROR
            self._error_message = f"Config file not found: {config_path}"
            return None

        return config_path

    @staticmethod
    def _build_command(
        config: ToolConfig, config_path: Path
    ) -> tuple[list[str], str | None]:
        """Build the OpenVPN command and optional sudo password.

        Args:
            config: Tool configuration providing extra args and options.
            config_path: Resolved path to the .ovpn config file.

        Returns:
            A tuple of the command args and the sudo password (or None).
        """
        if IS_WINDOWS:
            # Windows: run directly (requires running as Administrator)
            args = ["openvpn", "--config", str(config_path)]
            password = None
        else:
            # Unix: use sudo -S (read password from stdin)
            args = ["sudo", "-S", "openvpn", "--config", str(config_path)]
            sudo_password = config.options.get("sudo_password")
            password = str(sudo_password) if sudo_password is not None else None

        args.extend(config.extra_args)
        return args, password

    async def _evaluate_start(self) -> bool:
        """Evaluate the process state after the initial connection attempt.

        Returns:
            True if the connection is up (or still initializing).
        """
        if not ProcessManager.is_process_running(self._process):
            self._status = ToolStatus.ERROR
            self._error_message = "Process exited unexpectedly"
            return False

        # Check output for success/failure indicators. A completed
        # initialization wins even if AUTH_FAILED also appears in the log.
        output = "\n".join(self._output_lines)
        if (
            "Initialization Sequence Completed" not in output
            and "AUTH_FAILED" in output
        ):
            self._status = ToolStatus.ERROR
            self._error_message = "Authentication failed"
            await self.stop()
            return False

        # Initialized, or still connecting: assume success for now.
        self._status = ToolStatus.RUNNING
        return True

    @override
    async def stop(self) -> bool:
        """Stop the OpenVPN connection.

        Returns:
            True if the connection was stopped.
        """
        if self._process is None:
            self._status = ToolStatus.STOPPED
            return True

        self._status = ToolStatus.STOPPING

        success = await ProcessManager.stop_process(self._process)
        self._process = None
        self._current_config = None
        self._status = ToolStatus.STOPPED
        return success

    @override
    async def refresh_status(self) -> ToolStatus:
        """Refresh OpenVPN status.

        Returns:
            The current ToolStatus.
        """
        if self._status == ToolStatus.UNAVAILABLE:
            await self.check_available()
            return self._status

        if self._process is not None:
            if ProcessManager.is_process_running(self._process):
                self._status = ToolStatus.RUNNING
            else:
                # Process died
                self._status = ToolStatus.STOPPED
                self._process = None
                self._current_config = None

        return self._status

    @override
    def get_config_files(self, config: ToolConfig) -> list[str]:
        """Find all .ovpn files in configured directories.

        Args:
            config: Tool configuration listing directories to scan.

        Returns:
            A sorted list of matching config file paths.
        """
        files: list[str] = []

        for dir_path in config.config_dirs:
            expanded = Path(dir_path).expanduser()
            if not expanded.exists():
                continue

            for ext in self.config_extensions:
                files.extend(str(p) for p in expanded.glob(f"*{ext}"))

        return sorted(files)

    def _handle_output(self, line: str) -> None:
        """Handle output from OpenVPN process."""
        self._output_lines.append(line)
        self._output_lines = self._output_lines[-100:]  # Keep only last 100 lines
        self._emit_output(line)
