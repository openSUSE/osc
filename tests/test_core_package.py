import os
import unittest

import osc.core
import osc.oscerr

from .common import OscTestCase


FIXTURES_DIR = os.path.join(os.path.dirname(__file__), "fixtures", "packages")


class PackageMock(osc.core.Package):
    def __init__(self, apiurl, project_name, name):
        """
        Let's override __init__ to avoid loading from a working copy.
        """
        self.apiurl = apiurl
        self.prjname = project_name
        self.name = name


class TestPackage(unittest.TestCase):
    def test_eq(self):
        p1 = PackageMock("http://urlA", "projA", "pkgA")
        p2 = PackageMock("http://urlA", "projA", "pkgA")
        self.assertEqual(p1, p2)

        p1 = PackageMock("http://urlA", "projA", "pkgA")
        p2 = PackageMock("http://urlA", "projA", "pkgB")
        self.assertNotEqual(p1, p2)

        p1 = PackageMock("http://urlA", "projA", "pkgA")
        p2 = PackageMock("http://urlA", "projB", "pkgA")
        self.assertNotEqual(p1, p2)

        p1 = PackageMock("http://urlA", "projA", "pkgA")
        p2 = PackageMock("http://urlB", "projA", "pkgA")
        self.assertNotEqual(p1, p2)

    def test_lt(self):
        p1 = PackageMock("http://urlA", "projA", "pkgA")
        p2 = PackageMock("http://urlA", "projA", "pkgA")
        self.assertFalse(p1 < p2)

        p1 = PackageMock("http://urlA", "projA", "pkgA")
        p2 = PackageMock("http://urlA", "projA", "pkgB")
        self.assertTrue(p1 < p2)

        p1 = PackageMock("http://urlA", "projA", "pkgA")
        p2 = PackageMock("http://urlA", "projB", "pkgA")
        self.assertTrue(p1 < p2)

        p1 = PackageMock("http://urlA", "projA", "pkgA")
        p2 = PackageMock("http://urlB", "projA", "pkgA")
        self.assertTrue(p1 < p2)

    def test_hash(self):
        p1 = PackageMock("http://urlA", "projA", "pkgA")
        p2 = PackageMock("http://urlA", "projA", "pkgA")
        packages = set()
        packages.add(p1)
        # the second instance appears to be there because it has the same hash
        # it is ok, because we consider such packages equal
        self.assertIn(p2, packages)


