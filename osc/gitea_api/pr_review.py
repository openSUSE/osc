from typing import List
from typing import Optional

from .common import GiteaModel
from .common import dt_sanitize
from .connection import Connection
from .user import User


class PullRequestReview(GiteaModel):
    @property
    def commit(self) -> str:
        return self._data["commit_id"]

    @property
    def state(self) -> str:
        return self._data["state"]

    @property
    def dismissed(self) -> str:
        return self._data["dismissed"]

    @property
    def user(self) -> Optional[str]:
        if not self._data["user"]:
            return None
        return self._data["user"]["login"]

    @property
    def user_obj(self) -> Optional[str]:
        if not self._data["user"]:
            return None
        return User(self._data["user"])

    @property
    def team(self) -> Optional[str]:
        if not self._data["team"]:
            return None
        return self._data["team"]["name"]

    @property
    def who(self) -> str:
        return self.user if self.user else f"@{self.team}"

    @property
    def who_login_full_name_email(self) -> str:
        return self.user_obj.login_full_name_email if self.user_obj else f"@{self.team}"

    @property
    def created_at(self) -> str:
        return self._data["submitted_at"]

    @property
    def updated_at(self) -> str:
        return self._data["updated_at"]

    @property
    def created_updated_str(self) -> str:
        result = dt_sanitize(self.created_at)
        if self.updated_at and self.updated_at != self.created_at:
            result += f" (updated: {dt_sanitize(self.updated_at)})"
        return result

    @property
    def body(self) -> str:
        return self._data["body"]

    @property
    def pr_owner(self) -> str:
        from .pr import PullRequest

        return PullRequest.get_owner_repo_number(self._data["pull_request_url"])[0]

    @property
    def pr_repo(self) -> str:
        from .pr import PullRequest

        return PullRequest.get_owner_repo_number(self._data["pull_request_url"])[1]

    @property
    def pr_number(self) -> int:
        from .pr import PullRequest

        return PullRequest.get_owner_repo_number(self._data["pull_request_url"])[2]

    @property
    def comments_count(self) -> int:
        return self._data["comments_count"]

    @classmethod
    def get(
        cls,
        conn: Connection,
        owner: str,
        repo: str,
        number: int,
        review_id: int
    ) -> "PullRequestReview":
        """
        Get a review associated with a pull request.

        :param conn: Gitea ``Connection`` instance.
        :param owner: Owner of the repo.
        :param repo: Name of the repo.
        :param number: Number of the pull request in owner/repo.
        :param review_id: ID of the review.
        """
        url = conn.makeurl("repos", owner, repo, "pulls", str(number), "reviews", review_id)
        response = conn.request("GET", url, context={"owner": owner, "repo": repo, "number": number})
        obj = cls(response.json(), response=response, conn=conn)
        return obj

    @classmethod
    def list(
        cls,
        conn: Connection,
        owner: str,
        repo: str,
        number: int,
    ) -> List["PullRequestReview"]:
        """
        List reviews associated with a pull request.

        :param conn: Gitea ``Connection`` instance.
        :param owner: Owner of the repo.
        :param repo: Name of the repo.
        :param number: Number of the pull request in owner/repo.
        """
        q = {
            "limit": -1,
        }
        url = conn.makeurl("repos", owner, repo, "pulls", str(number), "reviews", query=q)
        response = conn.request("GET", url)
        obj_list = [cls(i, response=response, conn=conn) for i in response.json()]
        return obj_list
