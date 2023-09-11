import contextlib
import importlib
import io
import unittest

import osc.conf
from osc._private import print_msg
from osc.output import KeyValueTable


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


class TestPrintMsg(unittest.TestCase):
    def setUp(self):
        # reset the global `config` in preparation for running the tests
        importlib.reload(osc.conf)

    def tearDown(self):
        # reset the global `config` to avoid impacting tests from other classes
        importlib.reload(osc.conf)

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


if __name__ == "__main__":
    unittest.main()
