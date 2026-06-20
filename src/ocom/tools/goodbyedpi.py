"""GoodbyeDPI tool implementation (Windows only)."""

import asyncio

from ocom.core.process import ProcessManager, is_admin
from ocom.core.tool import BaseTool, ToolConfig, ToolStatus


class GoodbyeDPITool(BaseTool):
    """GoodbyeDPI anti-censorship tool for Windows.

    GoodbyeDPI is a DPI bypass utility that works at the packet level.
    It modifies packets to evade Deep Packet Inspection.
    Requires Administrator privileges on Windows.
    """

    name = "GoodbyeDPI"
    description = "DPI bypass (Windows)"
    command = "goodbyedpi"
    requires_sudo = False  # Windows uses Administrator, not sudo
    supports_configs = False
    install_url = "https://github.com/ValdikSS/GoodbyeDPI/releases"
    conflicts_with = ["SpoofDPI"]  # Same function, different platform

    def __init__(self) -> None:
        super().__init__()
        self._mode: int = 9  # Default mode

    async def start(self, config: ToolConfig) -> bool:
        """Start GoodbyeDPI.

        Args:
            config: Can contain options for mode (1-9), block_quic (bool).

        Returns:
            True if started successfully.
        """
        # Check for Administrator privileges upfront
        if not is_admin():
            self._status = ToolStatus.ERROR
            self._error_message = "Administrator privileges required"
            self._emit_output("Error: GoodbyeDPI requires Administrator privileges")
            self._emit_output(
                "Run ocom as Administrator (right-click → Run as administrator)"
            )
            return False

        self._status = ToolStatus.STARTING

        # Build command with options
        args = ["goodbyedpi"]

        # Get mode from config (1-9, default 9)
        mode = config.options.get("mode", 9)
        self._mode = int(mode)
        args.append(f"-{self._mode}")

        # Optionally block QUIC/HTTP3 (default: True)
        if config.options.get("block_quic", True):
            args.append("-q")

        args.extend(config.extra_args)

        try:
            self._process = await ProcessManager.start_process(
                args,
                on_output=self._handle_output,
            )

            # Check if it started successfully
            await asyncio.sleep(1)

            if not ProcessManager.is_process_running(self._process):
                self._status = ToolStatus.ERROR
                self._error_message = (
                    "Process exited unexpectedly (run as Administrator?)"
                )
                self._emit_output(f"Error: {self._error_message}")
                return False

            self._status = ToolStatus.RUNNING
            self._emit_output(f"DPI bypass started (mode {self._mode})")
            return True

        except Exception as e:
            self._status = ToolStatus.ERROR
            self._error_message = str(e)
            self._emit_output(f"Error: {e}")
            return False

    async def stop(self) -> bool:
        """Stop GoodbyeDPI."""
        if self._process is None:
            self._status = ToolStatus.STOPPED
            return True

        self._status = ToolStatus.STOPPING

        success = await ProcessManager.stop_process(self._process)
        self._process = None
        self._status = ToolStatus.STOPPED
        self._emit_output("DPI bypass stopped")
        return success

    async def refresh_status(self) -> ToolStatus:
        """Refresh GoodbyeDPI status."""
        if self._status == ToolStatus.UNAVAILABLE:
            await self.check_available()
            return self._status

        if self._process is not None:
            if ProcessManager.is_process_running(self._process):
                self._status = ToolStatus.RUNNING
            else:
                self._status = ToolStatus.STOPPED
                self._process = None

        return self._status

    def get_status_text(self) -> str:
        """Get GoodbyeDPI-specific status text."""
        if self._status == ToolStatus.RUNNING:
            return f"Mode {self._mode}"
        return super().get_status_text()

    def _handle_output(self, line: str) -> None:
        """Handle output from GoodbyeDPI process."""
        self._emit_output(line)
