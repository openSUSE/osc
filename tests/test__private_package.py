import os
import unittest

from osc._private.package import ApiPackage
from osc._private.package import LocalPackage
from osc._private.package import PackageBase

from .common import GET
from .common import OscTestCase


FIXTURES_DIR = os.path.join(os.path.dirname(__file__), "fixtures", "packages")


class PackageBaseMock(PackageBase):
    def _get_directory_node(self):
        pass

    def _load_from_directory_node(self, directory_node):
        pass


class TestPackageBase(unittest.TestCase):
    def setUp(self):
        self.p1 = PackageBaseMock("http://urlA", "projA", "pkgA")

    def test_str(self):
        self.assertEqual(str(self.p1), "projA/pkgA")

    def test_repr(self):
        self.assertTrue(repr(self.p1).endswith("(projA/pkgA)"))

    def test_eq(self):
        # the same
        p2 = PackageBaseMock(self.p1.apiurl, self.p1.project, self.p1.name)
        self.assertEqual(self.p1, p2)

        # package name differs
        p2 = PackageBaseMock(self.p1.apiurl, self.p1.project, "pkgB")
        self.assertNotEqual(self.p1, p2)

        # project name differs
        p2 = PackageBaseMock(self.p1.apiurl, "projB", self.p1.name)
        self.assertNotEqual(self.p1, p2)

        # baseurl differs
        p2 = PackageBaseMock("http://urlB", self.p1.project, self.p1.name)
        self.assertNotEqual(self.p1, p2)

    def test_lt(self):
        # the same
        p2 = PackageBaseMock(self.p1.apiurl, self.p1.project, self.p1.name)
        self.assertFalse(self.p1 < p2)

        # package name differs
        p2 = PackageBaseMock(self.p1.apiurl, self.p1.project, "pkgB")
        self.assertTrue(self.p1 < p2)

        # project name differs
        p2 = PackageBaseMock(self.p1.apiurl, "projB", self.p1.name)
        self.assertTrue(self.p1 < p2)

        # baseurl differs
        p2 = PackageBaseMock("http://urlB", self.p1.project, self.p1.name)
        self.assertTrue(self.p1 < p2)

    def test_hash(self):
        p2 = PackageBaseMock(self.p1.apiurl, self.p1.project, self.p1.name)
        self.assertEqual(hash(self.p1), hash(p2))

        packages = set()
        packages.add(self.p1)
        # the second instance appears to be there because it has the same hash
        # it is ok, because we consider such packages equal
        self.assertIn(p2, packages)


class TestLocalPackage(OscTestCase):
    def _get_fixtures_dir(self):
        return FIXTURES_DIR

    def test_load(self):
        path = os.path.join(self.tmpdir, "osctest", "openSUSE:Tools", "osc")
        p = LocalPackage(path)

        self.assertEqual(p.name, "osc")
        self.assertEqual(p.project, "openSUSE:Tools")
        self.assertEqual(p.apiurl, "http://localhost")
        self.assertEqual(p.rev, "373")
        self.assertEqual(p.vrev, "339")
        self.assertEqual(p.srcmd5, "30ccce6c3a1a4322e79c2935a52af18b")

        self.assertEqual(p.linkinfo.project, "openSUSE:Factory")
        self.assertEqual(p.linkinfo.package, "osc")
        self.assertEqual(p.linkinfo.srcmd5, "1ccbcd1b0b531a37ad75b34b5a1e2e3e")
        self.assertEqual(p.linkinfo.baserev, "2c3ae65909d69e0f63113ccfe0e5f3f8")
        self.assertEqual(p.linkinfo.xsrcmd5, "6a31b956f9431b0644ad6cf8e845c4e5")
        self.assertEqual(p.linkinfo.lsrcmd5, "30ccce6c3a1a4322e79c2935a52af18b")

        self.assertEqual(len(p.files), 3)

        f = p.files[0]
        self.assertEqual(f.name, "osc-0.182.0.tar.gz")
        self.assertEqual(f.md5, "87f040c76f3da86fd7218c972b9df1dc")
        self.assertEqual(f.size, 381596)
        self.assertEqual(f.mtime, 1662638726)


class TestApiPackage(OscTestCase):
    def _get_fixtures_dir(self):
        return FIXTURES_DIR

    @GET("http://localhost/source/openSUSE:Tools/osc", file="osctest/openSUSE:Tools/osc/.osc/_files")
    def test_load(self):
        p = ApiPackage("http://localhost", "openSUSE:Tools", "osc")

        self.assertEqual(p.name, "osc")
        self.assertEqual(p.project, "openSUSE:Tools")
        self.assertEqual(p.apiurl, "http://localhost")
        self.assertEqual(p.rev, "373")
        self.assertEqual(p.vrev, "339")
        self.assertEqual(p.srcmd5, "30ccce6c3a1a4322e79c2935a52af18b")

        self.assertEqual(p.linkinfo.project, "openSUSE:Factory")
        self.assertEqual(p.linkinfo.package, "osc")
        self.assertEqual(p.linkinfo.srcmd5, "1ccbcd1b0b531a37ad75b34b5a1e2e3e")
        self.assertEqual(p.linkinfo.baserev, "2c3ae65909d69e0f63113ccfe0e5f3f8")
        self.assertEqual(p.linkinfo.xsrcmd5, "6a31b956f9431b0644ad6cf8e845c4e5")
        self.assertEqual(p.linkinfo.lsrcmd5, "30ccce6c3a1a4322e79c2935a52af18b")

        self.assertEqual(len(p.files), 3)

        f = p.files[0]
        self.assertEqual(f.name, "osc-0.182.0.tar.gz")
        self.assertEqual(f.md5, "87f040c76f3da86fd7218c972b9df1dc")
        self.assertEqual(f.size, 381596)
        self.assertEqual(f.mtime, 1662638726)


if __name__ == "__main__":
    unittest.main()
