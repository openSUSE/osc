import os
import shutil
import subprocess
import tempfile
import unittest

from osc.git_scm.store import GitStore


class TestGitStore(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.mkdtemp(prefix="osc_test")
        os.chdir(self.tmpdir)
        # 'git init -b <initial-branch>' is not supported on older distros
        subprocess.check_output(["git", "init", "-q"])
        subprocess.check_output(["git", "checkout", "-b", "factory", "-q"])
        subprocess.check_output(["git", "remote", "add", "origin", "https://example.com/packages/my-package.git"])

    def tearDown(self):
        try:
            shutil.rmtree(self.tmpdir)
        except OSError:
            pass

    def test_package(self):
        store = GitStore(self.tmpdir)
        self.assertEqual(store.package, "my-package")

    def test_project(self):
        store = GitStore(self.tmpdir)
        self.assertEqual(store.project, "openSUSE:Factory")

    def test_last_buildroot(self):
        store = GitStore(self.tmpdir)
        self.assertEqual(store.last_buildroot, None)
        store.last_buildroot = ("repo", "arch", "vm_type")

        store = GitStore(self.tmpdir)
        self.assertEqual(store.last_buildroot, ("repo", "arch", "vm_type"))

    def test_last_buildroot_empty_vm_type(self):
        store = GitStore(self.tmpdir)
        self.assertEqual(store.last_buildroot, None)
        store.last_buildroot = ("repo", "arch", None)

        store = GitStore(self.tmpdir)
        self.assertEqual(store.last_buildroot, ("repo", "arch", None))

    def test_scmurl(self):
        store = GitStore(self.tmpdir)
        self.assertEqual(store.scmurl, "https://example.com/packages/my-package.git")


if not shutil.which("git"):
    TestGitStore = unittest.skip("The 'git' executable is not available")(TestGitStore)


if __name__ == "__main__":
    unittest.main()
