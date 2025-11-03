from typing import List
from typing import Optional

from .common import GiteaModel
from .connection import Connection
from .exceptions import ForkExists
from .repo import Repo


class Fork(GiteaModel):
    @classmethod
    def list(
        cls,
        conn: Connection,
        owner: str,
        repo: str,
    ) -> List["Repo"]:
        """
        List forks of a repository.

        :param conn: Gitea ``Connection`` instance.
        :param owner: Owner of the repo.
        :param repo: Name of the repo.
        """
        q = {
            "limit": 50,
        }
        url = conn.makeurl("repos", owner, repo, "forks", query=q)
        obj_list = []
        for response in conn.request_all_pages("GET", url):
            obj_list.extend([Repo(i, response=response, conn=conn) for i in response.json()])
        return obj_list

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
    ) -> Repo:
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
            response = conn.request("POST", url, json_data=json_data)
            obj = Repo(response.json(), response=response)
            return obj
        except ForkExists as e:
            if not exist_ok:
                raise
            return Repo.get(conn, e.fork_owner, e.fork_repo)
