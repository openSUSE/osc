try:
    from typeguard import install_import_hook
except ImportError:
    install_import_hook = None

if not install_import_hook:
    try:
        from typeguard.importhook import install_import_hook
    except ImportError:
        install_import_hook = None

if install_import_hook:
    # install typeguard import hook only if available
    install_import_hook("osc")
