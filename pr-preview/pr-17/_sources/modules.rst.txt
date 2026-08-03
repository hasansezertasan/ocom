.. Keep every underline LONGER than its title: an underline whose length equals
   the title (e.g. a 7-char "=" under "Modules") is treated as a merge-conflict
   separator by ``git diff --check`` / ``check-merge-conflict``.

Modules
=================

An overview of the packages that make up ``ocom``.
The API reference below is generated automatically from the source docstrings.

Application (``ocom.app``)
----------------------------------

The Textual application entry point.

.. automodule:: ocom.app

Configuration (``ocom.config``)
----------------------------------

Pydantic-settings based configuration.

.. automodule:: ocom.config

Core (``ocom.core``)
----------------------------------

Shared abstractions: the ``BaseTool`` interface and the subprocess
``ProcessManager``.

.. automodule:: ocom.core.tool

.. automodule:: ocom.core.process

Tools (``ocom.tools``)
----------------------------------

Concrete tool implementations (OpenVPN, SpoofDPI, GoodbyeDPI, WARP, Tailscale).

.. automodule:: ocom.tools

User interface (``ocom.ui``)
----------------------------------

Textual screens and widgets.

.. automodule:: ocom.ui.screens.main

.. automodule:: ocom.ui.widgets.tool_card

.. automodule:: ocom.ui.widgets.log_panel
