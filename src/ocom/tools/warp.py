"""Cloudflare WARP tool implementation."""

from typing import ClassVar

from ocom.core.process import ProcessManager, ProcessResult
from ocom.core.tool import BaseTool, ToolConfig, ToolStatus

__all__ = ["WarpTool"]


class WarpTool(BaseTool):
    """Cloudflare WARP connection manager.

    Uses warp-cli to connect/disconnect from Cloudflare's WARP service.
    WARP runs as a system daemon, so we just send commands to it.
    """

    name = "WARP"
    description = "Cloudflare WARP VPN"
    command = "warp-cli"
    requires_sudo = False
    supports_configs = False
    install_url = "https://developers.cloudflare.com/warp-client/get-started/linux/"
    conflicts_with: ClassVar[list[str]] = ["OpenVPN"]  # Both control routing and DNS

    async def check_available(self) -> bool:
        """Check if warp-cli is installed and daemon is running.

        Returns:
            True if the CLI is available.
        """
        if not await super().check_available():
            return False
        # Also check daemon status
        await self.refresh_status()
        if self._status == ToolStatus.UNAVAILABLE:
            self._status = ToolStatus.STOPPED
        return True

    async def start(self, config: ToolConfig) -> bool:
        """Connect to WARP.

        Args:
            config: Can contain mode option (warp, doh, proxy).

        Returns:
            True if connection initiated.
        """
        self._status = ToolStatus.STARTING

        # Set mode if specified (non-fatal if it fails)
        mode = str(config.options.get("mode", "warp"))
        if mode:
            await ProcessManager.run_command(["warp-cli", "mode", mode], timeout=10.0)

        # Connect
        result = await ProcessManager.run_command(["warp-cli", "connect"], timeout=30.0)

        if result.success:
            self._status = ToolStatus.RUNNING
            self._emit_output("Connected to Cloudflare WARP")
            return True
        self._status = ToolStatus.ERROR
        self._error_message = result.stderr or result.stdout or "Failed to connect"
        self._emit_output(f"Error: {self._error_message}")
        return False

    async def stop(self) -> bool:
        """Disconnect from WARP.

        Returns:
            True if disconnected successfully.
        """
        self._status = ToolStatus.STOPPING

        result = await ProcessManager.run_command(
            ["warp-cli", "disconnect"], timeout=10.0
        )

        if result.success:
            self._status = ToolStatus.STOPPED
            self._emit_output("Disconnected from WARP")
            return True
        self._status = ToolStatus.ERROR
        self._error_message = result.stderr or result.stdout or "Failed to disconnect"
        self._emit_output(f"Error: {self._error_message}")
        return False

    async def refresh_status(self) -> ToolStatus:
        """Check WARP connection status.

        Returns:
            The current ToolStatus.
        """
        if self._status == ToolStatus.UNAVAILABLE and not ProcessManager.find_command(
            self.command
        ):
            return self._status

        try:
            result = await ProcessManager.run_command(
                ["warp-cli", "status"], timeout=5.0
            )
        except Exception as e:  # noqa: BLE001  # warp-cli can fail in many ways
            self._status = ToolStatus.ERROR
            self._error_message = str(e)
            return self._status

        self._status = self._parse_status(result)
        return self._status

    def _parse_status(self, result: ProcessResult) -> ToolStatus:
        """Map a `warp-cli status` result to a ToolStatus.

        Args:
            result: The completed `warp-cli status` process result.

        Returns:
            The mapped ToolStatus.
        """
        if not result.success:
            return self._status_from_failure(result)
        return self._status_from_output(result.stdout.lower())

    def _status_from_failure(self, result: ProcessResult) -> ToolStatus:
        """Map a failed `warp-cli status` result to a ToolStatus.

        Args:
            result: The failed process result.

        Returns:
            ERROR if the daemon is unreachable, otherwise STOPPED.
        """
        # Daemon might not be running
        if "unable to connect" in result.stderr.lower():
            self._error_message = "WARP daemon not running"
            return ToolStatus.ERROR
        return ToolStatus.STOPPED

    @staticmethod
    def _status_from_output(output: str) -> ToolStatus:
        """Map lowercased `warp-cli status` stdout to a ToolStatus.

        Args:
            output: Lowercased status output.

        Returns:
            The mapped ToolStatus.
        """
        # Check disconnected FIRST since "connected" is a substring
        # of "disconnected".
        if "disconnected" in output:
            return ToolStatus.STOPPED
        if "connecting" in output:
            return ToolStatus.STARTING
        if "connected" in output:
            return ToolStatus.RUNNING
        return ToolStatus.STOPPED
