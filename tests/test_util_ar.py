import os
import shutil
import tempfile
import unittest

from osc.util.ar import Ar
from osc.util.ar import ArError


FIXTURES_DIR = os.path.join(os.path.dirname(__file__), "fixtures")


class TestAr(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.mkdtemp(prefix="osc_test_")
        try:
            self.old_cwd = os.getcwd()
        except FileNotFoundError:
            self.old_cwd = os.path.expanduser("~")
        os.chdir(self.tmpdir)
        self.archive = os.path.join(FIXTURES_DIR, "archive.ar")
        self.ar = Ar(self.archive)
        self.ar.read()

    def tearDown(self):
        os.chdir(self.old_cwd)
        shutil.rmtree(self.tmpdir)

    def test_file_list(self):
        actual = [i.name for i in self.ar]
        expected = [
            # absolute path
            b"/tmp/foo",
            # this is a filename, not a long filename reference
            b"/123",
            b"very-long-long-long-long-name",
            b"very-long-long-long-long-name2",
            # long file name with a newline
            b"very-long-name\n-with-newline",
            # short file name with a newline
            b"a\nb",
            b"dir/file",
        ]
        self.assertEqual(actual, expected)

    def test_get_file(self):
        f = self.ar.get_file(b"/tmp/foo")
        self.assertIsNotNone(f)

        f = self.ar.get_file("/tmp/foo")
        self.assertIsNotNone(f)

        f = self.ar.get_file("does-not-exist")
        self.assertIsNone(f)

    def test_saveTo(self):
        f = self.ar.get_file("a\nb")
        path = f.saveTo(self.tmpdir)

        # check that we've got the expected path
        self.assertEqual(path, os.path.join(self.tmpdir, "a\nb"))

        # ... and that the contents also match
        with open(path, "r", encoding="utf-8") as f:
            self.assertEqual(f.read(), "newline\n")

    def test_saveTo_subdir(self):
        f = self.ar.get_file("dir/file")
        path = f.saveTo(self.tmpdir)

        # check that we've got the expected path
        self.assertEqual(path, os.path.join(self.tmpdir, "dir/file"))

        # ... and that the contents also match
        with open(path, "r", encoding="utf-8") as f:
            self.assertEqual(f.read(), "file-in-a-dir\n")

    def test_saveTo_abspath(self):
        f = self.ar.get_file("/tmp/foo")
        assert f is not None
        # this is supposed to throw an error, extracting files with absolute paths might overwrite system files
        self.assertRaises(ArError, f.saveTo, self.tmpdir)

    def test_no_exthdr(self):
        self.archive = os.path.join(FIXTURES_DIR, "archive-no-ext_fnhdr.ar")
        self.ar = Ar(self.archive)
        self.ar.read()
        self.test_saveTo_subdir()


if __name__ == "__main__":
    unittest.main()
