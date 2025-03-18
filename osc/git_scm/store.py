import json
import os
import subprocess
import urllib.parse
from pathlib import Path

import ruamel.yaml

from .. import conf as osc_conf
from .. import oscerr


class GitStore:

    @classmethod
    def is_project_dir(cls, path):
        try:
            store = cls(path)
        except oscerr.NoWorkingCopy:
            return False
        return store.is_project

    @classmethod
    def is_package_dir(cls, path):
        try:
            store = cls(path)
        except oscerr.NoWorkingCopy:
            return False
        return store.is_package

    @property
    def git_project_dir(self):
        if not hasattr(self, "_git_project_dir"):
            self._git_project_dir = None
            path = self.abspath
            while path and path != "/":
                path, _ = os.path.split(path)

                osc_path = os.path.join(path, ".osc")
                git_path = os.path.join(path, ".git")
                config_path = os.path.join(path, "_config")
                pbuild_path = os.path.join(path, "_pbuild")
                subdirs_path = os.path.join(path, "_subdirs")

                if os.path.isdir(osc_path) and os.path.isdir(git_path) and (os.path.isfile(config_path) or os.path.isfile(pbuild_path)):
                    if os.path.isfile(subdirs_path):
                        # the _subdirs file contains a list of project subdirs that contain packages
                        yaml = ruamel.yaml.YAML()
                        with open(subdirs_path, "r") as f:
                            subdirs = yaml.load(f).get("subdirs", [])
                        subdirs_abspath = [os.path.abspath(os.path.join(path, subdir)) for subdir in subdirs]
                        if os.path.abspath(os.path.join(self.abspath, "..")) not in subdirs_abspath:
                            break
                    else:
                        # no _subdirs file and self.abspath is not directly under the project dir -> not a valid package
                        if path != os.path.abspath(os.path.join(self.abspath, "..")):
                            break

                    self._git_project_dir = path
                    break
        return self._git_project_dir

    def __init__(self, path, check=True):
        self.path = path
        self.abspath = os.path.abspath(self.path)

        self.is_project = False
        self.is_package = False

        self.project_obs_scm_store = None

        if os.path.isdir(os.path.join(self.abspath, ".git")):
            # NOTE: we have only one store in project-git for all packages
            config_path = os.path.join(self.abspath, "_config")
            pbuild_path = os.path.join(self.abspath, "_pbuild")
            if os.path.isfile(config_path) or os.path.isfile(pbuild_path):
                # there's .git and _config/_pbuild in the working directory -> it's a project
                self.is_project = True
            else:
                # there's .git and no _config/_pbuild in the working directory -> it's a package
                self.is_package = True
        elif self.git_project_dir:
            from ..obs_scm import Store

            # there's no .git in the working directory and there's .osc, .git and _config/_pbuild in the parent directory tree -> it's a package
            self.is_package = True
            self.project_obs_scm_store = Store(self.git_project_dir, check=False)

        self._apiurl = None
        self._package = None
        self._project = None

        if check and not any([self.is_project, self.is_package]):
            msg = f"Directory '{self.path}' is not a Git SCM working copy"
            raise oscerr.NoWorkingCopy(msg)

        if check and not self.scmurl:
            msg = f"Directory '{self.path}' is a Git SCM repo that lacks the 'origin' remote"
            raise oscerr.NoWorkingCopy(msg)

        # TODO: decide if we need explicit 'git lfs pull' or not
        # self._run_git(["lfs", "pull"])

    def assert_is_project(self):
        if not self.is_project:
            msg = f"Directory '{self.path}' is not a Git SCM working copy of a project"
            raise oscerr.NoWorkingCopy(msg)

    def assert_is_package(self):
        if not self.is_package:
            msg = f"Directory '{self.path}' is not a Git SCM working copy of a package"
            raise oscerr.NoWorkingCopy(msg)

    def _run_git(self, args):
        return subprocess.check_output(["git"] + args, encoding="utf-8", cwd=self.abspath).strip()

    @property
    def apiurl(self):
        if not self._apiurl:
            if self.is_package and self.project_obs_scm_store:
                # read apiurl from parent directory that contains a project with .osc metadata
                self._apiurl = self.project_obs_scm_store.apiurl
            if not self._apiurl:
                # HACK: use the currently configured apiurl
                self._apiurl = osc_conf.config["apiurl"]
        return self._apiurl

    @apiurl.setter
    def apiurl(self, value):
        self._apiurl = value

    @property
    def project(self):
        if not self._project:
            if self.is_package and self.project_obs_scm_store:
                # read project from parent directory that contains a project with .osc metadata
                self._project = self.project_obs_scm_store.project
            if not self._project:
                # HACK: assume openSUSE:Factory project if project metadata is missing
                self._project = "openSUSE:Factory"
        return self._project

    @project.setter
    def project(self, value):
        self._project = value

    @property
    def package(self):
        if self._package is None:
            origin = self._run_git(["remote", "get-url", "origin"])
            self._package = Path(urllib.parse.urlsplit(origin).path).stem
        return self._package

    @package.setter
    def package(self, value):
        self._package = value

    def _get_option(self, name):
        try:
            result = self._run_git(["config", "--local", "--get", f"osc.{name}"])
        except subprocess.CalledProcessError:
            result = None
        return result

    def _check_type(self, name, value, expected_type):
        if not isinstance(value, expected_type):
            raise TypeError(f"The option '{name}' should be {expected_type.__name__}, not {type(value).__name__}")

    def _set_option(self, name, value):
        self._run_git(["config", "--local", f"osc.{name}", value])

    def _unset_option(self, name):
        try:
            self._run_git(["config", "--local", "--unset", f"osc.{name}"])
        except subprocess.CalledProcessError:
            pass

    def _get_dict_option(self, name):
        result = self._get_option(name)
        if result is None:
            return None
        result = json.loads(result)
        self._check_type(name, result, dict)
        return result

    def _set_dict_option(self, name, value):
        if value is None:
            self._unset_option(name)
            return
        self._check_type(name, value, dict)
        value = json.dumps(value)
        self._set_option(name, value)

    @property
    def last_buildroot(self):
        self.assert_is_package()
        result = self._get_dict_option("last-buildroot")
        if result is not None:
            result = (result["repo"], result["arch"], result["vm_type"])
        return result

    @last_buildroot.setter
    def last_buildroot(self, value):
        self.assert_is_package()
        if len(value) != 3:
            raise ValueError("A tuple with exactly 3 items is expected: (repo, arch, vm_type)")
        value = {
            "repo": value[0],
            "arch": value[1],
            "vm_type": value[2],
        }
        self._set_dict_option("last-buildroot", value)

    @property
    def scmurl(self):
        try:
            return self._run_git(["remote", "get-url", "origin"])
        except subprocess.CalledProcessError:
            return None
