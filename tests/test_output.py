import unittest

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


if __name__ == "__main__":
    unittest.main()
