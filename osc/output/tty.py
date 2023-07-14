import os
import sys


IS_INTERACTIVE = os.isatty(sys.stdout.fileno())


ESCAPE_CODES = {
    "reset": "\033[0m",
    "bold": "\033[1m",
    "underline": "\033[4m",
    "black": "\033[30m",
    "red": "\033[31m",
    "green": "\033[32m",
    "yellow": "\033[33m",
    "blue": "\033[34m",
    "magenta": "\033[35m",
    "cyan": "\033[36m",
    "white": "\033[37m",
}


def colorize(text, color):
    """
    Colorize `text` if the `color` is specified and we're running in an interactive terminal.
    """
    if not IS_INTERACTIVE:
        return text

    if not color:
        return text

    result = ""
    for i in color.split(","):
        result += ESCAPE_CODES[i]
    result += text
    result += ESCAPE_CODES["reset"]
    return result
