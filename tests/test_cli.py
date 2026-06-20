"""Tests for the ocom command-line entry point."""

import pytest

from ocom import __version__
from ocom.__main__ import main


class TestCLIVersion:
    """The --version flag prints the version and exits without launching the TUI."""

    def test_version_exits_zero(
        self, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """`ocom --version` should print the version and exit with code 0."""
        monkeypatch.setattr("sys.argv", ["ocom", "--version"])
        with pytest.raises(SystemExit) as exc:
            main()
        assert exc.value.code == 0
        assert __version__ in capsys.readouterr().out

    def test_version_does_not_launch_tui(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """`ocom --version` must not launch the TUI."""
        launched = False

        def fake_run() -> None:
            nonlocal launched
            launched = True

        monkeypatch.setattr("ocom.__main__.run", fake_run)
        monkeypatch.setattr("sys.argv", ["ocom", "--version"])
        with pytest.raises(SystemExit):
            main()
        assert launched is False


class TestCLIHelp:
    """The --help flag prints usage and exits without launching the TUI."""

    def test_help_exits_zero(
        self, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """`ocom --help` should print usage and exit with code 0."""
        monkeypatch.setattr("sys.argv", ["ocom", "--help"])
        with pytest.raises(SystemExit) as exc:
            main()
        assert exc.value.code == 0
        assert "usage" in capsys.readouterr().out

    def test_help_does_not_launch_tui(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """`ocom --help` must not launch the TUI."""
        launched = False

        def fake_run() -> None:
            nonlocal launched
            launched = True

        monkeypatch.setattr("ocom.__main__.run", fake_run)
        monkeypatch.setattr("sys.argv", ["ocom", "--help"])
        with pytest.raises(SystemExit):
            main()
        assert launched is False


class TestCLINoArgs:
    """Invoking the CLI with no arguments launches the TUI."""

    def test_no_args_launches_tui(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """`ocom` without flags should launch the TUI exactly once."""
        calls = 0

        def fake_run() -> None:
            nonlocal calls
            calls += 1

        monkeypatch.setattr("ocom.__main__.run", fake_run)
        monkeypatch.setattr("sys.argv", ["ocom"])
        main()
        assert calls == 1
