from typing import Optional

from .connection import Connection
from .connection import GiteaHTTPResponse
from .exceptions import ForkExists


class Fork:
    @classmethod
    def list(
        cls,
        conn: Connection,
        owner: str,
        repo: str,
    ) -> GiteaHTTPResponse:
        """
        List forks of a repository.

        :param conn: Gitea ``Connection`` instance.
        :param owner: Owner of the repo.
        :param repo: Name of the repo.
        """
        q = {
            "limit": -1,
        }
        url = conn.makeurl("repos", owner, repo, "forks", query=q)
        return conn.request("GET", url)

    @classmethod
    def create(
        cls,
        conn: Connection,
        owner: str,
        repo: str,
        *,
        new_repo_name: Optional[str] = None,
        target_org: Optional[str] = None,
        exist_ok: bool = False,
    ) -> GiteaHTTPResponse:
        """
        Fork a repository.

        :param conn: Gitea ``Connection`` instance.
        :param owner: Owner of the repo.
        :param repo: Name of the repo.
        :param new_repo_name: Name of the forked repository.
        :param target_org: Name of the organization, if forking into organization.
        :param exist_ok: A ``ForkExists`` exception is raised when the target exists. Set to ``True`` to avoid throwing the exception.
        """

        json_data = {
            "name": new_repo_name,
            "organization": target_org,
        }
        url = conn.makeurl("repos", owner, repo, "forks")
        try:
            return conn.request("POST", url, json_data=json_data)
        except ForkExists as e:
            if not exist_ok:
                raise

            from . import Repo  # pylint: disable=import-outside-toplevel
            return Repo.get(conn, e.fork_owner, e.fork_repo)
