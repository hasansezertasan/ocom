"""OpenVPN tool implementation."""

import asyncio
from pathlib import Path

from ocom.core.process import IS_WINDOWS, ProcessManager
from ocom.core.tool import BaseTool, ToolConfig, ToolStatus


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
    config_extensions = [".ovpn", ".conf"]
    install_url = "https://openvpn.net/community-resources/installing-openvpn/"
    conflicts_with = ["WARP"]  # Both control routing table and DNS

    def __init__(self) -> None:
        super().__init__()
        self._output_lines: list[str] = []

    async def start(self, config: ToolConfig) -> bool:
        """Start OpenVPN with the specified config file.

        Args:
            config: Must have config_file set to an .ovpn path.

        Returns:
            True if connection initiated successfully.
        """
        if not config.config_file:
            self._status = ToolStatus.ERROR
            self._error_message = "No config file selected"
            return False

        config_path = Path(config.config_file).expanduser()
        if not config_path.exists():
            self._status = ToolStatus.ERROR
            self._error_message = f"Config file not found: {config_path}"
            return False

        self._status = ToolStatus.STARTING
        self._current_config = config_path.name
        self._output_lines.clear()

        # Build command - platform specific
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

        try:
            self._process = await ProcessManager.start_process(
                args,
                on_output=self._handle_output,
                stdin_data=password,
            )

            # Wait briefly for initial connection attempt
            await asyncio.sleep(2)

            # Check if still running
            if ProcessManager.is_process_running(self._process):
                # Check output for success/failure indicators
                output = "\n".join(self._output_lines)
                if "Initialization Sequence Completed" in output:
                    self._status = ToolStatus.RUNNING
                    return True
                elif "AUTH_FAILED" in output:
                    self._status = ToolStatus.ERROR
                    self._error_message = "Authentication failed"
                    await self.stop()
                    return False
                else:
                    # Still connecting, assume success for now
                    self._status = ToolStatus.RUNNING
                    return True
            else:
                self._status = ToolStatus.ERROR
                self._error_message = "Process exited unexpectedly"
                return False

        except Exception as e:
            self._status = ToolStatus.ERROR
            self._error_message = str(e)
            return False

    async def stop(self) -> bool:
        """Stop the OpenVPN connection."""
        if self._process is None:
            self._status = ToolStatus.STOPPED
            return True

        self._status = ToolStatus.STOPPING

        success = await ProcessManager.stop_process(self._process)
        self._process = None
        self._current_config = None
        self._status = ToolStatus.STOPPED
        return success

    async def refresh_status(self) -> ToolStatus:
        """Refresh OpenVPN status."""
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

    def get_config_files(self, config: ToolConfig) -> list[str]:
        """Find all .ovpn files in configured directories."""
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
