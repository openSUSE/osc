from typing import Optional

from .connection import Connection
from .connection import GiteaHTTPResponse
from .exceptions import BranchDoesNotExist
from .exceptions import BranchExists
from .exceptions import GiteaException


class Branch:
    @classmethod
    def get(
        cls,
        conn: Connection,
        owner: str,
        repo: str,
        branch: str,
    ) -> GiteaHTTPResponse:
        """
        Retrieve details about a repository branch.

        :param conn: Gitea ``Connection`` instance.
        :param owner: Owner of the repo.
        :param repo: Name of the repo.
        :param branch: Name of the branch.
        """
        url = conn.makeurl("repos", owner, repo, "branches", branch)
        return conn.request("GET", url, context={"owner": owner, "repo": repo})

    @classmethod
    def list(
        cls,
        conn: Connection,
        owner: str,
        repo: str,
    ) -> GiteaHTTPResponse:
        """
        Retrieve details about all repository branches.

        :param conn: Gitea ``Connection`` instance.
        :param owner: Owner of the repo.
        :param repo: Name of the repo.
        """
        q = {
            "limit": -1,
        }
        url = conn.makeurl("repos", owner, repo, "branches", query=q)
        # XXX: returns 'null' when there are no branches; an empty list would be a better API
        return conn.request("GET", url)

    @classmethod
    def create(
        cls,
        conn: Connection,
        owner: str,
        repo: str,
        *,
        old_ref_name: Optional[str] = None,
        new_branch_name: str,
        exist_ok: bool = False,
    ) -> GiteaHTTPResponse:
        """
        Create a new branch in a repository.

        :param conn: Gitea ``Connection`` instance.
        :param owner: Owner of the repo.
        :param repo: Name of the repo.
        :param old_ref_name: Name of the old branch/tag/commit to create from.
        :param new_branch_name: Name of the branch to create.
        :param exist_ok: A ``BranchExists`` exception is raised when the target exists. Set to ``True`` to avoid throwing the exception.
        """
        json_data = {
            "new_branch_name": new_branch_name,
            "old_ref_name": old_ref_name,
        }
        url = conn.makeurl("repos", owner, repo, "branches")
        try:
            return conn.request("POST", url, json_data=json_data, context={"owner": owner, "repo": repo, "branch": new_branch_name})
        except BranchExists as e:
            if not exist_ok:
                raise
            return cls.get(conn, owner, repo, new_branch_name)
