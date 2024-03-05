import sys
from typing import Optional

from . import tty


def print_msg(*args, print_to: Optional[str] = "debug"):
    """
    Print ``*args`` to the ``print_to`` target:
      - None: print nothing
      - debug: print() to stderr with "DEBUG:" prefix if config["debug"] is set
      - verbose: print() to stdout if config["verbose"] or config["debug"] is set
      - error: print() to stderr with red "ERROR:" prefix
      - warning: print() to stderr with yellow "WARNING:" prefix
      - stdout: print() to stdout
      - stderr: print() to stderr
    """
    from .. import conf

    if print_to is None:
        return
    elif print_to == "debug":
        # print a debug message to stderr if config["debug"] is set
        if conf.config["debug"]:
            print("DEBUG:", *args, file=sys.stderr)
    elif print_to == "verbose":
        # print a verbose message to stdout if config["verbose"] or config["debug"] is set
        if conf.config["verbose"] or conf.config["debug"]:
            print(*args)
    elif print_to == "error":
        print(tty.colorize("ERROR:", "red,bold"), *args, file=sys.stderr)
    elif print_to == "warning":
        print(tty.colorize("WARNING:", "yellow,bold"), *args, file=sys.stderr)
    elif print_to == "stdout":
        # print the message to stdout
        print(*args)
    elif print_to == "stderr":
        # print the message to stderr
        print(*args, file=sys.stderr)
    else:
        raise ValueError(f"Invalid value of the 'print_to' option: {print_to}")
