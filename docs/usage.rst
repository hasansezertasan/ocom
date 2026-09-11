Usage
===========

``ocom`` manages network/privacy tools (OpenVPN, SpoofDPI/GoodbyeDPI, Cloudflare
WARP, Tailscale) through a Textual terminal user interface, with a small
command-line interface built into the same ``ocom`` command.

<<<<<<< before updating
Launching the TUI
--------------------

Run ``ocom`` with no arguments to start the terminal user interface:
=======
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

As a command-line tool
----------------------

To use ``ocom`` as a command-line tool:
>>>>>>> after updating

.. code-block:: sh

   ocom

Inside the app, each tool card shows the tool's status and an action button to
install, start, or stop it. Starting a tool automatically stops any running tool
it conflicts with.

Command-line interface
--------------------------

The same ``ocom`` command exposes a few subcommands (see ``ocom --help``):

.. code-block:: sh

<<<<<<< before updating
   ocom version   # print the installed version
   ocom info      # print version, Python, and platform details
=======
   ocom interactive
>>>>>>> after updating
