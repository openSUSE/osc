"""
Store class wraps access to files in the '.osc' directory.
It is meant to be used as an implementation detail of Project and Package classes
and shouldn't be used in any code outside osc.
"""


import os
from xml.etree import ElementTree as ET

from . import oscerr
from . import git_scm
from .obs_scm import Store


def get_store(path, check=True, print_warnings=False):
    """
    Return a store object that wraps SCM in given `path`:
     - Store for OBS SCM
     - GitStore for Git SCM
    """

    # if there are '.osc' and '.git' directories next to each other, '.osc' takes preference
    if os.path.exists(os.path.join(path, ".osc")):
        store = Store(path, check)
    elif os.path.exists(os.path.join(path, ".git")):
        store = git_scm.GitStore(path, check)
        if print_warnings:
            git_scm.warn_experimental()
    else:
        store = None

    if not store:
        msg = f"Directory '{path}' is not a working copy"
        raise oscerr.NoWorkingCopy(msg)

    return store
