"""Tests for TailscaleTool."""

import json
from typing import TYPE_CHECKING
from unittest.mock import AsyncMock

import pytest

from ocom.core.process import ProcessResult
from ocom.core.tool import ToolConfig, ToolStatus
from ocom.core.tools.tailscale import TailscaleTool

if TYPE_CHECKING:
    from pytest_mock import MockerFixture


@pytest.fixture
def tool() -> TailscaleTool:
    """Create a TailscaleTool instance."""
    return TailscaleTool()


def _result(returncode: int = 0, stdout: str = "", stderr: str = "") -> ProcessResult:
    """Build a ProcessResult for mocking run_command."""
    return ProcessResult(returncode=returncode, stdout=stdout, stderr=stderr)


class TestConstruction:
    """Test TailscaleTool attributes."""

    def test_attributes(self, tool: TailscaleTool) -> None:
        """Class attributes should match the documented tool contract."""
        assert tool.name == "Tailscale"
        assert tool.command == "tailscale"
        assert tool.requires_sudo is False
        assert tool.conflicts_with == []


class TestCheckAvailable:
    """Test TailscaleTool.check_available()."""

    async def test_command_missing(
        self, tool: TailscaleTool, mocker: MockerFixture
    ) -> None:
        """A missing CLI short-circuits to unavailable."""
        mocker.patch(
            "ocom.core.tools.tailscale.ProcessManager.find_command", return_value=None
        )
        assert await tool.check_available() is False
        assert tool.status == ToolStatus.UNAVAILABLE

    async def test_available_reconciles(
        self, tool: TailscaleTool, mocker: MockerFixture
    ) -> None:
        """An available CLI reconciles with the daemon state."""
        mocker.patch(
            "ocom.core.tools.tailscale.ProcessManager.find_command",
            return_value="/usr/bin/tailscale",
        )
        mocker.patch(
            "ocom.core.tools.tailscale.ProcessManager.run_command",
            new=AsyncMock(
                return_value=_result(stdout=json.dumps({"BackendState": "Running"}))
            ),
        )
        assert await tool.check_available() is True
        assert tool.status == ToolStatus.RUNNING


class TestStart:
    """Test TailscaleTool.start()."""

    async def test_start_success(
        self, tool: TailscaleTool, mocker: MockerFixture
    ) -> None:
        """A successful up sets RUNNING."""
        mocker.patch(
            "ocom.core.tools.tailscale.ProcessManager.run_command",
            new=AsyncMock(return_value=_result(stdout="ok")),
        )
        assert await tool.start(ToolConfig()) is True
        assert tool.status == ToolStatus.RUNNING

    async def test_start_failure(
        self, tool: TailscaleTool, mocker: MockerFixture
    ) -> None:
        """A failing up sets ERROR with stderr message."""
        mocker.patch(
            "ocom.core.tools.tailscale.ProcessManager.run_command",
            new=AsyncMock(return_value=_result(returncode=1, stderr="login url")),
        )
        assert await tool.start(ToolConfig()) is False
        assert tool.status == ToolStatus.ERROR
        assert tool.error_message == "login url"

    async def test_start_failure_default_message(
        self, tool: TailscaleTool, mocker: MockerFixture
    ) -> None:
        """A failing up with no output uses a default message."""
        mocker.patch(
            "ocom.core.tools.tailscale.ProcessManager.run_command",
            new=AsyncMock(return_value=_result(returncode=1)),
        )
        assert await tool.start(ToolConfig()) is False
        assert tool.error_message == "Failed to bring Tailscale up"


class TestStop:
    """Test TailscaleTool.stop()."""

    async def test_stop_success(
        self, tool: TailscaleTool, mocker: MockerFixture
    ) -> None:
        """A successful down sets STOPPED."""
        mocker.patch(
            "ocom.core.tools.tailscale.ProcessManager.run_command",
            new=AsyncMock(return_value=_result(stdout="ok")),
        )
        assert await tool.stop() is True
        assert tool.status == ToolStatus.STOPPED

    async def test_stop_failure(
        self, tool: TailscaleTool, mocker: MockerFixture
    ) -> None:
        """A failing down sets ERROR with the message."""
        mocker.patch(
            "ocom.core.tools.tailscale.ProcessManager.run_command",
            new=AsyncMock(return_value=_result(returncode=1, stdout="cannot")),
        )
        assert await tool.stop() is False
        assert tool.status == ToolStatus.ERROR
        assert tool.error_message == "cannot"

    async def test_stop_failure_default_message(
        self, tool: TailscaleTool, mocker: MockerFixture
    ) -> None:
        """A failing down with no output uses a default message."""
        mocker.patch(
            "ocom.core.tools.tailscale.ProcessManager.run_command",
            new=AsyncMock(return_value=_result(returncode=1)),
        )
        assert await tool.stop() is False
        assert tool.error_message == "Failed to bring Tailscale down"


