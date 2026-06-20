"""Main dashboard screen."""

import webbrowser
from pathlib import Path
from typing import Any

from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical
from textual.css.query import NoMatches
from textual.screen import ModalScreen, Screen
from textual.widgets import Button, Footer, Header, Input, Label, OptionList, Static
from textual.widgets.option_list import Option

from ocom.config import AppConfig
from ocom.core.tool import BaseTool, ToolConfig, ToolStatus
from ocom.tools import get_all_tools
from ocom.ui.widgets.log_panel import LogPanel
from ocom.ui.widgets.tool_card import ToolCard


class ConfigSelectorScreen(ModalScreen[str | None]):
    """Modal screen for selecting a config file."""

    BINDINGS = [
        Binding("escape", "cancel", "Cancel"),
    ]

    def __init__(self, tool: BaseTool, configs: list[str], **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self.tool = tool
        self.configs = configs

    def compose(self) -> ComposeResult:
        with Vertical(id="modal-container"):
            yield Label(f"Select config for {self.tool.name}", id="modal-title")
            options = [Option(Path(c).name, id=c) for c in self.configs]
            yield OptionList(*options, id="config-options")
            with Horizontal(id="modal-buttons"):
                yield Button("Cancel", variant="default", id="btn-cancel")

    def on_mount(self) -> None:
        """Focus the option list when mounted."""
        self.query_one("#config-options", OptionList).focus()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        """Handle button press."""
        if event.button.id == "btn-cancel":
            self.dismiss(None)

    def on_option_list_option_selected(self, event: OptionList.OptionSelected) -> None:
        """Handle config selection."""
        self.dismiss(str(event.option.id))

    def action_cancel(self) -> None:
        """Cancel and close modal."""
        self.dismiss(None)


class PasswordPromptScreen(ModalScreen[str | None]):
    """Modal screen for entering sudo password."""

    BINDINGS = [
        Binding("escape", "cancel", "Cancel"),
    ]

    def __init__(self, tool: BaseTool, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self.tool = tool

    def compose(self) -> ComposeResult:
        with Vertical(id="modal-container"):
            yield Label(f"{self.tool.name} - Authentication", id="modal-title")
            yield Label("This tool requires sudo privileges.")
            yield Label("Enter your password:")
            yield Input(password=True, id="password-input", placeholder="Password")
            with Horizontal(id="modal-buttons"):
                yield Button("Cancel", variant="default", id="btn-cancel")
                yield Button("Connect", variant="primary", id="btn-connect")

    def on_mount(self) -> None:
        """Focus the password input."""
        self.query_one("#password-input", Input).focus()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        """Handle button press."""
        if event.button.id == "btn-connect":
            self._submit_password()
        elif event.button.id == "btn-cancel":
            self.dismiss(None)

    def on_input_submitted(self, event: Input.Submitted) -> None:
        """Handle Enter key in password field."""
        self._submit_password()

    def _submit_password(self) -> None:
        """Submit the password."""
        password = self.query_one("#password-input", Input).value
        self.dismiss(password)

    def action_cancel(self) -> None:
        """Cancel and close modal."""
        self.dismiss(None)


class MainScreen(Screen):
    """Main dashboard showing all network tools."""

    BINDINGS = [
        Binding("q", "quit", "Quit"),
        Binding("r", "refresh", "Refresh"),
        Binding("c", "clear_logs", "Clear Logs"),
    ]

    def __init__(self, config: AppConfig, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self.config = config
        self.tools = get_all_tools()
        self._cards: dict[str, ToolCard] = {}

    def compose(self) -> ComposeResult:
        yield Header()
        with Horizontal(id="main-content"):
            with Vertical(id="tool-grid"):
                for tool in self.tools:
                    card = ToolCard(tool, id=f"card-{tool.name.lower()}")
                    self._cards[tool.name] = card
                    yield card
            yield LogPanel(id="log-panel")
        yield Static("Ready", id="status-bar")
        yield Footer()

    async def on_mount(self) -> None:
        """Initialize tools and start status refresh."""
        # Set up output callbacks for all tools
        for tool in self.tools:
            tool.set_output_callback(self._handle_tool_output)

        # Check tool availability
        for tool in self.tools:
            await tool.check_available()
            self._cards[tool.name].refresh_status(tool.status)

        # Log initial status
        self.query_one("#log-panel", LogPanel).log_system("ocom started")

        # Start periodic status refresh
        self.set_interval(
            self.config.general.refresh_interval,
            self._refresh_all_statuses,
        )

        # Try auto-connect if enabled
        self._try_auto_connect()

    def _handle_tool_output(self, tool_name: str, message: str) -> None:
        """Handle output from a tool and display in log panel."""
        try:
            log_panel = self.query_one("#log-panel", LogPanel)
        except NoMatches:
            return  # Panel not mounted yet; drop early output
        log_panel.add_log(tool_name, message)

    def _get_tool_by_name(self, name: str) -> BaseTool | None:
        """Find a tool by name."""
        for tool in self.tools:
            if tool.name == name:
                return tool
        return None

    def _try_auto_connect(self) -> None:
        """Attempt auto-connect if enabled and configured.

        Checks if:
        - auto_connect is enabled in config
        - default_config is set for OpenVPN
        - The config file exists
        - OpenVPN tool is available

        If all conditions are met, initiates the connection flow.
        """
        if not self.config.general.auto_connect:
            return

        default_config = self.config.openvpn.default_config
        if not default_config:
            return

        config_path = Path(default_config).expanduser()
        if not config_path.is_file():
            log_panel = self.query_one("#log-panel", LogPanel)
            log_panel.log_system(f"Auto-connect: config file not found: {config_path}")
            return

        openvpn_tool = self._get_tool_by_name("OpenVPN")
        if openvpn_tool is None:
            return

        if openvpn_tool.status == ToolStatus.UNAVAILABLE:
            log_panel = self.query_one("#log-panel", LogPanel)
            log_panel.log_system("Auto-connect: OpenVPN not installed")
            return

        # Build config for OpenVPN
        tool_config = self._get_tool_config(openvpn_tool)
        tool_config.config_file = str(config_path)

        log_panel = self.query_one("#log-panel", LogPanel)
        log_panel.log_system(f"Auto-connect: {config_path.name}")

        # If tool requires sudo, prompt for password
        if openvpn_tool.requires_sudo:
            self._show_password_prompt(openvpn_tool, tool_config)
        else:
            # Windows or no sudo needed - start directly
            self.run_worker(self._start_tool(openvpn_tool, tool_config))

    async def _refresh_all_statuses(self) -> None:
        """Refresh status for all tools.

        Each tool is refreshed independently so a single failing tool doesn't
        cancel the whole periodic refresh loop and leave other statuses stale.
        """
        log_panel = self.query_one("#log-panel", LogPanel)
        for tool in self.tools:
            try:
                new_status = await tool.refresh_status()
                self._cards[tool.name].refresh_status(new_status)
            except Exception as exc:
                log_panel.log_system(f"Error refreshing status for {tool.name}: {exc}")

    def on_tool_card_tool_action(self, event: ToolCard.ToolAction) -> None:
        """Handle tool actions from cards."""
        if event.action == "start":
            self._handle_start(event.tool)
        elif event.action == "stop":
            self._handle_stop(event.tool)
        elif event.action == "install":
            self._handle_install(event.tool)

    def _handle_start(self, tool: BaseTool) -> None:
        """Handle starting a tool."""
        if tool.supports_configs:
            # Need to select a config first
            self._show_config_selector(tool)
        else:
            # Start directly with tool-specific config
            config = self._get_tool_config(tool)
            self.run_worker(self._start_tool(tool, config))

    def _get_tool_config(self, tool: BaseTool) -> ToolConfig:
        """Build a ToolConfig with tool-specific options."""
        config = ToolConfig()
        if tool.name == "SpoofDPI":
            config.options = {
                "dns_addr": self.config.spoofdpi.dns_addr,
                "dns_mode": self.config.spoofdpi.dns_mode,
                "port": self.config.spoofdpi.port,
                "system_proxy": self.config.spoofdpi.system_proxy,
            }
        elif tool.name == "WARP":
            config.options = {"mode": self.config.warp.mode}
        elif tool.name == "OpenVPN":
            config.config_dirs = self.config.openvpn.config_dirs
        elif tool.name == "GoodbyeDPI":
            config.options = {
                "mode": self.config.goodbyedpi.mode,
                "block_quic": self.config.goodbyedpi.block_quic,
            }
        return config

    def _handle_stop(self, tool: BaseTool) -> None:
        """Handle stopping a tool."""
        self.run_worker(self._stop_tool(tool))

    def _handle_install(self, tool: BaseTool) -> None:
        """Handle opening install documentation for a tool."""
        if tool.install_url:
            webbrowser.open(tool.install_url)
            self._update_status_bar(f"Opened install docs for {tool.name}")
        else:
            self._update_status_bar(f"No install URL configured for {tool.name}")

    def _get_running_conflicts(self, tool: BaseTool) -> list[BaseTool]:
        """Find running tools that conflict with the given tool."""
        conflicts = []
        for other in self.tools:
            if other.name in tool.conflicts_with and other.status == ToolStatus.RUNNING:
                conflicts.append(other)
        return conflicts

    async def _start_tool(self, tool: BaseTool, config: ToolConfig) -> None:
        """Start a tool with the given config."""
        # Stop conflicting tools first
        conflicts = self._get_running_conflicts(tool)
        for conflicting_tool in conflicts:
            msg = f"Stopping {conflicting_tool.name} (conflicts with {tool.name})..."
            self._update_status_bar(msg)
            self._cards[conflicting_tool.name].refresh_status(ToolStatus.STOPPING)
            stop_success = await conflicting_tool.stop()
            self._cards[conflicting_tool.name].refresh_status(conflicting_tool.status)
            log_panel = self.query_one("#log-panel", LogPanel)

            if not stop_success:
                log_panel.log_system(
                    f"Warning: Failed to stop {conflicting_tool.name}, proceeding anyway"
                )
            else:
                log_panel.log_system(
                    f"Stopped {conflicting_tool.name} (conflicts with {tool.name})"
                )

        self._update_status_bar(f"Starting {tool.name}...")
        self._cards[tool.name].refresh_status(ToolStatus.STARTING)

        success = await tool.start(config)

        if success:
            self._update_status_bar(f"{tool.name} started")
        else:
            self._update_status_bar(
                f"Failed to start {tool.name}: {tool.error_message}"
            )

        self._cards[tool.name].refresh_status(tool.status)

    async def _stop_tool(self, tool: BaseTool) -> None:
        """Stop a tool."""
        self._update_status_bar(f"Stopping {tool.name}...")
        self._cards[tool.name].refresh_status(ToolStatus.STOPPING)

        success = await tool.stop()

        if success:
            self._update_status_bar(f"{tool.name} stopped")
        else:
            self._update_status_bar(f"Failed to stop {tool.name}")

        self._cards[tool.name].refresh_status(tool.status)

    def _show_config_selector(self, tool: BaseTool) -> None:
        """Show config file selector for a tool."""
        tool_config = self._get_tool_config(tool)
        configs = tool.get_config_files(tool_config)

        if not configs:
            if tool_config.config_dirs:
                dirs = ", ".join(tool_config.config_dirs)
            else:
                dirs = "none configured"
            self._update_status_bar(f"No config files found. Check dirs: {dirs}")
            return

        def on_config_selected(config_path: str | None) -> None:
            if config_path is None:
                return  # User cancelled

            config = self._get_tool_config(tool)
            config.config_file = config_path

            # If tool requires sudo, prompt for password
            if tool.requires_sudo:
                self._show_password_prompt(tool, config)
            else:
                self.run_worker(self._start_tool(tool, config))

        self.app.push_screen(
            ConfigSelectorScreen(tool, configs),
            on_config_selected,
        )

    def _show_password_prompt(self, tool: BaseTool, config: ToolConfig) -> None:
        """Show password prompt for sudo-requiring tools."""

        def on_password_submitted(password: str | None) -> None:
            if password is None:
                log_panel = self.query_one("#log-panel", LogPanel)
                log_panel.log_system(f"{tool.name}: connection cancelled")
                return

            config.options["sudo_password"] = password
            self.run_worker(self._start_tool(tool, config))

        self.app.push_screen(
            PasswordPromptScreen(tool),
            on_password_submitted,
        )

    def _update_status_bar(self, message: str) -> None:
        """Update the status bar message."""
        status_bar = self.query_one("#status-bar", Static)
        status_bar.update(message)

    def action_refresh(self) -> None:
        """Manually refresh all tool statuses."""
        self.run_worker(self._refresh_all_statuses())
        self._update_status_bar("Refreshed")

    def action_clear_logs(self) -> None:
        """Clear the log panel."""
        log_panel = self.query_one("#log-panel", LogPanel)
        log_panel.clear()
        log_panel.log_system("Logs cleared")

    def action_quit(self) -> None:
        """Quit the application."""
        self.app.exit()
