import unittest

from osc.util.rpmquery import RpmQuery

# (ver1, ver2, expected); the tilde and caret cases are taken from rpm's tests/rpmvercmp.at
RPMVERCMP_CASES = (
    (b"1.0", b"1.0", 0),
    (b"1.0", b"2.0", -1),
    (b"2.0.1", b"2.0", 1),
    (b"1.0~rc1", b"1.0", -1),
    (b"1.0~rc1", b"1.0~rc2", -1),
    (b"1.0^", b"1.0^", 0),
    (b"1.0^", b"1.0", 1),
    (b"1.0", b"1.0^", -1),
    (b"1.0^git1", b"1.0^git1", 0),
    (b"1.0^git1", b"1.0", 1),
    (b"1.0", b"1.0^git1", -1),
    (b"1.0^git1", b"1.0^git2", -1),
    (b"1.0^git2", b"1.0^git1", 1),
    (b"1.0^git1", b"1.01", -1),
    (b"1.01", b"1.0^git1", 1),
    (b"1.0^20160101", b"1.0^20160101", 0),
    (b"1.0^20160101", b"1.0.1", -1),
    (b"1.0.1", b"1.0^20160101", 1),
    (b"1.0^20160101^git1", b"1.0^20160101^git1", 0),
    (b"1.0^20160102", b"1.0^20160101^git1", 1),
    (b"1.0^20160101^git1", b"1.0^20160102", -1),
    (b"1.0~rc1^git1", b"1.0~rc1", 1),
    (b"1.0~rc1", b"1.0~rc1^git1", -1),
    (b"1.0^git1~pre", b"1.0^git1", -1),
    (b"1.0^git1", b"1.0^git1~pre", 1),
)


class TestRpmvercmp(unittest.TestCase):
    def test_rpmvercmp(self):
        for ver1, ver2, expected in RPMVERCMP_CASES:
            with self.subTest(ver1=ver1, ver2=ver2):
                self.assertEqual(RpmQuery.rpmvercmp(ver1, ver2), expected)


if __name__ == "__main__":
    unittest.main()
