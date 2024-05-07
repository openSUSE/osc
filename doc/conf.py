# Configuration file for the Sphinx documentation builder.
#
# This file only contains a selection of the most common options. For a full
# list see the documentation:
# https://www.sphinx-doc.org/en/master/usage/configuration.html

# -- Path setup --------------------------------------------------------------

# If extensions (or modules to document with autodoc) are in another directory,
# add these directories to sys.path here. If the directory is relative to the
# documentation root, use os.path.abspath to make it absolute, like shown here.
#
import os
import sys
import textwrap

TOPDIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(TOPDIR, ".."))

import osc.conf


# -- Project information -----------------------------------------------------

project = 'osc'
copyright = 'Contributors to the osc project'
author = 'see the AUTHORS list'


# -- General configuration ---------------------------------------------------

# Add any Sphinx extension module names here, as strings. They can be
# extensions coming with Sphinx (named 'sphinx.ext.*') or your custom
# ones.
extensions = [
    'sphinx.ext.todo',
    'sphinx.ext.autodoc',
    'sphinx.ext.doctest',
    'sphinx.ext.ifconfig',
]

# Add any paths that contain templates here, relative to this directory.
templates_path = ['_templates']

# List of patterns, relative to source directory, that match files and
# directories to ignore when looking for source files.
# This pattern also affects html_static_path and html_extra_path.
exclude_patterns = ['_build', 'Thumbs.db', '.DS_Store']

# A string of reStructuredText that will be included at the end of every
# source file that is read. This is a possible place to add substitutions
# that should be available in every file.
rst_epilog = """
.. |obs| replace:: open build service
"""

master_doc = 'index'

# order members by __all__ or their order in the source code
autodoc_default_options = {
    'member-order': 'bysource',
}

autodoc_typehints = "both"

# -- Generate documents -------------------------------------------------

osc.conf._model_to_rst(
    cls=osc.conf.Options,
    title="Configuration file",
    description=textwrap.dedent(
        """
        The configuration file path is ``$XDG_CONFIG_HOME/osc/oscrc``, which usually translates into ``~/.config/osc/oscrc``.

        The configuration options are loaded with the following priority:
            1. environment variables: ``OSC_<uppercase_option>`` or ``OSC_<uppercase_host_alias>_<uppercase_host_option>``
            2. command-line options
            3. oscrc config file
        """
    ),
    sections={
        "Host options": osc.conf.HostOptions,
    },
    output_file=os.path.join(TOPDIR, "oscrc.rst"),
)


# -- Options for HTML output -------------------------------------------------

# The theme to use for HTML and HTML Help pages.  See the documentation for
# a list of builtin themes.
#
# html_theme = 'alabaster'
html_theme = 'sphinx_rtd_theme'

# Add any paths that contain custom static files (such as style sheets) here,
# relative to this directory. They are copied after the builtin static files,
# so a file named "default.css" will overwrite the builtin "default.css".
html_static_path = ['_static']

html_css_files = [
    # fixes https://github.com/readthedocs/sphinx_rtd_theme/issues/1301
    'css/custom.css',
]


# -- Options for MAN output -------------------------------------------------

# (source start file, name, description, authors, manual section).
man_pages = [
    ("oscrc", "oscrc", "openSUSE Commander configuration file", "openSUSE project <opensuse-buildservice@opensuse.org>", 5),
]
