from typing import Optional

from .connection import Connection
from .connection import GiteaHTTPResponse


class User:
    def __init__(self, data: dict, *, response: Optional[GiteaHTTPResponse] = None):
        self._data = data
        self._response = response

    @property
    def login(self) -> str:
        return self._data["login"]

    @property
    def full_name(self) -> str:
        return self._data["full_name"]

    @property
    def email(self) -> str:
        return self._data["email"]

    @property
    def full_name_email(self) -> str:
        if self.full_name:
            return f"{self.full_name} <{self.email}>"
        return self.email

    @property
    def login_full_name_email(self) -> str:
        return f"{self.login} ({self.full_name_email})"

    @classmethod
    def get(
        cls,
        conn: Connection,
        username: Optional[str] = None,
    ) -> "Self":
        """
        Retrieve details about a user.
        If ``username`` is not specified, data about the current user is returned."

        :param conn: Gitea ``Connection`` instance.
        :param username: Username of the queried user."
        """
        if not username:
            url = conn.makeurl("user")
        else:
            url = conn.makeurl("users", username)
        response = conn.request("GET", url)
        obj = cls(response.json(), response=response)
        return obj
