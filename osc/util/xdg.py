import os

XDG_DATA_HOME = os.environ.get("XDG_DATA_HOME", "~/.local/share")
XDG_CONFIG_HOME = os.environ.get("XDG_CONFIG_HOME", "~/.config")
XDG_STATE_HOME = os.environ.get("XDG_STATE_HOME", "~/.local/state")
XDG_CACHE_HOME = os.environ.get("XDG_CACHE_HOME", "~/.cache")
