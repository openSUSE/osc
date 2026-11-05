import functools
import unittest

from osc.util.debquery import DebQuery


# (version 1, version 2, expected sign), checked against "dpkg --compare-versions"
EXPECTED = [
    ("1.0~rc1", "1.0", -1),
    ("1.0", "1.0~rc1", 1),
    ("1.0~~", "1.0~", -1),
    ("1.0~", "1.0", -1),
    ("1.0~a", "1.0~b", -1),
    ("1~", "1", -1),
    ("1~~a", "1~a", -1),
    ("1.0", "1.", 0),
    ("1.00", "1.", 0),
    ("1.0", "1.00", 0),
    ("1.0a", "1.0", 1),
    ("1.0+b1", "1.0", 1),
    ("1.0.1", "1.0", 1),
    ("1.0", "1.0", 0),
    ("1.a", "1.1", 1),
    ("2", "10", -1),
    ("1.0~rc1", "1.0~rc2", -1),
    ("1.0+", "1.0", 1),
    ("1.0a", "1.0~a", 1),
    ("1.0.0~beta", "1.0.0", -1),
    ("a", "a~", 1),
    ("1.0.", "1.0", 1),
    ("0.9", "0.10", -1),
    ("1" + "0" * 40 + "1", "1" + "0" * 40 + "2", -1),
]


class TestDebVerCmp(unittest.TestCase):
    def test_dpkg_ordering(self):
        for ver1, ver2, expected in EXPECTED:
            with self.subTest(ver1=ver1, ver2=ver2):
                self.assertEqual(DebQuery.debvercmp(ver1.encode(), ver2.encode()), expected)
                # comparing the other way round gives the opposite
                self.assertEqual(DebQuery.debvercmp(ver2.encode(), ver1.encode()), -expected)

    def test_sorting_pre_releases(self):
        versions = [b"1.0", b"1.0~rc2", b"1.0~~", b"1.0~rc1", b"1.0~"]
        ordered = sorted(versions, key=functools.cmp_to_key(DebQuery.debvercmp))
        self.assertEqual(ordered, [b"1.0~~", b"1.0~", b"1.0~rc1", b"1.0~rc2", b"1.0"])


if __name__ == "__main__":
    unittest.main()
