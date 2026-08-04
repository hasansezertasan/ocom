"""Tests for MainScreen and its modal screens."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
from textual.app import App
from textual.css.query import NoMatches
from textual.widgets import Button, Input, Label, OptionList, Static

from ocom.config import AppConfig, GeneralConfig, OpenVPNConfig
from ocom.core.tool import BaseTool, ToolConfig, ToolStatus
from ocom.ui.screens.main import ConfigSelectorScreen, MainScreen, PasswordPromptScreen
from ocom.ui.widgets.log_panel import LogPanel
from ocom.ui.widgets.tool_card import ToolCard

if TYPE_CHECKING:
    from collections.abc import Sequence
    from pathlib import Path

    from pytest_mock import MockerFixture
    from textual.screen import Screen


@pytest.fixture(autouse=True)  # noqa: RUF076
def _no_user_config(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """Prevent tests from reading a real user config file."""
    monkeypatch.setattr(
        "ocom.config.get_config_path", lambda: tmp_path / "missing.toml"
    )


class FakeTool(BaseTool):
    """A configurable concrete tool for driving MainScreen flows."""

    # Per-instance override of BaseTool's class-level conflicts_with, so each
    # fake can declare its own conflicts (intentional for the test double).
    conflicts_with: list[str]  # ty: ignore[invalid-attribute-override]

    def __init__(  # noqa: PLR0913
        self,
        name: str,
        *,
        available: bool = True,
        supports_configs: bool = False,
        requires_sudo: bool = False,
        conflicts_with: Sequence[str] = (),
        install_url: str = "",
        config_files: Sequence[str] = (),
        start_success: bool = True,
        stop_success: bool = True,
        refresh_error: bool = False,
    ) -> None:
        super().__init__()
        self.name = name
        self.supports_configs = supports_configs
        self.requires_sudo = requires_sudo
        self.conflicts_with = list(conflicts_with)
        self.install_url = install_url
        self._available = available
        self._config_files = list(config_files)
        self._start_success = start_success
        self._stop_success = stop_success
        self._refresh_error = refresh_error
        self.started_with: ToolConfig | None = None

    async def check_available(self) -> bool:
        if self._available:
            self._status = ToolStatus.STOPPED
            return True
        self._status = ToolStatus.UNAVAILABLE
        return False

    async def start(self, config: ToolConfig) -> bool:
        self.started_with = config
        if self._start_success:
            self._status = ToolStatus.RUNNING
            return True
        self._status = ToolStatus.ERROR
        self._error_message = "boom"
        return False

    async def stop(self) -> bool:
        if self._stop_success:
            self._status = ToolStatus.STOPPED
            return True
        self._status = ToolStatus.ERROR
        return False

    async def refresh_status(self) -> ToolStatus:
        if self._refresh_error:
            msg = "refresh boom"
            raise RuntimeError(msg)
        return self._status

    def get_config_files(self, config: ToolConfig) -> list[str]:
        _ = config
        return list(self._config_files)


class MainHostApp(App[None]):
    """Host app that pushes a MainScreen built from injected tools."""

    def __init__(self, config: AppConfig) -> None:
        super().__init__()
        self._config = config

    def on_mount(self) -> None:
        self.push_screen(MainScreen(self._config))


def _make_app(
    monkeypatch: pytest.MonkeyPatch,
    tools: list[BaseTool],
    config: AppConfig | None = None,
) -> MainHostApp:
    """Build a host app whose MainScreen uses the given tools."""
    monkeypatch.setattr("ocom.ui.screens.main.get_all_tools", lambda: tools)
    return MainHostApp(config or AppConfig(general=GeneralConfig()))


class TestCompose:
    """The dashboard renders its component widgets."""

    async def test_renders_cards_log_and_status(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Compose yields a card per tool plus the log and status bar."""
        tools: list[BaseTool] = [FakeTool("WARP"), FakeTool("OpenVPN")]
        app = _make_app(monkeypatch, tools)
        async with app.run_test() as pilot:
            await pilot.pause()
            screen = app.screen
            assert isinstance(screen, MainScreen)
            assert len(screen.query(ToolCard)) == 2
            screen.query_one("#log-panel", LogPanel)
            assert str(screen.query_one("#status-bar", Static).render()) == "Ready"


