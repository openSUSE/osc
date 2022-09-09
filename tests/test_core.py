import unittest

from osc.core import parseRevisionOption
from osc.oscerr import OscInvalidRevision


class TestParseRevisionOption(unittest.TestCase):
    def test_empty(self):
        expected = None, None
        actual = parseRevisionOption("")
        self.assertEqual(expected, actual)

    def test_colon(self):
        expected = None, None
        actual = parseRevisionOption(":")
        # your revision ':' will be ignored
        self.assertEqual(expected, actual)

    def test_invalid_multiple_colons(self):
        self.assertRaises(OscInvalidRevision, parseRevisionOption, ":::::")

    def test_one_number(self):
        expected = ("1", None)
        actual = parseRevisionOption("1")
        self.assertEqual(expected, actual)

    def test_two_numbers(self):
        expected = ("1", "2")
        actual = parseRevisionOption("1:2")
        self.assertEqual(expected, actual)

    def test_invalid_multiple_numbers(self):
        self.assertRaises(OscInvalidRevision, parseRevisionOption, "1:2:3:4:5")

    def test_one_hash(self):
        expected = "c4ca4238a0b923820dcc509a6f75849b", None
        actual = parseRevisionOption("c4ca4238a0b923820dcc509a6f75849b")
        self.assertEqual(expected, actual)

    def test_two_hashes(self):
        expected = ("d41d8cd98f00b204e9800998ecf8427e", "c4ca4238a0b923820dcc509a6f75849b")
        actual = parseRevisionOption("d41d8cd98f00b204e9800998ecf8427e:c4ca4238a0b923820dcc509a6f75849b")
        self.assertEqual(expected, actual)

    def test_invalid_multiple_hashes(self):
        rev = "d41d8cd98f00b204e9800998ecf8427e:c4ca4238a0b923820dcc509a6f75849b:c81e728d9d4c2f636f067f89cc14862c"
        self.assertRaises(OscInvalidRevision, parseRevisionOption, rev)


if __name__ == "__main__":
    unittest.main()
