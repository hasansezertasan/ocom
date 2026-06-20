"""Process management for running network tools."""

import asyncio
import os
import shutil
import sys
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

IS_WINDOWS = sys.platform == "win32"


def is_admin() -> bool:
    """Check if the current process has elevated privileges.

    On Windows: checks if running as Administrator.
    On Unix: checks if running as root (uid 0).

    Returns:
        True if running with elevated privileges.
    """
    if IS_WINDOWS:
        try:
            import ctypes

            # windll is Windows-only and absent from ctypes' type stubs on other
            # platforms. Reach it through an Any-typed alias so mypy doesn't flag
            # the attribute. This avoids both a `# type: ignore` (which the ruff
            # autofix keeps relocating onto its own line, breaking mypy) and a
            # getattr-with-constant (which ruff's B009 would rewrite back).
            ctypes_any: Any = ctypes
            return bool(ctypes_any.windll.shell32.IsUserAnAdmin())
        except Exception:
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
        timeout: float | None = 30.0,
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
            asyncio.TimeoutError: If timeout exceeded.
            subprocess.CalledProcessError: If check=True and command fails.
        """
        proc = await asyncio.create_subprocess_exec(
            *args,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )

        try:
            stdout, stderr = await asyncio.wait_for(
                proc.communicate(),
                timeout=timeout,
            )
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
            raise RuntimeError(f"Command failed: {result.stderr or result.stdout}")

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
            asyncio.create_task(_read_output(proc.stdout, on_output))

        return proc

    @staticmethod
    async def stop_process(
        proc: asyncio.subprocess.Process,
        *,
        timeout: float = 5.0,
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
            proc.terminate()  # Cross-platform: SIGTERM on Unix, TerminateProcess on Windows
            await asyncio.wait_for(proc.wait(), timeout=timeout)
            return True
        except TimeoutError:
            proc.kill()
            await proc.wait()
            return True
        except ProcessLookupError:
            return True

    @staticmethod
    def is_process_running(proc: asyncio.subprocess.Process | None) -> bool:
        """Check if a process is still running."""
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
                asyncio.open_connection(host, port),
                timeout=1.0,
            )
            writer.close()
            await writer.wait_closed()
            return True
        except TimeoutError, OSError:
            return False


async def _read_output(
    stream: asyncio.StreamReader,
    callback: Callable[[str], None],
) -> None:
    """Read lines from a stream and call callback for each."""
    while True:
        line = await stream.readline()
        if not line:
            break
        callback(line.decode("utf-8", errors="replace").rstrip())