class TestPackageFromPaths(OscTestCase):
    def _get_fixtures_dir(self):
        return FIXTURES_DIR

    def test_package_object_dir(self):
        path = "projectA/pkgA"
        path = os.path.join(self.tmpdir, 'osctest', path)
        pac = osc.core.Package(path)

        self.assertEqual(pac.name, "pkgA")
        self.assertEqual(pac.prjname, "projectA")
        self.assertEqual(pac.apiurl, "http://localhost")
        self.assertEqual(pac.todo, [])

    def test_package_object_file(self):
        path = "projectA/pkgA/pkgA.spec"
        path = os.path.join(self.tmpdir, 'osctest', path)
        pac = osc.core.Package(path)

        self.assertEqual(pac.name, "pkgA")
        self.assertEqual(pac.prjname, "projectA")
        self.assertEqual(pac.apiurl, "http://localhost")
        self.assertEqual(pac.todo, ["pkgA.spec"])

    def test_package_object_file_missing(self):
        path = "projectA/pkgA/missing-file"
        path = os.path.join(self.tmpdir, 'osctest', path)
        pac = osc.core.Package(path)

        self.assertEqual(pac.name, "pkgA")
        self.assertEqual(pac.prjname, "projectA")
        self.assertEqual(pac.apiurl, "http://localhost")
        self.assertEqual(pac.todo, ["missing-file"])

    def test_single_package(self):
        paths = ["projectA/pkgA"]
        paths = [os.path.join(self.tmpdir, 'osctest', i) for i in paths]
        pacs = osc.core.Package.from_paths(paths)
        self.assertEqual(len(pacs), 1)

        pac = pacs[0]
        self.assertEqual(pac.name, "pkgA")
        self.assertEqual(pac.prjname, "projectA")
        self.assertEqual(pac.apiurl, "http://localhost")

    def test_duplicates(self):
        # passing a path twice is ok
        paths = ["projectA/pkgA", "projectA/pkgA"]
        paths = [os.path.join(self.tmpdir, 'osctest', i) for i in paths]
        pacs = osc.core.Package.from_paths(paths)
        pac = pacs[0]
        self.assertEqual(pac.name, "pkgA")
        self.assertEqual(pac.prjname, "projectA")
        self.assertEqual(pac.apiurl, "http://localhost")

        # the same package in 2 paths is an error
        paths = ["projectA/pkgA", "projectA/pkgA-symlink"]
        paths = [os.path.join(self.tmpdir, 'osctest', i) for i in paths]
        self.assertRaises(osc.oscerr.PackageExists, osc.core.Package.from_paths, paths)

    def test_one_package_two_files(self):
        paths = ["projectA/pkgA/pkgA.spec", "projectA/pkgA/pkgA.changes"]
        paths = [os.path.join(self.tmpdir, 'osctest', i) for i in paths]
        pacs = osc.core.Package.from_paths(paths)
        self.assertEqual(len(pacs), 1)

        pac = pacs[0]
        self.assertEqual(pac.name, "pkgA")
        self.assertEqual(pac.prjname, "projectA")
        self.assertEqual(pac.apiurl, "http://localhost")

    def test_two_packages(self):
        paths = ["projectA/pkgA", "projectA/pkgB"]
        paths = [os.path.join(self.tmpdir, 'osctest', i) for i in paths]
        pacs = osc.core.Package.from_paths(paths)
        self.assertEqual(len(pacs), 2)

        pac = pacs[0]
        self.assertEqual(pac.name, "pkgA")
        self.assertEqual(pac.prjname, "projectA")
        self.assertEqual(pac.apiurl, "http://localhost")

        pac = pacs[1]
        self.assertEqual(pac.name, "pkgB")
        self.assertEqual(pac.prjname, "projectA")
        self.assertEqual(pac.apiurl, "http://localhost")

    def test_two_projects(self):
        paths = ["projectA/pkgA", "projectA/pkgB", "projectB/pkgA", "projectB/pkgB"]
        paths = [os.path.join(self.tmpdir, 'osctest', i) for i in paths]
        pacs = osc.core.Package.from_paths(paths)
        self.assertEqual(len(pacs), 4)

        pac = pacs[0]
        self.assertEqual(pac.name, "pkgA")
        self.assertEqual(pac.prjname, "projectA")
        self.assertEqual(pac.apiurl, "http://localhost")

        pac = pacs[1]
        self.assertEqual(pac.name, "pkgB")
        self.assertEqual(pac.prjname, "projectA")
        self.assertEqual(pac.apiurl, "http://localhost")

        pac = pacs[2]
        self.assertEqual(pac.name, "pkgA")
        self.assertEqual(pac.prjname, "projectB")
        self.assertEqual(pac.apiurl, "http://localhost")

        pac = pacs[3]
        self.assertEqual(pac.name, "pkgB")
        self.assertEqual(pac.prjname, "projectB")
        self.assertEqual(pac.apiurl, "http://localhost")

    def test_two_apiurls(self):
        paths = ["projectA/pkgA", "projectA/pkgB", "projectA-different-apiurl/pkgA", "projectA-different-apiurl/pkgB"]
        paths = [os.path.join(self.tmpdir, 'osctest', i) for i in paths]
        pacs = osc.core.Package.from_paths(paths)
        self.assertEqual(len(pacs), 4)

        pac = pacs[0]
        self.assertEqual(pac.name, "pkgA")
        self.assertEqual(pac.prjname, "projectA")
        self.assertEqual(pac.apiurl, "http://localhost")

        pac = pacs[1]
        self.assertEqual(pac.name, "pkgB")
        self.assertEqual(pac.prjname, "projectA")
        self.assertEqual(pac.apiurl, "http://localhost")

        pac = pacs[2]
        self.assertEqual(pac.name, "pkgA")
        self.assertEqual(pac.prjname, "projectA")
        self.assertEqual(pac.apiurl, "http://example.com")

        pac = pacs[3]
        self.assertEqual(pac.name, "pkgB")
        self.assertEqual(pac.prjname, "projectA")
        self.assertEqual(pac.apiurl, "http://example.com")

    def test_invalid_package(self):
        paths = ["projectA/pkgA", "projectA"]
        paths = [os.path.join(self.tmpdir, 'osctest', i) for i in paths]
        self.assertRaises(osc.oscerr.NoWorkingCopy, osc.core.Package.from_paths, paths)

    def test_nofail(self):
        # valid package, invalid package, nonexistent package
        paths = ["projectA/pkgA", "projectA", "does-not-exist"]
        paths = [os.path.join(self.tmpdir, 'osctest', i) for i in paths]
        pacs, nopacs = osc.core.Package.from_paths_nofail(paths)

        self.assertEqual(len(pacs), 1)

        pac = pacs[0]
        self.assertEqual(pac.name, "pkgA")
        self.assertEqual(pac.prjname, "projectA")
        self.assertEqual(pac.apiurl, "http://localhost")

        expected = [
            os.path.join(self.tmpdir, "osctest", "projectA"),
            os.path.join(self.tmpdir, "osctest", "does-not-exist"),
        ]
        self.assertEqual(nopacs, expected)


if __name__ == "__main__":
    unittest.main()
