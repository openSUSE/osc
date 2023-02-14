import os
import sys
import tempfile
import unittest

import osc.core as osc_core
from osc.store import Store


class TestStore(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.mkdtemp(prefix='osc_test')
        self.store = Store(self.tmpdir, check=False)
        self.store.is_package = True
        self.store.project = "project name"
        self.store.package = "package name"

    def tearDown(self):
        try:
            shutil.rmtree(self.tmpdir)
        except:
            pass

    def fileEquals(self, fn, expected_value):
        path = os.path.join(self.tmpdir, ".osc", fn)
        with open(path) as f:
            actual_value = f.read()
            self.assertEqual(actual_value, expected_value, f"File: {fn}")

    def test_read_write_file(self):
        self.store.write_file("_file", "\n\nline1\nline2")
        self.fileEquals("_file", "\n\nline1\nline2")
        self.assertEqual(self.store.read_file("_file"), "\n\nline1\nline2")

        # writing None removes the file
        self.store.write_file("_file", None)
        self.assertFalse(self.store.exists("_file"))

        self.assertRaises(TypeError, self.store.write_string, "_file", 123)
        self.assertRaises(TypeError, self.store.write_string, "_file", ["123"])

    def test_read_write_int(self):
        self.store.write_int("_int", 123)
        self.fileEquals("_int", "123\n")
        self.assertEqual(self.store.read_int("_int"), 123)

        # writing None removes the file
        self.store.write_int("_int", None)
        self.assertFalse(self.store.exists("_int"))

        self.assertRaises(TypeError, self.store.write_int, "_int", "123")
        self.assertRaises(TypeError, self.store.write_int, "_int", b"123")
        self.assertRaises(TypeError, self.store.write_int, "_int", ["123"])

    def test_read_write_list(self):
        self.store.write_list("_list", ["one", "two", "three"])
        self.fileEquals("_list", "one\ntwo\nthree\n")
        self.assertEqual(self.store.read_list("_list"), ["one", "two", "three"])

        # writing None removes the file
        self.store.write_list("_list", None)
        self.assertFalse(self.store.exists("_list"))

        self.assertRaises(TypeError, self.store.write_list, "_list", "123")
        self.assertRaises(TypeError, self.store.write_list, "_list", b"123")
        self.assertRaises(TypeError, self.store.write_list, "_list", 123)

    def test_read_write_string(self):
        self.store.write_string("_string", "string")
        self.fileEquals("_string", "string\n")
        self.assertEqual(self.store.read_string("_string"), "string")

        self.store.write_string("_bytes", b"bytes")
        self.fileEquals("_bytes", "bytes\n")
        self.assertEqual(self.store.read_string("_bytes"), "bytes")

        # writing None removes the file
        self.store.write_string("_string", None)
        self.assertFalse(self.store.exists("_string"))

        self.assertRaises(TypeError, self.store.write_string, "_string", 123)
        self.assertRaises(TypeError, self.store.write_string, "_string", ["123"])

    def test_contains(self):
        self.assertTrue("_project" in self.store)
        self.assertTrue("_package" in self.store)
        self.assertFalse("_foo" in self.store)

    def test_iter(self):
        self.assertEqual(len(list(self.store)), 2)
        for fn in self.store:
            self.assertIn(fn, ["_project", "_package"])

    def test_apiurl(self):
        self.store.apiurl = "https://example.com"
        self.fileEquals("_apiurl", "https://example.com\n")

        store2 = Store(self.tmpdir)
        self.assertEqual(store2.apiurl, "https://example.com")

    def test_apiurl_no_trailing_slash(self):
        self.store.apiurl = "https://example.com/"
        self.fileEquals("_apiurl", "https://example.com\n")

        self.store.write_string("_apiurl", "https://example.com/")
        self.fileEquals("_apiurl", "https://example.com/\n")
        self.assertEqual(self.store.apiurl, "https://example.com")

    def test_package(self):
        self.fileEquals("_package", "package name\n")

        store2 = Store(self.tmpdir)
        self.assertEqual(store2.package, "package name")

    def test_project(self):
        self.fileEquals("_project", "project name\n")

        store2 = Store(self.tmpdir)
        self.assertEqual(store2.project, "project name")

    def test_scmurl(self):
        self.store.scmurl = "https://example.com/project.git"
        self.fileEquals("_scm", "https://example.com/project.git\n")

        store2 = Store(self.tmpdir)
        self.assertEqual(store2.scmurl, "https://example.com/project.git")

    def test_size_limit(self):
        self.store.size_limit = 123
        self.fileEquals("_size_limit", "123\n")

        store2 = Store(self.tmpdir)
        self.assertEqual(store2.size_limit, 123)

    def test_to_be_added(self):
        self.store.to_be_added = ["foo", "bar", "baz"]
        self.fileEquals("_to_be_added", "foo\nbar\nbaz\n")

        store2 = Store(self.tmpdir)
        self.assertEqual(store2.to_be_added, ["foo", "bar", "baz"])

    def test_to_be_deleted(self):
        self.store.to_be_deleted = ["foo", "bar", "baz"]
        self.fileEquals("_to_be_deleted", "foo\nbar\nbaz\n")

        store2 = Store(self.tmpdir)
        self.assertEqual(store2.to_be_deleted, ["foo", "bar", "baz"])

    def test_in_conflict(self):
        self.store.in_conflict = ["foo", "bar", "baz"]
        self.fileEquals("_in_conflict", "foo\nbar\nbaz\n")

        store2 = Store(self.tmpdir)
        self.assertEqual(store2.in_conflict, ["foo", "bar", "baz"])

    def test_osclib_version(self):
        # no setter, users are not supposed to set the version
        self.assertRaises(AttributeError, setattr, self.store, "osclib_version", "123")
        self.store.write_string("_osclib_version", "123")
        self.fileEquals("_osclib_version", "123\n")

        store2 = Store(self.tmpdir)
        self.assertEqual(store2.osclib_version, "123")

    def test_files(self):
        files = [
            osc_core.File(name="foo", md5="aabbcc", size=1, mtime=2),
            osc_core.File(name="bar", md5="ddeeff", size=3, mtime=4, skipped=True),
        ]

        self.store.files = files

        expected = """
<directory>
  <entry name="bar" md5="ddeeff" size="3" mtime="4" skipped="true" />
  <entry name="foo" md5="aabbcc" size="1" mtime="2" />
</directory>""".lstrip()

        if sys.version_info[:2] <= (3, 7):
            # ElementTree doesn't preserve attribute order on py <= 3.7; https://bugs.python.org/issue34160
            expected = """
<directory>
  <entry md5="ddeeff" mtime="4" name="bar" size="3" skipped="true" />
  <entry md5="aabbcc" mtime="2" name="foo" size="1" />
</directory>""".lstrip()

        self.fileEquals("_files", expected)

        store2 = Store(self.tmpdir)
        files2 = store2.files
        # files got ordered
        self.assertTrue(files2[0] == files[1])
        self.assertTrue(files2[1] == files[0])

    def test_last_buildroot(self):
        self.store.last_buildroot = "repo", "arch", "vm_type"
        self.fileEquals("_last_buildroot", "repo\narch\nvm_type\n")

        self.assertRaises(ValueError, setattr, self.store, "last_buildroot", ["one"])
        self.assertRaises(ValueError, setattr, self.store, "last_buildroot", ["one", "two"])
        self.assertRaises(ValueError, setattr, self.store, "last_buildroot", ["one", "two", "three", "four"])

        store2 = Store(self.tmpdir)
        self.assertEqual(store2.last_buildroot, ["repo", "arch", "vm_type"])

    def test_meta_node(self):
        self.store.write_string(
            "_meta",
            """<package name="test-pkgA" project="projectA">
  <title>title</title>
  <description>desc</description>
  <releasename>name</releasename>
  <build>
    <enable repository="repo1"/>
    <enable repository="repo2"/>
  </build>
</package>""",
        )
        node = self.store._meta_node
        self.assertNotEqual(node, None)

        # try to read the _meta via a package class
        from osc._private import LocalPackage

        self.store.files = []
        pkg = LocalPackage(self.tmpdir)
        self.assertEqual(pkg.get_meta_value("releasename"), "name")


if __name__ == "__main__":
    unittest.main()
