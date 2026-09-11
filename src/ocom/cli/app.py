<<<<<<< before updating
"""CLI application for ocom.

Running bare ``ocom`` (no subcommand) launches the Textual TUI; subcommands
(``version``, ``info``) and ``--help`` act as a conventional command-line tool.
=======
"""CLI application for the project.

The ``ocom`` command is the single Typer root. Every enabled
component other than the primary (CLI > GUI > TUI > web > MCP > worker) is hung
off it as a lazily-imported subcommand — ``ocom interactive``
(TUI), ``ocom web``, ``ocom mcp``, ... — rather
than a separate ``ocom-<name>`` console script (see ADR-019).
>>>>>>> after updating
"""
# mypy: disable-error-code="misc"

from __future__ import annotations

import platform
from importlib.metadata import Distribution, PackageNotFoundError

import typer

from ocom.__metadata__ import PROJECT_NAME
from ocom.core.logging_setup import get_logger

__all__ = ["app", "info", "main_callback", "show_version"]

logger = get_logger()

app = typer.Typer(name=PROJECT_NAME, no_args_is_help=False)


@app.callback(invoke_without_command=True)
def main_callback(ctx: typer.Context) -> None:
    """Manage network/privacy tools. Run with no command to open the TUI.

    Typer runs this callback before any subcommand, so when one (version, info)
    was requested we defer to it; otherwise bare ocom starts the Textual
    dashboard.
    """
    if ctx.invoked_subcommand is not None:
        return
    logger.info("No subcommand given; launching the TUI.")
    from ocom.tui.app import run  # noqa: PLC0415

    run()


@app.command(name="version")
def show_version() -> None:
    """Show the current version number of ocom.

    Raises:
        typer.Exit: If the package metadata cannot be found.
    """
    try:
        distribution = Distribution.from_name(PROJECT_NAME)
    except PackageNotFoundError:
        # An uninstalled or partial package is an expected, user-facing error, so
        # log without the traceback that logging.exception would add.
        logger.error("Package metadata not found for %s", PROJECT_NAME)  # noqa: TRY400
        typer.echo(
            f"Error: Package '{PROJECT_NAME}' metadata not found. Is the package installed correctly?",  # noqa: E501
            err=True,
        )
        raise typer.Exit(code=1) from None
    logger.info("Command `version` called.")
    typer.echo(distribution.version)
    logger.info("Version displayed successfully.")


@app.command()
def info() -> None:
    """Display information about the ocom application.

    Raises:
        typer.Exit: If the package metadata cannot be found.
    """
    try:
        distribution = Distribution.from_name(PROJECT_NAME)
    except PackageNotFoundError:
        # An uninstalled or partial package is an expected, user-facing error, so
        # log without the traceback that logging.exception would add.
        logger.error("Package metadata not found for %s", PROJECT_NAME)  # noqa: TRY400
        typer.echo(
            f"Error: Package '{PROJECT_NAME}' metadata not found. Is the package installed correctly?",  # noqa: E501
            err=True,
        )
        raise typer.Exit(code=1) from None
    logger.info("Command `info` called.")
    python_version = platform.python_version()
    python_implementation = platform.python_implementation()
    typer.echo(f"Application Version: {distribution.version}")
    typer.echo(f"Python Version: {python_version} ({python_implementation})")
    typer.echo(f"Platform: {platform.system()}")
    logger.info("Application information displayed successfully.")
<<<<<<< before updating
=======


@app.command()
def interactive() -> None:  # pragma: no cover
    """Start interactive mode (TUI) for ocom.

    Launch the terminal user interface:
        ocom interactive

    Raises:
        typer.Exit: Propagating the TUI's exit code.
    """
    from ocom.tui.app import main  # noqa: PLC0415

    raise typer.Exit(code=main())
>>>>>>> after updating
