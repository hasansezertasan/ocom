"""Tests for the Textual widgets: ToolCard and LogPanel."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
from textual.app import App
from textual.widgets import Button, RichLog

from ocom.core.tool import BaseTool, ToolConfig, ToolStatus
from ocom.tui.widgets.log_panel import LogPanel
from ocom.tui.widgets.tool_card import ToolCard

if TYPE_CHECKING:
    from pathlib import Path

    from textual.app import ComposeResult


@pytest.fixture(autouse=True)
def _no_user_config(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """Prevent tests from reading a real user config file."""
    monkeypatch.setattr(
        "ocom.core.config.get_config_path", lambda: tmp_path / "missing.toml"
    )


class FakeTool(BaseTool):
    """A minimal concrete tool used to drive widget behavior."""

    def __init__(self, name: str = "FakeTool") -> None:
        super().__init__()
        self.name = name
        self._status = ToolStatus.STOPPED

    async def start(self, config: ToolConfig) -> bool:
        _ = config
        self._status = ToolStatus.RUNNING
        return True

    async def stop(self) -> bool:
        self._status = ToolStatus.STOPPED
        return True

    async def refresh_status(self) -> ToolStatus:
        return self._status


class ToolCardHostApp(App[None]):
    """Host app that mounts a single ToolCard and records its actions."""

    def __init__(self, card: ToolCard) -> None:
        super().__init__()
        self._card = card
        self.actions: list[tuple[str, str]] = []

    def compose(self) -> ComposeResult:
        yield self._card

    def on_tool_card_tool_action(self, event: ToolCard.ToolAction) -> None:
        self.actions.append((event.tool.name, event.action))


class LogPanelHostApp(App[None]):
    """Host app that mounts a single LogPanel."""

    def compose(self) -> ComposeResult:
        yield LogPanel(id="log-panel")


class TestToolCardWatchGuard:
    """watch_status must not touch the DOM before the card is mounted."""

    def test_refresh_status_before_mount_is_noop(self) -> None:
        """Setting status before mount stores it without updating display."""
        card = ToolCard(FakeTool("Guard"))
        card.refresh_status(ToolStatus.RUNNING)
        assert card.status == ToolStatus.RUNNING
        assert card.is_mounted is False


class TestToolCardDisplay:
    """The card display reacts to every status transition."""

    async def test_initial_stopped_shows_start(self) -> None:
        """A stopped tool shows an enabled Start button."""
        card = ToolCard(FakeTool("Alpha"), id="card-alpha")
        app = ToolCardHostApp(card)
        async with app.run_test() as pilot:
            await pilot.pause()
            btn = card.query_one("#toggle-btn", Button)
            assert str(btn.label) == "Start"
            assert btn.disabled is False
            assert card.has_class("stopped")

    async def test_running_shows_stop(self) -> None:
        """A running tool shows a Stop button and running class."""
        card = ToolCard(FakeTool("Beta"), id="card-beta")
        app = ToolCardHostApp(card)
        async with app.run_test() as pilot:
            card.refresh_status(ToolStatus.RUNNING)
            await pilot.pause()
            btn = card.query_one("#toggle-btn", Button)
            assert str(btn.label) == "Stop"
            assert card.has_class("running")

    async def test_unavailable_shows_install(self) -> None:
        """An unavailable tool shows an Install button."""
        card = ToolCard(FakeTool("Gamma"), id="card-gamma")
        app = ToolCardHostApp(card)
        async with app.run_test() as pilot:
            card.refresh_status(ToolStatus.UNAVAILABLE)
            await pilot.pause()
            btn = card.query_one("#toggle-btn", Button)
            assert str(btn.label) == "Install"
            assert card.has_class("unavailable")

    async def test_error_shows_start(self) -> None:
        """An errored tool can be started again."""
        card = ToolCard(FakeTool("Delta"), id="card-delta")
        app = ToolCardHostApp(card)
        async with app.run_test() as pilot:
            card.refresh_status(ToolStatus.ERROR)
            await pilot.pause()
            btn = card.query_one("#toggle-btn", Button)
            assert str(btn.label) == "Start"
            assert card.has_class("error")

    @pytest.mark.parametrize("status", [ToolStatus.STARTING, ToolStatus.STOPPING])
    async def test_transitioning_disables_button(self, status: ToolStatus) -> None:
        """Transitional states disable the toggle button."""
        card = ToolCard(FakeTool("Epsilon"), id="card-epsilon")
        app = ToolCardHostApp(card)
        async with app.run_test() as pilot:
            card.refresh_status(status)
            await pilot.pause()
            btn = card.query_one("#toggle-btn", Button)
            assert btn.disabled is True
            assert str(btn.label) == "..."


class TestToolCardButton:
    """Pressing the toggle button emits the right ToolAction."""

    async def test_press_start(self) -> None:
        """A stopped tool posts a start action."""
        card = ToolCard(FakeTool("StartMe"), id="card-startme")
        app = ToolCardHostApp(card)
        async with app.run_test() as pilot:
            await pilot.pause()
            await pilot.click("#toggle-btn")
            await pilot.pause()
            assert ("StartMe", "start") in app.actions

    async def test_press_stop(self) -> None:
        """A running tool posts a stop action."""
        card = ToolCard(FakeTool("StopMe"), id="card-stopme")
        app = ToolCardHostApp(card)
        async with app.run_test() as pilot:
            card.refresh_status(ToolStatus.RUNNING)
            await pilot.pause()
            await pilot.click("#toggle-btn")
            await pilot.pause()
            assert ("StopMe", "stop") in app.actions

    async def test_press_install(self) -> None:
        """An unavailable tool posts an install action."""
        card = ToolCard(FakeTool("InstallMe"), id="card-installme")
        app = ToolCardHostApp(card)
        async with app.run_test() as pilot:
            card.refresh_status(ToolStatus.UNAVAILABLE)
            await pilot.pause()
            await pilot.click("#toggle-btn")
            await pilot.pause()
            assert ("InstallMe", "install") in app.actions

    async def test_press_while_transitioning_posts_nothing(self) -> None:
        """A transitional state ignores toggle presses."""
        card = ToolCard(FakeTool("Busy"), id="card-busy")
        app = ToolCardHostApp(card)
        async with app.run_test() as pilot:
            card.refresh_status(ToolStatus.STARTING)
            await pilot.pause()
            btn = card.query_one("#toggle-btn", Button)
            card.on_button_pressed(Button.Pressed(btn))
            await pilot.pause()
            assert app.actions == []

    async def test_non_toggle_button_is_ignored(self) -> None:
        """A press from a foreign button is ignored."""
        card = ToolCard(FakeTool("Other"), id="card-other")
        app = ToolCardHostApp(card)
        async with app.run_test() as pilot:
            await pilot.pause()
            other = Button("x", id="other-btn")
            card.on_button_pressed(Button.Pressed(other))
            await pilot.pause()
            assert app.actions == []


class TestLogPanel:
    """LogPanel writes and clears entries."""

    async def test_add_and_clear(self) -> None:
        """Logs from known and unknown sources render, then clear empties them."""
        app = LogPanelHostApp()
        async with app.run_test() as pilot:
            panel = app.query_one("#log-panel", LogPanel)
            panel.add_log("OpenVPN", "known source colour")
            panel.add_log("Mystery", "unknown source colour")
            panel.log_system("system message")
            await pilot.pause()
            rich_log = panel.query_one("#log-output", RichLog)
            assert len(rich_log.lines) >= 3
            panel.clear()
            await pilot.pause()
            assert len(rich_log.lines) == 0
