import os
import sys
from typing import Optional
from typing import TextIO
from typing import Union

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


# Forbidden characters are nearly all control characters 0-31 with the exception of:
#   0x09 - horizontal tab (\t)
#   0x0A - line feed (\n)
#   0x0D - carriage return (\r)
# (related to CVE-2012-1095)
#
# It would be good to selectively allow 0x1B with safe & trusted escape sequences.
FORBIDDEN_BYTES = b"\x00\x01\x02\x03\x04\x05\x06\x07\x08\x0b\x0c\x0e\x0f\x10\x11\x12\x13\x14\x15\x16\x17\x18\x19\x1a\x1b\x1c\x1d\x1e\x1f"
FORBIDDEN_CHARS = dict.fromkeys(FORBIDDEN_BYTES)


def sanitize_text(text: Union[bytes, str]) -> Union[bytes, str]:
    """
    Remove forbidden characters from ``text``.
    """
    if isinstance(text, bytes):
        return text.translate(None, FORBIDDEN_BYTES)
    return text.translate(FORBIDDEN_CHARS)


def safe_print(*args, **kwargs):
    """
    A wrapper to print() that runs sanitize_text() on all arguments.
    """
    args = [sanitize_text(i) for i in args]
    print(*args, **kwargs)


def safe_write(file: TextIO, text: Union[str, bytes], *, add_newline: bool = False):
    """
    Run sanitize_text() on ``text`` and write it to ``file``.

    :param add_newline: Write a newline after writing the ``text``.
    """
    text = sanitize_text(text)
    if isinstance(text, bytes):
        file.buffer.write(text)
        if add_newline:
            file.buffer.write(os.linesep.encode("utf-8"))
    else:
        file.write(text)
        if add_newline:
            file.write(os.linesep)
