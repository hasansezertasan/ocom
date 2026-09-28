"""SpoofDPI tool implementation."""

import asyncio
from typing import ClassVar, final, override

from ocom.core.config import SpoofDPIConfig
from ocom.core.process import ProcessManager
from ocom.core.tool import BaseTool, ToolConfig, ToolStatus

__all__ = ["SpoofDPITool"]

# How long start() waits for the proxy to accept connections before giving up.
READY_TIMEOUT = 10.0
# Delay between readiness probes while waiting for the listener.
READY_POLL_INTERVAL = 0.25


@final
class SpoofDPITool(BaseTool):
    """SpoofDPI anti-censorship proxy.

    SpoofDPI is a simple DPI bypass tool that runs as a local proxy.
    It modifies packets to evade Deep Packet Inspection.
    """

    name = "SpoofDPI"
    description = "DPI bypass proxy"
    command = "spoofdpi"
    requires_sudo = False
    supports_configs = False
    install_url = "https://github.com/xvzc/SpoofDPI#installation"
    # Same function, different platform
    conflicts_with: ClassVar[list[str]] = ["GoodbyeDPI"]

    def __init__(self) -> None:
        """Initialize the SpoofDPI tool with its default proxy port."""
        super().__init__()
        self._port: int = 8080

    @override
    async def start(self, config: ToolConfig) -> bool:
        """Start SpoofDPI proxy.

        Args:
            config: Can contain options for dns_addr, dns_mode, port, system_proxy.

        Returns:
            True if the proxy started successfully.
        """
        self._status = ToolStatus.STARTING

        # Build command with options
        args = ["spoofdpi"]

        # Get options from config (defaults match SpoofDPIConfig)
        dns_addr = config.options.get("dns_addr", SpoofDPIConfig().dns_addr)
        dns_mode = config.options.get("dns_mode", SpoofDPIConfig().dns_mode)
        port = config.options.get("port", SpoofDPIConfig().port)
        system_proxy = config.options.get("system_proxy", SpoofDPIConfig().system_proxy)
        self._port = int(port)

        args.extend(["--listen-addr", f"127.0.0.1:{self._port}"])
        args.extend(["--dns-addr", str(dns_addr)])
        args.extend(["--dns-mode", str(dns_mode)])
        # No --silent flag: output is streamed to the log panel via on_output
        if system_proxy:
            args.append("--system-proxy")

        args.extend(config.extra_args)

        try:
            self._process = await ProcessManager.start_process(
                args, on_output=self._emit_output
            )
        except Exception as e:  # ruff: ignore[blind-except]  # external CLI can fail many ways
            self._status = ToolStatus.ERROR
            self._error_message = str(e)
            self._emit_output(f"Error: {e}")
            return False

        if not await self._wait_until_ready():
            self._emit_output(f"Command was: {' '.join(args)}")
            await self._abort_start()
            return False

        self._status = ToolStatus.RUNNING
        self._emit_output(f"Proxy started on 127.0.0.1:{self._port}")
        return True

    async def _wait_until_ready(self) -> bool:
        """Poll until the proxy listens, the process exits, or time runs out.

        Returns:
            True once the port accepts connections; False (with the error
            recorded) if the process exits or the port never opens in time.
        """
        try:
            async with asyncio.timeout(READY_TIMEOUT):
                while not await ProcessManager.check_port_in_use(self._port):
                    if not ProcessManager.is_process_running(self._process):
                        exit_code = self._process.returncode if self._process else None
                        return self._fail(f"Process exited with code {exit_code}")
                    await asyncio.sleep(READY_POLL_INTERVAL)
        except TimeoutError:
            address = f"127.0.0.1:{self._port}"
            timeout = f"{READY_TIMEOUT:g}s"
            return self._fail(f"Proxy did not listen on {address} within {timeout}")
        return True

    def _fail(self, message: str) -> bool:
        """Record a startup failure as ERROR and log it.

        Returns:
            Always False, so callers can ``return self._fail(...)``.
        """
        self._status = ToolStatus.ERROR
        self._error_message = message
        self._emit_output(f"Error: {message}")
        return False

    async def _abort_start(self) -> None:
        """Stop a process that never became ready, keeping the ERROR status."""
        if self._process is not None:
            await ProcessManager.stop_process(self._process)
        self._process = None

    @override
    async def stop(self) -> bool:
        """Stop SpoofDPI proxy.

        Returns:
            True if the proxy was stopped.
        """
        if self._process is None:
            self._status = ToolStatus.STOPPED
            return True

        self._status = ToolStatus.STOPPING

        success = await ProcessManager.stop_process(self._process)
        self._process = None
        self._status = ToolStatus.STOPPED
        self._emit_output("Proxy stopped")
        return success

    @override
    async def refresh_status(self) -> ToolStatus:
        """Refresh SpoofDPI status.

        Returns:
            The current ToolStatus.
        """
        if self._status == ToolStatus.UNAVAILABLE:
            await self.check_available()
            return self._status

        # start()/stop() own the status while a transition is in flight, so a
        # periodic refresh must not report RUNNING before the port is ready.
        if self._status.is_transitioning:
            return self._status

        if self._process is not None:
            self._reconcile_process_state()
        elif self._status == ToolStatus.RUNNING:
            await self._reconcile_port_state()

        return self._status

    def _reconcile_process_state(self) -> None:
        """Update status from the tracked process's liveness."""
        if ProcessManager.is_process_running(self._process):
            self._status = ToolStatus.RUNNING
        else:
            self._status = ToolStatus.STOPPED
            self._process = None

    async def _reconcile_port_state(self) -> None:
        """Update status from whether the proxy port is still in use.

        Handles the case where the proxy was started externally.
        """
        if await ProcessManager.check_port_in_use(self._port):
            self._status = ToolStatus.RUNNING
        else:
            self._status = ToolStatus.STOPPED

    @override
    def get_status_text(self) -> str:
        """Get SpoofDPI-specific status text.

        Returns:
            A short human-readable status string.
        """
        if self._status == ToolStatus.RUNNING:
            return f"Proxy on :{self._port}"
        return super().get_status_text()
