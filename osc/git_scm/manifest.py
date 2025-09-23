import os
import pathlib

from typing import List
from typing import Optional


class Manifest:
    """
    A wrapper to _manifest file that lives in a project, such as _ObsPrj repo.
    """

    @classmethod
    def from_file(cls, path: str) -> "Manifest":
        from ..util import yaml as osc_yaml

        with open(path, "r", encoding="utf-8") as f:
            data = osc_yaml.yaml_load(f)
        obj = cls(data)
        return obj

    @classmethod
    def from_string(cls, text: str) -> "Manifest":
        from ..util import yaml as osc_yaml

        data = osc_yaml.yaml_loads(text)
        obj = cls(data)
        return obj

    def __init__(self, data: dict = None):
        self._data = data

    @property
    def obs_apiurl(self) -> Optional[str]:
        return self._data.get("obs_apiurl", None)

    @property
    def obs_project(self) -> Optional[str]:
        return self._data.get("obs_project", None)

    @property
    def packages(self) -> List[str]:
        return self._data.get("packages", [])

    @property
    def package_directories(self) -> List[str]:
        result = self._data.get("subdirectories", [])
        if not result and not self.packages:
            return ["."]
        return result

    def resolve_package_path(self, project_path: str, package_path: str) -> Optional[str]:
        """
        Return package topdir or `None` if it cannot be resolved.
        The `package_path` argument may point inside the directory tree under the package's location.
        """
        project_path = os.path.abspath(project_path)
        package_path = os.path.abspath(package_path)

        # package path must not be equal to project path
        if package_path == project_path:
            return None

        # package path must be under project path
        if os.path.commonpath([project_path, package_path]) != project_path:
            return None

        packages_abspath = [os.path.abspath(os.path.join(project_path, i)) for i in self.packages]
        for i in packages_abspath:
            if os.path.commonpath([package_path, i]) == i:
                return i

        package_directories_abspath = [os.path.abspath(os.path.join(project_path, i)) for i in self.package_directories]
        package_path_obj = pathlib.Path(package_path)
        for i in package_directories_abspath:
            if os.path.commonpath([package_path, i]) == i:
                i_obj = pathlib.Path(i)
                if i_obj in package_path_obj.parents:
                    i_obj /= package_path_obj.parts[len(i_obj.parts)]
                    return i_obj.as_posix()

        return None


class Subdirs(Manifest):
    """
    A wrapper to _subdirs file that has been deprecated by _manifest.
    """

    @property
    def package_directories(self) -> List[str]:
        result = self._data.get("subdirs", [])
        if self._data.get("toplevel", None) == "include":
            result.append(".")
        return result
