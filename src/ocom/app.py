"""Main Textual application for ocom."""

from pathlib import Path

from textual.app import App

from ocom.config import AppConfig
from ocom.ui.screens.main import MainScreen

# Path to the TCSS file
CSS_PATH = Path(__file__).parent / "styles" / "app.tcss"


class OcomApp(App):
    """Network tools manager TUI application."""

    TITLE = "ocom"
    SUB_TITLE = "Network Tools Manager"

    CSS_PATH = CSS_PATH if CSS_PATH.exists() else None

    def __init__(self, config: AppConfig | None = None) -> None:
        super().__init__()
        self.config = config or AppConfig.load()

    def on_mount(self) -> None:
        """Push the main screen on startup."""
        self.push_screen(MainScreen(self.config))


def run() -> None:
    """Run the ocom application."""
    app = OcomApp()
    app.run()
