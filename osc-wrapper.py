#!/usr/bin/env python3

"""
This wrapper allows osc to be called from the source directory during development.
"""


import os


USE_TYPEGUARD = os.environ.get("OSC_TYPEGUARD", "1").lower() in ("1", "true", "on")

if USE_TYPEGUARD:
    try:
        from typeguard import install_import_hook
    except ImportError:
        install_import_hook = None

    if install_import_hook is None:
        try:
            from typeguard.importhook import install_import_hook
        except ImportError:
            install_import_hook = None

    if install_import_hook:
        # install typeguard import hook only if available
        install_import_hook("osc")


import osc.babysitter

osc.babysitter.main()
