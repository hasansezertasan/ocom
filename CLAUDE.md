# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

ocom is a unified Terminal User Interface (TUI) for managing network/privacy tools: OpenVPN, SpoofDPI/GoodbyeDPI, and Cloudflare WARP. Built with Textual (Python 3.14+). Cross-platform: macOS, Linux, and Windows.

## Development Commands

```bash
# Install dependencies
uv sync --dev

# Run the app
uv run ocom
# or
python -m ocom

# Run tests
uv run pytest
uv run pytest tests/test_file.py::test_name # single test

# Lint and format
uv run ruff check .
uv run ruff format .
uv run ruff check --fix . # auto-fix
```

## Architecture

### Core Abstractions (`src/ocom/core/`)

- **BaseTool** (`tool.py`): Abstract base class all tools inherit from. Defines the interface: `check_available()`, `start(config)`, `stop()`, `refresh_status()`, output callback registration, `install_url` for documentation links, and `conflicts_with` for declaring tool conflicts.
- **ToolStatus** (`tool.py`): Enum with states: UNAVAILABLE, STOPPED, STARTING, RUNNING, STOPPING, ERROR. Has helper properties `is_transitioning`, `can_start`, `can_stop`.
- **ToolConfig** (`tool.py`): Dataclass for tool instance configuration (config files, dirs, extra args, options).
- **ProcessManager** (`process.py`): Subprocess handling - `run_command()`, `start_process()`, `stop_process()`, `find_command()`.

### Tool Implementations (`src/ocom/tools/`)

| Tool           | Command      | Sudo      | Platform | Notes                                                                                                                                                |
| -------------- | ------------ | --------- | -------- | ---------------------------------------------------------------------------------------------------------------------------------------------------- |
| OpenVPNTool    | `openvpn`    | Unix only | All      | Uses `.ovpn` config files. Unix: sudo via stdin. Windows: needs Admin. Conflicts with WARP.                                                          |
| SpoofDPITool   | `spoofdpi`   | No        | Unix     | Configurable port/DNS, status via process check.                                                                                                     |
| GoodbyeDPITool | `goodbyedpi` | No        | Windows  | DPI bypass, runs in modes 1-9. Conflicts with SpoofDPI.                                                                                              |
| WarpTool       | `warp-cli`   | No        | All      | Uses CLI commands (connect/disconnect), status from `warp-cli status`. Conflicts with OpenVPN.                                                       |
| TailscaleTool  | `tailscale`  | No        | All      | Mesh VPN via `tailscale up`/`down`, status from `tailscale status --json`. No conflicts (mesh mode coexists; revisit if exit-node support is added). |

### UI Layer (`src/ocom/ui/`)

**Screens** (`screens/main.py`):

- MainScreen - Dashboard with tool cards grid + log panel
- ConfigSelectorScreen - Modal for selecting config files (OptionList)
- PasswordPromptScreen - Modal for sudo password entry

**Widgets** (`widgets/`):

- ToolCard - Displays tool status with action button (Install/Start/Stop). Uses Textual reactive attributes. Shows "Install" when tool unavailable.
- LogPanel - RichLog-based scrollable log with timestamped, color-coded entries.

**Message Flow**: Button press → ToolCard.ToolAction message → MainScreen handler → (optional modals) → tool.start/stop → output callbacks → LogPanel.

### Configuration (`config.py`)

Uses Pydantic-settings with TOML. Config file: `~/.config/ocom/config.toml`

## Adding a New Tool

1. Create `src/ocom/tools/newtool.py` implementing `BaseTool`:

   ```python
   class NewTool(BaseTool):
       name = "NewTool"
       command = "newtool"  # CLI command to check availability
       requires_sudo = False
       supports_configs = False
       install_url = "https://example.com/newtool/install"
       conflicts_with = []  # e.g., ["WARP", "OpenVPN"] if it's a VPN

       async def start(self, config: ToolConfig) -> bool: ...
       async def stop(self) -> bool: ...
       async def refresh_status(self) -> ToolStatus: ...
   ```

2. Register in `src/ocom/tools/__init__.py` `get_all_tools()`

3. Add config section to `config.py` if needed

4. Add color to `LogPanel.SOURCE_COLORS` (optional)

## Code Style

- Line length: 100 characters
- Ruff rules: E, F, I, UP, B, SIM
- Async-first: All I/O operations use asyncio
- Type hints throughout (Python 3.14+)
- Pydantic for validation and settings

## Key Patterns

- **Output streaming**: Tools emit output via `_emit_output()` → registered callback → LogPanel
- **Reactive UI**: ToolCard uses Textual's reactive `status` attribute for automatic updates
- **Graceful shutdown**: ProcessManager uses cross-platform terminate() for process cleanup
- **Dependency injection**: Tools receive ToolConfig with runtime settings
- **Conflict resolution**: Starting a tool auto-stops any running tools listed in `conflicts_with`
