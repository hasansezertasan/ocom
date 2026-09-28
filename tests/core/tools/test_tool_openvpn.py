"""Tests for OpenVPNTool."""

import asyncio
from pathlib import Path
from typing import TYPE_CHECKING
from unittest.mock import AsyncMock, MagicMock

import pytest

from ocom.core.tool import ToolConfig, ToolStatus
from ocom.core.tools.openvpn import INIT_COMPLETE, OpenVPNTool

if TYPE_CHECKING:
    from collections.abc import Callable

    from pytest_mock import MockerFixture


@pytest.fixture
def tool() -> OpenVPNTool:
    """Create an OpenVPNTool instance."""
    return OpenVPNTool()


class TestConstruction:
    """Test OpenVPNTool attributes and construction."""

    def test_attributes(self, tool: OpenVPNTool) -> None:
        """Class attributes should match the documented tool contract."""
        assert tool.name == "OpenVPN"
        assert tool.command == "openvpn"
        assert tool.supports_configs is True
        assert tool.conflicts_with == ["WARP"]
        assert tool.install_url.startswith("https://")
        assert tool.config_extensions == [".ovpn", ".conf"]
        assert tool._initialized is False
        assert tool._auth_failed is False


class TestValidateConfig:
    """Test OpenVPNTool.start() config validation."""

    async def test_start_no_config_file(self, tool: OpenVPNTool) -> None:
        """Missing config_file should set ERROR and return False."""
        result = await tool.start(ToolConfig())
        assert result is False
        assert tool.status == ToolStatus.ERROR
        assert tool.error_message == "No config file selected"

    async def test_start_config_not_found(self, tool: OpenVPNTool) -> None:
        """Nonexistent config file should set ERROR and return False."""
        result = await tool.start(ToolConfig(config_file="/no/such/file.ovpn"))
        assert result is False
        assert tool.status == ToolStatus.ERROR
        assert tool.error_message is not None
        assert "not found" in tool.error_message


