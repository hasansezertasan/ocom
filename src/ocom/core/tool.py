"""Base tool abstraction for network/privacy tools."""

import asyncio
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from typing import TYPE_CHECKING, ClassVar

from ocom.core.process import ProcessManager

if TYPE_CHECKING:
    from collections.abc import Awaitable, Callable

__all__ = ["BaseTool", "StartError", "ToolConfig", "ToolStatus"]

# Delay between readiness probes while a started process comes up.
READY_POLL_INTERVAL = 0.25


class StartError(Exception):
    """A tool failed to start; the message is shown to the user."""


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
        return self in {ToolStatus.STARTING, ToolStatus.STOPPING}

    @property
    def can_start(self) -> bool:
        """Check if tool can be started from this state."""
        return self in {ToolStatus.STOPPED, ToolStatus.ERROR}

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
    options: dict[str, str | bool | int] = field(
        default_factory=dict
    )  # Tool-specific options


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
    config_extensions: ClassVar[list[str]] = []  # File extensions (e.g., [".ovpn"])
    install_url: str = ""  # URL to installation documentation
    conflicts_with: ClassVar[list[str]] = []  # Conflicting tool names (auto-stopped)

    def __init__(self) -> None:
        """Initialize the tool in the UNAVAILABLE state."""
        self._status: ToolStatus = ToolStatus.UNAVAILABLE
        self._process: asyncio.subprocess.Process | None = None
        self._error_message: str | None = None
        self._current_config: str | None = None
        self._output_callback: Callable[[str, str], None] | None = None
        # The task running _run_start(), so a concurrent stop() can abort it.
        self._start_task: asyncio.Task[object] | None = None
        self._start_aborted: bool = False

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

    async def _run_start(self, launch: Callable[[], Awaitable[None]]) -> bool:
        """Run ``launch`` as a start transition that always settles.

        The tool is STARTING while ``launch`` runs and RUNNING once it returns.
        Every other exit leaves a terminal status and no stray process behind,
        because ``refresh_status()`` does not correct a transitional status.
        A concurrent ``stop()`` aborts the start, which then returns False
        with the tool STOPPED.

        Args:
            launch: Spawns the tool and waits for it to be ready; raises
                ``StartError`` (or anything else) on failure.

        Returns:
            True if the tool is RUNNING; False after a recorded failure.

        Raises:
            CancelledError: Re-raised after cleanup if the start is cancelled.
        """
        self._status = ToolStatus.STARTING
        self._error_message = None
        self._start_task = asyncio.current_task()
        try:
            return await self._attempt_start(launch)
        except asyncio.CancelledError:
            # Also reached when stop() lands during a failed start's cleanup.
            await self._abandon(ToolStatus.STOPPED)
            if not self._absorb_abort():
                raise
            return False
        finally:
            self._start_task = None
            # Scope the abort request to this attempt, even if an outside
            # cancel interrupted cleanup before _absorb_abort() consumed it.
            self._start_aborted = False

    async def _attempt_start(self, launch: Callable[[], Awaitable[None]]) -> bool:
        """Run ``launch``, settling on RUNNING or, after a failure, ERROR.

        Returns:
            True if the tool is RUNNING; False after a recorded failure.
        """
        try:
            await launch()
        except Exception as e:  # ruff: ignore[blind-except]  # external CLI can fail many ways
            self._fail(str(e) or type(e).__name__)
            await self._abandon(ToolStatus.ERROR)
            return False
        self._status = ToolStatus.RUNNING
        return True

    def _absorb_abort(self) -> bool:
        """Swallow a cancellation that came only from ``stop()``.

        Returns:
            True if ``stop()`` requested the cancellation and nothing else
            also cancelled the task; False if it must propagate.
        """
        aborted, self._start_aborted = self._start_aborted, False
        task = asyncio.current_task()
        return aborted and task is not None and task.uncancel() == 0

    async def _wait_until_ready(
        self, is_ready: Callable[[], Awaitable[bool]] | None, *, within: float
    ) -> bool:
        """Poll the tracked process until it is ready, exits, or time runs out.

        A process that exits before it is ready raises ``StartError``.

        Args:
            is_ready: Tool-specific readiness probe; may raise ``StartError``
                for a definite failure. None watches liveness for the whole
                window, for tools whose only readiness signal is staying up.
            within: Seconds to wait.

        Returns:
            True once ``is_ready`` passes; False if the window ends with the
            process still alive.

        Raises:
            TimeoutError: If ``is_ready`` itself times out.
        """
        deadline = asyncio.timeout(within)
        try:
            async with deadline:
                return await self._poll_until_ready(is_ready)
        except TimeoutError:
            # Only the deadline means "not ready in time"; a probe's own
            # TimeoutError is a failure like any other.
            if not deadline.expired():
                raise
        # The process may have died after the last poll but before the deadline.
        self._raise_if_exited()
        return False

    async def _poll_until_ready(
        self, is_ready: Callable[[], Awaitable[bool]] | None
    ) -> bool:
        """Poll until the probe passes; the caller bounds this with a deadline.

        Returns:
            True once ``is_ready`` passes on a still-running process.
        """
        while True:
            # Probe before the liveness check, so a tool that logs why it
            # failed and then exits reports that reason; but only accept
            # "ready" from a process that is still alive.
            ready = is_ready is not None and await is_ready()
            self._raise_if_exited()
            if ready:
                return True
            await asyncio.sleep(READY_POLL_INTERVAL)

    def _raise_if_exited(self) -> None:
        """Raise ``StartError`` if the tracked process is not running.

        Raises:
            StartError: If the process has exited (or was never spawned).
        """
        proc = self._process
        if not ProcessManager.is_process_running(proc):
            code = proc.returncode if proc is not None else None
            msg = f"Process exited with code {code}"
            raise StartError(msg)

    def _fail(self, message: str) -> None:
        """Record a failure as ERROR and log it."""
        self._status = ToolStatus.ERROR
        self._error_message = message
        self._emit_output(f"Error: {message}")

    async def _abandon(self, status: ToolStatus) -> None:
        """Settle on ``status`` and stop the tracked process, if any.

        The status is set and the process detached before awaiting its
        shutdown, so a refresh meanwhile cannot overwrite the outcome.
        """
        self._status = status
        proc, self._process = self._process, None
        if proc is not None:
            await ProcessManager.stop_process(proc)

    async def _stop_tracked_process(self, stopped_message: str | None = None) -> bool:
        """Stop the tracked process and settle on STOPPED, even if cancelled.

        Args:
            stopped_message: Logged once a tracked process has been stopped.

        Returns:
            True if the process was stopped (or there was none).
        """
        if (
            self._start_task is not None
            and self._start_task is not asyncio.current_task()
        ):
            await self._abort_start(self._start_task)
            if stopped_message:
                self._emit_output(stopped_message)
            return True

        proc, self._process = self._process, None
        if proc is None:
            self._status = ToolStatus.STOPPED
            return True

        self._status = ToolStatus.STOPPING
        try:
            success = await ProcessManager.stop_process(proc)
        finally:
            # Settle even if cancelled: refresh_status() won't leave STOPPING.
            self._status = ToolStatus.STOPPED
        if stopped_message:
            self._emit_output(stopped_message)
        return success

    async def _abort_start(self, task: asyncio.Task[object]) -> None:
        """Cancel an in-flight ``_run_start()`` and wait for it to settle.

        The start's own cleanup stops the process and settles on STOPPED. A
        second stop() while that cleanup runs only waits for it: cancelling
        again would interrupt the cleanup and leave the tool STOPPING.
        """
        if not self._start_aborted:
            self._status = ToolStatus.STOPPING
            self._start_aborted = True
            task.cancel()
        await asyncio.wait([task])

    def get_config_files(self, config: ToolConfig) -> list[str]:  # ruff: ignore[no-self-use]
        """Get list of available config files.

        Override this for tools that use config files.

        Args:
            config: Tool configuration with directories to scan.

        Returns:
            List of config file paths.
        """
        # Base hook: the default implementation ignores config; subclasses that
        # support config files override this and read it.
        _ = config
        return []

    def get_status_text(self) -> str:
        """Get human-readable status text for display.

        Can be overridden for tool-specific status details.

        Returns:
            A human-readable string describing the current status.
        """
        if self._status == ToolStatus.ERROR and self._error_message:
            return f"Error: {self._error_message}"
        if self._status == ToolStatus.RUNNING and self._current_config:
            return self._current_config
        return self._status.value.capitalize()
