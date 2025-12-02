import contextlib
import io
import os
import shutil
import subprocess
import tempfile
import unittest

import osc.conf
from osc import oscerr
from osc.git_scm.store import GitStore
from osc.git_scm.store import LocalGitStore
from osc.util import yaml as osc_yaml

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
        store = GitStore(self.tmpdir, check=False)
        self.assertEqual(store.package, "my-package")

    def test_project(self):
        store = GitStore(self.tmpdir, check=False)
        self.assertEqual(store.project, None)

    def test_last_buildroot(self):
        store = GitStore(self.tmpdir, check=False)
        self.assertEqual(store.last_buildroot, None)
        store.last_buildroot = ("repo", "arch", "vm_type")

        store = GitStore(self.tmpdir, check=False)
        self.assertEqual(store.last_buildroot, ("repo", "arch", "vm_type"))

    def test_last_buildroot_empty_vm_type(self):
        store = GitStore(self.tmpdir, check=False)
        self.assertEqual(store.last_buildroot, None)
        store.last_buildroot = ("repo", "arch", None)

        store = GitStore(self.tmpdir, check=False)
        self.assertEqual(store.last_buildroot, ("repo", "arch", None))

    def test_scmurl(self):
        store = GitStore(self.tmpdir, check=False)
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

    def _git_init(self, path, *, branch="factory", separate_git_dir=None):
        os.makedirs(path, exist_ok=True)
        git_init_cmd = ["git", "init", "-q"]
        if separate_git_dir:
            git_init_cmd += ["--separate-git-dir", separate_git_dir]
        subprocess.check_output(git_init_cmd, cwd=path)
        subprocess.check_output(["git", "config", "user.email", "user@example.com"], cwd=path)
        subprocess.check_output(["git", "config", "user.name", "User Name"], cwd=path)
        subprocess.check_output(["git", "commit", "-m", "empty", "--allow-empty"], cwd=path)
        subprocess.check_output(["git", "checkout", "-b", branch, "-q"], cwd=path)
        subprocess.check_output(["git", "remote", "add", "origin", "https://example.com/packages/my-package.git"], cwd=path)

    def _setup_project(self, path, *, apiurl="https://api.example.com", project=None):
        store = LocalGitStore(path, check=False)
        store._type = "project"
        if apiurl:
            store.apiurl = apiurl
        if project:
            store.project = project

    def _setup_package(self, path, *, apiurl="https://api.example.com", project=None, package=None):
        store = LocalGitStore(path, check=False)
        store._type = "package"
        if apiurl:
            store.apiurl = apiurl
        if project:
            store.project = project
        if package:
            store.package = package

    def _osc_init(self, path, *, apiurl="https://api.example.com", project=None, package=None):
        from osc.store import Store

        os.makedirs(path, exist_ok=True)
        store = Store(path, check=False)
        store.apiurl = apiurl
        store.project = project
        store.package = package

    def _write(self, path: str, data: str = ""):
        with open(path, "w", encoding="utf-8") as f:
            f.write(data)

    def test_pkg_no_project(self):
        pkg_path = os.path.join(self.tmpdir, "pkg")
        self._git_init(pkg_path)

        with self.assertRaises(oscerr.NoWorkingCopy):
            GitStore(pkg_path)

        store = GitStore(pkg_path, check=False)
        self.assertEqual(store.project, None)
        self.assertEqual(store.package, "my-package")

    def test_pkg_osc_project(self):
        prj_path = os.path.join(self.tmpdir, "project")
        self._osc_init(prj_path, project="PROJ")

        pkg_path = os.path.join(prj_path, "package")
        self._git_init(pkg_path)

        store = GitStore(pkg_path)
        self.assertEqual(store.project, "PROJ")
        self.assertEqual(store.package, "package")

    def test_nested_pkg_osc_project_from_git(self):
        # project .git and .osc are next to each other
        prj_path = os.path.join(self.tmpdir, "project")
        self._git_init(prj_path)
        self._write(os.path.join(prj_path, "_config"))
        self._osc_init(prj_path, project="PROJ")

        # the nested package must be under a subdirectory tracked in _subdirs file
        # otherwise it's not recognized as a package
        subdirs = {"subdirs": ["group"]}
        self._write(os.path.join(prj_path, "_subdirs"), osc_yaml.yaml_dumps(subdirs))

        pkg_path = os.path.join(prj_path, "group/package")
        os.makedirs(pkg_path, exist_ok=True)

        store = GitStore(pkg_path)
        self.assertEqual(store.project, "PROJ")
        self.assertEqual(store.package, "package")

    def test_nested_pkg_osc_project_from_git_both_subdirs_and_manifest(self):
        # project .git and .osc are next to each other
        prj_path = os.path.join(self.tmpdir, "project")
        self._git_init(prj_path)
        self._write(os.path.join(prj_path, "_config"))
        self._osc_init(prj_path, project="PROJ")

        # the nested package must be under a subdirectory tracked in _subdirs file
        # otherwise it's not recognized as a package
        # IMPORTANT: in this case, _manifest prevails over _subdirs
        subdirs = {"subdirs": ["does-not-exist"]}
        self._write(os.path.join(prj_path, "_subdirs"), osc_yaml.yaml_dumps(subdirs))

        # the nested package must be under a subdirectory tracked in _manifest file
        # otherwise it's not recognized as a package
        subdirs = {"subdirectories": ["group"]}
        self._write(os.path.join(prj_path, "_manifest"), osc_yaml.yaml_dumps(subdirs))

        pkg_path = os.path.join(prj_path, "group/package")
        os.makedirs(pkg_path, exist_ok=True)

        store = GitStore(pkg_path)
        self.assertEqual(store.project, "PROJ")
        self.assertEqual(store.package, "package")

    def test_manifest_packages(self):
        # project .git and .osc are next to each other
        prj_path = os.path.join(self.tmpdir, "project")
        self._git_init(prj_path)
        self._write(os.path.join(prj_path, "_config"))
        self._osc_init(prj_path, project="PROJ")

        manifest_data = {"packages": ["group/package"]}
        self._write(os.path.join(prj_path, "_manifest"), osc_yaml.yaml_dumps(manifest_data))

        pkg_path = os.path.join(prj_path, "group/package")
        os.makedirs(pkg_path, exist_ok=True)

        store = GitStore(pkg_path)
        self.assertEqual(store.project, "PROJ")
        self.assertEqual(store.package, "package")

    def test_manifest_subdirectories(self):
        # project .git and .osc are next to each other
        prj_path = os.path.join(self.tmpdir, "project")
        self._git_init(prj_path)
        self._write(os.path.join(prj_path, "_config"))
        self._osc_init(prj_path, project="PROJ")

        manifest_data = {"subdirectories": ["group"]}
        self._write(os.path.join(prj_path, "_manifest"), osc_yaml.yaml_dumps(manifest_data))

        pkg_path = os.path.join(prj_path, "group/package")
        os.makedirs(pkg_path, exist_ok=True)

        store = GitStore(pkg_path)
        self.assertEqual(store.project, "PROJ")
        self.assertEqual(store.package, "package")

    def test_manifest_apiurl_project(self):
        # project .git and .osc are next to each other
        prj_path = os.path.join(self.tmpdir, "project")
        self._git_init(prj_path)

        manifest_data = {
            "packages": ["group/package"],
            "obs_apiurl": "https://api.example.com",
            "obs_project": "example-project",
        }
        self._write(os.path.join(prj_path, "_manifest"), osc_yaml.yaml_dumps(manifest_data))

        pkg_path = os.path.join(prj_path, "group/package")
        os.makedirs(pkg_path, exist_ok=True)

        store = GitStore(pkg_path)
        self.assertEqual(store.apiurl, "https://api.example.com")
        self.assertEqual(store.project, "example-project")
        self.assertEqual(store.package, "package")

    def test_pkg_git_project(self):
        prj_path = os.path.join(self.tmpdir, "project")
        self._git_init(prj_path)
        self._setup_project(prj_path, project="PROJ")
        self._write(os.path.join(prj_path, "_config"))

        pkg_path = os.path.join(prj_path, "package")
        self._git_init(pkg_path)

        store = GitStore(pkg_path)
        self.assertEqual(store.project, "PROJ")
        self.assertEqual(store.package, "package")

    def test_pkg_git_project_with_config_without_pbuild(self):
        prj_path = os.path.join(self.tmpdir, "project")
        self._git_init(prj_path)
        self._setup_project(prj_path, project="PROJ")
        self._write(os.path.join(prj_path, "_config"))

        pkg_path = os.path.join(prj_path, "package")
        self._git_init(pkg_path)

        store = GitStore(pkg_path)
        self.assertEqual(store.project, "PROJ")
        self.assertEqual(store.package, "package")

    def test_pkg_git_project_without_config_with_pbuild(self):
        prj_path = os.path.join(self.tmpdir, "project")
        self._git_init(prj_path)
        self._setup_project(prj_path, project="PROJ")
        self._write(os.path.join(prj_path, "_pbuild"))

        pkg_path = os.path.join(prj_path, "package")
        self._git_init(pkg_path)

        store = GitStore(pkg_path)
        self.assertEqual(store.project, "PROJ")
        self.assertEqual(store.package, "package")

    def test_pkg_separate_git_dir_git_project(self):
        prj_path = os.path.join(self.tmpdir, "project")
        self._git_init(prj_path)
        self._setup_project(prj_path, project="PROJ")
        self._write(os.path.join(prj_path, "_config"))

        # .git is not a directory, it's a file that contains "gitdir: <path>"
        pkg_path = os.path.join(prj_path, "package")
        self._git_init(pkg_path, separate_git_dir="../package-git-dir")

        store = GitStore(pkg_path, check=False)
        self.assertEqual(store.project, "PROJ")
        self.assertEqual(store.package, "package")

    def test_pkg_git_with_no_project(self):
        prj_path = os.path.join(self.tmpdir, "project")
        self._git_init(prj_path)
        self._write(os.path.join(prj_path, "_config"))
        self._write(os.path.join(prj_path, "project.build"), "PROJ")

        git_subdir_path = os.path.join(prj_path, "git")
        self._git_init(git_subdir_path)

        pkg_path = os.path.join(git_subdir_path, "package")
        self._git_init(pkg_path)

        # the parent directory contains arbitrary git repo -> no project
        with self.assertRaises(oscerr.NoWorkingCopy):
            GitStore(pkg_path)

    def test_pkg_git_in_submodule(self):
        import subprocess

        pkg_upstream_path = os.path.join(self.tmpdir, "pkg-upstream")
        self._git_init(pkg_upstream_path)

        prj_path = os.path.join(self.tmpdir, "project")
        self._git_init(prj_path)
        manifest_data = {
            "obs_apiurl": "https://api.example.com",
            "obs_project": "PROJ",
        }
        self._write(os.path.join(prj_path, "_manifest"), osc_yaml.yaml_dumps(manifest_data))

        subprocess.check_output(["git", "-c", "protocol.file.allow=always", "submodule", "add", pkg_upstream_path, "pkg"], cwd=prj_path, stderr=subprocess.DEVNULL)
        pkg_path = os.path.join(prj_path, "pkg")

        store = GitStore(pkg_path)
        self.assertEqual(store.project, "PROJ")
        self.assertEqual(store.package, "pkg")

    def test_project_with_different_branch(self):
        prj_path = os.path.join(self.tmpdir, "project")
        self._git_init(prj_path, branch="project-foo")
        manifest_data = {
            "obs_apiurl": "https://api.example.com",
            "obs_project": "PROJ",
        }

        self._write(os.path.join(prj_path, "_manifest"), osc_yaml.yaml_dumps(manifest_data))

        pkg_path = os.path.join(prj_path, "package")
        self._git_init(pkg_path, branch="project-bar")

        stderr = io.StringIO()
        with contextlib.redirect_stderr(stderr):
            GitStore(pkg_path)
        self.assertIn("WARNING", stderr.getvalue())

    def test_project_with_empty_manifest(self):
        prj_path = os.path.join(self.tmpdir, "project")
        self._git_init(prj_path)
        self._setup_project(prj_path, project="PROJ")
        self._write(os.path.join(prj_path, "_manifest"), "")

        pkg_path = os.path.join(prj_path, "package")
        os.makedirs(pkg_path)

        store = GitStore(prj_path)
        self.assertEqual(store.project, "PROJ")

        paths = store.manifest.get_package_paths(store.topdir)
        self.assertEqual(paths, [pkg_path])


if __name__ == "__main__":
    unittest.main()
