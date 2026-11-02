import configparser
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

    def test_set_value_matching_placeholder(self):
        # values that are substrings of the '%s' placeholder used to corrupt the format string
        for value in ("s", "%", "s=", "%s", "secret", "p%ssword", ""):
            with self.subTest(value=value):
                self.parser.set("http://localhost", "pass", value)
                lines = str(self.parser).splitlines()
                self.assertIn(f"pass={value}", lines)

    def test_read_preserves_format(self):
        lines = ["user : s ; comment", "pass  =  %", "foo=foofoo", "x = 1 ; 100%", "y = a%b ; 50% off", "a%b = %%s"]
        self.parser.read_string("[section]\n" + "\n".join(lines) + "\n")
        self.assertEqual(self.parser.get("section", "y"), "a%b")
        self.assertEqual(self.parser.get("section", "a%b"), "%%s")
        self.parser.set("section", "user", "s")
        written = str(self.parser).splitlines()
        for line in lines[1:]:
            self.assertIn(line, written)
        self.assertIn("user=s", written)

    def test_read_empty_value_at_eof(self):
        self.parser.read_string("[section]\nk=")
        self.assertIn("k=", str(self.parser).splitlines())

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
