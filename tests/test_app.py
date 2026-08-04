"""Tests for the OcomApp application and run() entry point."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from ocom.app import OcomApp, run
from ocom.config import AppConfig
from ocom.ui.screens.main import MainScreen

if TYPE_CHECKING:
    from pathlib import Path

    from pytest_mock import MockerFixture


@pytest.fixture(autouse=True)  # noqa: RUF076
def _no_user_config(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """Prevent tests from reading a real user config file."""
    monkeypatch.setattr(
        "ocom.config.get_config_path", lambda: tmp_path / "missing.toml"
    )


class TestOcomAppConfig:
    """The app loads config from disk only when none is supplied."""

    def test_uses_supplied_config(self) -> None:
        """A provided config is stored as-is without loading from disk."""
        config = AppConfig()
        app = OcomApp(config)
        assert app.config is config

    def test_loads_config_when_none(self, mocker: MockerFixture) -> None:
        """When no config is given, AppConfig.load supplies one."""
        sentinel = AppConfig()
        loader = mocker.patch("ocom.app.AppConfig.load", return_value=sentinel)
        app = OcomApp()
        assert app.config is sentinel
        loader.assert_called_once_with()


class TestOcomAppMount:
    """on_mount pushes the MainScreen dashboard."""

    async def test_pushes_main_screen(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Starting the app makes MainScreen the active screen."""
        monkeypatch.setattr("ocom.ui.screens.main.get_all_tools", list)
        app = OcomApp(AppConfig())
        async with app.run_test() as pilot:
            await pilot.pause()
            assert isinstance(app.screen, MainScreen)


class TestRun:
    """run() builds an app and starts its event loop."""

    def test_run_invokes_app_run(self, mocker: MockerFixture) -> None:
        """run() constructs OcomApp and calls its run() method once."""
        mocker.patch("ocom.app.AppConfig.load", return_value=AppConfig())
        app_run = mocker.patch("ocom.app.OcomApp.run")
        run()
        app_run.assert_called_once_with()
