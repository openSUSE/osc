import os
import sys


try:
    IS_INTERACTIVE = os.isatty(sys.stdout.fileno())
except OSError:
    IS_INTERACTIVE = False


ESCAPE_CODES = {
    "reset": "\033[0m",
    "bold": "\033[1m",
    "dim": "\033[2m",
    "italic": "\033[3m",
    "underline": "\033[4m",
    "blink": "\033[5m",
    "black": "\033[30m",
    "red": "\033[31m",
    "green": "\033[32m",
    "yellow": "\033[33m",
    "blue": "\033[34m",
    "magenta": "\033[35m",
    "cyan": "\033[36m",
    "white": "\033[37m",
    "bg_black": "\033[40m",
    "bg_red": "\033[41m",
    "bg_green": "\033[42m",
    "bg_yellow": "\033[43m",
    "bg_blue": "\033[44m",
    "bg_magenta": "\033[45m",
    "bg_cyan": "\033[46m",
    "bg_white": "\033[47m",
}


def colorize(text, color):
    """
    Colorize `text` if the `color` is specified and we're running in an interactive terminal.
    """
    if not IS_INTERACTIVE:
        return text

    if not color:
        return text

    if not text:
        return text

    result = ""
    for i in color.split(","):
        result += ESCAPE_CODES[i]
    result += text
    result += ESCAPE_CODES["reset"]
    return result
