import unittest

import osc.core


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


if __name__ == "__main__":
    unittest.main()
