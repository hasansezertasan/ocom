"""Tool card widget for displaying tool status."""

from typing import Any

from textual.app import ComposeResult
from textual.containers import Horizontal, Vertical
from textual.message import Message
from textual.reactive import reactive
from textual.widgets import Button, Label, Static

from ocom.core.tool import BaseTool, ToolStatus

# Status icons mapping
STATUS_ICONS = {
    ToolStatus.RUNNING: "●",
    ToolStatus.STOPPED: "○",
    ToolStatus.UNAVAILABLE: "◌",
    ToolStatus.STARTING: "⟳",
    ToolStatus.STOPPING: "⟳",
    ToolStatus.ERROR: "✕",
}


class ToolCard(Static):
    """A card widget displaying a single tool's status and controls."""

    status: reactive[ToolStatus] = reactive(ToolStatus.UNAVAILABLE, init=False)

    class ToolAction(Message):
        """Message sent when a tool action is requested."""

        def __init__(self, tool: BaseTool, action: str) -> None:
            self.tool = tool
            self.action = action
            super().__init__()

    def __init__(self, tool: BaseTool, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self.tool = tool

    def compose(self) -> ComposeResult:
        """Compose the card layout."""
        with Horizontal(classes="card-content"):
            with Vertical(classes="tool-info"):
                yield Label(
                    f"{self._status_icon} {self.tool.name}", classes="tool-name"
                )
                yield Label(
                    self.tool.get_status_text(), classes="tool-status", id="status-text"
                )
            with Vertical(classes="buttons"):
                yield Button("Start", id="toggle-btn", variant="primary")

    def on_mount(self) -> None:
        """Update UI on mount."""
        self.status = self.tool.status
        self._update_display()

    def watch_status(self, new_status: ToolStatus) -> None:
        """React to status changes."""
        if self.is_mounted:
            self._update_display()

    def _update_display(self) -> None:
        """Update the card display based on current status."""
        # Update CSS classes
        self.remove_class("unavailable", "running", "error", "stopped")
        self.add_class(self.status.value)

        # Update status text
        status_label = self.query_one("#status-text", Label)
        status_label.update(self.tool.get_status_text())

        # Update name with status icon
        name_label = self.query_one(".tool-name", Label)
        name_label.update(f"{self._status_icon} {self.tool.name}")

        # Update toggle button
        toggle_btn = self.query_one("#toggle-btn", Button)
        if self.status == ToolStatus.UNAVAILABLE:
            toggle_btn.disabled = False
            toggle_btn.label = "Install"
            toggle_btn.variant = "warning"
        elif self.status.can_start:
            toggle_btn.disabled = False
            toggle_btn.label = "Start"
            toggle_btn.variant = "primary"
        elif self.status.can_stop:
            toggle_btn.disabled = False
            toggle_btn.label = "Stop"
            toggle_btn.variant = "error"
        elif self.status.is_transitioning:
            toggle_btn.disabled = True
            toggle_btn.label = "..."

    @property
    def _status_icon(self) -> str:
        """Get the status indicator icon for current status."""
        return STATUS_ICONS.get(self.status, "?")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        """Handle button presses."""
        if event.button.id == "toggle-btn":
            if self.status == ToolStatus.UNAVAILABLE:
                self.post_message(self.ToolAction(self.tool, "install"))
            elif self.status.can_start:
                self.post_message(self.ToolAction(self.tool, "start"))
            elif self.status.can_stop:
                self.post_message(self.ToolAction(self.tool, "stop"))

    def refresh_status(self, new_status: ToolStatus) -> None:
        """Update the card with a new status."""
        self.status = new_status
