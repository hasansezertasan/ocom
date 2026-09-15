"""Test cases for the ocom Typer root."""

from __future__ import annotations

import importlib
from importlib.metadata import Distribution, PackageNotFoundError
from typing import TYPE_CHECKING

import pytest
from typer.testing import CliRunner

from ocom.cli.app import app

if TYPE_CHECKING:
    from typer.testing import Result


# The cli ``__init__`` re-exports the Typer ``app`` object, which shadows the
# ``app`` submodule on any attribute-based import (``from ... import app``,
# ``import ...app as ...``). importlib returns the real module from sys.modules —
# the object the monkeypatch below needs to patch.
cli_app = importlib.import_module("ocom.cli.app")


class _MissingDistribution:
    """Stub whose ``from_name`` always reports missing package metadata."""

    @staticmethod
    def from_name(name: str) -> Distribution:
        raise PackageNotFoundError(name)


@pytest.fixture
def runner() -> CliRunner:
    """Fixture that provides a CLI runner for testing Typer commands."""
    return CliRunner()


def test_help_exits_cleanly(runner: CliRunner) -> None:
    """``--help`` renders the root usage and exits 0.

    Given:
        - The ocom Typer root.
    When:
        - ``--help`` is requested.
    Then:
        - The command exits 0 and every enabled component
          subcommand is advertised in the help output.
    """
    result: Result = runner.invoke(app, ["--help"])

    assert result.exit_code == 0, result.output
    assert "interactive" in result.output


def test_version(runner: CliRunner) -> None:
    """The `version` command runs successfully and prints the version.

    Given:
        - The application is set up with a `version` command.
    When:
        - The `version` command is invoked using the CLI runner.
    Then:
        - The command exits 0 and the output contains the version.
    """
    result: Result = runner.invoke(app, ["version"])
    assert result.exit_code == 0, result.output


def test_info(runner: CliRunner) -> None:
    """The `info` command runs successfully and prints application information.

    Given:
        - The application is set up with an `info` command.
    When:
        - The `info` command is invoked using the CLI runner.
    Then:
        - The command exits 0 and the output contains the application info.
    """
    result: Result = runner.invoke(app, ["info"])
    assert result.exit_code == 0, result.output


@pytest.mark.parametrize("command", ["version", "info"])
def test_command_fails_loudly_when_metadata_missing(
    runner: CliRunner, monkeypatch: pytest.MonkeyPatch, command: str
) -> None:
    """Commands exit non-zero with an error when package metadata is missing.

    Given:
        - Package metadata cannot be resolved (broken/partial install).
    When:
        - The `version` or `info` command is invoked.
    Then:
        - The command exits with code 1 (the documented ``typer.Exit`` contract)
          instead of dumping a traceback or silently printing nothing.
    """
    monkeypatch.setattr(cli_app, "Distribution", _MissingDistribution)

    result: Result = runner.invoke(app, [command])

    assert result.exit_code == 1


def test_bare_invocation_launches_tui(
    runner: CliRunner, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Running ``ocom`` with no subcommand launches the TUI.

    Given:
        - The CLI is invoked with no subcommand or arguments.
    When:
        - The Typer app runs (its ``invoke_without_command`` callback fires).
    Then:
        - The TUI ``run()`` entry point is called exactly once and the process
          exits cleanly.
    """
    launched: list[bool] = []
    monkeypatch.setattr("ocom.tui.app.run", lambda: launched.append(True))

    result: Result = runner.invoke(app, [])

    assert result.exit_code == 0, result.output
    assert launched == [True]
