import re
from typing import List
from typing import Optional
from typing import Tuple

from .connection import Connection
from .connection import GiteaHTTPResponse


class PullRequest:
    @classmethod
    def cmp(cls, entry: dict):
        if "base" in entry:
            # a proper pull request
            return entry["base"]["repo"]["full_name"], entry["number"]
        else:
            # an issue without pull request details
            return entry["repository"]["full_name"], entry["number"]

    @classmethod
    def split_id(cls, pr_id: str) -> Tuple[str, str, int]:
        """
        Split <owner>/<repo>#<number> into individual components and return them in a tuple.
        """
        match = re.match(r"^([^/]+)/([^/]+)#([0-9]+)$", pr_id)
        if not match:
            raise ValueError(f"Invalid pull request id: {pr_id}")
        return match.group(1), match.group(2), int(match.group(3))

    @classmethod
    def to_human_readable_string(cls, entry: dict):
        from osc.output import KeyValueTable
        from . import User

        def yes_no(value):
            return "yes" if value else "no"

        if "base" in entry:
            # a proper pull request
            entry_id = f"{entry['base']['repo']['full_name']}#{entry['number']}"
            is_pull_request = True
        else:
            # an issue without pull request details
            entry_id = f"{entry['repository']['full_name']}#{entry['number']}"
            is_pull_request = False

        # HACK: search API returns issues, the URL needs to be transformed to a pull request URL
        entry_url = entry["url"]
        entry_url = re.sub(r"^(.*)/api/v1/repos/(.+/.+)/issues/([0-9]+)$", r"\1/\2/pulls/\3", entry_url)

        table = KeyValueTable()
        table.add("ID", entry_id, color="bold")
        table.add("URL", f"{entry_url}")
        table.add("Title", f"{entry['title']}")
        table.add("State", entry["state"])
        if is_pull_request:
            table.add("Draft", yes_no(entry["draft"]))
            table.add("Merged", yes_no(entry["merged"]))
            table.add("Allow edit", yes_no(entry["allow_maintainer_edit"]))
        table.add("Author", f"{User.to_login_full_name_email_string(entry['user'])}")
        if is_pull_request:
            table.add("Source", f"{entry['head']['repo']['full_name']}, branch: {entry['head']['ref']}, commit: {entry['head']['sha']}")
        table.add("Description", entry["body"])

        return str(table)

    @classmethod
    def list_to_human_readable_string(cls, entries: List, sort: bool = False):
        if sort:
            entries = sorted(entries, key=cls.cmp)
        result = []
        for entry in entries:
            result.append(cls.to_human_readable_string(entry))
        return "\n\n".join(result)

    @classmethod
    def create(
        cls,
        conn: Connection,
        *,
        target_owner: str,
        target_repo: str,
        target_branch: str,
        source_owner: str,
        source_branch: str,
        title: str,
        description: Optional[str] = None,
    ) -> GiteaHTTPResponse:
        """
        Create a pull request to ``owner``/``repo`` to the ``base`` branch.
        The pull request comes from a fork. The fork repo name is determined from gitea database.

        :param conn: Gitea ``Connection`` instance.
        :param target_owner: Owner of the target repo.
        :param target_repo: Name of the target repo.
        :param target_branch: Name of the target branch in the target repo.
        :param source_owner: Owner of the source (forked) repo.
        :param source_branch: Name of the source branch in the source (forked) repo.
        :param title: Pull request title.
        :param description: Pull request description.
        """
        url = conn.makeurl("repos", target_owner, target_repo, "pulls")
        data = {
            "base": target_branch,
            "head": f"{source_owner}:{source_branch}",
            "title": title,
            "body": description,
        }
        return conn.request("POST", url, json_data=data)

    @classmethod
    def get(
        cls,
        conn: Connection,
        owner: str,
        repo: str,
        number: int,
    ) -> GiteaHTTPResponse:
        """
        Get a pull request.

        :param conn: Gitea ``Connection`` instance.
        :param owner: Owner of the repo.
        :param repo: Name of the repo.
        :param number: Number of the pull request in the repo.
        """
        url = conn.makeurl("repos", owner, repo, "pulls", str(number))
        return conn.request("GET", url)

    @classmethod
    def set(
        cls,
        conn: Connection,
        owner: str,
        repo: str,
        number: int,
        *,
        title: Optional[str] = None,
        description: Optional[str] = None,
        allow_maintainer_edit: Optional[bool] = None,
    ) -> GiteaHTTPResponse:
        """
        Change a pull request.

        :param conn: Gitea ``Connection`` instance.
        :param owner: Owner of the repo.
        :param repo: Name of the repo.
        :param number: Number of the pull request in the repo.
        :param title: Change pull request title.
        :param description: Change pull request description.
        :param allow_maintainer_edit: Change whether users with write access to the base branch can also push to the pull request's head branch.
        """
        json_data = {
            "title": title,
            "description": description,
            "allow_maintainer_edit": allow_maintainer_edit,
        }
        url = conn.makeurl("repos", owner, repo, "pulls", str(number))
        return conn.request("PATCH", url, json_data=json_data)

    @classmethod
    def list(
        cls,
        conn: Connection,
        owner: str,
        repo: str,
        *,
        state: Optional[str] = "open",
    ) -> GiteaHTTPResponse:
        """
        List pull requests in a repo.

        :param conn: Gitea ``Connection`` instance.
        :param owner: Owner of the repo.
        :param repo: Name of the repo.
        :param state: Filter by state: open, closed, all. Defaults to open.
        """
        if state == "all":
            state = None

        q = {
            "state": state,
            "limit": -1,
        }
        url = conn.makeurl("repos", owner, repo, "pulls", query=q)
        return conn.request("GET", url)

    @classmethod
    def search(
        cls,
        conn: Connection,
        *,
        state: str = "open",
        title: Optional[str] = None,
        owner: Optional[str] = None,
        labels: Optional[List[str]] = None,
        assigned: bool = False,
        created: bool = False,
        mentioned: bool = False,
        review_requested: bool = False,
    ) -> GiteaHTTPResponse:
        """
        Search pull requests.
        :param conn: Gitea ``Connection`` instance.
        :param state: Filter by state: open, closed. Defaults to open.
        :param title: Filter by substring in title.
        :param owner: Filter by owner of the repository associated with the pull requests.
        :param labels: Filter by associated labels. Non existent labels are discarded.
        :param assigned: Filter pull requests assigned to you.
        :param created: Filter pull requests created by you.
        :param mentioned: Filter pull requests mentioning you.
        :param review_requested: Filter pull requests requesting your review.
        """
        q = {
            "type": "pulls",
            "state": state,
            "q": title,
            "owner": owner,
            "labels": ",".join(labels) if labels else None,
            "assigned": assigned,
            "created": created,
            "mentioned": mentioned,
            "review_requested": review_requested,
            # HACK: limit=-1 doesn't work, the request gets stuck; we need to use a high number to avoid pagination
            "limit": 10**6,
        }
        url = conn.makeurl("repos", "issues", "search", query=q)
        return conn.request("GET", url)

    @classmethod
    def get_patch(
        cls,
        conn: Connection,
        owner: str,
        repo: str,
        number: int,
    ) -> GiteaHTTPResponse:
        """
        Get a patch associated with a pull request.

        :param conn: Gitea ``Connection`` instance.
        :param owner: Owner of the repo.
        :param repo: Name of the repo.
        :param number: Number of the pull request in the repo.
        """
        url = conn.makeurl("repos", owner, repo, "pulls", f"{number}.patch")
        return conn.request("GET", url)

    @classmethod
    def add_comment(
        cls,
        conn: Connection,
        owner: str,
        repo: str,
        number: int,
        msg: str,
    ) -> GiteaHTTPResponse:
        """
        Add comment to a pull request.
        """
        url = conn.makeurl("repos", owner, repo, "issues", str(number), "comments")
        json_data = {
            "body": msg,
        }
        return conn.request("POST", url, json_data=json_data)

    @classmethod
    def get_reviews(
        cls,
        conn: Connection,
        owner: str,
        repo: str,
        number: int,
    ):
        url = conn.makeurl("repos", owner, repo, "pulls", str(number), "reviews")
        return conn.request("GET", url)

    @classmethod
    def approve_review(
        cls,
        conn: Connection,
        owner: str,
        repo: str,
        number: int,
        msg: str = "LGTM",
    ) -> GiteaHTTPResponse:
        """
        Approve review in a pull request.
        """
        url = conn.makeurl("repos", owner, repo, "pulls", str(number), "reviews")
        json_data = {
            "event": "APPROVED",
            "body": msg,
        }
        return conn.request("POST", url, json_data=json_data)

    @classmethod
    def decline_review(
        cls,
        conn: Connection,
        owner: str,
        repo: str,
        number: int,
        msg: str,
    ) -> GiteaHTTPResponse:
        """
        Decline review (request changes) in a pull request.
        """
        url = conn.makeurl("repos", owner, repo, "pulls", str(number), "reviews")
        json_data = {
            "event": "REQUEST_CHANGES",
            "body": msg,
        }
        return conn.request("POST", url, json_data=json_data)
