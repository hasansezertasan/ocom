"""Tests for ProcessManager."""

import asyncio
import sys

import pytest

from ocom.core.process import IS_WINDOWS, ProcessManager, ProcessResult


class TestProcessResult:
    """Test ProcessResult dataclass."""

    def test_success_when_returncode_zero(self) -> None:
        """success property should be True when returncode is 0."""
        result = ProcessResult(returncode=0, stdout="output", stderr="")
        assert result.success is True

    def test_failure_when_returncode_nonzero(self) -> None:
        """success property should be False when returncode is non-zero."""
        result = ProcessResult(returncode=1, stdout="", stderr="error")
        assert result.success is False

    @pytest.mark.parametrize("code", [-1, 127, 255])
    def test_various_error_codes(self, code: int) -> None:
        """Various non-zero codes should all be failures."""
        result = ProcessResult(returncode=code, stdout="", stderr="")
        assert result.success is False


class TestFindCommand:
    """Test ProcessManager.find_command()."""

    def test_find_existing_command(self) -> None:
        """Should find common system commands."""
        # 'python' should exist since we're running tests with it
        cmd = "python" if IS_WINDOWS else "python3"
        result = ProcessManager.find_command(cmd)
        assert result is not None
        assert cmd in result.lower() or "python" in result.lower()

    def test_find_nonexistent_command(self) -> None:
        """Should return None for non-existent commands."""
        result = ProcessManager.find_command("nonexistent_command_xyz_123")
        assert result is None


class TestRunCommand:
    """Test ProcessManager.run_command()."""

    async def test_run_simple_command(self) -> None:
        """Should capture stdout from a simple command."""
        if IS_WINDOWS:
            result = await ProcessManager.run_command(["cmd", "/c", "echo", "hello"])
        else:
            result = await ProcessManager.run_command(["echo", "hello"])

        assert result.success
        assert "hello" in result.stdout

    async def test_run_command_with_args(self) -> None:
        """Should pass arguments correctly."""
        result = await ProcessManager.run_command(
            [sys.executable, "-c", "print('test123')"]
        )
        assert result.success
        assert "test123" in result.stdout

    async def test_run_failing_command(self) -> None:
        """Should capture failure status."""
        result = await ProcessManager.run_command([sys.executable, "-c", "exit(1)"])
        assert not result.success
        assert result.returncode == 1

    async def test_run_command_captures_stderr(self) -> None:
        """Should capture stderr output."""
        result = await ProcessManager.run_command(
            [
                sys.executable,
                "-c",
                "import sys; sys.stderr.write('error\\n')",
            ]
        )
        assert "error" in result.stderr

    async def test_run_command_timeout(self) -> None:
        """Should raise TimeoutError when command exceeds timeout."""
        with pytest.raises(TimeoutError):
            await ProcessManager.run_command(
                [sys.executable, "-c", "import time; time.sleep(10)"],
                timeout=0.1,
            )

    async def test_run_command_check_raises(self) -> None:
        """Should raise when check=True and command fails."""
        with pytest.raises(RuntimeError, match="Command failed"):
            await ProcessManager.run_command(
                [sys.executable, "-c", "import sys; sys.stderr.write('oops'); exit(1)"],
                check=True,
            )


class TestStartProcess:
    """Test ProcessManager.start_process()."""

    async def test_start_process_returns_process(self) -> None:
        """Should return a running Process object."""
        proc = await ProcessManager.start_process(
            [
                sys.executable,
                "-c",
                "import time; time.sleep(5)",
            ]
        )
        try:
            assert ProcessManager.is_process_running(proc)
        finally:
            proc.terminate()
            await proc.wait()

    async def test_start_process_with_output_callback(self) -> None:
        """Should call callback with output lines."""
        output_lines: list[str] = []

        def collect_output(line: str) -> None:
            output_lines.append(line)

        proc = await ProcessManager.start_process(
            [sys.executable, "-c", "print('line1'); print('line2')"],
            on_output=collect_output,
        )

        await proc.wait()
        # Poll for output to be processed (callback runs in background task)
        for _ in range(20):
            if "line1" in output_lines and "line2" in output_lines:
                break
            await asyncio.sleep(0.05)

        assert "line1" in output_lines
        assert "line2" in output_lines

    async def test_start_process_with_stdin(self) -> None:
        """Should write stdin data to process."""
        proc = await ProcessManager.start_process(
            [sys.executable, "-c", "print(input())"],
            stdin_data="hello_stdin",
        )

        # Read output
        assert proc.stdout is not None
        output = await proc.stdout.read()
        await proc.wait()

        assert b"hello_stdin" in output


