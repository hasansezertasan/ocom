"""SpoofDPI tool implementation."""

from typing import ClassVar, final, override

from ocom.core.config import SpoofDPIConfig
from ocom.core.process import ProcessManager
from ocom.core.tool import BaseTool, StartError, ToolConfig, ToolStatus

__all__ = ["SpoofDPITool"]

# How long start() waits for the proxy to accept connections before giving up.
READY_TIMEOUT = 10.0


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

    @property
    def _listen_addr(self) -> str:
        """The loopback address the proxy listens on."""
        return f"127.0.0.1:{self._port}"

    @override
    async def start(self, config: ToolConfig) -> bool:
        """Start SpoofDPI proxy.

        The tool stays STARTING until the proxy accepts connections.

        Args:
            config: Can contain options for dns_addr, dns_mode, port, system_proxy.

        Returns:
            True if the proxy started successfully.
        """
        if not await self._run_start(lambda: self._launch(config)):
            return False
        self._emit_output(f"Proxy started on {self._listen_addr}")
        return True

    async def _launch(self, config: ToolConfig) -> None:
        """Spawn the proxy and wait for it to listen.

        Raises:
            StartError: If the port is taken, or the proxy never listens.
        """
        # Get options from config (defaults match SpoofDPIConfig)
        dns_addr = config.options.get("dns_addr", SpoofDPIConfig().dns_addr)
        dns_mode = config.options.get("dns_mode", SpoofDPIConfig().dns_mode)
        port = config.options.get("port", SpoofDPIConfig().port)
        system_proxy = config.options.get("system_proxy", SpoofDPIConfig().system_proxy)
        self._port = int(port)

        args = ["spoofdpi", "--listen-addr", self._listen_addr]
        args.extend(["--dns-addr", str(dns_addr)])
        args.extend(["--dns-mode", str(dns_mode)])
        # No --silent flag: output is streamed to the log panel via on_output
        if system_proxy:
            args.append("--system-proxy")

        args.extend(config.extra_args)

        # A listener already on the port would answer the readiness probe even
        # though the new process cannot bind, so refuse up front.
        if await ProcessManager.check_port_in_use(self._port):
            msg = f"Port {self._listen_addr} is already in use"
            raise StartError(msg)

        self._process = await ProcessManager.start_process(
            args, on_output=self._emit_output
        )
        try:
            await self._wait_until_listening()
        except StartError:
            self._emit_output(f"Command was: {' '.join(args)}")
            raise

    async def _wait_until_listening(self) -> None:
        """Wait until the proxy port accepts connections.

        Raises:
            StartError: If the process exits or the port never opens in time.
        """
        if not await self._wait_until_ready(self._is_listening, within=READY_TIMEOUT):
            timeout = f"{READY_TIMEOUT:g}s"
            msg = f"Proxy did not listen on {self._listen_addr} within {timeout}"
            raise StartError(msg)

    async def _is_listening(self) -> bool:
        """Probe whether the proxy port accepts connections.

        Returns:
            True if the port is in use.
        """
        return await ProcessManager.check_port_in_use(self._port)

    @override
    async def stop(self) -> bool:
        """Stop SpoofDPI proxy.

        Returns:
            True if the proxy was stopped.
        """
        return await self._stop_tracked_process("Proxy stopped")

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
