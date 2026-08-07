Usage
===========

``ocom`` is a terminal user interface (TUI). After installation, launch it from
your shell:

.. code-block:: sh

   ocom

Or run it as a module:

.. code-block:: sh

   python -m ocom

Print the version and exit (useful for smoke-testing a packaged build):

.. code-block:: sh

   ocom --version

Inside the app, each tool card shows the tool's status and an action button to
install, start, or stop it. Starting a tool automatically stops any running tool
it conflicts with.
