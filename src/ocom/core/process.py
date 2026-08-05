"""Process management for running network tools."""

import asyncio
import os
import shutil
import sys
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from collections.abc import Callable

__all__ = ["ProcessManager", "ProcessResult", "is_admin"]

IS_WINDOWS = sys.platform == "win32"

# Keep strong references to background output-reader tasks so they are not
# garbage-collected mid-run (asyncio only holds weak references to tasks).
_background_tasks: set[asyncio.Task[None]] = set()


def is_admin() -> bool:
    """Check if the current process has elevated privileges.

    On Windows: checks if running as Administrator.
    On Unix: checks if running as root (uid 0).

    Returns:
        True if running with elevated privileges.
    """
    if IS_WINDOWS:
        try:
            import ctypes  # ruff: ignore[import-outside-top-level]  # Windows-only lazy import

            # windll is Windows-only and absent from ctypes' type stubs on other
            # platforms. Reach it through an Any-typed alias so mypy doesn't flag
            # the attribute. This avoids both a type-ignore comment (which the
            # ruff autofix keeps relocating onto its own line, breaking mypy) and
            # a getattr-with-constant (which ruff's B009 would rewrite back).
            ctypes_any: Any = ctypes  # pyright: ignore[reportExplicitAny]  # windll is Windows-only, absent from cross-platform ctypes stubs
            return bool(ctypes_any.windll.shell32.IsUserAnAdmin())  # pyright: ignore[reportAny]  # untyped Windows-only ctypes attribute chain
        except Exception:  # ruff: ignore[blind-except]  # ctypes call may fail many ways; treat as not-admin
            return False
    else:
        return os.getuid() == 0


@dataclass
class ProcessResult:
    """Result of a process execution."""

    returncode: int
    stdout: str
    stderr: str

    @property
    def success(self) -> bool:
        """Check if process completed successfully."""
        return self.returncode == 0


class ProcessManager:
    """Manages subprocess lifecycle for network tools.

    Provides utilities for:
    - Running commands and capturing output
    - Starting long-running processes
    - Monitoring process output
    - Graceful shutdown
    """

    @staticmethod
    def find_command(command: str) -> str | None:
        """Find the full path to a command.

        Args:
            command: Command name to find.

        Returns:
            Full path to the command, or None if not found.
        """
        return shutil.which(command)

    @staticmethod
    async def run_command(
        args: list[str],
        *,
        timeout: float | None = 30.0,  # ruff: ignore[async-function-with-timeout]  # explicit timeout is part of the public API
        check: bool = False,
    ) -> ProcessResult:
        """Run a command and wait for completion.

        Args:
            args: Command and arguments as a list.
            timeout: Maximum time to wait in seconds.
            check: Raise exception if command fails.

        Returns:
            ProcessResult with output and return code.

        Raises:
            TimeoutError: If timeout exceeded.
            RuntimeError: If check=True and command fails.
        """
        proc = await asyncio.create_subprocess_exec(
            *args, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE
        )

        try:
            stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=timeout)
        except TimeoutError:
            proc.kill()
            await proc.wait()
            raise

        result = ProcessResult(
            returncode=proc.returncode or 0,
            stdout=stdout.decode("utf-8", errors="replace"),
            stderr=stderr.decode("utf-8", errors="replace"),
        )

        if check and not result.success:
            msg = f"Command failed: {result.stderr or result.stdout}"
            raise RuntimeError(msg)

        return result

    @staticmethod
    async def start_process(
        args: list[str],
        *,
        on_output: Callable[[str], None] | None = None,
        env: dict[str, str] | None = None,
        stdin_data: str | None = None,
    ) -> asyncio.subprocess.Process:
        """Start a long-running process.

        Args:
            args: Command and arguments as a list.
            on_output: Callback for stdout lines (optional).
            env: Environment variables (merged with current env).
            stdin_data: Data to write to stdin (e.g., password for sudo -S).

        Returns:
            The started Process object.
        """
        process_env = os.environ.copy()
        if env:
            process_env.update(env)

        proc = await asyncio.create_subprocess_exec(
            *args,
            stdin=asyncio.subprocess.PIPE if stdin_data else None,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.STDOUT,
            env=process_env,
        )

        # Write stdin data if provided (e.g., sudo password)
        if stdin_data and proc.stdin:
            proc.stdin.write((stdin_data + "\n").encode())
            await proc.stdin.drain()
            # Don't close stdin - process may need it open

        if on_output and proc.stdout:
            task = asyncio.create_task(_read_output(proc.stdout, on_output))
            _background_tasks.add(task)
            task.add_done_callback(_background_tasks.discard)

        return proc

    @staticmethod
    async def stop_process(
        proc: asyncio.subprocess.Process,
        *,
        timeout: float = 5.0,  # ruff: ignore[async-function-with-timeout]  # explicit timeout is part of the public API
    ) -> bool:
        """Gracefully stop a process.

        Uses terminate() first (cross-platform), then kill() if needed.

        Args:
            proc: Process to stop.
            timeout: Time to wait for graceful shutdown.

        Returns:
            True if process was stopped.
        """
        if proc.returncode is not None:
            return True

        try:
            # Cross-platform: SIGTERM on Unix, TerminateProcess on Windows.
            proc.terminate()
            await asyncio.wait_for(proc.wait(), timeout=timeout)
        except TimeoutError:
            proc.kill()
            await proc.wait()
        except ProcessLookupError:
            return True
        return True

    @staticmethod
    def is_process_running(proc: asyncio.subprocess.Process | None) -> bool:
        """Check if a process is still running.

        Returns:
            True if the process exists and has not exited.
        """
        return proc is not None and proc.returncode is None

    @staticmethod
    async def check_port_in_use(port: int, host: str = "127.0.0.1") -> bool:
        """Check if a port is in use (for proxy tools).

        Args:
            port: Port number to check.
            host: Host to check on.

        Returns:
            True if port is in use.
        """
        try:
            _, writer = await asyncio.wait_for(
                asyncio.open_connection(host, port), timeout=1.0
            )
            writer.close()
            await writer.wait_closed()
        # TimeoutError is a subclass of OSError, so this catches both a
        # connection failure and the wait_for timeout with a single (paren-free,
        # format-stable) exception type.
        except OSError:
            return False
        return True


async def _read_output(
    stream: asyncio.StreamReader, callback: Callable[[str], None]
) -> None:
    """Read lines from a stream and call callback for each."""
    while True:
        line = await stream.readline()
        if not line:
            break
        callback(line.decode("utf-8", errors="replace").rstrip())
