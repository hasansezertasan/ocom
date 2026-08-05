"""Tailscale tool implementation."""

import json
from typing import ClassVar, cast, final, override

from ocom.core.process import ProcessManager, ProcessResult
from ocom.core.tool import BaseTool, ToolConfig, ToolStatus

__all__ = ["TailscaleTool"]


@final
class TailscaleTool(BaseTool):
    """Tailscale mesh VPN connection manager.

    Uses the `tailscale` CLI to bring the node up/down and read status.
    Tailscale runs as a system daemon (tailscaled), so we just send it
    commands - much like the WARP tool.

    Mesh-only: this manages the plain `tailscale up`/`down` lifecycle and
    does not configure an exit node. In mesh mode Tailscale only routes the
    100.64.0.0/10 CGNAT range and does not seize the default route, so it
    coexists with OpenVPN/WARP - hence ``conflicts_with`` is empty. If exit
    node support is added later (full-tunnel), revisit the conflict list.
    """

    name = "Tailscale"
    description = "Tailscale mesh VPN"
    command = "tailscale"
    requires_sudo = False
    supports_configs = False
    install_url = "https://tailscale.com/download"
    # Mesh mode coexists with full-tunnel VPNs (see docstring)
    conflicts_with: ClassVar[list[str]] = []

    @override
    async def check_available(self) -> bool:
        """Check if the tailscale CLI is installed and read daemon status.

        Returns:
            True if the CLI is available.
        """
        if not await super().check_available():
            return False
        # Also reconcile with the daemon's actual state
        await self.refresh_status()
        return True

    @override
    async def start(self, config: ToolConfig) -> bool:
        """Bring the Tailscale node up.

        Args:
            config: Unused for mesh mode; reserved for future options
                (e.g. exit node, accept-routes).

        Returns:
            True if the node came up successfully.
        """
        self._status = ToolStatus.STARTING

        result = await ProcessManager.run_command(["tailscale", "up"], timeout=30.0)

        if result.success:
            self._status = ToolStatus.RUNNING
            self._emit_output("Tailscale is up")
            return True

        self._status = ToolStatus.ERROR
        self._error_message = (
            result.stderr or result.stdout or "Failed to bring Tailscale up"
        )
        # First-run authentication surfaces here as a login URL in stderr.
        self._emit_output(f"Error: {self._error_message}")
        return False

    @override
    async def stop(self) -> bool:
        """Bring the Tailscale node down.

        Returns:
            True if the node was brought down successfully.
        """
        self._status = ToolStatus.STOPPING

        result = await ProcessManager.run_command(["tailscale", "down"], timeout=10.0)

        if result.success:
            self._status = ToolStatus.STOPPED
            self._emit_output("Tailscale is down")
            return True

        self._status = ToolStatus.ERROR
        self._error_message = (
            result.stderr or result.stdout or "Failed to bring Tailscale down"
        )
        self._emit_output(f"Error: {self._error_message}")
        return False

    @override
    async def refresh_status(self) -> ToolStatus:
        """Check Tailscale connection status via `tailscale status --json`.

        Returns:
            The current ToolStatus.
        """
        if self._status == ToolStatus.UNAVAILABLE and not ProcessManager.find_command(
            self.command
        ):
            return self._status

        try:
            result = await ProcessManager.run_command(
                ["tailscale", "status", "--json"], timeout=5.0
            )
            if not result.success:
                return self._status_from_failure(result)
            status = cast("dict[str, object]", json.loads(result.stdout))
            backend_state = str(status.get("BackendState", ""))
        except Exception as e:  # ruff: ignore[blind-except]  # tailscale CLI/JSON can fail many ways
            self._status = ToolStatus.ERROR
            self._error_message = str(e)
            return self._status

        self._error_message = None
        self._status = self._map_backend_state(backend_state)
        return self._status

    def _status_from_failure(self, result: ProcessResult) -> ToolStatus:
        """Record and return an error status from a failed status query.

        Args:
            result: The failed `tailscale status` process result.

        Returns:
            The ERROR ToolStatus.
        """
        # Daemon not reachable (not installed/running as a service)
        self._status = ToolStatus.ERROR
        self._error_message = result.stderr.strip() or "tailscaled not reachable"
        return self._status

    def _map_backend_state(self, backend_state: str) -> ToolStatus:
        """Map Tailscale's BackendState to a ToolStatus.

        Tailscale reports one of: "Running", "Stopped", "Starting",
        "NeedsLogin", "NeedsMachineAuth", "NoState".

        Auth-required states surface as ERROR so the user is prompted to act
        (the login URL is emitted by `tailscale up`). "NoState" means the
        daemon is up but unconfigured, which we treat as STOPPED.

        Args:
            backend_state: The BackendState string reported by Tailscale.

        Returns:
            The ToolStatus corresponding to the backend state.
        """
        match backend_state:
            case "Running":
                return ToolStatus.RUNNING
            case "Starting":
                return ToolStatus.STARTING
            case "Stopped" | "NoState":
                return ToolStatus.STOPPED
            case "NeedsLogin" | "NeedsMachineAuth":
                self._error_message = (
                    "Tailscale needs authentication (run `tailscale up`)"
                )
                return ToolStatus.ERROR
            case _:
                self._error_message = f"Unknown Tailscale state: {backend_state}"
                return ToolStatus.ERROR
