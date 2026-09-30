"""GoodbyeDPI tool implementation (Windows only)."""

from typing import ClassVar, final, override

from ocom.core.process import ProcessManager, is_admin
from ocom.core.tool import BaseTool, StartError, ToolConfig, ToolStatus

__all__ = ["GoodbyeDPITool"]

# How long the process must stay up before start() reports RUNNING.
READY_WINDOW = 1.0


@final
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
    conflicts_with: ClassVar[list[str]] = ["SpoofDPI"]  # Same function, other platform

    def __init__(self) -> None:
        """Initialize the GoodbyeDPI tool with its default mode."""
        super().__init__()
        self._mode: int = 9  # Default mode

    @override
    async def start(self, config: ToolConfig) -> bool:
        """Start GoodbyeDPI.

        The tool stays STARTING until the process has stayed up for
        ``READY_WINDOW`` seconds: GoodbyeDPI has no port or output marker to
        probe, and a failed launch (no Administrator rights, WinDivert driver
        errors) exits almost immediately.

        Args:
            config: Can contain options for mode (1-9), block_quic (bool).

        Returns:
            True if started successfully.
        """
        # Check for Administrator privileges upfront
        if not is_admin():
            self._fail("Administrator privileges required")
            self._emit_output(
                "Run ocom as Administrator (right-click → Run as administrator)"
            )
            return False

        if not await self._run_start(lambda: self._launch(config)):
            return False
        self._emit_output(f"DPI bypass started (mode {self._mode})")
        return True

    async def _launch(self, config: ToolConfig) -> None:
        """Spawn GoodbyeDPI and wait for it to stay up.

        Raises:
            StartError: If the process exits during the readiness window.
        """
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

        self._process = await ProcessManager.start_process(
            args, on_output=self._handle_output
        )
        try:
            await self._wait_until_ready(None, within=READY_WINDOW)
        except StartError as e:
            msg = f"{e} (run as Administrator?)"
            raise StartError(msg) from e

    @override
    async def stop(self) -> bool:
        """Stop GoodbyeDPI.

        Returns:
            True if the process was stopped.
        """
        return await self._stop_tracked_process("DPI bypass stopped")

    @override
    async def refresh_status(self) -> ToolStatus:
        """Refresh GoodbyeDPI status.

        Returns:
            The current ToolStatus.
        """
        if self._status == ToolStatus.UNAVAILABLE:
            await self.check_available()
            return self._status

        # start()/stop() own the status while a transition is in flight, so a
        # periodic refresh must not report RUNNING before the process is ready.
        if self._status.is_transitioning:
            return self._status

        if self._process is not None:
            if ProcessManager.is_process_running(self._process):
                self._status = ToolStatus.RUNNING
            else:
                self._status = ToolStatus.STOPPED
                self._process = None

        return self._status

    @override
    def get_status_text(self) -> str:
        """Get GoodbyeDPI-specific status text.

        Returns:
            A short human-readable status string.
        """
        if self._status == ToolStatus.RUNNING:
            return f"Mode {self._mode}"
        return super().get_status_text()

    def _handle_output(self, line: str) -> None:
        """Handle output from GoodbyeDPI process."""
        self._emit_output(line)
