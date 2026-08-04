"""ocom - A unified TUI for managing network/privacy tools."""

from __future__ import annotations

try:
    # Written by hatch-vcs at build/editable-install time from the Git tag.
    from ocom._version import __version__
except ImportError:  # pragma: no cover
    from importlib.metadata import PackageNotFoundError, version

    try:
        __version__ = version("ocom")
    except PackageNotFoundError:
        # Not a real release: a clearly-synthetic sentinel for an uninstalled
        # source checkout where neither _version.py nor package metadata exists.
        __version__ = "0.0.0+unknown"

__all__ = ["__version__"]
