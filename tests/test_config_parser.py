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
