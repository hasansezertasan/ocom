Installation
============

<<<<<<< before updating
``ocom`` is an end-user application, not a library, so install it as a
standalone tool rather than as a project dependency. It ships a single
``ocom`` command that launches the TUI.
=======
``ocom`` is a library. Add it to your project as a dependency.
>>>>>>> after updating

Stable release
--------------

<<<<<<< before updating
Install ``ocom`` into an isolated environment with your preferred tool
installer:

.. code-block:: sh

   uv tool install ocom

.. code-block:: sh

   pipx install ocom

Or run it without installing:

.. code-block:: sh

   uvx ocom

On macOS/Linux, install it from the
`Homebrew tap <https://github.com/hasansezertasan/homebrew-tap>`_:
=======
To add ``ocom`` to your project, run this command in your
terminal:
>>>>>>> after updating

.. code-block:: sh

   brew install hasansezertasan/tap/ocom

On Windows, install it from the
`Scoop bucket <https://github.com/hasansezertasan/scoop-bucket>`_:

.. code-block:: sh

   scoop bucket add hasansezertasan https://github.com/hasansezertasan/scoop-bucket
   scoop install ocom

From source
-----------

The source files for ``ocom`` can be downloaded from the
`GitHub repo <https://github.com/hasansezertasan/ocom>`_.

You can either clone the public repository:

.. code-block:: sh

   git clone https://github.com/hasansezertasan/ocom.git

Or download the
`tarball <https://github.com/hasansezertasan/ocom/tarball/main>`_:

.. code-block:: sh

   mkdir ocom
   curl -fL https://github.com/hasansezertasan/ocom/tarball/main | tar -xz --strip-components=1 -C ocom

Once you have a copy of the source, you can install it with:

.. code-block:: sh

   cd ocom
   uv sync