class TestBuildCommand:
    """Test OpenVPNTool._build_command()."""

    def test_windows_command(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """On Windows the command runs directly without sudo."""
        monkeypatch.setattr("ocom.core.tools.openvpn.IS_WINDOWS", True)
        config = ToolConfig(extra_args=["--verb", "3"])
        args, sudo_pw = OpenVPNTool._build_command(config, Path("my.ovpn"))
        assert args[:3] == ["openvpn", "--config", "my.ovpn"]
        assert args[-2:] == ["--verb", "3"]
        assert sudo_pw is None

    def test_unix_command_with_password(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """On Unix a provided sudo password is threaded through."""
        monkeypatch.setattr("ocom.core.tools.openvpn.IS_WINDOWS", False)
        config = ToolConfig(options={"sudo_password": "secret"})
        args, sudo_pw = OpenVPNTool._build_command(config, Path("my.ovpn"))
        assert args[:4] == ["sudo", "-S", "openvpn", "--config"]
        assert sudo_pw == "secret"

    def test_unix_command_without_password(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """On Unix a missing sudo password yields None."""
        monkeypatch.setattr("ocom.core.tools.openvpn.IS_WINDOWS", False)
        args, sudo_pw = OpenVPNTool._build_command(ToolConfig(), Path("my.ovpn"))
        assert args[0] == "sudo"
        assert sudo_pw is None


@pytest.mark.usefixtures("fast_ready")
class TestStart:
    """Test OpenVPNTool.start() process handling and readiness."""

    @pytest.fixture
    def fast_ready(self, mocker: MockerFixture) -> None:
        """Shrink the readiness wait so a hung poll fails fast."""
        mocker.patch("ocom.core.tools.openvpn.READY_TIMEOUT", 1.0)
        mocker.patch("ocom.core.tool.READY_POLL_INTERVAL", 0.001)

    @pytest.fixture
    def config(self, tmp_path: Path) -> ToolConfig:
        """Build a config pointing at an existing .ovpn file."""
        config_file = tmp_path / "vpn.ovpn"
        config_file.write_text("dummy")
        return ToolConfig(config_file=str(config_file))

    @pytest.fixture
    def stop(self, mocker: MockerFixture) -> AsyncMock:
        """Patch stop_process."""
        return mocker.patch(
            "ocom.core.tools.openvpn.ProcessManager.stop_process",
            new=AsyncMock(return_value=True),
        )

    @staticmethod
    def _spawn_logging(
        mocker: MockerFixture,
        tool: OpenVPNTool,
        lines: list[str],
        returncode: int | None = None,
    ) -> MagicMock:
        """Patch start_process to return a process that logs ``lines``."""
        proc = MagicMock(returncode=returncode)

        async def spawn(*_args: object, **_kwargs: object) -> MagicMock:
            for line in lines:
                tool._handle_output(line)
            return proc

        mocker.patch("ocom.core.tools.openvpn.ProcessManager.start_process", new=spawn)
        return proc

    async def test_start_process_raises(
        self, tool: OpenVPNTool, config: ToolConfig, mocker: MockerFixture
    ) -> None:
        """A raising start_process should be caught and reported as ERROR."""
        mocker.patch(
            "ocom.core.tools.openvpn.ProcessManager.start_process",
            new=AsyncMock(side_effect=RuntimeError("boom")),
        )
        result = await tool.start(config)
        assert result is False
        assert tool.status == ToolStatus.ERROR
        assert tool.error_message == "boom"

    async def test_start_success(
        self, tool: OpenVPNTool, config: ToolConfig, mocker: MockerFixture
    ) -> None:
        """The init-complete marker brings the tunnel to RUNNING."""
        self._spawn_logging(mocker, tool, ["connecting", INIT_COMPLETE])
        result = await tool.start(config)
        assert result is True
        assert tool.status == ToolStatus.RUNNING
        assert tool.current_config == "vpn.ovpn"

    async def test_starting_until_initialized(
        self, tool: OpenVPNTool, config: ToolConfig, mocker: MockerFixture
    ) -> None:
        """Status stays STARTING, even across a refresh, until the marker."""
        self._spawn_logging(mocker, tool, ["connecting..."])
        task = asyncio.create_task(tool.start(config))
        await asyncio.sleep(0.01)
        assert await tool.refresh_status() == ToolStatus.STARTING
        tool._handle_output(f"2026-09-29 {INIT_COMPLETE}")
        assert await task is True
        assert tool.status == ToolStatus.RUNNING

    async def test_auth_failed(
        self,
        tool: OpenVPNTool,
        config: ToolConfig,
        mocker: MockerFixture,
        stop: AsyncMock,
    ) -> None:
        """AUTH_FAILED without initialization is ERROR and stops the process."""
        proc = self._spawn_logging(mocker, tool, ["some log", "AUTH_FAILED"])
        result = await tool.start(config)
        assert result is False
        assert tool.status == ToolStatus.ERROR  # ERROR preserved, not reset
        assert tool.error_message == "Authentication failed"
        assert tool._process is None
        stop.assert_awaited_once_with(proc)

    async def test_init_completed_wins_over_auth_failed(
        self, tool: OpenVPNTool, config: ToolConfig, mocker: MockerFixture
    ) -> None:
        """A completed init overrides an AUTH_FAILED line."""
        self._spawn_logging(mocker, tool, [INIT_COMPLETE, "AUTH_FAILED"])
        assert await tool.start(config) is True
        assert tool.status == ToolStatus.RUNNING

    async def test_process_exits(
        self,
        tool: OpenVPNTool,
        config: ToolConfig,
        mocker: MockerFixture,
        stop: AsyncMock,
    ) -> None:
        """A process that exits before initializing is ERROR."""
        self._spawn_logging(mocker, tool, [], returncode=1)
        result = await tool.start(config)
        assert result is False
        assert tool.status == ToolStatus.ERROR
        assert tool.error_message == "Process exited with code 1"
        stop.assert_awaited_once()

    async def test_timeout(
        self,
        tool: OpenVPNTool,
        config: ToolConfig,
        mocker: MockerFixture,
        stop: AsyncMock,
    ) -> None:
        """A tunnel that never comes up times out to ERROR and is stopped."""
        mocker.patch("ocom.core.tools.openvpn.READY_TIMEOUT", 0.02)
        proc = self._spawn_logging(mocker, tool, ["connecting..."])
        result = await tool.start(config)
        assert result is False
        assert tool.status == ToolStatus.ERROR
        assert tool.error_message == "Connection not established within 0.02s"
        assert tool._process is None
        stop.assert_awaited_once_with(proc)

    @pytest.mark.usefixtures("stop")
    async def test_markers_reset_between_starts(
        self, tool: OpenVPNTool, config: ToolConfig, mocker: MockerFixture
    ) -> None:
        """A previous run's markers do not satisfy a new start."""
        mocker.patch("ocom.core.tools.openvpn.READY_TIMEOUT", 0.02)
        tool._initialized = True
        self._spawn_logging(mocker, tool, [])
        assert await tool.start(config) is False

    async def test_cancelled(
        self,
        tool: OpenVPNTool,
        config: ToolConfig,
        mocker: MockerFixture,
        stop: AsyncMock,
    ) -> None:
        """Cancelling mid-wait stops the process instead of stranding STARTING."""
        mocker.patch("ocom.core.tools.openvpn.READY_TIMEOUT", 60.0)
        proc = self._spawn_logging(mocker, tool, [])
        task = asyncio.create_task(tool.start(config))
        await asyncio.sleep(0.01)
        task.cancel()
        await asyncio.wait([task])
        assert task.cancelled()
        assert tool.status == ToolStatus.STOPPED
        assert tool._process is None
        stop.assert_awaited_once_with(proc)


class TestStop:
    """Test OpenVPNTool.stop()."""

    async def test_stop_without_process(self, tool: OpenVPNTool) -> None:
        """Stopping with no process should just report STOPPED."""
        result = await tool.stop()
        assert result is True
        assert tool.status == ToolStatus.STOPPED

    async def test_stop_with_process(
        self, tool: OpenVPNTool, mocker: MockerFixture
    ) -> None:
        """Stopping with a process should stop it and clear state."""
        tool._process = MagicMock(returncode=None)
        tool._current_config = "vpn.ovpn"
        mocker.patch(
            "ocom.core.tools.openvpn.ProcessManager.stop_process",
            new=AsyncMock(return_value=True),
        )
        result = await tool.stop()
        assert result is True
        assert tool.status == ToolStatus.STOPPED
        assert tool._process is None
        assert tool.current_config is None


class TestRefreshStatus:
    """Test OpenVPNTool.refresh_status()."""

    async def test_unavailable_rechecks(
        self, tool: OpenVPNTool, mocker: MockerFixture
    ) -> None:
        """UNAVAILABLE should re-run availability detection."""
        tool._status = ToolStatus.UNAVAILABLE
        mocker.patch(
            "ocom.core.tools.openvpn.ProcessManager.find_command", return_value=None
        )
        assert await tool.refresh_status() == ToolStatus.UNAVAILABLE

    async def test_process_running(
        self, tool: OpenVPNTool, mocker: MockerFixture
    ) -> None:
        """A live process should be reported RUNNING."""
        tool._status = ToolStatus.RUNNING
        tool._process = MagicMock(returncode=None)
        mocker.patch(
            "ocom.core.tools.openvpn.ProcessManager.is_process_running",
            return_value=True,
        )
        assert await tool.refresh_status() == ToolStatus.RUNNING

    @pytest.mark.parametrize("status", [ToolStatus.STARTING, ToolStatus.STOPPING])
    async def test_transitioning_left_alone(
        self, tool: OpenVPNTool, mocker: MockerFixture, status: ToolStatus
    ) -> None:
        """A refresh mid-transition must not override start()/stop()'s status."""
        tool._status = status
        tool._process = MagicMock(returncode=None)
        running = mocker.patch(
            "ocom.core.tools.openvpn.ProcessManager.is_process_running",
            return_value=True,
        )
        assert await tool.refresh_status() == status
        running.assert_not_called()

    async def test_process_died(self, tool: OpenVPNTool, mocker: MockerFixture) -> None:
        """A dead process should reset to STOPPED and clear state."""
        tool._status = ToolStatus.RUNNING
        tool._process = MagicMock(returncode=1)
        tool._current_config = "vpn.ovpn"
        mocker.patch(
            "ocom.core.tools.openvpn.ProcessManager.is_process_running",
            return_value=False,
        )
        assert await tool.refresh_status() == ToolStatus.STOPPED
        assert tool._process is None
        assert tool.current_config is None

    async def test_no_process(self, tool: OpenVPNTool) -> None:
        """With no process the current status is returned unchanged."""
        tool._status = ToolStatus.STOPPED
        assert await tool.refresh_status() == ToolStatus.STOPPED


class TestGetConfigFiles:
    """Test OpenVPNTool.get_config_files()."""

    def test_finds_matching_files(self, tool: OpenVPNTool, tmp_path: Path) -> None:
        """Only .ovpn/.conf files should be returned, sorted, others skipped."""
        (tmp_path / "a.ovpn").write_text("")
        (tmp_path / "b.conf").write_text("")
        (tmp_path / "c.txt").write_text("")
        config = ToolConfig(config_dirs=[str(tmp_path), "/no/such/dir"])
        files = tool.get_config_files(config)
        assert files == sorted([str(tmp_path / "a.ovpn"), str(tmp_path / "b.conf")])


class TestHandleOutput:
    """Test OpenVPNTool._handle_output()."""

    def test_tracks_markers_and_emits(
        self,
        tool: OpenVPNTool,
        output_collector: tuple[list[tuple[str, str]], Callable[[str, str], None]],
    ) -> None:
        """Progress markers are recorded and every line is forwarded."""
        messages, callback = output_collector
        tool.set_output_callback(callback)
        tool._handle_output("plain line")
        assert (tool._initialized, tool._auth_failed) == (False, False)
        tool._handle_output("SENT CONTROL: AUTH_FAILED")
        assert tool._auth_failed is True
        tool._handle_output(f"Tue Sep 29 {INIT_COMPLETE}")
        assert tool._initialized is True
        assert [msg for _, msg in messages] == [
            "plain line",
            "SENT CONTROL: AUTH_FAILED",
            f"Tue Sep 29 {INIT_COMPLETE}",
        ]
