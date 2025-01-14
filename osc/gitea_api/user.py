from .connection import Connection
from .connection import GiteaHTTPResponse


class User:
    @classmethod
    def to_full_name_email_string(cls, data):
        full_name = data["full_name"]
        email = data["email"]
        if full_name:
            return f"{full_name} <{email}>"
        return email

    @classmethod
    def to_login_full_name_email_string(cls, data):
        return f"{data['login']} ({cls.to_full_name_email_string(data)})"

    @classmethod
    def get(
        cls,
        conn: Connection,
    ) -> GiteaHTTPResponse:
        """
        Retrieve details about the current user.

        :param conn: Gitea ``Connection`` instance.
        """
        url = conn.makeurl("user")
        return conn.request("GET", url)
