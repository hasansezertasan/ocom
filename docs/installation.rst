Installation
============

Possible extras:

- ``all``: Installs all extras if available.

Stable release
--------------

To install ``ocom``, run this command in your terminal:

.. code-block:: sh

   uv add ocom

Or if you prefer to use ``pip``:

.. code-block:: sh

   pip install ocom

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
   uv pip install .
