import contextlib
import io
import tempfile
import unittest

import osc.conf
from osc.output import KeyValueTable
from osc.output import print_msg
from osc.output import safe_write
from osc.output import sanitize_text
from osc.output import tty


class TestKeyValueTable(unittest.TestCase):
    def test_empty(self):
        t = KeyValueTable()
        self.assertEqual(str(t), "")

    def test_simple(self):
        t = KeyValueTable()
        t.add("Key", "Value")
        t.add("FooBar", "Text")

        expected = """
Key    : Value
FooBar : Text
""".strip()
        self.assertEqual(str(t), expected)

    def test_newline(self):
        t = KeyValueTable()
        t.add("Key", "Value")
        t.newline()
        t.add("FooBar", "Text")

        expected = """
Key    : Value

FooBar : Text
""".strip()
        self.assertEqual(str(t), expected)

    def test_continuation(self):
        t = KeyValueTable()
        t.add("Key", ["Value1", "Value2"])

        expected = """
Key : Value1
      Value2
""".strip()
        self.assertEqual(str(t), expected)

    def test_section(self):
        t = KeyValueTable()
        t.add("Section", None)
        t.add("Key", "Value", indent=4)
        t.add("FooBar", "Text", indent=4)

        expected = """
Section
    Key    : Value
    FooBar : Text
""".strip()
        self.assertEqual(str(t), expected)

    def test_wide_chars(self):
        t = KeyValueTable()
        t.add("Key", "Value")
        t.add("🚀🚀🚀", "Value")

        expected = """
Key    : Value
🚀🚀🚀 : Value
""".strip()
        self.assertEqual(str(t), expected)

    def test_empty_value_no_color(self):
        t = KeyValueTable()
        t.add("Key", "", color="bold")

        expected = "Key : "
        self.assertEqual(str(t), expected)


class TestPrintMsg(unittest.TestCase):
    def setUp(self):
        osc.conf.config = osc.conf.Options()

    def test_debug(self):
        osc.conf.config["debug"] = False
        stdout = io.StringIO()
        stderr = io.StringIO()
        with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
            print_msg("foo", "bar", print_to="debug")
        self.assertEqual("", stdout.getvalue())
        self.assertEqual("", stderr.getvalue())

        osc.conf.config["debug"] = True
        stdout = io.StringIO()
        stderr = io.StringIO()
        with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
            print_msg("foo", "bar", print_to="debug")
        self.assertEqual("", stdout.getvalue())
        self.assertEqual("DEBUG: foo bar\n", stderr.getvalue())

    def test_verbose(self):
        osc.conf.config["verbose"] = False
        stdout = io.StringIO()
        stderr = io.StringIO()
        with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
            print_msg("foo", "bar", print_to="verbose")
        self.assertEqual("", stdout.getvalue())
        self.assertEqual("", stderr.getvalue())

        osc.conf.config["verbose"] = True
        stdout = io.StringIO()
        stderr = io.StringIO()
        with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
            print_msg("foo", "bar", print_to="verbose")
        self.assertEqual("foo bar\n", stdout.getvalue())
        self.assertEqual("", stderr.getvalue())

        osc.conf.config["verbose"] = False
        osc.conf.config["debug"] = True
        stdout = io.StringIO()
        stderr = io.StringIO()
        with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
            print_msg("foo", "bar", print_to="verbose")
        self.assertEqual("foo bar\n", stdout.getvalue())
        self.assertEqual("", stderr.getvalue())

    def test_error(self):
        stdout = io.StringIO()
        stderr = io.StringIO()
        with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
            print_msg("foo", "bar", print_to="error")
        self.assertEqual("", stdout.getvalue())
        self.assertEqual(f"{tty.colorize('ERROR:', 'red,bold')} foo bar\n", stderr.getvalue())

    def test_warning(self):
        stdout = io.StringIO()
        stderr = io.StringIO()
        with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
            print_msg("foo", "bar", print_to="warning")
        self.assertEqual("", stdout.getvalue())
        self.assertEqual(f"{tty.colorize('WARNING:', 'yellow,bold')} foo bar\n", stderr.getvalue())

    def test_none(self):
        stdout = io.StringIO()
        stderr = io.StringIO()
        with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
            print_msg("foo", "bar", print_to=None)
        self.assertEqual("", stdout.getvalue())
        self.assertEqual("", stderr.getvalue())

    def test_stdout(self):
        stdout = io.StringIO()
        stderr = io.StringIO()
        with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
            print_msg("foo", "bar", print_to="stdout")
        self.assertEqual("foo bar\n", stdout.getvalue())
        self.assertEqual("", stderr.getvalue())

    def test_stderr(self):
        stdout = io.StringIO()
        stderr = io.StringIO()
        with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
            print_msg("foo", "bar", print_to="stderr")
        self.assertEqual("", stdout.getvalue())
        self.assertEqual("foo bar\n", stderr.getvalue())


