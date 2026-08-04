"""Tests for OpenVPNTool."""

from pathlib import Path
from typing import TYPE_CHECKING
from unittest.mock import AsyncMock, MagicMock

import pytest

from ocom.core.tool import ToolConfig, ToolStatus
from ocom.tools.openvpn import OpenVPNTool

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
        assert tool._output_lines == []


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
        monkeypatch.setattr("ocom.tools.openvpn.IS_WINDOWS", True)
        config = ToolConfig(extra_args=["--verb", "3"])
        args, sudo_pw = OpenVPNTool._build_command(config, Path("my.ovpn"))
        assert args[:3] == ["openvpn", "--config", "my.ovpn"]
        assert args[-2:] == ["--verb", "3"]
        assert sudo_pw is None

    def test_unix_command_with_password(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """On Unix a provided sudo password is threaded through."""
        monkeypatch.setattr("ocom.tools.openvpn.IS_WINDOWS", False)
        config = ToolConfig(options={"sudo_password": "secret"})
        args, sudo_pw = OpenVPNTool._build_command(config, Path("my.ovpn"))
        assert args[:4] == ["sudo", "-S", "openvpn", "--config"]
        assert sudo_pw == "secret"

    def test_unix_command_without_password(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """On Unix a missing sudo password yields None."""
        monkeypatch.setattr("ocom.tools.openvpn.IS_WINDOWS", False)
        args, sudo_pw = OpenVPNTool._build_command(ToolConfig(), Path("my.ovpn"))
        assert args[0] == "sudo"
        assert sudo_pw is None


class TestStart:
    """Test OpenVPNTool.start() process handling."""

    async def test_start_process_raises(
        self, tool: OpenVPNTool, tmp_path: Path, mocker: MockerFixture
    ) -> None:
        """A raising start_process should be caught and reported as ERROR."""
        config_file = tmp_path / "vpn.ovpn"
        config_file.write_text("dummy")
        mocker.patch(
            "ocom.tools.openvpn.ProcessManager.start_process",
            new=AsyncMock(side_effect=RuntimeError("boom")),
        )
        result = await tool.start(ToolConfig(config_file=str(config_file)))
        assert result is False
        assert tool.status == ToolStatus.ERROR
        assert tool.error_message == "boom"

    async def test_start_success(
        self, tool: OpenVPNTool, tmp_path: Path, mocker: MockerFixture
    ) -> None:
        """A running process with clean output should reach RUNNING."""
        config_file = tmp_path / "vpn.ovpn"
        config_file.write_text("dummy")
        mocker.patch(
            "ocom.tools.openvpn.ProcessManager.start_process",
            new=AsyncMock(return_value=MagicMock(returncode=None)),
        )
        mocker.patch(
            "ocom.tools.openvpn.ProcessManager.is_process_running", return_value=True
        )
        mocker.patch("ocom.tools.openvpn.asyncio.sleep", new=AsyncMock())
        result = await tool.start(ToolConfig(config_file=str(config_file)))
        assert result is True
        assert tool.status == ToolStatus.RUNNING
        assert tool.current_config == "vpn.ovpn"


class TestEvaluateStart:
    """Test OpenVPNTool._evaluate_start() branches."""

    async def test_process_exited(
        self, tool: OpenVPNTool, mocker: MockerFixture
    ) -> None:
        """A dead process should be reported as ERROR."""
        tool._process = MagicMock(returncode=1)
        mocker.patch(
            "ocom.tools.openvpn.ProcessManager.is_process_running", return_value=False
        )
        result = await tool._evaluate_start()
        assert result is False
        assert tool.status == ToolStatus.ERROR
        assert tool.error_message == "Process exited unexpectedly"

    async def test_auth_failed(self, tool: OpenVPNTool, mocker: MockerFixture) -> None:
        """AUTH_FAILED without initialization should ERROR and stop."""
        tool._process = MagicMock(returncode=None)
        tool._output_lines = ["some log", "AUTH_FAILED"]
        mocker.patch(
            "ocom.tools.openvpn.ProcessManager.is_process_running", return_value=True
        )
        stop = mocker.patch(
            "ocom.tools.openvpn.ProcessManager.stop_process",
            new=AsyncMock(return_value=True),
        )
        result = await tool._evaluate_start()
        assert result is False
        assert tool.status == ToolStatus.ERROR  # ERROR preserved, not reset
        assert tool.error_message == "Authentication failed"
        assert tool._process is None  # process torn down
        stop.assert_awaited_once()

    async def test_init_completed_wins_over_auth_failed(
        self, tool: OpenVPNTool, mocker: MockerFixture
    ) -> None:
        """A completed init overrides an AUTH_FAILED line."""
        tool._process = MagicMock(returncode=None)
        tool._output_lines = ["Initialization Sequence Completed", "AUTH_FAILED"]
        mocker.patch(
            "ocom.tools.openvpn.ProcessManager.is_process_running", return_value=True
        )
        result = await tool._evaluate_start()
        assert result is True
        assert tool.status == ToolStatus.RUNNING

    async def test_still_connecting(
        self, tool: OpenVPNTool, mocker: MockerFixture
    ) -> None:
        """No completion and no auth failure should assume success."""
        tool._process = MagicMock(returncode=None)
        tool._output_lines = ["connecting..."]
        mocker.patch(
            "ocom.tools.openvpn.ProcessManager.is_process_running", return_value=True
        )
        result = await tool._evaluate_start()
        assert result is True
        assert tool.status == ToolStatus.RUNNING


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
            "ocom.tools.openvpn.ProcessManager.stop_process",
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
            "ocom.tools.openvpn.ProcessManager.find_command", return_value=None
        )
        assert await tool.refresh_status() == ToolStatus.UNAVAILABLE

    async def test_process_running(
        self, tool: OpenVPNTool, mocker: MockerFixture
    ) -> None:
        """A live process should be reported RUNNING."""
        tool._status = ToolStatus.RUNNING
        tool._process = MagicMock(returncode=None)
        mocker.patch(
            "ocom.tools.openvpn.ProcessManager.is_process_running", return_value=True
        )
        assert await tool.refresh_status() == ToolStatus.RUNNING

    async def test_process_died(self, tool: OpenVPNTool, mocker: MockerFixture) -> None:
        """A dead process should reset to STOPPED and clear state."""
        tool._status = ToolStatus.RUNNING
        tool._process = MagicMock(returncode=1)
        tool._current_config = "vpn.ovpn"
        mocker.patch(
            "ocom.tools.openvpn.ProcessManager.is_process_running", return_value=False
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

    def test_buffer_capped_and_emitted(
        self,
        tool: OpenVPNTool,
        output_collector: tuple[list[tuple[str, str]], Callable[[str, str], None]],
    ) -> None:
        """Output buffer keeps the last 100 lines and emits each line."""
        messages, callback = output_collector
        tool.set_output_callback(callback)
        for i in range(150):
            tool._handle_output(f"line {i}")
        assert len(tool._output_lines) == 100
        assert tool._output_lines[0] == "line 50"
        assert tool._output_lines[-1] == "line 149"
        assert len(messages) == 150
