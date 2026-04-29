from typing import List, Dict, Optional

from osc.util.models import BaseModel, Field, Enum


class MaintainerInfo(BaseModel):
    """
    A model representing users and groups associated with a project or package.
    """
    users: Optional[List[str]] = Field(default=None)
    groups: Optional[List[str]] = Field(default=None)


class MaintainershipDocumentType(str, Enum):
    VALUE = "obs-maintainers"


class MaintainershipHeader(BaseModel):
    """
    A model representing the maintainership document header.
    """
    document: MaintainershipDocumentType = Field(default="obs-maintainers")
    version: str = Field(default="1.0")


class Maintainership(BaseModel):
    """
    A class to handle maintainership information for projects and packages.
    """
    header: Optional[MaintainershipHeader] = Field(default=None)
    project: MaintainerInfo = Field(default=MaintainerInfo())
    packages: Dict[str, MaintainerInfo] = Field(default={})

    @classmethod
    def from_string(cls, text: str) -> "Maintainership":
        """
        Load maintainership data from a JSON string.
        """
        import json

        data = json.loads(text)

        if data.get("header", None) is None:
            # format: legacy
            # entry with "" name holds project maintainers
            project_data = data.pop("", [])
            p_users = [i for i in project_data if not i.startswith("@")]
            p_groups = [i[1:] for i in project_data if i.startswith("@")]
            project = {
                "users": p_users if p_users else None,
                "groups": p_groups if p_groups else None,
            }
            packages = {}
            for package, package_data in data.items():
                if isinstance(package_data, list):
                    pkg_users = [i for i in package_data if not i.startswith("@")]
                    pkg_groups = [i[1:] for i in package_data if i.startswith("@")]
                    packages[package] = {
                        "users": pkg_users if pkg_users else None,
                        "groups": pkg_groups if pkg_groups else None,
                    }
            data = {
                # version is the default (latest), because we do conversion to that format
                "header": {"document": "obs-maintainers"},
                "project": project,
                "packages": packages,
            }
        elif data["header"]["version"] == "1.0":
            # format: 1.0
            pass
        else:
            raise ValueError(f"Unknown maintainership.json version: {data['header']['version']}")

        return cls(**data)

    def get_package_maintainers_users(self, package: str) -> List[str]:
        if package not in self.packages:
            raise ValueError(f"Package '{package}' not found in maintainership data.")
        return self.packages[package].users or []

    def get_package_maintainers_groups(self, package: str) -> List[str]:
        if package not in self.packages:
            raise ValueError(f"Package '{package}' not found in maintainership data.")
        return self.packages[package].groups or []

    def get_package_maintainers(self, package: str) -> List[str]:
        """
        Return users + groups prefixed with @.
        """
        if package not in self.packages:
            raise ValueError(f"Package '{package}' not found in maintainership data.")
        info = self.packages[package]
        users = info.users or []
        groups = ["@" + g for g in (info.groups or [])]
        return users + groups

    def get_project_maintainers_users(self) -> List[str]:
        return self.project.users or []

    def get_project_maintainers_groups(self) -> List[str]:
        return self.project.groups or []

    def get_project_maintainers(self) -> List[str]:
        """
        Return users + groups prefixed with @.
        """
        users = self.project.users or []
        groups = ["@" + g for g in (self.project.groups or [])]
        return users + groups

    def get_user_packages(self, user: str) -> List[str]:
        """
        Reverse lookup for packages maintained by a specific user.
        """
        result = []
        for pkg, info in self.packages.items():
            if info.users and user in info.users:
                result.append(pkg)
        if not result:
            raise ValueError(f"No packages found for user '{user}'.")
        return sorted(result)

    def get_group_packages(self, group: str) -> List[str]:
        """
        Reverse lookup for packages maintained by a specific group.
        """
        result = []
        for pkg, info in self.packages.items():
            if info.groups and group in info.groups:
                result.append(pkg)
        if not result:
            raise ValueError(f"No packages found for group '{group}'.")
        return sorted(result)
