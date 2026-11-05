import unittest

from osc.util.rpmquery import RpmQuery


# (version 1, version 2, expected sign), the "^" cases are the ones in rpm's own test suite
EXPECTED = [
    ("1.0^", "1.0", 1),
    ("1.0", "1.0^", -1),
    ("1.0^", "1.0^", 0),
    ("1.0^git1", "1.0", 1),
    ("1.0", "1.0^git1", -1),
    ("1.0^git1", "1.0^git2", -1),
    ("1.01", "1.0^git1", 1),
    ("1.0^20160101", "1.0.1", -1),
    ("1.0^20160101^git1", "1.0^20160101", 1),
    ("1.0~rc1^git1", "1.0~rc1", 1),
    ("1.0^git1~pre", "1.0^git1", -1),
    ("1.0^git1", "1.0a", -1),
    ("^1", "1", -1),
    # nothing to do with the caret
    ("1.0~rc1", "1.0", -1),
    ("1.0", "1.0.1", -1),
    ("1.0a", "1.0", 1),
    ("1.0", "1_0", 0),
    ("1.010", "1.9", 1),
    ("1a", "1", 1),
]


class TestRpmVerCmp(unittest.TestCase):
    def test_rpm_ordering(self):
        for ver1, ver2, expected in EXPECTED:
            with self.subTest(ver1=ver1, ver2=ver2):
                self.assertEqual(RpmQuery.rpmvercmp(ver1.encode(), ver2.encode()), expected)
                self.assertEqual(RpmQuery.rpmvercmp(ver2.encode(), ver1.encode()), -expected)


if __name__ == "__main__":
    unittest.main()