class TestStopProcess:
    """Test ProcessManager.stop_process()."""

    async def test_stop_running_process(self) -> None:
        """Should gracefully terminate a running process."""
        proc = await ProcessManager.start_process(
            [
                sys.executable,
                "-c",
                "import time; time.sleep(30)",
            ]
        )

        assert ProcessManager.is_process_running(proc)
        success = await ProcessManager.stop_process(proc)

        assert success
        assert not ProcessManager.is_process_running(proc)

    async def test_stop_already_finished_process(self) -> None:
        """Should handle already-finished processes."""
        proc = await ProcessManager.start_process([sys.executable, "-c", "pass"])
        await proc.wait()

        # Process already finished
        success = await ProcessManager.stop_process(proc)
        assert success

    async def test_stop_process_timeout_triggers_kill(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Should fall back to kill() when terminate() doesn't stop in time."""
        proc = await ProcessManager.start_process(
            [
                sys.executable,
                "-c",
                "import time; time.sleep(30)",
            ]
        )

        killed = False
        real_wait = proc.wait

        def fake_kill() -> None:
            # Record the kill request without re-signalling; terminate() already
            # reaped this child, so a real kill() would raise ProcessLookupError.
            nonlocal killed
            killed = True

        # Delay wait() past the timeout so the graceful path times out and the
        # kill branch runs, then defer to the real wait so cleanup completes.
        async def slow_wait() -> int:
            await asyncio.sleep(0.2)
            return await real_wait()

        monkeypatch.setattr(proc, "kill", fake_kill)
        monkeypatch.setattr(proc, "wait", slow_wait)

        try:
            success = await ProcessManager.stop_process(proc, timeout=0.05)
            assert success is True
            assert killed is True
        finally:
            monkeypatch.undo()
            if ProcessManager.is_process_running(proc):
                proc.kill()
            await proc.wait()


class TestIsProcessRunning:
    """Test ProcessManager.is_process_running()."""

    def test_none_process_is_not_running(self) -> None:
        """None should not be considered running."""
        assert ProcessManager.is_process_running(None) is False

    async def test_active_process_is_running(self) -> None:
        """Active process should be considered running."""
        proc = await ProcessManager.start_process(
            [
                sys.executable,
                "-c",
                "import time; time.sleep(10)",
            ]
        )
        try:
            assert ProcessManager.is_process_running(proc) is True
        finally:
            proc.terminate()
            await proc.wait()

    async def test_finished_process_is_not_running(self) -> None:
        """Finished process should not be considered running."""
        proc = await ProcessManager.start_process([sys.executable, "-c", "pass"])
        await proc.wait()
        assert ProcessManager.is_process_running(proc) is False


class TestCheckPortInUse:
    """Test ProcessManager.check_port_in_use()."""

    async def test_unused_port_returns_false(self) -> None:
        """Unused port should return False."""
        # Bind to port 0 to get an OS-assigned free port, then release it
        server = await asyncio.start_server(lambda r, w: None, "127.0.0.1", 0)
        port = server.sockets[0].getsockname()[1]
        server.close()
        await server.wait_closed()

        result = await ProcessManager.check_port_in_use(port)
        assert result is False

    async def test_used_port_returns_true(self) -> None:
        """Port with a listener should return True."""
        # Start a simple TCP server
        server = await asyncio.start_server(
            lambda r, w: None,  # Dummy handler
            "127.0.0.1",
            0,  # Let OS pick a free port
        )
        port = server.sockets[0].getsockname()[1]

        try:
            result = await ProcessManager.check_port_in_use(port)
            assert result is True
        finally:
            server.close()
            await server.wait_closed()

    @pytest.mark.parametrize("exc_type", [OSError, TimeoutError])
    async def test_connection_errors_return_false(
        self, monkeypatch: pytest.MonkeyPatch, exc_type: type[Exception]
    ) -> None:
        """Connection failures and timeouts should be treated as port not in use."""

        async def raise_error(*_args: object, **_kwargs: object) -> None:
            raise exc_type("boom")

        monkeypatch.setattr(asyncio, "open_connection", raise_error)

        result = await ProcessManager.check_port_in_use(65535)
        assert result is False
