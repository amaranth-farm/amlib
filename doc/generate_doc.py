
import os
import shutil

from jinja2 import Environment, FileSystemLoader
from sphinx.application import Sphinx
from sphinx.util.docutils import docutils_namespace

DOCDIR = os.path.join(os.path.abspath("."), "doc")
BUILD_DIR = os.path.join(DOCDIR, "build")

TEST_JINJA_DICT = {
    "hdl_diagrams_path": "'{}'".format(DOCDIR),
    "master_doc": "'nmigen_library'",
    "custom_variables": "''"
}

sphinx_dirs = {
    "srcdir": DOCDIR,
    "confdir": DOCDIR,
    "outdir": BUILD_DIR,
    "doctreedir": os.path.join(BUILD_DIR, "doctrees")
}

# Run the Sphinx
with docutils_namespace():
    app = Sphinx(buildername="html", warningiserror=True, **sphinx_dirs)
    app.build(force_all=True)
