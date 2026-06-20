"""Log panel widget for displaying tool output."""

from datetime import datetime

from textual.app import ComposeResult
from textual.widgets import RichLog, Static


class LogPanel(Static):
    """A panel for displaying logs from running tools."""

    # Color mapping for log sources
    SOURCE_COLORS = {
        "OpenVPN": "green",
        "WARP": "cyan",
        "Tailscale": "blue",
        "SpoofDPI": "yellow",
        "GoodbyeDPI": "yellow",  # Same as SpoofDPI (same function)
        "SYSTEM": "bold magenta",
    }

    def compose(self) -> ComposeResult:
        yield RichLog(id="log-output", highlight=True, markup=True)

    @property
    def _log_widget(self) -> RichLog:
        """Get the log output widget."""
        return self.query_one("#log-output", RichLog)

    def _write_log(self, source: str, message: str) -> None:
        """Write a formatted log entry."""
        timestamp = datetime.now().strftime("%H:%M:%S")
        color = self.SOURCE_COLORS.get(source, "white")
        self._log_widget.write(f"[dim]{timestamp}[/dim] [{color}]{source}[/{color}]: {message}")

    def add_log(self, tool_name: str, message: str) -> None:
        """Add a log entry from a tool.

        Named ``add_log`` rather than ``log`` to avoid shadowing the ``log``
        logger attribute that Textual's ``MessagePump`` provides on every widget.
        """
        self._write_log(tool_name, message)

    def log_system(self, message: str) -> None:
        """Add a system log entry."""
        self._write_log("SYSTEM", message)

    def clear(self) -> None:
        """Clear all log entries."""
        self._log_widget.clear()
