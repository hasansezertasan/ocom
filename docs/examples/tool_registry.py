"""List the tools the TUI dashboard manages, without starting it."""

from __future__ import annotations

from ocom.core.tools import get_all_tools


def tool_names() -> list[str]:
    """Return the names of the tools available on this platform.

    Returns:
        list[str]: One name per tool card the dashboard shows.
    """
    return [tool.name for tool in get_all_tools()]