class TestSanitization(unittest.TestCase):
    def test_control_chars_bytes(self):
        original = b"".join([i.to_bytes(1, byteorder="big") for i in range(32)])
        sanitized = sanitize_text(original)
        self.assertEqual(sanitized, b"\t\n\r")

    def test_control_chars_str(self):
        original = "".join([chr(i) for i in range(32)])
        sanitized = sanitize_text(original)
        self.assertEqual(sanitized, "\t\n\r")

    def test_csi_escape_sequences_str(self):
        # allowed CSI escape sequences
        originals = [">\033[0m<", ">\033[1;31;47m]<"]
        for original in originals:
            sanitized = sanitize_text(original)
            self.assertEqual(sanitized, original)

        # not allowed CSI escape sequences
        originals = [">\033[8m<"]
        for original in originals:
            sanitized = sanitize_text(original)
            self.assertEqual(sanitized, "><")

    def test_csi_escape_sequences_bytes(self):
        # allowed CSI escape sequences
        originals = [b">\033[0m<", b">\033[1;31;47m]<"]
        for original in originals:
            sanitized = sanitize_text(original)
            self.assertEqual(sanitized, original)

        # not allowed CSI escape sequences
        originals = [b">\033[8m<"]
        for original in originals:
            sanitized = sanitize_text(original)
            self.assertEqual(sanitized, b"><")

    def test_standalone_escape_str(self):
        original = ">\033<"
        sanitized = sanitize_text(original)
        self.assertEqual(sanitized, "><")

    def test_standalone_escape_bytes(self):
        # standalone escape
        original = b">\033<"
        sanitized = sanitize_text(original)
        self.assertEqual(sanitized, b"><")

    def test_fe_escape_sequences_str(self):
        for i in range(0x40, 0x5F + 1):
            char = chr(i)
            original = f">\033{char}<"
            sanitized = sanitize_text(original)
            self.assertEqual(sanitized, "><")

    def test_fe_escape_sequences_bytes(self):
        for i in range(0x40, 0x5F + 1):
            byte = i.to_bytes(1, byteorder="big")
            original = b">\033" + byte + b"<"
            sanitized = sanitize_text(original)
            self.assertEqual(sanitized, b"><")

    def test_osc_escape_sequences_str(self):
        # OSC (Operating System Command) sequences
        original = "\033]0;this is the window title\007"
        sanitized = sanitize_text(original)
        # \033] is removed with the Fe sequences
        self.assertEqual(sanitized, "0;this is the window title")

    def test_osc_escape_sequences_bytes(self):
        #  OSC (Operating System Command) sequences
        original = b"\033]0;this is the window title\007"
        sanitized = sanitize_text(original)
        # \033] is removed with the Fe sequences
        self.assertEqual(sanitized, b"0;this is the window title")


class TestSafeWrite(unittest.TestCase):
    def test_string_to_file(self):
        with tempfile.NamedTemporaryFile(mode="w+") as f:
            safe_write(f, "string")

    def test_bytes_to_file(self):
        with tempfile.NamedTemporaryFile(mode="wb+") as f:
            safe_write(f, b"bytes")

    def test_string_to_stringio(self):
        with io.StringIO() as f:
            safe_write(f, "string")

    def test_bytes_to_bytesio(self):
        with io.BytesIO() as f:
            safe_write(f, b"bytes")


if __name__ == "__main__":
    unittest.main()
