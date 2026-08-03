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
        __version__ = "0.0.0"

__all__ = ["__version__"]
