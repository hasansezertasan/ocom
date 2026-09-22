"""Test cases for the ocom Typer root."""

from __future__ import annotations

import importlib
import sys
from typing import TYPE_CHECKING

import pytest
import typer
from typer.testing import CliRunner

from ocom.cli.app import app

if TYPE_CHECKING:
    from collections.abc import Sequence
    from importlib.machinery import ModuleSpec
    from types import ModuleType

    from typer.testing import Result
# The cli ``__init__`` re-exports the Typer ``app`` object, which shadows the
# ``app`` submodule on any attribute-based import (``from ... import app``,
# ``import ...app as ...``). importlib returns the real module from sys.modules —
# the object the guard tests below need to reach.
cli_app = importlib.import_module("ocom.cli.app")


# Bound to a name so the raises in the guard tests stay single statements (EM101).
_MISSING_MODULE_MESSAGE = "No module named 'uvicorn'"
_NAMELESS_MODULE_MESSAGE = "nameless import failure"
_SUBMODULE_MESSAGE = "No module named 'uvicorn.user_plugin'"


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
@pytest.mark.usefixtures("missing_metadata")
def test_command_fails_loudly_when_metadata_missing(
    runner: CliRunner, command: str
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
    result: Result = runner.invoke(app, [command])

    assert result.exit_code == 1


<<<<<<< before updating
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
=======
def test_missing_component_dependency_is_actionable(
    capsys: pytest.CaptureFixture[str],
) -> None:
    """A missing component dependency exits 1 with a message naming the fix.

    Given:
        - A launcher command whose lazy import raises ``ModuleNotFoundError`` (an
          environment out of sync with the installed package).
    When:
        - The import is performed inside the component-dependency guard.
    Then:
        - The guard raises ``typer.Exit(1)`` and stderr names the component, the
          missing module, and ``uv sync`` -- instead of dumping a bare
          ``ModuleNotFoundError``.

    Raises:
        ModuleNotFoundError: Simulating the missing dependency; the guard converts
            it into the actionable exit.
    """
    with (
        pytest.raises(typer.Exit) as excinfo,
        vars(cli_app)["_component_dependencies"]("web", "uvicorn"),
    ):
        raise ModuleNotFoundError(_MISSING_MODULE_MESSAGE, name="uvicorn")

    assert excinfo.value.exit_code == 1
    err = capsys.readouterr().err
    assert "web" in err
    assert "uvicorn" in err
    assert "uv sync" in err


def test_nameless_module_error_is_not_translated(
    capsys: pytest.CaptureFixture[str],
) -> None:
    """An import failure carrying no module name propagates untouched.

    Given:
        - A ``ModuleNotFoundError`` without a ``name``, so the guard cannot tell
          whether the failure involves one of the component's dependencies.
    When:
        - It is raised inside the component-dependency guard.
    Then:
        - The original error propagates instead of being relabelled as an
          out-of-sync environment.

    Raises:
        ModuleNotFoundError: The nameless failure under test.
    """
    with (
        pytest.raises(ModuleNotFoundError, match="nameless"),
        vars(cli_app)["_component_dependencies"]("web", "uvicorn"),
    ):
        raise ModuleNotFoundError(_NAMELESS_MODULE_MESSAGE)

    assert "uv sync" not in capsys.readouterr().err


def test_submodule_of_a_dependency_is_not_translated(
    capsys: pytest.CaptureFixture[str],
) -> None:
    """A bad import *below* an installed dependency keeps its own diagnostics.

    Given:
        - A customized component importing a name that does not exist under an
          installed dependency (``from uvicorn.user_plugin import X``), so the
          error names ``uvicorn.user_plugin`` rather than ``uvicorn``.
    When:
        - It is raised inside the component-dependency guard.
    Then:
        - The original error propagates: this is an application defect, and
          recommending ``uv sync`` for it would send the reader down the wrong
          path.

    Raises:
        ModuleNotFoundError: The application defect under test.
    """
    with (
        pytest.raises(ModuleNotFoundError, match="user_plugin"),
        vars(cli_app)["_component_dependencies"]("web", "uvicorn"),
    ):
        raise ModuleNotFoundError(_SUBMODULE_MESSAGE, name="uvicorn.user_plugin")

    assert "uv sync" not in capsys.readouterr().err


#: A name no distribution claims, so only the finder below can resolve it.
_BROKEN_MODULE = "broken_preflight_target"
_BROKEN_MODULE_MESSAGE = "cannot import name 'x' from a partially initialized module"


class _BrokenModuleFinder:
    """Simulate a dependency that is installed but whose import raises."""

    @staticmethod
    def find_spec(
        fullname: str, path: Sequence[str] | None, target: ModuleType | None = None
    ) -> ModuleSpec | None:
        """Fail the sentinel import with a *nameless* ``ImportError``.

        Raises:
            ImportError: Carrying no module name, the shape faststream's broker
                re-export raises and that exact-name matching cannot classify.
        """
        del path, target
        if fullname == _BROKEN_MODULE:
            raise ImportError(_BROKEN_MODULE_MESSAGE)
        return None


def test_preflight_names_a_dependency_that_fails_to_import(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A nameless ``ImportError`` is re-raised naming the preflighted module.

    Given:
        - A dependency present on disk whose own import raises without naming a
          module -- a broken install, or faststream's guarded broker re-export.
    When:
        - The launcher preflights it.
    Then:
        - It becomes a ``ModuleNotFoundError`` carrying that module's name, so
          the guard's exact-match rule can classify it.
    """
    finder = _BrokenModuleFinder()
    # The stub intercepts only its own target, so an unrelated import still
    # resolves normally -- and the pass-through arm stays exercised.
    assert finder.find_spec("json", None) is None
    monkeypatch.setattr(sys, "meta_path", [finder, *sys.meta_path])

    with pytest.raises(ModuleNotFoundError) as excinfo:
        vars(cli_app)["_preflight"](_BROKEN_MODULE)

    assert excinfo.value.name == _BROKEN_MODULE


def test_tui_launcher_reports_missing_deferred_dependency(
    runner: CliRunner, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The TUI launcher translates a missing lazy ``textual`` import."""
    monkeypatch.setitem(sys.modules, "textual", None)

    result: Result = runner.invoke(app, ["interactive"])

    assert result.exit_code == 1
    assert not isinstance(result.exception, ModuleNotFoundError)
    assert "tui" in result.output.lower()
    assert "textual" in result.output
    assert "uv sync" in result.output
    assert "Traceback" not in result.output


def test_subcommand_interactive_dispatches(
    runner: CliRunner, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The `interactive` subcommand invokes the interactive component entry point."""
    called = False

    def mock_main() -> int:
        nonlocal called
        called = True
        return 0

    target_mod = importlib.import_module("ocom.tui.app")
    monkeypatch.setattr(target_mod, "main", mock_main)
    result: Result = runner.invoke(app, ["interactive"])
    assert result.exit_code == 0
    assert called
>>>>>>> after updating
