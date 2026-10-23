Configuration
=============

ocom is configured through a `pydantic-settings
<https://docs.pydantic.dev/latest/concepts/pydantic_settings/>`_ model. Every
field below can be set via an environment variable (or a ``.env`` file) named
after the field, prefixed with the uppercased project name — for example
``debug`` is read from ``OCOM_DEBUG``.

The reference below is generated on every docs build directly from the live
:class:`~ocom.core.config.Settings` model (via
`autodoc-pydantic <https://autodoc-pydantic.readthedocs.io/>`_), so the
documented fields, types, defaults, and constraints stay in lockstep with the
code and each field's ``description=``. The rendered config summary reports the
model's ``env_prefix`` (``OCOM_``);
compose a field's environment variable by joining that prefix with the uppercased
field name as shown above (autodoc-pydantic does not render the fully-qualified
per-field names itself).

.. The ``core.config`` module is also autodoc'd on the Modules page, which owns
   the canonical index anchor for ``Settings``; ``:noindex:`` here renders the
   rich field reference without registering a duplicate object description.
.. autopydantic_settings:: ocom.core.config.Settings
   :noindex:
