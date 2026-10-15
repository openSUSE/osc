import configparser
import io
import unittest

from osc.OscConfigParser import OscConfigParser


class TestOscConfigParser(unittest.TestCase):
    def setUp(self):
        self.parser = OscConfigParser()
        self.parser.read_string("""
[general]
apiurl = http://localhost

[http://localhost]
credentials_mgr_class=
user=
pass=
""")

    def test_disabled_interpolation(self):
        # with interpolation on, this would raise
        # ValueError: invalid interpolation syntax in '%' at position 0
        self.parser.set("http://localhost", "pass", "%")

    def test_write_value_that_looks_like_a_placeholder(self):
        # The written format string is built by substituting the option name
        # and the value, so a value of "s" or "%" used to land inside the "%s"
        # written for the name and leave a format string that cannot render.
        for value in ("secret", "p%ssword", "s", "%", "s=", ""):
            with self.subTest(value=value):
                parser = OscConfigParser()
                parser.read_string("[general]\napiurl = http://localhost\n"
                                   "\n[http://localhost]\npass = placeholder\n")
                parser.set("http://localhost", "pass", value)
                sio = io.StringIO()
                parser.write(sio, comments=True)
                written = [line for line in sio.getvalue().splitlines()
                           if line.startswith("pass")]
                self.assertEqual(written, ["pass=" + value])

    def test_duplicate_section(self):
        conf = """
[general]

[http://localhost]

[http://localhost]
"""
        parser = OscConfigParser()
        self.assertRaises(configparser.DuplicateSectionError, parser.read_string, conf)

    def test_duplicate_option(self):
        conf = """
[general]

[http://localhost]
user=
user=
"""
        parser = OscConfigParser()
        self.assertRaises(configparser.DuplicateOptionError, parser.read_string, conf)


if __name__ == "__main__":
    unittest.main()
