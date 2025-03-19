import io
import os
from typing import Any
from typing import Dict
from typing import List
from typing import Optional

import ruamel.yaml

from osc import oscerr
from osc.util.models import BaseModel
from osc.util.models import Field


class Login(BaseModel):
    name: str = Field()  # type: ignore[assignment]
    url: str = Field()  # type: ignore[assignment]
    user: str = Field()  # type: ignore[assignment]
    token: str = Field()  # type: ignore[assignment]
    ssh_key: Optional[str] = Field()  # type: ignore[assignment]
    default: Optional[bool] = Field()  # type: ignore[assignment]

    class AlreadyExists(oscerr.OscBaseError):
        def __init__(self, name):
            super().__init__()
            self.name = name

        def __str__(self):
            return f"Gitea config entry with name '{self.name}' already exists"

    class DoesNotExist(oscerr.OscBaseError):
        def __init__(self, **kwargs):
            super().__init__()
            self.kwargs = kwargs

        def __str__(self):
            if self.kwargs == {"name": None}:
                return "Could not find a default Gitea config entry"
            kwargs_str = ", ".join([f"{key}={value}" for key, value in self.kwargs.items()])
            return f"Could not find a matching Gitea config entry: {kwargs_str}"

    def __init__(self, **kwargs):
        # ignore extra fields
        for key in list(kwargs):
            if key not in self.__fields__:
                kwargs.pop(key, None)
        super().__init__(**kwargs)

    def to_human_readable_string(self, *, show_token: bool = False):
        from osc.output import KeyValueTable

        table = KeyValueTable()
        table.add("Name", self.name, color="bold")
        if self.default:
            table.add("Default", "true", color="bold")
        table.add("URL", self.url)
        table.add("User", self.user)
        if self.ssh_key:
            table.add("SSH Key", self.ssh_key)
        if show_token:
            # tokens are stored in the plain text, there's not reason to protect them too much
            # let's only hide them from the output by default
            table.add("Token", self.token)
        return f"{table}"


class Config:
    """
    Manage the tea config.yml file.
    No data is cached in the objects, all changes are in sync with the file on disk.
    """

    def __init__(self, path: Optional[str] = None):
        if not path:
            path = "~/.config/tea/config.yml"
        self.path = os.path.abspath(os.path.expanduser(path))

        self.logins: List[Login] = []

    def _read(self) -> Dict[str, Any]:
        try:
            with open(self.path, "r") as f:
                yaml = ruamel.yaml.YAML()
                return yaml.load(f)
        except FileNotFoundError:
            return {}

    def _write(self, data):
        yaml = ruamel.yaml.YAML()
        yaml.default_flow_style = False
        buf = io.StringIO()
        yaml.dump(data, buf)
        buf.seek(0)
        text = buf.read()

        os.makedirs(os.path.dirname(self.path), mode=0o700, exist_ok=True)
        with open(self.path, "w") as f:
            f.write(text)

    def list_logins(self) -> List[Login]:
        data = self._read()
        result = []
        for i in data.get("logins", []):
            login = Login(**i)
            result.append(login)
        return result

    def get_login(self, name: Optional[str] = None) -> Login:
        """
        Return ``Login`` object for the given ``name``.
        If ``name`` equals to ``None``, return the default ``Login``.
        """
        for login in self.list_logins():
            if name is None and login.default:
                return login
            if login.name == name:
                return login
        raise Login.DoesNotExist(name=name)

    def get_login_by_url_user(self, url: str, user: str) -> Login:
        """
        Return ``Login`` object for the given ``url`` and ``user``.
        """
        for login in self.list_logins():
            if (login.url, login.user) == (url, user):
                return login
        raise Login.DoesNotExist(url=url, user=user)

    def add_login(self, login: Login):
        data = self._read()
        data.setdefault("logins", [])

        for entry in data["logins"]:
            if entry.get("name", None) == login.name:
                raise Login.AlreadyExists(login.name)
            else:
                if login.default:
                    entry.pop("default", None)

        data["logins"].append(login.dict())
        self._write(data)

    def remove_login(self, name: str) -> Login:
        # throw an exception if the login name doesn't exist
        login = self.get_login(name)

        data = self._read()
        for num, entry in enumerate(list(data["logins"])):
            if entry.get("name", None) == login.name:
                data["logins"].pop(num)
        self._write(data)
        return login

    def update_login(
        self,
        name: str,
        new_name: Optional[str] = None,
        new_url: Optional[str] = None,
        new_user: Optional[str] = None,
        new_token: Optional[str] = None,
        new_ssh_key: Optional[str] = None,
        set_as_default: Optional[bool] = None,
    ) -> Login:
        login = self.get_login(name)

        if new_name is not None:
            login.name = new_name
        if new_url is not None:
            login.url = new_url
        if new_user is not None:
            login.user = new_user
        if new_token is not None:
            login.token = new_token
        if new_ssh_key is not None:
            login.ssh_key = new_ssh_key
        if set_as_default:
            login.default = True

        if not login.has_changed():
            return login

        data = self._read()
        for entry in data["logins"]:
            if entry.get("name", None) == name:
                entry.update(login.dict())
            else:
                if set_as_default:
                    entry.pop("default", None)
        self._write(data)

        return login
