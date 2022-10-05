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


if __name__ == "__main__":
    unittest.main()
