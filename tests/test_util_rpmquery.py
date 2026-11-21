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

    def test_rpmvercmp_empty_and_none(self):
        self.assertEqual(RpmQuery.rpmvercmp(None, None), 0)
        self.assertEqual(RpmQuery.rpmvercmp("", ""), 0)
        self.assertEqual(RpmQuery.rpmvercmp(b"", b""), 0)
        self.assertEqual(RpmQuery.rpmvercmp(None, "1.0"), -1)
        self.assertEqual(RpmQuery.rpmvercmp("1.0", None), 1)
        self.assertEqual(RpmQuery.rpmvercmp("", "1.0"), -1)
        self.assertEqual(RpmQuery.rpmvercmp("1.0", ""), 1)


class TestRpmQuery(unittest.TestCase):
    def test_filename(self):
        self.assertEqual(
            RpmQuery.filename(b"foo", None, b"1.0", b"1", b"x86_64"),
            b"foo-1.0-1.x86_64.rpm",
        )

    def test_mock_header(self):
        import rpm

        hdr = rpm.hdr()
        hdr[rpm.RPMTAG_NAME] = "mypkg"
        hdr[rpm.RPMTAG_VERSION] = "2.0"
        hdr[rpm.RPMTAG_RELEASE] = "3.1"
        hdr[rpm.RPMTAG_EPOCH] = 1
        hdr[rpm.RPMTAG_ARCH] = "x86_64"
        hdr[rpm.RPMTAG_SUMMARY] = "Test Summary"
        hdr[rpm.RPMTAG_DESCRIPTION] = "Test Description"
        hdr[rpm.RPMTAG_URL] = "https://example.com"
        hdr[rpm.RPMTAG_PROVIDENAME] = ["foo", "bar"]
        hdr[rpm.RPMTAG_PROVIDEFLAGS] = [8, 12]
        hdr[rpm.RPMTAG_PROVIDEVERSION] = ["1.0", "2.0"]

        rpmq = RpmQuery.__new__(RpmQuery)
        rpmq.header = hdr
        rpmq._RpmQuery__path = "/fake/mypkg.rpm"

        self.assertEqual(rpmq.name(), b"mypkg")
        self.assertEqual(rpmq.version(), b"2.0")
        self.assertEqual(rpmq.release(), b"3.1")
        self.assertEqual(rpmq.epoch(), 1)
        self.assertEqual(rpmq.arch(), b"x86_64")
        self.assertEqual(rpmq.summary(), b"Test Summary")
        self.assertEqual(rpmq.description(), b"Test Description")
        self.assertEqual(rpmq.url(), b"https://example.com")
        self.assertEqual(rpmq.path(), "/fake/mypkg.rpm")
        self.assertEqual(rpmq.canonname(), b"mypkg-2.0-3.1.src.rpm")
        self.assertEqual(rpmq.provides(), [b"foo = 1.0", b"bar >= 2.0"])
        self.assertTrue(rpmq.is_src())
        self.assertFalse(rpmq.is_nosrc())

        hdr[rpm.RPMTAG_NOSOURCE] = [0]
        self.assertTrue(rpmq.is_nosrc())
        self.assertEqual(rpmq.canonname(), b"mypkg-2.0-3.1.nosrc.rpm")

        del hdr[rpm.RPMTAG_NOSOURCE]
        hdr[rpm.RPMTAG_SOURCERPM] = "mypkg-2.0-3.1.src.rpm"
        self.assertFalse(rpmq.is_src())
        self.assertFalse(rpmq.is_nosrc())
        self.assertEqual(rpmq.canonname(), b"mypkg-2.0-3.1.x86_64.rpm")

        # Test legacy recommends / suggests (RPMTAG_OLDSUGGESTS*)
        from osc.util.rpmquery import (
            RPMSENSE_STRONG,
            RPMTAG_OLDSUGGESTSFLAGS,
            RPMTAG_OLDSUGGESTSNAME,
            RPMTAG_OLDSUGGESTSVERSION,
        )

        hdr[RPMTAG_OLDSUGGESTSNAME] = ["rec-pkg", "sug-pkg"]
        hdr[RPMTAG_OLDSUGGESTSFLAGS] = [RPMSENSE_STRONG | 8, 8]  # '=' with & without RPMSENSE_STRONG
        hdr[RPMTAG_OLDSUGGESTSVERSION] = ["1.0", "2.0"]
        self.assertEqual(rpmq.recommends(), [b"rec-pkg = 1.0"])
        self.assertEqual(rpmq.suggests(), [b"sug-pkg = 2.0"])

    def test_mock_header_bytes(self):
        import rpm

        rpmq = RpmQuery.__new__(RpmQuery)
        rpmq.header = {
            rpm.RPMTAG_NAME: b"mypkg",
            rpm.RPMTAG_VERSION: b"2.0",
            rpm.RPMTAG_RELEASE: b"3.1",
            rpm.RPMTAG_EPOCH: 1,
            rpm.RPMTAG_ARCH: b"x86_64",
            rpm.RPMTAG_SUMMARY: b"Test Summary",
            rpm.RPMTAG_DESCRIPTION: b"Test Description",
            rpm.RPMTAG_URL: b"https://example.com",
            rpm.RPMTAG_PROVIDENAME: [b"foo", b"bar", b"baz"],
            rpm.RPMTAG_PROVIDEFLAGS: [8, 12, 0],
            rpm.RPMTAG_PROVIDEVERSION: [b"1.0", b"2.0", b""],
            rpm.RPMTAG_REQUIRENAME: [b"req1", b"req2"],
            rpm.RPMTAG_REQUIREFLAGS: [2, 4],
            rpm.RPMTAG_REQUIREVERSION: [b"0.9", b"1.1"],
            rpm.RPMTAG_SOURCERPM: None,
        }
        rpmq._RpmQuery__path = "/fake/mypkg.rpm"

        self.assertEqual(rpmq.name(), b"mypkg")
        self.assertEqual(rpmq.version(), b"2.0")
        self.assertEqual(rpmq.release(), b"3.1")
        self.assertEqual(rpmq.epoch(), 1)
        self.assertEqual(rpmq.arch(), b"x86_64")
        self.assertEqual(rpmq.provides(), [b"foo = 1.0", b"bar >= 2.0", b"baz"])
        self.assertEqual(rpmq.requires(), [b"req1 < 0.9", b"req2 > 1.1"])

    def test_queryhdrmd5_missing_file(self):
        self.assertIsNone(RpmQuery.queryhdrmd5("/non/existent/package.rpm"))


if __name__ == "__main__":
    unittest.main()
