from typing import List
from typing import Optional

from .common import GiteaModel
from .connection import Connection
from .connection import GiteaHTTPResponse
from .exceptions import BranchExists


class Branch(GiteaModel):
    @property
    def commit(self) -> str:
        return self._data["commit"]["id"]

    @property
    def name(self) -> str:
        return self._data["name"]

    @classmethod
    def get(
        cls,
        conn: Connection,
        owner: str,
        repo: str,
        branch: str,
    ) -> "Branch":
        """
        Retrieve details about a repository branch.

        :param conn: Gitea ``Connection`` instance.
        :param owner: Owner of the repo.
        :param repo: Name of the repo.
        :param branch: Name of the branch.
        """
        url = conn.makeurl("repos", owner, repo, "branches", branch)
        response = conn.request("GET", url, context={"owner": owner, "repo": repo})
        obj = cls(response.json(), response=response)
        return obj

    @classmethod
    def list(
        cls,
        conn: Connection,
        owner: str,
        repo: str,
    ) -> List["Branch"]:
        """
        Retrieve details about all repository branches.

        :param conn: Gitea ``Connection`` instance.
        :param owner: Owner of the repo.
        :param repo: Name of the repo.
        """
        q = {
            "limit": 50,
        }
        url = conn.makeurl("repos", owner, repo, "branches", query=q)
        # XXX: returns 'null' when there are no branches; an empty list would be a better API
        obj_list = []
        for response in conn.request_all_pages("GET", url):
            obj_list.extend([cls(i, response=response, conn=conn) for i in response.json() or []])
        return obj_list

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
    ) -> "Branch":
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
            response = conn.request("POST", url, json_data=json_data, context={"owner": owner, "repo": repo, "branch": new_branch_name})
            obj = cls(response.json(), response=response)
            return obj
        except BranchExists:
            if not exist_ok:
                raise
            return cls.get(conn, owner, repo, new_branch_name)
