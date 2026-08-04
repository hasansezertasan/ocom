"""Tests for WarpTool."""

from typing import TYPE_CHECKING
from unittest.mock import AsyncMock

import pytest

from ocom.core.process import ProcessResult
from ocom.core.tool import ToolConfig, ToolStatus
from ocom.tools.warp import WarpTool

if TYPE_CHECKING:
    from pytest_mock import MockerFixture


@pytest.fixture
def tool() -> WarpTool:
    """Create a WarpTool instance."""
    return WarpTool()


def _result(returncode: int = 0, stdout: str = "", stderr: str = "") -> ProcessResult:
    """Build a ProcessResult for mocking run_command."""
    return ProcessResult(returncode=returncode, stdout=stdout, stderr=stderr)


class TestConstruction:
    """Test WarpTool attributes."""

    def test_attributes(self, tool: WarpTool) -> None:
        """Class attributes should match the documented tool contract."""
        assert tool.name == "WARP"
        assert tool.command == "warp-cli"
        assert tool.requires_sudo is False
        assert tool.conflicts_with == ["OpenVPN"]


class TestCheckAvailable:
    """Test WarpTool.check_available()."""

    async def test_command_missing(self, tool: WarpTool, mocker: MockerFixture) -> None:
        """A missing CLI should short-circuit to unavailable."""
        mocker.patch("ocom.tools.warp.ProcessManager.find_command", return_value=None)
        assert await tool.check_available() is False
        assert tool.status == ToolStatus.UNAVAILABLE

    async def test_available_daemon_running(
        self, tool: WarpTool, mocker: MockerFixture
    ) -> None:
        """An available CLI with a running daemon reflects that status."""
        mocker.patch(
            "ocom.tools.warp.ProcessManager.find_command",
            return_value="/usr/bin/warp-cli",
        )
        mocker.patch(
            "ocom.tools.warp.ProcessManager.run_command",
            new=AsyncMock(return_value=_result(stdout="Status: Connected")),
        )
        assert await tool.check_available() is True
        assert tool.status == ToolStatus.RUNNING

    async def test_available_daemon_unavailable_normalized(
        self, tool: WarpTool, mocker: MockerFixture
    ) -> None:
        """A daemon status left UNAVAILABLE is normalized to STOPPED."""
        mocker.patch(
            "ocom.tools.warp.ProcessManager.find_command",
            return_value="/usr/bin/warp-cli",
        )

        async def leave_unavailable() -> ToolStatus:
            tool._status = ToolStatus.UNAVAILABLE
            return tool._status

        mocker.patch.object(tool, "refresh_status", side_effect=leave_unavailable)
        result = await tool.check_available()
        assert result is True
        assert tool.status == ToolStatus.STOPPED


class TestStart:
    """Test WarpTool.start()."""

    async def test_start_success(self, tool: WarpTool, mocker: MockerFixture) -> None:
        """Successful connect sets RUNNING and sends the mode command."""
        run = mocker.patch(
            "ocom.tools.warp.ProcessManager.run_command",
            new=AsyncMock(return_value=_result(stdout="ok")),
        )
        result = await tool.start(ToolConfig(options={"mode": "doh"}))
        assert result is True
        assert tool.status == ToolStatus.RUNNING
        # mode + connect
        assert run.await_count == 2

    async def test_start_failure(self, tool: WarpTool, mocker: MockerFixture) -> None:
        """A failing connect sets ERROR with the stderr message."""
        mocker.patch(
            "ocom.tools.warp.ProcessManager.run_command",
            new=AsyncMock(return_value=_result(returncode=1, stderr="nope")),
        )
        result = await tool.start(ToolConfig())
        assert result is False
        assert tool.status == ToolStatus.ERROR
        assert tool.error_message == "nope"

    async def test_start_failure_default_message(
        self, tool: WarpTool, mocker: MockerFixture
    ) -> None:
        """With no stderr/stdout a default failure message is used."""
        mocker.patch(
            "ocom.tools.warp.ProcessManager.run_command",
            new=AsyncMock(return_value=_result(returncode=1)),
        )
        result = await tool.start(ToolConfig(options={"mode": ""}))
        assert result is False
        assert tool.error_message == "Failed to connect"


