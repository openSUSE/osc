from .connection import Connection
from .connection import GiteaHTTPResponse


def get_user(
    conn: Connection,
) -> GiteaHTTPResponse:
    """
    Retrieve details about the current user.

    :param conn: Gitea ``Connection`` instance.
    """
    url = conn.makeurl("user")
    return conn.request("GET", url)
