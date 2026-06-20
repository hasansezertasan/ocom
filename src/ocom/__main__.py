"""Entry point for ocom CLI."""

from __future__ import annotations

import argparse

from ocom import __version__
from ocom.app import run


def main() -> None:
    """Parse CLI arguments and launch the ocom TUI.

    With no arguments the Textual app starts. ``--version`` and ``--help`` print
    and exit without launching, so the packaged Nuitka binary can be smoke-tested
    in a headless CI environment where launching the TUI would hang.
    """
    parser = argparse.ArgumentParser(
        prog="ocom",
        description="Unified TUI for managing network/privacy tools.",
    )
    parser.add_argument(
        "--version",
        action="version",
        version=f"%(prog)s {__version__}",
    )
    parser.parse_args()
    run()


if __name__ == "__main__":
    main()
