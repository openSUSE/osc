import io
import os
from typing import Any
from typing import Dict
from typing import List
from typing import Optional

from osc import oscerr
from osc.util import yaml as osc_yaml
from osc.util.models import BaseModel
from osc.util.models import Field


class Login(BaseModel):
    # Any time the fields change, make corresponding changes in the ENV variables in the following places:
    # * Config.get_login() in this file - update ENV variables passed to Login()
    # * GitObsMainCommand.init_arguments in ../commandline_git.py - update help
    name: str = Field()  # type: ignore[assignment]
    url: str = Field()  # type: ignore[assignment]
    user: str = Field()  # type: ignore[assignment]
    token: str = Field()  # type: ignore[assignment]
    ssh_key: Optional[str] = Field()  # type: ignore[assignment]
    git_uses_http: Optional[bool] = Field()  # type: ignore[assignment]
    quiet: Optional[bool] = Field()  # type: ignore[assignment]
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
                return (
                    "Could not find a default Gitea config entry\n"
                    " * either set the default entry by running `git-obs login update <login> --set-as-default`\n"
                    " * or run the command with `-G/--gitea-login <login>` option"
                )
            kwargs_str = ", ".join([f"{key}={value}" for key, value in self.kwargs.items() if value])
            return (
                f"Could not find a matching Gitea config entry: {kwargs_str}\n"
                " * see `git-obs login list` for valid entries"
            )

    class MultipleEntriesReturned(oscerr.OscBaseError):
        def __init__(self, **kwargs):
            super().__init__()
            self.kwargs = kwargs

        def __str__(self):
            kwargs_str = ", ".join([f"{key}={value}" for key, value in self.kwargs.items() if value])
            return f"Multiple login entries returned for the following args: {kwargs_str}"

    def __init__(self, **kwargs):
        # ignore extra fields
        for key in list(kwargs):
            if key not in self.__fields__:
                kwargs.pop(key, None)
        super().__init__(**kwargs)

    def to_human_readable_string(self, *, show_token: bool = False):
        from osc.output import KeyValueTable

        table = KeyValueTable(min_key_length=20)
        table.add("Name", self.name, color="bold")
        if self.default:
            table.add("Default", "true", color="bold")
        table.add("URL", self.url)
        table.add("User", self.user)
        if self.ssh_key:
            table.add("Private SSH key path", self.ssh_key)
        if self.git_uses_http:
            table.add("Git uses http(s)", "yes" if self.git_uses_http else "no")
        if self.quiet:
            table.add("Quiet", "yes" if self.quiet else "no")
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
                return osc_yaml.yaml_load(f)
        except FileNotFoundError:
            return {}

    def _write(self, data):
        os.makedirs(os.path.dirname(self.path), mode=0o700, exist_ok=True)
        with open(self.path, "w") as f:
            osc_yaml.yaml_dump(data, f)

    def list_logins(self) -> List[Login]:
        data = self._read()
        result = []
        for i in data.get("logins", []):
            login_name = i["name"]

            # override values from GIT_OBS_LOGIN_{login_name}_{field_name.upper()}
            for field_name in Login.__fields__.keys():
                if field_name in ("name", "url"):
                    continue
                value = os.environ.get(f"GIT_OBS_LOGIN_{login_name}_{field_name.upper()}", None)
                if value:
                    i[field_name] = value

            login = Login(**i)
            result.append(login)
        return result

    def get_login(self, name: Optional[str] = None) -> Login:
        """
        Return ``Login`` object for the given ``name``.
        If ``name`` equals to ``None``, return the default ``Login``.
        """

        if name is None:
            # if login name was not explicitly specified, check if there are credentials specified in env
            env_gitea_url = os.environ.get("GIT_OBS_GITEA_URL", None)
            env_gitea_user = os.environ.get("GIT_OBS_GITEA_USER", None)
            env_gitea_token = os.environ.get("GIT_OBS_GITEA_TOKEN", None)
            env_ssh_key = os.environ.get("GIT_OBS_GITEA_SSH_KEY", None)
            if env_gitea_url and env_gitea_user and env_gitea_token:
                return Login(
                    name="<ENV>",
                    url=env_gitea_url,
                    user=env_gitea_user,
                    token=env_gitea_token,
                    ssh_key=env_ssh_key,
                )

        for login in self.list_logins():
            if name is None and login.default:
                return login
            if login.name == name:
                return login
        raise Login.DoesNotExist(name=name)

    def get_login_by_url_user(self, url: str, user: Optional[str] = None) -> Login:
        """
        Return ``Login`` object for the given ``url`` and ``user``.
        """
        from .git import Git

        # exact match
        matches = []
        for login in self.list_logins():
            if user is None:
                if login.url == url:
                    matches.append(login)
            elif (login.url, login.user) == (url, user):
                matches.append(login)

        if len(matches) == 1:
            return matches[0]
        if len(matches) >= 2:
            raise Login.MultipleEntriesReturned(url=url, user=user)

        def url_to_hostname(value):
            netloc = Git.urlparse(value).netloc

            # remove user from hostname
            if "@" in netloc:
                netloc = netloc.split("@")[-1]

            # remove port from hostname
            if ":" in netloc:
                netloc = netloc.split(":")[0]

            return netloc

        # match only hostname (netloc without 'user@' and ':port') + user
        matches = []
        for login in self.list_logins():
            if user is None:
                if url_to_hostname(login.url) == url_to_hostname(url):
                    matches.append(login)
            elif (url_to_hostname(login.url), login.user) == (url_to_hostname(url), user):
                matches.append(login)

        if len(matches) == 1:
            return matches[0]
        if len(matches) >= 2:
            raise Login.MultipleEntriesReturned(url=url, user=user)

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
        new_git_uses_http: Optional[bool] = None,
        new_quiet: Optional[bool] = None,
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

        if new_git_uses_http is None:
            # keep the original value
            pass
        elif new_git_uses_http:
            login.git_uses_http = True
        else:
            # remove from the config instead of setting to False
            login.git_uses_http = None

        if new_quiet is not None:
            login.quiet = new_quiet

        if set_as_default:
            login.default = True

        if not login.has_changed():
            return login

        data = self._read()
        for entry in data["logins"]:
            if entry.get("name", None) == name:
                entry.update(login.dict())

                # remove keys with no value
                for key, value in entry.copy().items():
                    if value is None:
                        del entry[key]
            else:
                if set_as_default:
                    entry.pop("default", None)
        self._write(data)

        return login

    def git_obs_repo_init_template(self, name: Optional[str] = None) -> str:
        data = self._read()

        env_git_obs_repo_init_template = os.environ.get("GIT_OBS_REPO_INIT_TEMPLATE", "")
        if env_git_obs_repo_init_template:
            return env_git_obs_repo_init_template

        res = None
        general = data.get("general")
        if general:
            res = general.get("git_obs_repo_init_template")

        for i in data.get("logins", []):
            login_name = i.get("name", "")
            if not login_name:
                continue
            if name:
                if name != login_name:
                    continue
                else:
                    res = i.get("git_obs_repo_init_template", res)

            if not res and i.get("default", True):
                res = i.get("git_obs_repo_init_template", res)

        if not res:
            res = "pool/new_package"

        return res
