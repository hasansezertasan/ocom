"""CLI application for ocom.

The ``ocom`` command is the single Typer root: ``ocom --help`` lists the
commands, ``version`` and ``info`` report on the install, and every other
component is hung off it as a lazily-imported subcommand -- ``ocom interactive``
launches the Textual TUI -- rather than a separate ``ocom-<name>`` console script
(see ADR-019).
"""
# mypy: disable-error-code="misc"

from __future__ import annotations

import contextlib
import importlib
from typing import TYPE_CHECKING

import typer

from ocom.__metadata__ import PROJECT_NAME
from ocom.core import app as service
from ocom.core.logging_setup import get_logger

if TYPE_CHECKING:
    from collections.abc import Generator

__all__ = ["app", "info", "interactive", "show_version"]

logger = get_logger()

# Every component's runtime dependency is a core ``dependency`` of this package
# (there are no per-component extras), so a missing one never means "install the
# extra" -- it means this environment is out of sync with the installed metadata.
# That happens after a ``copier update`` enables a component, or in a stale venv.
_MISSING_DEPENDENCY = "Error: The {component} component requires '{missing}', which is not available in this environment. {hint}"  # noqa: E501
_SYNC_HINT = f"Component dependencies ship with '{PROJECT_NAME}', so this usually means your environment is out of sync -- run `uv sync` (or reinstall the package) and try again."  # noqa: E501
_TUI_DEPENDENCIES = ("textual",)


def _preflight(module: str) -> None:
    """Import a component dependency eagerly, so the guard below can classify it.

    Two kinds of dependency never reach the guard in a usable form. ``uvicorn``
    and Tkinter are imported at *call* time -- after the guarded block has closed
    -- and ``faststream.<broker>`` is a guarded re-export that raises a plain,
    *nameless* ``ImportError`` when the broker extra is absent, which exact-name
    matching cannot classify. Importing here, and supplying the module name when
    the interpreter does not, puts both back in reach of the guard.

    Args:
        module: Import module name to import eagerly.

    Raises:
        ModuleNotFoundError: Naming ``module`` when it cannot be imported.
    """
    try:
        _ = importlib.import_module(module)
    except ModuleNotFoundError as exc:
        # A nested failure belongs to the dependency being preflighted: a
        # partially installed uvicorn or web framework may name a sub-dependency
        # like ``click`` or ``starlette``, but the launcher's allowlist
        # intentionally knows only its direct dependencies.
        raise ModuleNotFoundError(str(exc), name=module) from None
    except ImportError as exc:
        # Not just "missing": a module whose own import raises is unusable here
        # too, and ``uv sync`` is the same repair. This is also the only shape
        # faststream's nameless broker-extra ``ImportError`` arrives in.
        raise ModuleNotFoundError(str(exc), name=module) from None


@contextlib.contextmanager
def _component_dependencies(
    component: str, *dependencies: str, hint: str = _SYNC_HINT
) -> Generator[None]:
    """Translate a missing component dependency into an actionable CLI error.

    Wraps a launcher command's lazy import so a ``ModuleNotFoundError`` for a
    known dependency becomes a message naming the component, missing module, and
    fix. Dependencies the component imports later than this block are imported
    eagerly by ``_preflight`` above instead.

    Args:
        component: Human name of the component being launched (e.g. ``"web"``).
        *dependencies: Import module names owned by the component, matched
            exactly.
        hint: Remediation sentence appended to the error. Defaults to the
            out-of-sync-environment ``uv sync`` hint, which is right for every
            component whose dependency is a real distribution.

    Yields:
        ``None``; the caller performs the import inside the block.

    Raises:
        ModuleNotFoundError: Propagating a missing module that is not exactly one
            of the component's known dependencies.
        typer.Exit: With code 1 if a dependency of ``component`` is missing.
    """
    try:
        yield
    except ModuleNotFoundError as exc:
        missing = exc.name
        # Exact matches only. A failure *below* an installed dependency's
        # namespace -- a typo'd ``from <dep>.user_plugin import X`` in a
        # customized component -- is an application defect, not a stale
        # environment, and suppressing its traceback to recommend ``uv sync``
        # would send the reader down the wrong path. A genuine missing dependency
        # reaching *this* block always names a root, because the component
        # imports it as ``from <dep> import X`` at module scope; the awkward
        # cases (deferred and guarded imports) go through ``_preflight``.
        if missing is None or missing not in dependencies:
            raise
        # An out-of-sync environment is an expected, user-facing error, so log
        # without the traceback that logging.exception would add.
        logger.error(  # noqa: TRY400
            "Missing dependency %r for the %s component", missing, component
        )
        typer.echo(
            _MISSING_DEPENDENCY.format(component=component, missing=missing, hint=hint),
            err=True,
        )
        raise typer.Exit(code=1) from None


app = typer.Typer(name="ocom", no_args_is_help=True)


@app.command(name="version")
def show_version() -> None:
    """Show the current version number of ocom.

    Raises:
        typer.Exit: If the package metadata cannot be found.
    """
    try:
        resolved = service.version()
    except service.MetadataUnavailableError:
        # An uninstalled or partial package is an expected, user-facing error, so
        # log without the traceback that logging.exception would add.
        logger.error("Package metadata not found for %s", PROJECT_NAME)  # noqa: TRY400
        typer.echo(
            f"Error: Package '{PROJECT_NAME}' metadata not found. Is the package installed correctly?",  # noqa: E501
            err=True,
        )
        raise typer.Exit(code=1) from None
    logger.info("Command `version` called.")
    typer.echo(resolved)
    logger.info("Version displayed successfully.")


@app.command()
def info() -> None:
    """Display information about the ocom application.

    Raises:
        typer.Exit: If the package metadata cannot be found.
    """
    try:
        payload = service.info()
    except service.MetadataUnavailableError:
        # An uninstalled or partial package is an expected, user-facing error, so
        # log without the traceback that logging.exception would add.
        logger.error("Package metadata not found for %s", PROJECT_NAME)  # noqa: TRY400
        typer.echo(
            f"Error: Package '{PROJECT_NAME}' metadata not found. Is the package installed correctly?",  # noqa: E501
            err=True,
        )
        raise typer.Exit(code=1) from None
    logger.info("Command `info` called.")
    python = f"{payload['python_version']} ({payload['python_implementation']})"
    typer.echo(f"Application Version: {payload['application_version']}")
    typer.echo(f"Python Version: {python}")
    typer.echo(f"Platform: {payload['platform']}")
    logger.info("Application information displayed successfully.")


@app.command()
def interactive() -> None:
    """Start interactive mode (TUI) for ocom.

    Launch the terminal user interface:
        ocom interactive

    Raises:
        typer.Exit: Propagating the TUI's exit code, or code 1 if a dependency of
            the TUI is missing from this environment.
    """
    with _component_dependencies("TUI", *_TUI_DEPENDENCIES):
        _preflight("textual")
        from ocom.tui.app import main  # noqa: PLC0415

    raise typer.Exit(code=main())
