import os
import shutil
import subprocess
import tempfile
import unittest

import osc.conf
from osc.git_scm.store import GitStore

from .common import patch


@unittest.skipIf(not shutil.which("git"), "The 'git' executable is not available")
class TestGitStore(unittest.TestCase):
    def setUp(self):
        environ = {
            "OSC_CONFIG": "/dev/null",
            "OSC_APIURL": "",
            "OSC_USERNAME": "user",
            "OSC_PASSWORD": "pass",
        }
        with patch.dict(os.environ, environ, clear=True):
            # reload osc configuration to use the ENV variables
            osc.conf.get_config()

        self.tmpdir = tempfile.mkdtemp(prefix="osc_test_")

        # 'git init -b <initial-branch>' is not supported on older distros
        subprocess.check_output(["git", "init", "-q"], cwd=self.tmpdir)
        subprocess.check_output(["git", "checkout", "-b", "factory", "-q"], cwd=self.tmpdir)
        subprocess.check_output(["git", "remote", "add", "origin", "https://example.com/packages/my-package.git"], cwd=self.tmpdir)

    def tearDown(self):
        osc.conf.config = None
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


@unittest.skipIf(not shutil.which("git"), "The 'git' executable is not available")
class TestGitStoreProject(unittest.TestCase):
    """
    We're guessting the project so much that it requires testing.
    """

    def setUp(self):
        environ = {
            "OSC_CONFIG": "/dev/null",
            "OSC_APIURL": "",
            "OSC_USERNAME": "user",
            "OSC_PASSWORD": "pass",
        }
        with patch.dict(os.environ, environ, clear=True):
            # reload osc configuration to use the ENV variables
            osc.conf.get_config()

        self.tmpdir = tempfile.mkdtemp(prefix="osc_test_")

    def tearDown(self):
        osc.conf.config = None
        try:
            shutil.rmtree(self.tmpdir)
        except OSError:
            pass

    def _git_init(self, path):
        os.makedirs(path, exist_ok=True)
        subprocess.check_output(["git", "init", "-q"], cwd=path)
        subprocess.check_output(["git", "checkout", "-b", "factory", "-q"], cwd=path)
        subprocess.check_output(["git", "remote", "add", "origin", "https://example.com/packages/my-package.git"], cwd=path)

    def _osc_init(self, path, project, package=None):
        from osc.store import Store

        os.makedirs(path, exist_ok=True)
        store = Store(path, check=False)
        store.project = project
        store.package = package

    def _write(self, path: str, data: str = ""):
        with open(path, "w", encoding="utf-8") as f:
            f.write(data)

    def test_pkg_no_project(self):
        pkg_path = os.path.join(self.tmpdir, "pkg")
        self._git_init(pkg_path)

        store = GitStore(pkg_path)
        # fallback to openSUSE:Factory
        self.assertEqual(store.project, "openSUSE:Factory")
        self.assertEqual(store.package, "my-package")

    def test_pkg_osc_project(self):
        prj_path = os.path.join(self.tmpdir, "project")
        self._osc_init(prj_path, project="PROJ")

        pkg_path = os.path.join(prj_path, "package")
        self._git_init(pkg_path)

        store = GitStore(pkg_path)
        self.assertEqual(store.project, "PROJ")
        self.assertEqual(store.package, "my-package")

    def test_pkg_git_project(self):
        prj_path = os.path.join(self.tmpdir, "project")
        self._git_init(prj_path)
        self._write(os.path.join(prj_path, "_config"))
        self._write(os.path.join(prj_path, "project.build"), "PROJ")

        pkg_path = os.path.join(prj_path, "package")
        self._git_init(pkg_path)

        store = GitStore(pkg_path)
        self.assertEqual(store.project, "PROJ")
        self.assertEqual(store.package, "my-package")

    def test_pkg_git_with_no_project(self):
        prj_path = os.path.join(self.tmpdir, "project")
        self._git_init(prj_path)
        self._write(os.path.join(prj_path, "_config"))
        self._write(os.path.join(prj_path, "project.build"), "PROJ")

        git_subdir_path = os.path.join(prj_path, "git")
        self._git_init(git_subdir_path)

        pkg_path = os.path.join(git_subdir_path, "package")
        self._git_init(pkg_path)

        store = GitStore(pkg_path)
        # the parent directory contains arbitrary git repo -> fallback to openSUSE:Factory
        self.assertEqual(store.project, "openSUSE:Factory")
        self.assertEqual(store.package, "my-package")

    def test_pkg_git_project_ObsPrj(self):
        pkg_path = os.path.join(self.tmpdir, "package")
        self._git_init(pkg_path)

        class Repo:
            def clone(self, *args, **kwargs):
                path = kwargs["directory"]
                with open(os.path.join(path, "_config"), "w", encoding="utf-8") as f:
                    f.write("")
                with open(os.path.join(path, "project.build"), "w", encoding="utf-8") as f:
                    f.write("PROJ")

        with patch("osc.gitea_api.Config"), patch("osc.gitea_api.Connection"):
            with patch("osc.gitea_api.Repo", new_callable=Repo) as mock_clone:
                store = GitStore(pkg_path)
                self.assertEqual(store.project, "PROJ")
                self.assertEqual(store.package, "my-package")

    def test_pkg_git_project_ObsPrj_no_config(self):
        pkg_path = os.path.join(self.tmpdir, "package")
        self._git_init(pkg_path)

        class Repo:
            def clone(self, *args, **kwargs):
                path = kwargs["directory"]
                with open(os.path.join(path, "project.build"), "w", encoding="utf-8") as f:
                    f.write("PROJ")

        with patch("osc.gitea_api.Config"), patch("osc.gitea_api.Connection"):
            with patch("osc.gitea_api.Repo", new_callable=Repo) as mock_clone:
                store = GitStore(pkg_path)
                self.assertEqual(store.project, "PROJ")
                self.assertEqual(store.package, "my-package")

    def test_pkg_git_project_ObsPrj_no_project_build(self):
        pkg_path = os.path.join(self.tmpdir, "package")
        self._git_init(pkg_path)

        class Repo:
            def clone(self, *args, **kwargs):
                path = kwargs["directory"]
                with open(os.path.join(path, "_config"), "w", encoding="utf-8") as f:
                    f.write("")

        with patch("osc.gitea_api.Config"), patch("osc.gitea_api.Connection"):
            with patch("osc.gitea_api.Repo", new_callable=Repo) as mock_clone:
                store = GitStore(pkg_path)
                self.assertEqual(store.project, "openSUSE:Factory")
                self.assertEqual(store.package, "my-package")


if __name__ == "__main__":
    unittest.main()
