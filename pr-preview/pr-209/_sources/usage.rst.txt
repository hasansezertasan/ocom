Usage
===========

``ocom`` manages network/privacy tools (OpenVPN, SpoofDPI/GoodbyeDPI, Cloudflare
WARP, Tailscale) through a Textual terminal user interface, with a small
command-line interface built into the same ``ocom`` command.

Launching the TUI
--------------------

Run the ``interactive`` subcommand to start the terminal user interface:

.. code-block:: sh

   ocom interactive

Inside the app, each tool card shows the tool's status and an action button to
install, start, or stop it. Starting a tool automatically stops any running tool
it conflicts with.

The tools the dashboard shows can also be listed from Python, without starting
the TUI:

.. literalinclude:: examples/tool_registry.py
   :language: python
   :caption: examples/tool_registry.py

Command-line interface
--------------------------

Running ``ocom`` with no arguments (or ``ocom --help``) lists the subcommands:

.. code-block:: sh

   ocom version   # print the installed version
   ocom info      # print version, Python, and platform details

Or invoke it programmatically from Python:

.. literalinclude:: examples/cli_usage.py
   :language: python
   :caption: examples/cli_usage.py

Look up the installed distribution version:

.. literalinclude:: examples/version_lookup.py
   :language: python
   :caption: examples/version_lookup.py

For short interactive snippets embedded in prose, the ``docs-doctest`` task
executes ``>>>`` blocks too:

.. doctest::

   >>> from ocom.__metadata__ import PROJECT_NAME
   >>> PROJECT_NAME
   'ocom'
