import os
import platform
import re
import shlex
import subprocess
import sys
import tempfile
from typing import Dict
from typing import List
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


# cached compiled regular expressions; they are created on the first use
SANITIZE_TEXT_RE: Optional[Dict] = None


def sanitize_text(text: Union[bytes, str]) -> Union[bytes, str]:
    """
    Remove forbidden characters and escape sequences from ``text``.

    This must be run on lines or the whole text to work correctly.
    Processing blocks of constant size might lead to splitting escape sequences
    and leaving garbage characters after sanitizing.
    """
    global SANITIZE_TEXT_RE

    if not SANITIZE_TEXT_RE:
        SANITIZE_TEXT_RE = {}

        # CONTROL CHARACTERS
        # remove all control characters with the exception of:
        #   0x09 - horizontal tab (\t)
        #   0x0A - line feed (\n)
        #   0x0D - carriage return (\r)
        #   0x1B - escape - is selectively handled later as part of sanitizing escape sequences

        regex = r"[\x00-\x08\x0B\x0C\x0E-\x1A\x1C-\x1F]"
        SANITIZE_TEXT_RE["str_control"] = re.compile(regex)
        SANITIZE_TEXT_RE["bytes_control"] = re.compile(regex.encode("ascii"))

        # CSI ESCAPE SEQUENCES
        # https://en.wikipedia.org/wiki/ANSI_escape_code#CSI_codes
        # remove all but allowed CSI escape sequences

        # negative lookahead assertion that allows safe color escape sequences
        neg_allowed_csi_sequences = r"(?!\[([0-5]|[34][0-7]|;)+m)"

        # range 0x30–0x3F (OCT \040-\077) (ASCII 0–9:;<=>?); zero or more characters
        csi_parameter_bytes = r"[\x30-\x3F]*"

        # range 0x20–0x2F (OCT \040-\057) (ASCII space and !"#$%&'()*+,-./); zero or more characters
        csi_itermediate_bytes = r"[\x20-\x2F]*"

        # range 0x40–0x7E (OCT \100-\176) (ASCII @A–Z[\]^_`a–z{|}~); 1 character
        csi_final_byte = r"[\x40-\x7E]"

        regex = rf"\033{neg_allowed_csi_sequences}\[{csi_parameter_bytes}{csi_itermediate_bytes}{csi_final_byte}"
        SANITIZE_TEXT_RE["str_csi_sequences"] = re.compile(regex)
        SANITIZE_TEXT_RE["bytes_csi_sequences"] = re.compile(regex.encode("ascii"))

        # FE ESCAPE SEQUENCES
        # https://en.wikipedia.org/wiki/ANSI_escape_code#Fe_Escape_sequences
        # remove all Fe escape sequences

        # range 0x40 to 0x5F (ASCII @A–Z[\]^_); 1 character
        fe = r"[\x40-x5F]"
        regex = rf"\033{neg_allowed_csi_sequences}{fe}"
        SANITIZE_TEXT_RE["str_fe_sequences"] = re.compile(regex)
        SANITIZE_TEXT_RE["bytes_fe_sequences"] = re.compile(regex.encode("ascii"))

        # REMAINING ESCAPE CHARACTERS
        # remove all remaining escape characters that are not followed with the allowed CSI escape sequences

        regex = rf"\033{neg_allowed_csi_sequences}"
        SANITIZE_TEXT_RE["str_esc"] = re.compile(regex)
        SANITIZE_TEXT_RE["bytes_esc"] = re.compile(regex.encode("ascii"))

    if isinstance(text, bytes):
        text = SANITIZE_TEXT_RE["bytes_control"].sub(b"", text)
        text = SANITIZE_TEXT_RE["bytes_csi_sequences"].sub(b"", text)
        text = SANITIZE_TEXT_RE["bytes_fe_sequences"].sub(b"", text)
        text = SANITIZE_TEXT_RE["bytes_esc"].sub(b"", text)
    else:
        text = SANITIZE_TEXT_RE["str_control"].sub("", text)
        text = SANITIZE_TEXT_RE["str_csi_sequences"].sub("", text)
        text = SANITIZE_TEXT_RE["str_fe_sequences"].sub("", text)
        text = SANITIZE_TEXT_RE["str_esc"].sub("", text)
    return text


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
        if hasattr(file, "buffer"):
            file.buffer.write(text)
            if add_newline:
                file.buffer.write(os.linesep.encode("utf-8"))
        else:
            # file has no "buffer" attribute, let's try to write the bytes directly
            file.write(text)
            if add_newline:
                file.write(os.linesep.encode("utf-8"))
    else:
        file.write(text)
        if add_newline:
            file.write(os.linesep)


def get_default_pager():
    from ..core import _get_linux_distro

    system = platform.system()
    if system == 'Linux':
        dist = _get_linux_distro()
        if dist == 'debian':
            return 'pager'
        return 'less'
    return 'more'


def get_pager():
    """
    Return (pager, env) where
        ``pager`` is a list with parsed pager command
        ``env`` is copy of os.environ() with added variables specific to the pager
    """
    env = os.environ.copy()
    pager = os.getenv("PAGER", default="").strip()
    pager = pager or get_default_pager()

    # LESS env is not always set and we need -R to display escape sequences properly
    less_opts = os.getenv("LESS", default="")
    if "-R" not in less_opts:
        less_opts += " -R"
    env["LESS"] = less_opts

    return shlex.split(pager), env


def run_pager(message: Union[bytes, str], tmp_suffix: str = ""):
    from ..core import run_external

    if not message:
        return

    if not tty.IS_INTERACTIVE:
        safe_write(sys.stdout, message)
        return

    mode = "w+b" if isinstance(message, bytes) else "w+"
    with tempfile.NamedTemporaryFile(mode=mode, suffix=tmp_suffix) as tmpfile:
        safe_write(tmpfile, message)
        tmpfile.flush()

        pager, env = get_pager()
        cmd = pager + [tmpfile.name]
        run_external(*cmd, env=env)


def pipe_to_pager(lines: Union[List[bytes], List[str]], *, add_newlines=False):
    """
    Pipe ``lines`` to the pager.
    If running in a non-interactive terminal, print the data instead.
    Add a newline after each line if ``add_newlines`` is ``True``.
    """
    if not tty.IS_INTERACTIVE:
        for line in lines:
            safe_write(sys.stdout, line, add_newline=add_newlines)
        return

    pager, env = get_pager()
    with subprocess.Popen(pager, stdin=subprocess.PIPE, encoding="utf-8", env=env) as proc:
        try:
            for line in lines:
                safe_write(proc.stdin, line, add_newline=add_newlines)
                proc.stdin.flush()
            proc.stdin.close()
        except BrokenPipeError:
            pass
        proc.wait()
