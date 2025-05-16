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

    @staticmethod
    def get_build_project(git_repo_url: str):
        """
        Get the project we use for building from _ObsPrj git repo.
        The _ObsPrj is located under the same owner as the repo with the package.
        They share the same branch.
        """
        import tempfile

        from osc import gitea_api

        # parse the git_repo_url (which usually corresponds with the url of the 'origin' remote of the local git repo)
        scheme, netloc, path, params, query, fragment = gitea_api.Git.urlparse(git_repo_url)

        # scheme + host
        gitea_host = urllib.parse.urlunparse((scheme, netloc, "", None, None, None))

        # OBS and Gitea usernames are identical
        # XXX: we're using the configured apiurl; it would be great to have a mapping from -G/--gitea-login to -A/--apiurl so we don't have to provide -A on the command-line
        apiurl = osc_conf.config["apiurl"]
        gitea_user = osc_conf.get_apiurl_usr(apiurl)

        # remove trailing ".git" from path
        if path.endswith(".git"):
            path = path[:-4]

        gitea_owner, gitea_repo = path.strip("/").split("/")[-2:]

        # replace gitea_repo with _ObsPrj
        gitea_repo = "_ObsPrj"

        # XXX: we assume that the _ObsPrj project has the same branch as the package
        gitea_branch = fragment

        gitea_conf = gitea_api.Config()
        try:
            gitea_login = gitea_conf.get_login_by_url_user(url=gitea_host, user=gitea_user)
        except gitea_api.Login.DoesNotExist:
            # matching login entry doesn't exist in git-obs config
            return None

        gitea_conn = gitea_api.Connection(gitea_login)

        with tempfile.TemporaryDirectory(prefix="osc_devel_project_git") as tmp_dir:
            try:
                gitea_api.Repo.clone(gitea_conn, gitea_owner, gitea_repo, branch=gitea_branch, quiet=True, directory=tmp_dir)
                return GitStore(tmp_dir, check=False).project
            except gitea_api.GiteaException:
                # "_ObsPrj" repo doesn't exist
                return None
            except subprocess.CalledProcessError:
                # branch doesn't exist
                return None
            except FileNotFoundError:
                # "project.build" file doesn't exist
                return None

    def get_project_obs_scm_store(self):
        from ..obs_scm import Store

        if not self.is_package:
            return None

        try:
            store = Store(os.path.join(self.abspath, ".."))
            store.assert_is_project()
            return store
        except oscerr.NoWorkingCopy:
            return None

    def get_project_git_scm_store(self):
        if not self.is_package:
            return None

        path = self.abspath
        while path:
            if path == "/":
                # no git repo found
                return None

            path, _ = os.path.split(path)

            if os.path.isdir(os.path.join(path, ".git")):
                break

        config_path = os.path.join(path, "_config")
        pbuild_path = os.path.join(path, "_pbuild")
        subdirs_path = os.path.join(path, "_subdirs")

        # we always stop at the top-most directory that contains .git subdir
        if not os.path.isfile(config_path) or os.path.isfile(pbuild_path):
            # it's not a project, stop traversing and return
            return None

        if os.path.isfile(subdirs_path):
            # the _subdirs file contains a list of project subdirs that contain packages
            yaml = ruamel.yaml.YAML()
            with open(subdirs_path, "r") as f:
                data = yaml.load(f)

                # ``subdirs`` is a list of directories, which have subdirectories which are packages
                subdirs = data.get("subdirs", [])

                # if set to "include", then all top-level directories are packages in addition to ``subdirs``
                toplevel = data.get("toplevel", "")

            if toplevel == "include":
                subdirs.append(".")

            subdirs_abspath = [os.path.abspath(os.path.join(path, subdir)) for subdir in subdirs]

            # paths listed in ``subdirs`` are never packages, their subdirs are
            if self.abspath in subdirs_abspath:
                return None

            # we're outside paths specified in subdirs -> not a package
            if os.path.abspath(os.path.join(self.abspath, "..")) not in subdirs_abspath:
                return None
        else:
            # no _subdirs file and self.abspath is not directly under the project dir -> not a valid package
            if path != os.path.abspath(os.path.join(self.abspath, "..")):
                return None

        return GitStore(path)

    def __init__(self, path, check=True):
        self.path = path
        self.abspath = os.path.abspath(self.path)

        self._apiurl = None
        self._package = None
        self._project = None

        self.is_project = False
        self.is_package = False

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

        self.project_store = None

        if self.project_store is None:
            self.project_store = self.get_project_obs_scm_store()

        if self.project_store is None:
            self.project_store = self.get_project_git_scm_store()

        if self.project_store:
            self.is_package = True

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
            if self.is_package and self.project_store:
                # read apiurl from parent directory that contains a project with .osc metadata
                self._apiurl = self.project_store.apiurl
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
            if self.is_package:
                # handle _project in a package

                if self.project_store:
                    # read project from detected project store
                    self._project = self.project_store.project

                if not self._project:
                    # read project from Gitea (identical owner, repo: _ObsPrj, file: project.build)
                    origin = self._run_git(["remote", "get-url", "origin"])
                    self._project = self.get_build_project(origin)

            else:
                # handle _project in a project

                if not self._project:
                    # read project from "project.build" file
                    path = os.path.join(self.abspath, "project.build")
                    if os.path.exists(path):
                        with open(path, "r", encoding="utf-8") as f:
                            self._project = f.readline().strip()

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
