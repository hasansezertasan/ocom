"""Sphinx configuration for ocom.

See https://www.sphinx-doc.org/en/master/usage/configuration.html
"""

from __future__ import annotations

<<<<<<< before updating
from datetime import UTC, datetime
=======
import json
import os
from datetime import datetime, timezone
from pathlib import Path
>>>>>>> after updating

# -- Project information -----------------------------------------------------
project = "ocom"
author = "Hasan Sezer Tasan"
<<<<<<< before updating
copyright = f"{datetime.now(tz=UTC):%Y}, Hasan Sezer Tasan"
=======
# Reproducible builds: honor SOURCE_DATE_EPOCH (https://reproducible-builds.org/)
# so the stamped copyright year is a function of the source (e.g. the last
# commit date, as exported by the CI docs steps) rather than the clock. Local
# `tox` runs leave it unset and fall back to the current year below.
_source_date_epoch = os.environ.get("SOURCE_DATE_EPOCH")
_build_date = (
    datetime.fromtimestamp(int(_source_date_epoch), tz=timezone.utc)
    if _source_date_epoch
    else datetime.now(tz=timezone.utc)
)
copyright = f"{_build_date:%Y}, Hasan Sezer Tasan"  # noqa: A001
>>>>>>> after updating

# -- General configuration ---------------------------------------------------
extensions = [
    "sphinx.ext.autodoc",
    "sphinx.ext.doctest",
    "sphinx.ext.napoleon",
    "sphinx.ext.intersphinx",
    "sphinx.ext.autosectionlabel",
    "sphinx.ext.viewcode",
    "sphinx.ext.githubpages",  # emits .nojekyll so GitHub Pages serves _static/
    "sphinx_design",
    "sphinx_copybutton",
    "sphinx_togglebutton",
    "sphinx_paramlinks",
    "auto_pytabs.sphinx_ext",
    "myst_parser",
    "sphinx_last_updated_by_git",
    "sphinxcontrib.autodoc_pydantic",
]

# Both reStructuredText and (via MyST) Markdown source files are supported.
source_suffix = {".rst": "restructuredtext", ".md": "markdown"}
# ``_generated`` holds machine-generated reference material (CLI Markdown, etc.)
# that is ``{include}``d/``literalinclude``d into real pages; exclude it so those
# fragments are not also built as standalone orphan documents.
exclude_patterns = ["_build", "Thumbs.db", ".DS_Store", "_generated"]

# autosectionlabel can emit duplicate-label warnings across documents; the
# document prefix keeps them unique, so no blanket suppression is needed.
autosectionlabel_prefix_document = True

# -- Autodoc / Napoleon ------------------------------------------------------
autodoc_default_options = {
    "members": True,
    "show-inheritance": True,
    "member-order": "bysource",
}
autodoc_typehints = "description"
autoclass_content = "both"
napoleon_google_docstring = True
napoleon_numpy_docstring = False

# -- autodoc-pydantic --------------------------------------------------------
# https://autodoc-pydantic.readthedocs.io/
# Render the Configuration reference straight from the live ``core.config``
# settings model so the documented fields, types, defaults, and constraints
# never drift from what the model defines. The config summary surfaces the
# model's ``env_prefix`` (e.g. ``EXAMPLE_``); the actual environment variable
# for a field is that prefix + the uppercased field name (autodoc-pydantic
# 2.2.0 has no option to render those fully-qualified per-field names itself,
# so the Configuration page documents the composition rule). Trim the raw JSON
# schema and validator noise; keep the field summary and per-field constraints
# (min/max, patterns) that matter for configuring the app.
autodoc_pydantic_settings_show_json = False
autodoc_pydantic_settings_show_config_summary = True
autodoc_pydantic_settings_show_field_summary = True
autodoc_pydantic_settings_show_validator_summary = False
autodoc_pydantic_settings_show_validator_members = False
autodoc_pydantic_field_show_constraints = True
autodoc_pydantic_field_show_default = True

# -- auto-pytabs -------------------------------------------------------------
# Keep the version tabs in sync with this project's supported Python range
# (requires-python >= 3.10, classifiers/CI up to 3.14). auto-pytabs otherwise
# defaults to (3, 7), which would mislabel the rendered examples.
auto_pytabs_min_version = (3, 10)
auto_pytabs_max_version = (3, 14)

# -- Intersphinx -------------------------------------------------------------
intersphinx_mapping = {"python": ("https://docs.python.org/3", None)}
intersphinx_mapping["pydantic"] = ("https://docs.pydantic.dev/latest", None)


# -- HTML output (Shibuya theme) ---------------------------------------------
# https://shibuya.lepture.com/
html_theme = "shibuya"
html_title = "ocom"
html_theme_options = {
    "accent_color": "amber",
    "github_url": "https://github.com/hasansezertasan/ocom",
}

# -- Versioned docs switcher (ADR-027) ---------------------------------------
# tools/build_docs.py writes docs/_static/versions.json into each CI build from
# the gh-pages directory listing. When present, feed the Shibuya theme's native
# version switcher (components/nav-versions.html) via html_context. Absent (e.g.
# a local ``tox -e docs-build`` run) the switcher simply does not render.
# GitHub Pages serves a project site under ``/<repo>/``, so switcher links are
# rooted at that base path (not the domain root); a custom root domain would set
# ``_switcher_base = "/"`` instead.
_switcher_base = "/ocom/"
_versions_file = Path(__file__).parent / "_static" / "versions.json"
if _versions_file.exists():
    _versions = json.loads(_versions_file.read_text(encoding="utf-8"))
    _current = os.environ.get("DOCS_BUILD_VERSION_SLUG") or _versions.get("latest", "")
    html_context = {
        "current_version": _current,
        "versions": [
            ["latest", f"{_switcher_base}latest/"],
            *([slug, f"{_switcher_base}{slug}/"] for slug in _versions["versions"]),
        ],
    }

# -- Generated interface schemas and reference material ----------------------
# Emit the project's machine-readable interface contracts and CLI reference
# straight from the live ``app`` objects so the reference pages can
# ``literalinclude`` (or MyST-``{include}``) an always-in-sync description of
# channels/routes, payload/response schemas, status codes, and CLI commands.
# Each is derived from the source of truth (the ``description=`` strings and the
# Pydantic/response models already on the code, and the live Typer app),
# regenerated on every docs build, and is not committed (``docs/_generated/`` is
# gitignored). Each generator runs with ``check=True``, so a broken app import or
# a failed generation raises and fails the docs build.
import subprocess  # noqa: E402, S404
import sys  # noqa: E402

_generated_dir = Path(__file__).parent / "_generated"
_generated_dir.mkdir(exist_ok=True)

# The Typer CLI reference (commands, options, defaults, and any component
# subcommands) generated from the live ``ocom.cli.app`` app; the
# "CLI reference" page ``{include}``s the emitted Markdown. ``include_cli`` always
# makes the CLI the primary component, so the documented program name is the bare
# ``ocom`` console script.
subprocess.run(  # noqa: S603
    [
        sys.executable,
        "-m",
        "typer",
        "ocom.cli.app",
        "utils",
        "docs",
        "--name",
        "ocom",
        "--output",
        str(_generated_dir / "cli.md"),
    ],
    check=True,
)
