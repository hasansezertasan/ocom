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
