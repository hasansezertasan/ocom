"""Tests for the OcomApp application and run() entry point."""

from __future__ import annotations

<<<<<<< before updating
from typing import TYPE_CHECKING
=======
import platform
from importlib.metadata import Distribution

import pytest
from textual.widgets import Static
>>>>>>> after updating

import pytest

<<<<<<< before updating
from ocom.core.config import AppConfig
from ocom.tui.app import OcomApp, run
from ocom.tui.screens.main import MainScreen
=======

def test_build_info_message_contains_metadata() -> None:
    """The TUI message should include core project metadata.

    Given: The application is installed
    When: build_info_message is called
    Then: The message includes project name, version, Python version, and platform
    """
    message = tui_app.build_info_message()
    distribution = Distribution.from_name(PROJECT_NAME)

    assert PROJECT_NAME in message
    assert distribution.version in message
    assert platform.python_version() in message
    assert platform.system() in message
>>>>>>> after updating

if TYPE_CHECKING:
    from pathlib import Path

<<<<<<< before updating
    from pytest_mock import MockerFixture


@pytest.fixture(autouse=True)
def _no_user_config(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """Prevent tests from reading a real user config file."""
    monkeypatch.setattr(
        "ocom.core.config.get_config_path", lambda: tmp_path / "missing.toml"
    )


class TestOcomAppConfig:
    """The app loads config from disk only when none is supplied."""

    def test_uses_supplied_config(self) -> None:
        """A provided config is stored as-is without loading from disk."""
        config = AppConfig()
        app = OcomApp(config)
        assert app.config is config
=======
@pytest.mark.usefixtures("missing_metadata")
def test_build_info_message_handles_missing_metadata() -> None:
    """The message degrades to an "unknown" version when metadata is missing.

    Given: Package metadata cannot be resolved (broken/partial install)
    When: build_info_message is called
    Then: The message reports the version as "unknown" instead of raising
    """
    message = tui_app.build_info_message()

    assert "Version: unknown" in message
    assert PROJECT_NAME in message


@pytest.mark.asyncio
async def test_info_app_headless() -> None:
    """The TUI InfoApp layout renders metadata and quits on 'q'.

    Given:
        - An InfoApp initialized with a test message.
    When:
        - Driven headlessly via Textual's App.run_test pilot.
    Then:
        - Widgets contain expected titles and content, and pressing 'q' exits.
    """
    app = tui_app.InfoApp("Test Info Message")
    async with app.run_test() as pilot:
        assert app.title == f"{PROJECT_NAME} Info"
        title = app.query_one("#title", Static)
        assert title.content == PROJECT_NAME
        info = app.query_one("#info-text", Static)
        assert info.content == "Test Info Message"
        footer = app.query_one("#footer", Static)
        assert footer.content == "Press 'q' to quit"
        assert app.is_running
        await pilot.press("q")
        await pilot.pause()
        assert not app.is_running


def test_main_can_skip_tui(capsys: pytest.CaptureFixture[str]) -> None:
    """When TUI display is skipped, information is printed to stdout.

    Given: The application is installed
    When: main is called with show_tui=False
    Then: The exit code is 0 and info is written to stdout
    """
    exit_code = tui_app.main(show_tui=False)
    captured = capsys.readouterr()

    assert exit_code == 0
    assert PROJECT_NAME in captured.out


def test_main_displays_tui() -> None:
    """When the TUI displays successfully, ``main`` returns 0.

    Given:
        - A mock driver that intercepts app execution.
    When:
        - ``main()`` is called with the driver.
    Then:
        - The driver receives the InfoApp and ``main`` returns 0.
    """
    displayed: list[tui_app.InfoApp] = []
    exit_code = tui_app.main(driver=displayed.append)

    assert exit_code == 0
    assert len(displayed) == 1
    assert PROJECT_NAME in displayed[0].message
>>>>>>> after updating

    def test_loads_config_when_none(self, mocker: MockerFixture) -> None:
        """When no config is given, AppConfig.load supplies one."""
        sentinel = AppConfig()
        loader = mocker.patch("ocom.tui.app.AppConfig.load", return_value=sentinel)
        app = OcomApp()
        assert app.config is sentinel
        loader.assert_called_once_with()

<<<<<<< before updating

class TestOcomAppMount:
    """on_mount pushes the MainScreen dashboard."""

    async def test_pushes_main_screen(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Starting the app makes MainScreen the active screen."""
        monkeypatch.setattr("ocom.tui.screens.main.get_all_tools", list)
        app = OcomApp(AppConfig())
        async with app.run_test() as pilot:
            await pilot.pause()
            assert isinstance(app.screen, MainScreen)


class TestRun:
    """run() builds an app and starts its event loop."""

    def test_run_invokes_app_run(self, mocker: MockerFixture) -> None:
        """run() constructs OcomApp and calls its run() method once."""
        mocker.patch("ocom.tui.app.AppConfig.load", return_value=AppConfig())
        app_run = mocker.patch("ocom.tui.app.OcomApp.run")
        run()
        app_run.assert_called_once_with()
=======
def test_main_handles_display_errors(capsys: pytest.CaptureFixture[str]) -> None:
    """Errors while showing the TUI should fall back to stdout.

    Given:
        - The TUI display driver raises an error.
    When:
        - ``main()`` is called.
    Then:
        - The exit code is 1 and info is written to stdout.
    """

    def _raise_display_error(_: tui_app.InfoApp) -> None:
        msg = "boom"
        raise RuntimeError(msg)

    exit_code = tui_app.main(driver=_raise_display_error)
    captured = capsys.readouterr()

    assert exit_code == 1
    assert PROJECT_NAME in captured.out


@pytest.mark.parametrize("exc_type", [KeyboardInterrupt, SystemExit])
def test_main_propagates_interrupt(exc_type: type[BaseException]) -> None:
    """``KeyboardInterrupt`` and ``SystemExit`` propagate out of ``main``."""

    def _raise_interrupt(_: tui_app.InfoApp) -> None:
        raise exc_type

    with pytest.raises(exc_type):
        tui_app.main(driver=_raise_interrupt)
>>>>>>> after updating
