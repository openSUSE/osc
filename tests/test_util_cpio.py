import os
import shutil
import tempfile
import unittest

from osc.util.cpio import CpioRead
from osc.util.cpio import CpioError


FIXTURES_DIR = os.path.join(os.path.dirname(__file__), "fixtures")


class TestCpio(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.mkdtemp(prefix="osc_test_")
        try:
            self.old_cwd = os.getcwd()
        except FileNotFoundError:
            self.old_cwd = os.path.expanduser("~")
        os.chdir(self.tmpdir)
        self.archive = os.path.join(FIXTURES_DIR, "archive.cpio")
        self.cpio = CpioRead(self.archive)
        self.cpio.read()

    def tearDown(self):
        os.chdir(self.old_cwd)
        shutil.rmtree(self.tmpdir)

    def test_file_list(self):
        actual = [i.filename for i in self.cpio]
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

    def test_copyin_file(self):
        path = self.cpio.copyin_file("a\nb", dest=self.tmpdir)

        # check that we've got the expected path
        self.assertEqual(path, os.path.join(self.tmpdir, "a\nb"))

        # ... and that the contents also match
        with open(path, "r", encoding="utf-8") as f:
            self.assertEqual(f.read(), "newline\n")

    def test_copyin_file_abspath(self):
        self.assertRaises(CpioError, self.cpio.copyin_file, "/tmp/foo")

    def test_copyin_file_subdir(self):
        path = self.cpio.copyin_file("dir/file", dest=self.tmpdir)

        # check that we've got the expected path
        self.assertEqual(path, os.path.join(self.tmpdir, "dir/file"))

        # ... and that the contents also match
        with open(path, "r", encoding="utf-8") as f:
            self.assertEqual(f.read(), "file-in-a-dir\n")


if __name__ == "__main__":
    unittest.main()