class TestRefreshStatus:
    """Test TailscaleTool.refresh_status() and state mapping."""

    async def test_unavailable_and_missing_command(
        self, tool: TailscaleTool, mocker: MockerFixture
    ) -> None:
        """UNAVAILABLE with no CLI short-circuits without running commands."""
        tool._status = ToolStatus.UNAVAILABLE
        mocker.patch(
            "ocom.core.tools.tailscale.ProcessManager.find_command", return_value=None
        )
        run = mocker.patch("ocom.core.tools.tailscale.ProcessManager.run_command")
        assert await tool.refresh_status() == ToolStatus.UNAVAILABLE
        run.assert_not_called()

    async def test_command_failure_with_stderr(
        self, tool: TailscaleTool, mocker: MockerFixture
    ) -> None:
        """A failed status query records the stderr message as ERROR."""
        tool._status = ToolStatus.RUNNING
        mocker.patch(
            "ocom.core.tools.tailscale.ProcessManager.run_command",
            new=AsyncMock(return_value=_result(returncode=1, stderr="  boom  ")),
        )
        assert await tool.refresh_status() == ToolStatus.ERROR
        assert tool.error_message == "boom"

    async def test_command_failure_without_stderr(
        self, tool: TailscaleTool, mocker: MockerFixture
    ) -> None:
        """A failed status query with no stderr uses a default message."""
        tool._status = ToolStatus.RUNNING
        mocker.patch(
            "ocom.core.tools.tailscale.ProcessManager.run_command",
            new=AsyncMock(return_value=_result(returncode=1)),
        )
        assert await tool.refresh_status() == ToolStatus.ERROR
        assert tool.error_message == "tailscaled not reachable"

    async def test_invalid_json_raises(
        self, tool: TailscaleTool, mocker: MockerFixture
    ) -> None:
        """Malformed JSON is caught and reported as ERROR."""
        tool._status = ToolStatus.RUNNING
        mocker.patch(
            "ocom.core.tools.tailscale.ProcessManager.run_command",
            new=AsyncMock(return_value=_result(stdout="not json")),
        )
        assert await tool.refresh_status() == ToolStatus.ERROR
        assert tool.error_message is not None

    @pytest.mark.parametrize(
        ("state", "expected"),
        [
            ("Running", ToolStatus.RUNNING),
            ("Starting", ToolStatus.STARTING),
            ("Stopped", ToolStatus.STOPPED),
            ("NoState", ToolStatus.STOPPED),
            ("NeedsLogin", ToolStatus.ERROR),
            ("NeedsMachineAuth", ToolStatus.ERROR),
            ("Weird", ToolStatus.ERROR),
        ],
    )
    async def test_backend_states(
        self,
        tool: TailscaleTool,
        mocker: MockerFixture,
        state: str,
        expected: ToolStatus,
    ) -> None:
        """Each BackendState maps to the expected ToolStatus."""
        tool._status = ToolStatus.STOPPED
        mocker.patch(
            "ocom.core.tools.tailscale.ProcessManager.run_command",
            new=AsyncMock(
                return_value=_result(stdout=json.dumps({"BackendState": state}))
            ),
        )
        assert await tool.refresh_status() == expected

    async def test_running_clears_error(
        self, tool: TailscaleTool, mocker: MockerFixture
    ) -> None:
        """A healthy Running state clears any prior error message."""
        tool._status = ToolStatus.ERROR
        tool._error_message = "old error"
        mocker.patch(
            "ocom.core.tools.tailscale.ProcessManager.run_command",
            new=AsyncMock(
                return_value=_result(stdout=json.dumps({"BackendState": "Running"}))
            ),
        )
        assert await tool.refresh_status() == ToolStatus.RUNNING
        assert tool.error_message is None

    def test_map_needs_login_message(self, tool: TailscaleTool) -> None:
        """NeedsLogin records an authentication prompt message."""
        assert tool._map_backend_state("NeedsLogin") == ToolStatus.ERROR
        assert tool.error_message is not None
        assert "authentication" in tool.error_message

    def test_map_unknown_message(self, tool: TailscaleTool) -> None:
        """An unknown state records its name in the error message."""
        assert tool._map_backend_state("Bogus") == ToolStatus.ERROR
        assert tool.error_message == "Unknown Tailscale state: Bogus"