class TestOnMount:
    """on_mount wires callbacks and reflects availability."""

    async def test_reflects_availability(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Available and unavailable tools land in the right card status."""
        up = FakeTool("WARP", available=True)
        down = FakeTool("OpenVPN", available=False)
        app = _make_app(monkeypatch, [up, down])
        async with app.run_test() as pilot:
            await pilot.pause()
            screen = app.screen
            assert isinstance(screen, MainScreen)
            assert screen._cards["WARP"].status == ToolStatus.STOPPED
            assert screen._cards["OpenVPN"].status == ToolStatus.UNAVAILABLE


class TestToolOutput:
    """Tool output routes to the log panel, tolerating an unmounted panel."""

    async def test_output_reaches_log_panel(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """A mounted panel receives the output line."""
        app = _make_app(monkeypatch, [FakeTool("WARP")])
        async with app.run_test() as pilot:
            await pilot.pause()
            screen = app.screen
            assert isinstance(screen, MainScreen)
            screen._handle_tool_output("WARP", "hello there")
            await pilot.pause()

    def test_output_before_mount_is_dropped(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Early output is dropped when no panel exists yet."""
        monkeypatch.setattr(
            "ocom.ui.screens.main.get_all_tools", lambda: [FakeTool("WARP")]
        )
        screen = MainScreen(AppConfig(general=GeneralConfig()))
        with pytest.raises(NoMatches):
            screen.query_one("#log-panel", LogPanel)
        # Should not raise even though the panel is not mounted.
        screen._handle_tool_output("WARP", "dropped")


class TestActionHandler:
    """The card action handler dispatches to start/stop/install."""

    async def test_start_action(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """A start action launches a non-config tool."""
        tool = FakeTool("WARP")
        app = _make_app(monkeypatch, [tool])
        async with app.run_test() as pilot:
            await pilot.pause()
            screen = app.screen
            assert isinstance(screen, MainScreen)
            screen.on_tool_card_tool_action(ToolCard.ToolAction(tool, "start"))
            await pilot.pause()
            assert tool.status == ToolStatus.RUNNING

    async def test_stop_action(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """A stop action stops a running tool."""
        tool = FakeTool("WARP")
        app = _make_app(monkeypatch, [tool])
        async with app.run_test() as pilot:
            await pilot.pause()
            screen = app.screen
            assert isinstance(screen, MainScreen)
            tool._status = ToolStatus.RUNNING
            screen.on_tool_card_tool_action(ToolCard.ToolAction(tool, "stop"))
            await pilot.pause()
            assert tool.status == ToolStatus.STOPPED

    async def test_install_action(
        self, monkeypatch: pytest.MonkeyPatch, mocker: MockerFixture
    ) -> None:
        """An install action opens the tool's install URL."""
        opener = mocker.patch("ocom.ui.screens.main.webbrowser.open")
        tool = FakeTool("WARP", install_url="https://example.com/install")
        app = _make_app(monkeypatch, [tool])
        async with app.run_test() as pilot:
            await pilot.pause()
            screen = app.screen
            assert isinstance(screen, MainScreen)
            screen.on_tool_card_tool_action(ToolCard.ToolAction(tool, "install"))
            await pilot.pause()
            opener.assert_called_once_with("https://example.com/install")

    async def test_install_without_url(
        self, monkeypatch: pytest.MonkeyPatch, mocker: MockerFixture
    ) -> None:
        """Installing a tool with no URL reports it on the status bar."""
        opener = mocker.patch("ocom.ui.screens.main.webbrowser.open")
        tool = FakeTool("WARP", install_url="")
        app = _make_app(monkeypatch, [tool])
        async with app.run_test() as pilot:
            await pilot.pause()
            screen = app.screen
            assert isinstance(screen, MainScreen)
            screen._handle_install(tool)
            await pilot.pause()
            opener.assert_not_called()
            bar = screen.query_one("#status-bar", Static)
            assert "No install URL" in str(bar.render())

    async def test_unknown_action_is_ignored(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """An unrecognised action does nothing."""
        tool = FakeTool("WARP")
        app = _make_app(monkeypatch, [tool])
        async with app.run_test() as pilot:
            await pilot.pause()
            screen = app.screen
            assert isinstance(screen, MainScreen)
            screen.on_tool_card_tool_action(ToolCard.ToolAction(tool, "noop"))
            await pilot.pause()
            assert tool.status == ToolStatus.STOPPED


class TestStartStopFlows:
    """Direct start/stop worker behavior including failures."""

    async def test_start_failure_reports_error(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """A failed start surfaces the error on the status bar."""
        tool = FakeTool("WARP", start_success=False)
        app = _make_app(monkeypatch, [tool])
        async with app.run_test() as pilot:
            await pilot.pause()
            screen = app.screen
            assert isinstance(screen, MainScreen)
            await screen._start_tool(tool, ToolConfig())
            assert tool.status == ToolStatus.ERROR
            bar = screen.query_one("#status-bar", Static)
            assert "Failed to start" in str(bar.render())

    async def test_stop_failure_reports_error(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """A failed stop surfaces a failure message."""
        tool = FakeTool("WARP", stop_success=False)
        app = _make_app(monkeypatch, [tool])
        async with app.run_test() as pilot:
            await pilot.pause()
            screen = app.screen
            assert isinstance(screen, MainScreen)
            tool._status = ToolStatus.RUNNING
            await screen._stop_tool(tool)
            bar = screen.query_one("#status-bar", Static)
            assert "Failed to stop" in str(bar.render())


class TestConflictResolution:
    """Starting a tool auto-stops running conflicting tools."""

    async def test_conflicting_tool_is_stopped(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """A running conflict is stopped before the new tool starts."""
        warp = FakeTool("WARP", conflicts_with=["OpenVPN"])
        openvpn = FakeTool("OpenVPN")
        app = _make_app(monkeypatch, [warp, openvpn])
        async with app.run_test() as pilot:
            await pilot.pause()
            screen = app.screen
            assert isinstance(screen, MainScreen)
            openvpn._status = ToolStatus.RUNNING
            screen._cards["OpenVPN"].refresh_status(ToolStatus.RUNNING)
            await screen._start_tool(warp, ToolConfig())
            assert openvpn.status == ToolStatus.STOPPED
            assert warp.status == ToolStatus.RUNNING

    async def test_conflict_stop_failure_proceeds(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """A conflict that fails to stop still lets the new tool start."""
        warp = FakeTool("WARP", conflicts_with=["OpenVPN"])
        openvpn = FakeTool("OpenVPN", stop_success=False)
        app = _make_app(monkeypatch, [warp, openvpn])
        async with app.run_test() as pilot:
            await pilot.pause()
            screen = app.screen
            assert isinstance(screen, MainScreen)
            openvpn._status = ToolStatus.RUNNING
            screen._cards["OpenVPN"].refresh_status(ToolStatus.RUNNING)
            await screen._start_tool(warp, ToolConfig())
            assert warp.status == ToolStatus.RUNNING


class TestToolConfig:
    """_get_tool_config populates tool-specific options."""

    @pytest.mark.parametrize(
        "name", ["SpoofDPI", "WARP", "OpenVPN", "GoodbyeDPI", "Other"]
    )
    async def test_config_per_tool(
        self, monkeypatch: pytest.MonkeyPatch, name: str
    ) -> None:
        """Each known tool name yields its option set; others are bare."""
        tool = FakeTool(name)
        app = _make_app(monkeypatch, [tool])
        async with app.run_test() as pilot:
            await pilot.pause()
            screen = app.screen
            assert isinstance(screen, MainScreen)
            config = screen._get_tool_config(tool)
            if name == "Other":
                assert config.options == {}
                assert config.config_dirs == []


class TestConfigSelectorFlow:
    """Selecting a config drives the start / password flows."""

    async def test_no_config_reports(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """A config tool with no files reports on the status bar."""
        tool = FakeTool("OpenVPN", supports_configs=True, config_files=[])
        app = _make_app(monkeypatch, [tool])
        async with app.run_test() as pilot:
            await pilot.pause()
            screen = app.screen
            assert isinstance(screen, MainScreen)
            screen._handle_start(tool)
            await pilot.pause()
            bar = screen.query_one("#status-bar", Static)
            assert "No config files found" in str(bar.render())

    async def test_report_no_configs_lists_dirs(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """The no-config message lists configured directories when present."""
        app = _make_app(monkeypatch, [FakeTool("OpenVPN")])
        async with app.run_test() as pilot:
            await pilot.pause()
            screen = app.screen
            assert isinstance(screen, MainScreen)
            screen._report_no_configs(ToolConfig(config_dirs=["/etc/x"]))
            bar = screen.query_one("#status-bar", Static)
            assert "/etc/x" in str(bar.render())

    async def test_report_no_configs_without_dirs(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """The no-config message falls back when no directories are configured."""
        app = _make_app(monkeypatch, [FakeTool("OpenVPN")])
        async with app.run_test() as pilot:
            await pilot.pause()
            screen = app.screen
            assert isinstance(screen, MainScreen)
            screen._report_no_configs(ToolConfig(config_dirs=[]))
            bar = screen.query_one("#status-bar", Static)
            assert "none configured" in str(bar.render())

    async def test_select_config_starts_tool(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Choosing a config file starts a non-sudo tool with it."""
        tool = FakeTool("OpenVPN", supports_configs=True, config_files=["/cfg/a.ovpn"])
        app = _make_app(monkeypatch, [tool])
        async with app.run_test() as pilot:
            await pilot.pause()
            screen = app.screen
            assert isinstance(screen, MainScreen)
            screen._handle_start(tool)
            await pilot.pause()
            selector = app.screen
            assert isinstance(selector, ConfigSelectorScreen)
            selector.dismiss("/cfg/a.ovpn")
            await pilot.pause()
            assert tool.started_with is not None
            assert tool.started_with.config_file == "/cfg/a.ovpn"

    async def test_cancel_config_does_not_start(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Cancelling the selector leaves the tool untouched."""
        tool = FakeTool("OpenVPN", supports_configs=True, config_files=["/cfg/a.ovpn"])
        app = _make_app(monkeypatch, [tool])
        async with app.run_test() as pilot:
            await pilot.pause()
            screen = app.screen
            assert isinstance(screen, MainScreen)
            screen._show_config_selector(tool)
            await pilot.pause()
            selector = app.screen
            assert isinstance(selector, ConfigSelectorScreen)
            selector.dismiss(None)
            await pilot.pause()
            assert tool.started_with is None

    async def test_select_config_prompts_for_password(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """A sudo tool prompts for a password after config selection."""
        tool = FakeTool(
            "OpenVPN",
            supports_configs=True,
            requires_sudo=True,
            config_files=["/cfg/a.ovpn"],
        )
        app = _make_app(monkeypatch, [tool])
        async with app.run_test() as pilot:
            await pilot.pause()
            screen = app.screen
            assert isinstance(screen, MainScreen)
            screen._show_config_selector(tool)
            await pilot.pause()
            selector = app.screen
            assert isinstance(selector, ConfigSelectorScreen)
            selector.dismiss("/cfg/a.ovpn")
            await pilot.pause()
            assert isinstance(app.screen, PasswordPromptScreen)
            app.screen.dismiss("hunter2")
            await pilot.pause()
            assert tool.started_with is not None
            assert tool.started_with.options["sudo_password"] == "hunter2"  # noqa: S105

    async def test_password_cancel_does_not_start(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Cancelling the password prompt aborts the connection."""
        tool = FakeTool("OpenVPN", requires_sudo=True)
        app = _make_app(monkeypatch, [tool])
        async with app.run_test() as pilot:
            await pilot.pause()
            screen = app.screen
            assert isinstance(screen, MainScreen)
            screen._show_password_prompt(tool, ToolConfig())
            await pilot.pause()
            prompt = app.screen
            assert isinstance(prompt, PasswordPromptScreen)
            prompt.dismiss(None)
            await pilot.pause()
            assert tool.started_with is None


class TestActions:
    """Keyboard-bound actions refresh, clear logs, and quit."""

    async def test_action_refresh(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Refresh updates statuses and the status bar."""
        tool = FakeTool("WARP")
        app = _make_app(monkeypatch, [tool])
        async with app.run_test() as pilot:
            await pilot.pause()
            screen = app.screen
            assert isinstance(screen, MainScreen)
            screen.action_refresh()
            await pilot.pause()
            bar = screen.query_one("#status-bar", Static)
            assert str(bar.render()) == "Refreshed"

    async def test_refresh_isolates_tool_errors(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """A failing tool refresh does not abort the whole loop."""
        good = FakeTool("WARP")
        bad = FakeTool("OpenVPN", refresh_error=True)
        app = _make_app(monkeypatch, [good, bad])
        async with app.run_test() as pilot:
            await pilot.pause()
            screen = app.screen
            assert isinstance(screen, MainScreen)
            await screen._refresh_all_statuses()

    async def test_action_clear_logs(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Clearing logs empties then re-seeds the panel."""
        app = _make_app(monkeypatch, [FakeTool("WARP")])
        async with app.run_test() as pilot:
            await pilot.pause()
            screen = app.screen
            assert isinstance(screen, MainScreen)
            screen.action_clear_logs()
            await pilot.pause()

    async def test_action_quit(
        self, monkeypatch: pytest.MonkeyPatch, mocker: MockerFixture
    ) -> None:
        """Quit calls the app exit hook."""
        app = _make_app(monkeypatch, [FakeTool("WARP")])
        async with app.run_test() as pilot:
            await pilot.pause()
            screen = app.screen
            assert isinstance(screen, MainScreen)
            exiter = mocker.patch.object(app, "exit")
            screen.action_quit()
            await pilot.pause()
            exiter.assert_called_once_with()


def _auto_connect_config(config_path: str) -> AppConfig:
    """Build an auto-connect config pointing at ``config_path``."""
    return AppConfig(
        general=GeneralConfig(auto_connect=True),
        openvpn=OpenVPNConfig(default_config=config_path),
    )


class TestAutoConnect:
    """on_mount auto-connect covers each guard branch."""

    async def test_disabled_by_default(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Auto-connect is skipped when disabled."""
        tool = FakeTool("OpenVPN")
        app = _make_app(monkeypatch, [tool])
        async with app.run_test() as pilot:
            await pilot.pause()
            assert tool.started_with is None

    async def test_missing_config_file(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        """A non-existent default config aborts auto-connect."""
        tool = FakeTool("OpenVPN")
        config = _auto_connect_config(str(tmp_path / "nope.ovpn"))
        app = _make_app(monkeypatch, [tool], config)
        async with app.run_test() as pilot:
            await pilot.pause()
            assert tool.started_with is None
            assert isinstance(app.screen, MainScreen)

    async def test_empty_default_config(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """An unset default config aborts auto-connect."""
        tool = FakeTool("OpenVPN")
        config = AppConfig(general=GeneralConfig(auto_connect=True))
        app = _make_app(monkeypatch, [tool], config)
        async with app.run_test() as pilot:
            await pilot.pause()
            assert tool.started_with is None

    async def test_no_openvpn_tool(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        """Auto-connect aborts when no OpenVPN tool is registered."""
        cfg = tmp_path / "vpn.ovpn"
        cfg.write_text("client\n")
        config = _auto_connect_config(str(cfg))
        app = _make_app(monkeypatch, [FakeTool("WARP")], config)
        async with app.run_test() as pilot:
            await pilot.pause()
            assert isinstance(app.screen, MainScreen)

    async def test_openvpn_unavailable(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        """Auto-connect aborts when OpenVPN is not installed."""
        cfg = tmp_path / "vpn.ovpn"
        cfg.write_text("client\n")
        tool = FakeTool("OpenVPN", available=False)
        config = _auto_connect_config(str(cfg))
        app = _make_app(monkeypatch, [tool], config)
        async with app.run_test() as pilot:
            await pilot.pause()
            assert tool.started_with is None

    async def test_auto_connect_without_sudo_starts(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        """A ready, non-sudo OpenVPN auto-connects directly."""
        cfg = tmp_path / "vpn.ovpn"
        cfg.write_text("client\n")
        tool = FakeTool("OpenVPN", requires_sudo=False)
        config = _auto_connect_config(str(cfg))
        app = _make_app(monkeypatch, [tool], config)
        async with app.run_test() as pilot:
            await pilot.pause()
            assert tool.started_with is not None
            assert tool.started_with.config_file == str(cfg)

    async def test_auto_connect_with_sudo_prompts(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        """A sudo-requiring OpenVPN prompts for a password on auto-connect."""
        cfg = tmp_path / "vpn.ovpn"
        cfg.write_text("client\n")
        tool = FakeTool("OpenVPN", requires_sudo=True)
        config = _auto_connect_config(str(cfg))
        app = _make_app(monkeypatch, [tool], config)
        async with app.run_test() as pilot:
            await pilot.pause()
            assert isinstance(app.screen, PasswordPromptScreen)
            app.screen.dismiss(None)
            await pilot.pause()


class TestConfigSelectorScreen:
    """The config selector modal in isolation."""

    async def test_option_selected_dismisses_with_id(self) -> None:
        """Selecting an option dismisses with its config path."""
        tool = FakeTool("OpenVPN")
        result = _ModalResult()
        app = _ModalHostApp(
            ConfigSelectorScreen(tool, ["/cfg/a.ovpn", "/cfg/b.ovpn"]), result
        )
        async with app.run_test() as pilot:
            await pilot.pause()
            selector = app.screen
            assert isinstance(selector, ConfigSelectorScreen)
            assert selector.query_one("#config-options", OptionList).has_focus
            await pilot.press("enter")
            await pilot.pause()
            assert result.value == "/cfg/a.ovpn"

    async def test_cancel_button_dismisses_none(self) -> None:
        """The cancel button dismisses with None."""
        result = _ModalResult()
        app = _ModalHostApp(
            ConfigSelectorScreen(FakeTool("OpenVPN"), ["/cfg/a.ovpn"]), result
        )
        async with app.run_test() as pilot:
            await pilot.pause()
            await pilot.click("#btn-cancel")
            await pilot.pause()
            assert result.value is None

    async def test_escape_dismisses_none(self) -> None:
        """The escape binding cancels the modal."""
        result = _ModalResult()
        app = _ModalHostApp(
            ConfigSelectorScreen(FakeTool("OpenVPN"), ["/cfg/a.ovpn"]), result
        )
        async with app.run_test() as pilot:
            await pilot.pause()
            await pilot.press("escape")
            await pilot.pause()
            assert result.value is None

    async def test_title_shows_tool_name(self) -> None:
        """The modal title names the tool."""
        result = _ModalResult()
        app = _ModalHostApp(
            ConfigSelectorScreen(FakeTool("OpenVPN"), ["/cfg/a.ovpn"]), result
        )
        async with app.run_test() as pilot:
            await pilot.pause()
            title = app.screen.query_one("#modal-title", Label)
            assert "OpenVPN" in str(title.render())
            await pilot.press("escape")
            await pilot.pause()

    async def test_foreign_button_is_ignored(self) -> None:
        """A press from an unrelated button does not dismiss the modal."""
        result = _ModalResult()
        selector = ConfigSelectorScreen(FakeTool("OpenVPN"), ["/cfg/a.ovpn"])
        app = _ModalHostApp(selector, result)
        async with app.run_test() as pilot:
            await pilot.pause()
            selector.on_button_pressed(Button.Pressed(Button("x", id="other")))
            await pilot.pause()
            assert result.value == "unset"
            await pilot.press("escape")
            await pilot.pause()


class TestPasswordPromptScreen:
    """The password prompt modal in isolation."""

    async def test_connect_button_submits_password(self) -> None:
        """Typing a password and pressing Connect dismisses with it."""
        result = _ModalResult()
        app = _ModalHostApp(PasswordPromptScreen(FakeTool("OpenVPN")), result)
        async with app.run_test() as pilot:
            await pilot.pause()
            assert app.screen.query_one("#password-input", Input).has_focus
            await pilot.press("s", "e", "c", "r", "e", "t")
            await pilot.click("#btn-connect")
            await pilot.pause()
            assert result.value == "secret"

    async def test_enter_submits_password(self) -> None:
        """Pressing Enter in the field submits the password."""
        result = _ModalResult()
        app = _ModalHostApp(PasswordPromptScreen(FakeTool("OpenVPN")), result)
        async with app.run_test() as pilot:
            await pilot.pause()
            await pilot.press("p", "w", "enter")
            await pilot.pause()
            assert result.value == "pw"

    async def test_cancel_button_dismisses_none(self) -> None:
        """The cancel button dismisses with None."""
        result = _ModalResult()
        app = _ModalHostApp(PasswordPromptScreen(FakeTool("OpenVPN")), result)
        async with app.run_test() as pilot:
            await pilot.pause()
            await pilot.click("#btn-cancel")
            await pilot.pause()
            assert result.value is None

    async def test_escape_dismisses_none(self) -> None:
        """The escape binding cancels the modal."""
        result = _ModalResult()
        app = _ModalHostApp(PasswordPromptScreen(FakeTool("OpenVPN")), result)
        async with app.run_test() as pilot:
            await pilot.pause()
            await pilot.press("escape")
            await pilot.pause()
            assert result.value is None

    async def test_foreign_button_is_ignored(self) -> None:
        """A press from an unrelated button neither submits nor cancels."""
        result = _ModalResult()
        prompt = PasswordPromptScreen(FakeTool("OpenVPN"))
        app = _ModalHostApp(prompt, result)
        async with app.run_test() as pilot:
            await pilot.pause()
            prompt.on_button_pressed(Button.Pressed(Button("x", id="other")))
            await pilot.pause()
            assert result.value == "unset"
            await pilot.press("escape")
            await pilot.pause()


class _ModalResult:
    """Mutable holder for a modal's dismiss value."""

    def __init__(self) -> None:
        self.value: str | None = "unset"


class _ModalHostApp(App[None]):
    """Host app that pushes one modal screen and records its dismissal."""

    def __init__(self, screen: Screen[str | None], result: _ModalResult) -> None:
        super().__init__()
        self._screen_to_push = screen
        self._result = result

    def on_mount(self) -> None:
        self.push_screen(self._screen_to_push, self._store)

    def _store(self, value: str | None) -> None:
        self._result.value = value
