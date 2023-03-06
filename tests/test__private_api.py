import unittest

from osc._private.api import xml_escape


class TestXmlEscape(unittest.TestCase):
    def test_lt(self):
        actual = xml_escape("<")
        expected = "&lt;"
        self.assertEqual(actual, expected)

    def test_gt(self):
        actual = xml_escape(">")
        expected = "&gt;"
        self.assertEqual(actual, expected)

    def test_apos(self):
        actual = xml_escape("'")
        expected = "&apos;"
        self.assertEqual(actual, expected)

    def test_quot(self):
        actual = xml_escape("\"")
        expected = "&quot;"
        self.assertEqual(actual, expected)

    def test_amp(self):
        actual = xml_escape("&")
        expected = "&amp;"
        self.assertEqual(actual, expected)


if __name__ == "__main__":
    unittest.main()
