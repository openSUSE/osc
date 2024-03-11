#!/usr/bin/env python3

"""
This wrapper allows osc to be called from the source directory during development.
"""


# developers and early adopters have typeguard enabled
# so they can catch and report issues early
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
else:
    import osc.oscerr
    raise osc.oscerr.PackageNotInstalled("python3-typeguard")


import osc.babysitter

osc.babysitter.main()