class TestStop:
    """Test WarpTool.stop()."""

    async def test_stop_success(self, tool: WarpTool, mocker: MockerFixture) -> None:
        """A successful disconnect sets STOPPED."""
        mocker.patch(
            "ocom.tools.warp.ProcessManager.run_command",
            new=AsyncMock(return_value=_result(stdout="ok")),
        )
        result = await tool.stop()
        assert result is True
        assert tool.status == ToolStatus.STOPPED

    async def test_stop_failure(self, tool: WarpTool, mocker: MockerFixture) -> None:
        """A failing disconnect sets ERROR with the message."""
        mocker.patch(
            "ocom.tools.warp.ProcessManager.run_command",
            new=AsyncMock(return_value=_result(returncode=1, stdout="cannot")),
        )
        result = await tool.stop()
        assert result is False
        assert tool.status == ToolStatus.ERROR
        assert tool.error_message == "cannot"

    async def test_stop_failure_default_message(
        self, tool: WarpTool, mocker: MockerFixture
    ) -> None:
        """With no output a default disconnect message is used."""
        mocker.patch(
            "ocom.tools.warp.ProcessManager.run_command",
            new=AsyncMock(return_value=_result(returncode=1)),
        )
        result = await tool.stop()
        assert result is False
        assert tool.error_message == "Failed to disconnect"


class TestRefreshStatus:
    """Test WarpTool.refresh_status() and status parsing."""

    async def test_unavailable_and_missing_command(
        self, tool: WarpTool, mocker: MockerFixture
    ) -> None:
        """UNAVAILABLE with no CLI short-circuits without running commands."""
        tool._status = ToolStatus.UNAVAILABLE
        mocker.patch("ocom.tools.warp.ProcessManager.find_command", return_value=None)
        run = mocker.patch("ocom.tools.warp.ProcessManager.run_command")
        assert await tool.refresh_status() == ToolStatus.UNAVAILABLE
        run.assert_not_called()

    async def test_run_command_raises(
        self, tool: WarpTool, mocker: MockerFixture
    ) -> None:
        """A raising status command yields ERROR."""
        tool._status = ToolStatus.RUNNING
        mocker.patch(
            "ocom.tools.warp.ProcessManager.run_command",
            new=AsyncMock(side_effect=RuntimeError("crash")),
        )
        assert await tool.refresh_status() == ToolStatus.ERROR
        assert tool.error_message == "crash"

    @pytest.mark.parametrize(
        ("stdout", "expected"),
        [
            ("Disconnected", ToolStatus.STOPPED),
            ("Connecting", ToolStatus.STARTING),
            ("Connected", ToolStatus.RUNNING),
            ("Something else", ToolStatus.STOPPED),
        ],
    )
    async def test_status_from_output(
        self, tool: WarpTool, mocker: MockerFixture, stdout: str, expected: ToolStatus
    ) -> None:
        """Status text is mapped to the right ToolStatus."""
        tool._status = ToolStatus.STOPPED
        mocker.patch(
            "ocom.tools.warp.ProcessManager.run_command",
            new=AsyncMock(return_value=_result(stdout=stdout)),
        )
        assert await tool.refresh_status() == expected

    async def test_status_failure_daemon_down(
        self, tool: WarpTool, mocker: MockerFixture
    ) -> None:
        """An unreachable daemon maps to ERROR."""
        tool._status = ToolStatus.STOPPED
        mocker.patch(
            "ocom.tools.warp.ProcessManager.run_command",
            new=AsyncMock(
                return_value=_result(returncode=1, stderr="Unable to connect")
            ),
        )
        assert await tool.refresh_status() == ToolStatus.ERROR
        assert tool.error_message == "WARP daemon not running"

    async def test_status_failure_other(
        self, tool: WarpTool, mocker: MockerFixture
    ) -> None:
        """A generic failure maps to STOPPED."""
        tool._status = ToolStatus.RUNNING
        mocker.patch(
            "ocom.tools.warp.ProcessManager.run_command",
            new=AsyncMock(return_value=_result(returncode=1, stderr="other error")),
        )
        assert await tool.refresh_status() == ToolStatus.STOPPED
