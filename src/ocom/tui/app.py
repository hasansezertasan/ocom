"""Main Textual application for ocom."""

from pathlib import Path
from typing import final

<<<<<<< before updating
from textual.app import App

from ocom.core.config import AppConfig
from ocom.tui.screens.main import MainScreen

__all__ = ["OcomApp", "run"]


# Path to the TCSS file
CSS_PATH = Path(__file__).parent / "styles" / "app.tcss"
=======
import sys
from typing import TYPE_CHECKING, ClassVar, final

from textual.app import App, ComposeResult
from textual.containers import ScrollableContainer
from textual.widgets import Static
from typing_extensions import override

from ocom.__metadata__ import PROJECT_NAME
from ocom.core import app as service
from ocom.core.logging_setup import get_logger

if TYPE_CHECKING:
    from collections.abc import Callable

    from textual.binding import BindingType

__all__ = ["InfoApp", "TuiDisplayError", "build_info_message", "main"]
>>>>>>> after updating


@final
class OcomApp(App[None]):
    """Network tools manager TUI application."""

    TITLE = "ocom"
    SUB_TITLE = "Network Tools Manager"

    CSS_PATH = CSS_PATH if CSS_PATH.exists() else None

    def __init__(self, config: AppConfig | None = None) -> None:
        """Create the app, loading config from disk when none is given."""
        super().__init__()
        self.config = config or AppConfig.load()

<<<<<<< before updating
    def on_mount(self) -> None:
        """Push the main screen on startup."""
        self.push_screen(MainScreen(self.config))


def run() -> None:
    """Run the ocom application."""
    app = OcomApp()
    app.run()
=======
    Returns:
        str: A multi-line summary of the project name, version, and platform.
    """
    payload = service.info_or_unknown()
    return (
        f"{PROJECT_NAME}\n\n"
        f"Version: {payload['application_version']}\n"
        f"Python: {payload['python_version']} ({payload['python_implementation']})\n"
        f"Platform: {payload['platform']}"
    )


@final
class InfoApp(App[None]):
    """Simple TUI application displaying project info."""

    CSS = """
    Screen {
        align: center middle;
        background: $surface;
    }

    #info-container {
        width: 60;
        height: auto;
        border: solid $primary;
        background: $panel;
    }

    Static {
        width: 100%;
        height: auto;
        padding: 1;
    }

    #title {
        dock: top;
        height: 3;
        border-bottom: solid $primary;
        background: $boost;
        text-align: center;
        content-align: center middle;
    }

    #footer {
        dock: bottom;
        height: 1;
        border-top: solid $primary;
        text-align: center;
        background: $boost;
    }
    """

    BINDINGS: ClassVar[list[BindingType]] = [("q", "quit", "Quit")]

    def __init__(self, message: str) -> None:
        """Initialize the application.

        Args:
            message: The formatted information message to display.
        """
        super().__init__()
        self.message = message

    @override
    def compose(self) -> ComposeResult:
        """Compose the TUI layout.

        Yields:
            Widget: The widgets that make up the screen layout.
        """
        yield Static(PROJECT_NAME, id="title")
        with ScrollableContainer(id="info-container"):
            yield Static(self.message, id="info-text")
        yield Static("Press 'q' to quit", id="footer")

    def on_mount(self) -> None:
        """Set focus and style on mount."""
        self.title = f"{PROJECT_NAME} Info"


def _run_app(app: InfoApp) -> None:  # pragma: no cover
    """Execute the Textual event loop.

    The irreducible blocking call separated from UI setup and error handling.
    """
    app.run()


def _display_tui(message: str, *, driver: Callable[[InfoApp], None] = _run_app) -> None:
    """Display the information message in a Textual TUI application.

    Args:
        message: The information message to display.
        driver: Driver callable that runs the application event loop. Defaults
            to ``_run_app`` (running ``app.run()``).

    Raises:
        TuiDisplayError: If Textual fails to run.
        KeyboardInterrupt: If the user interrupts the running application.
        SystemExit: If the application requests interpreter exit.
    """
    app = InfoApp(message)
    try:
        driver(app)
    except (KeyboardInterrupt, SystemExit):
        raise  # Let these propagate naturally
    except Exception as exc:
        msg = f"Failed to display TUI: {exc}"
        raise TuiDisplayError(msg) from exc


def main(*, show_tui: bool = True, driver: Callable[[InfoApp], None] = _run_app) -> int:
    """Entry point for the TUI script.

    Args:
        show_tui: When ``False``, write the info to stdout instead of starting
            the TUI (useful for headless environments and tests).
        driver: Optional driver callable for running the TUI app.

    Returns:
        int: ``0`` on success, ``1`` if the TUI could not be displayed.
    """
    info_message = build_info_message()
    logger.info("TUI entry point invoked. show_tui=%s", show_tui)

    if not show_tui:
        logger.info("TUI display skipped; writing info to stdout.")
        _ = sys.stdout.write(f"{info_message}\n")
        return 0

    try:
        _display_tui(info_message, driver=driver)
    except TuiDisplayError:
        logger.exception("Failed to display TUI; falling back to stdout.")
        _ = sys.stdout.write(f"{info_message}\n")
        return 1

    logger.info("TUI application closed successfully.")
    return 0
>>>>>>> after updating
