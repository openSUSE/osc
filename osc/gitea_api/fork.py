from typing import Optional

from .connection import Connection
from .connection import GiteaHTTPResponse
from .exceptions import ForkExists
from .exceptions import GiteaException


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

        url = conn.makeurl("repos", owner, repo, "forks")
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
        except GiteaException as e:
            # use ForkExists exception to parse fork_owner and fork_repo from the response
            if e.status == 409:
                fork_exists_exception = ForkExists(e.response, owner, repo)
                if exist_ok:
                    from . import Repo
                    return Repo.get(conn, fork_exists_exception.fork_owner, fork_exists_exception.fork_repo)
                raise fork_exists_exception from None
            raise
