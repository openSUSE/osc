import functools
import re
from typing import List
from typing import Optional
from typing import Tuple

from .common import GiteaModel
from .connection import Connection
from .connection import GiteaHTTPResponse
from .user import User


class PullRequestReview(GiteaModel):
    @property
    def state(self) -> str:
        return self._data["state"]

    @property
    def user(self) -> Optional[str]:
        if not self._data["user"]:
            return None
        return self._data["user"]["login"]

    @property
    def team(self) -> Optional[str]:
        if not self._data["team"]:
            return None
        return self._data["team"]["name"]

    @property
    def who(self) -> str:
        return self.user if self.user else f"@{self.team}"

    @property
    def submitted_at(self) -> str:
        return self._data["submitted_at"]

    @property
    def updated_at(self) -> str:
        return self._data["updated_at"]

    @property
    def body(self) -> str:
        return self._data["body"]

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
        obj_list = [cls(i, response=response) for i in response.json()]
        return obj_list


@functools.total_ordering
class PullRequest(GiteaModel):
    def __eq__(self, other):
        (self.base_owner, self.base_repo, self.number) == (other.base_owner, other.base_repo, other.number)

    def __lt__(self, other):
        (self.base_owner, self.base_repo, self.number) < (other.base_owner, other.base_repo, other.number)

    @classmethod
    def split_id(cls, pr_id: str) -> Tuple[str, str, int]:
        """
        Split <owner>/<repo>#<number> or <owner>/<repo>!<number> into individual components and return them in a tuple.
        """
        match = re.match(r"^([^/]+)/([^/]+)[#!]([0-9]+)$", pr_id)
        if not match:
            match = re.match(r"^([^/]+)/([^/]+)/pulls/([0-9]+)$", pr_id)

        if not match:
            raise ValueError(f"Invalid pull request id: {pr_id}")
        return match.group(1), match.group(2), int(match.group(3))

    @staticmethod
    def get_owner_repo_number(url: str) -> Tuple[str, str, int]:
        """
        Parse pull request URL such as http(s)://example.com:<port>/<owner>/<repo>/pulls/<number>
        and return (owner, repo, number) tuple.
        """
        import urllib.parse

        parsed_url = urllib.parse.urlparse(url)
        path = parsed_url.path
        owner, repo, pulls, number = path.strip("/").split("/")
        if pulls not in ("pulls", "issues"):
            raise ValueError(f"URL doesn't point to a pull request or an issue: {url}")
        return owner, repo, int(number)

    def parse_pr_references(self) -> List[Tuple[str, str, int]]:
        refs = re.findall(r"^PR: *(.*)$", self.body, re.M)
        result = []

        for ref in refs:
            # try owner/repo#number first
            try:
                result.append(PullRequest.split_id(ref))
                continue
            except ValueError:
                pass

            # parse owner, repo, number from a pull request url
            if ref.startswith(f"{self._conn.login.url.rstrip('/')}/"):
                try:
                    result.append(PullRequest.get_owner_repo_number(ref))
                    continue
                except ValueError:
                    pass

            raise ValueError(f"Unable to parse pull request reference: {ref}")

        return result

    @property
    def is_pull_request(self):
        # determine if we're working with a proper pull request or an issue without pull request details
        return "base" in self._data

    @property
    def id(self) -> str:
        return f"{self.base_owner}/{self.base_repo}#{self.number}"

    @property
    def number(self) -> int:
        return self._data["number"]

    @property
    def title(self) -> str:
        return self._data["title"]

    @property
    def body(self) -> str:
        return self._data["body"]

    @property
    def state(self) -> str:
        return self._data["state"]

    @property
    def user(self) -> str:
        return self._data["user"]["login"]

    @property
    def user_obj(self) -> User:
        return User(self._data["user"])

    @property
    def draft(self) -> Optional[bool]:
        if not self.is_pull_request:
            return None
        return self._data["draft"]

    @property
    def merged(self) -> Optional[bool]:
        if not self.is_pull_request:
            return None
        return self._data["merged"]

    @property
    def allow_maintainer_edit(self) -> Optional[bool]:
        if not self.is_pull_request:
            return None
        return self._data["allow_maintainer_edit"]

    @property
    def base_owner(self) -> Optional[str]:
        if not self.is_pull_request:
            return self._data["repository"]["owner"]
        return self._data["base"]["repo"]["owner"]["login"]

    @property
    def base_repo(self) -> str:
        if not self.is_pull_request:
            return self._data["repository"]["name"]
        return self._data["base"]["repo"]["name"]

    @property
    def base_branch(self) -> Optional[str]:
        if not self.is_pull_request:
            return None
        return self._data["base"]["ref"]

    @property
    def base_commit(self) -> Optional[str]:
        if not self.is_pull_request:
            return None
        return self._data["base"]["sha"]

    @property
    def base_ssh_url(self) -> Optional[str]:
        if not self.is_pull_request:
            return None
        return self._data["base"]["repo"]["ssh_url"]

    @property
    def merge_base(self) -> Optional[str]:
        if not self.is_pull_request:
            return None
        return self._data["merge_base"]

    @property
    def head_owner(self) -> Optional[str]:
        if not self.is_pull_request:
            return None
        if self._data["head"]["repo"] is None:
            return None
        return self._data["head"]["repo"]["owner"]["login"]

    @property
    def head_repo(self) -> Optional[str]:
        if not self.is_pull_request:
            return None
        if self._data["head"]["repo"] is None:
            return None
        return self._data["head"]["repo"]["name"]

    @property
    def head_branch(self) -> Optional[str]:
        if not self.is_pull_request:
            return None
        return self._data["head"]["ref"]

    @property
    def head_commit(self) -> Optional[str]:
        if not self.is_pull_request:
            return None
        return self._data["head"]["sha"]

    @property
    def head_ssh_url(self) -> Optional[str]:
        if not self.is_pull_request:
            return None
        if self._data["head"]["repo"] is None:
            return None
        return self._data["head"]["repo"]["ssh_url"]

    @property
    def merge_commit(self) -> Optional[str]:
        if not self.is_pull_request:
            return None
        return self._data["merge_commit_sha"]

    @property
    def url(self) -> str:
        # HACK: search API returns issues, the URL needs to be transformed to a pull request URL
        return re.sub(r"^(.*)/api/v1/repos/(.+/.+)/issues/([0-9]+)$", r"\1/\2/pulls/\3", self._data["url"])
    
    @property
    def labels(self) -> List[str]:
        return [label["name"] for label in self._data.get("labels", [])]

    def to_human_readable_string(self):
        from osc.output import KeyValueTable

        def yes_no(value):
            return "yes" if value else "no"

        table = KeyValueTable()
        table.add("ID", self.id, color="bold")
        table.add("URL", self.url)
        table.add("Title", self.title)
        table.add("State", self.state)
        if self.is_pull_request:
            table.add("Draft", yes_no(self.draft))
            table.add("Merged", yes_no(self.merged))
            table.add("Allow edit", yes_no(self.allow_maintainer_edit))
        table.add("Author", f"{self.user_obj.login_full_name_email}")
        if self.is_pull_request:
            table.add(
                "Source", f"{self.head_owner}/{self.head_repo}, branch: {self.head_branch}, commit: {self.head_commit}"
            )
            table.add(
                "Target", f"{self.base_owner}/{self.base_repo}, branch: {self.base_branch}, commit: {self.base_commit}"
            )
        table.add("Description", self.body)

        return str(table)

    def to_light_dict(self, exclude_columns: Optional[list] = None):
        x = ["allow_maintainer_edit", "body"]
        if exclude_columns:
            x += exclude_columns
        return self.dict(x)

    def dict(self, exclude_columns: Optional[list] = None):
        import inspect

        exclude_columns = exclude_columns or []
        result = {}

        for mro in inspect.getmro(PullRequest):
            for name, value in vars(mro).items():
                if name.endswith("_obj"):
                    continue

                found = 0
                for i in exclude_columns:
                    if i == name:
                        found = 1
                        break

                if found:
                    continue

                if isinstance(value, property):
                    obj = getattr(self, name)
                    try:
                        result[name] = obj
                    except Exception:
                        pass  # ignore objects that cannot fit to dictionary

        return result

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
    ) -> "PullRequest":
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
        response = conn.request("POST", url, json_data=data)
        obj = cls(response.json(), response=response, conn=conn)
        return obj

    @classmethod
    def get(
        cls,
        conn: Connection,
        owner: str,
        repo: str,
        number: int,
    ) -> "PullRequest":
        """
        Get a pull request.

        :param conn: Gitea ``Connection`` instance.
        :param owner: Owner of the repo.
        :param repo: Name of the repo.
        :param number: Number of the pull request in the repo.
        """
        url = conn.makeurl("repos", owner, repo, "pulls", str(number))
        response = conn.request("GET", url)
        obj = cls(response.json(), response=response, conn=conn)
        return obj

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
    ) -> "PullRequest":
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
            "body": description,
            "allow_maintainer_edit": allow_maintainer_edit,
        }
        url = conn.makeurl("repos", owner, repo, "pulls", str(number))
        response = conn.request("PATCH", url, json_data=json_data)
        obj = cls(response.json(), response=response, conn=conn)
        return obj

    @classmethod
    def list(
        cls,
        conn: Connection,
        owner: str,
        repo: str,
        *,
        state: Optional[str] = "open",
    ) -> List["PullRequest"]:
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
        response = conn.request("GET", url)
        obj_list = [cls(i, response=response, conn=conn) for i in response.json()]
        return obj_list

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
    ) -> List["PullRequest"]:
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
            "limit": 50,
        }
        url = conn.makeurl("repos", "issues", "search", query=q)
        obj_list = []
        for response in conn.request_all_pages("GET", url):
            obj_list.extend([cls(i, response=response, conn=conn) for i in response.json()])
        return obj_list

    @classmethod
    def get_patch(
        cls,
        conn: Connection,
        owner: str,
        repo: str,
        number: int,
    ) -> "bytes":
        """
        Get a patch associated with a pull request.

        :param conn: Gitea ``Connection`` instance.
        :param owner: Owner of the repo.
        :param repo: Name of the repo.
        :param number: Number of the pull request in the repo.
        """
        q = {
            "binary": 0,
        }
        # XXX: .patch suffix doesn't work with binary=0
        url = conn.makeurl("repos", owner, repo, "pulls", f"{number}.diff", query=q)
        response = conn.request("GET", url)
        return response.data

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

    def get_reviews(
        self,
        conn: Connection,
    ) -> List[PullRequestReview]:
        return PullRequestReview.list(conn, self.base_owner, self.base_repo, self.number)

    @classmethod
    def approve_review(
        cls,
        conn: Connection,
        owner: str,
        repo: str,
        number: int,
        *,
        msg: Optional[str] = None,
        commit: Optional[str] = None,
        reviewer: Optional[str] = None,
        schedule_merge: bool = False,
    ):
        """
        Approve review in a pull request.
        """
        if commit:
            pr_obj = cls.get(conn, owner, repo, number)
            if pr_obj.head_commit != commit:
                raise RuntimeError("The pull request '{owner}/{repo}#{number}' has changed during the review")

        if reviewer:
            # group review bot is controlled via messages in comments
            new_msg = f"@{reviewer} : approve\n"
            if schedule_merge:
                new_msg += "merge ok\n"
            new_msg += "\n"
            new_msg += msg or ""
            new_msg = new_msg.strip()
            cls.add_comment(conn, owner, repo, number, msg=new_msg)
            return

        url = conn.makeurl("repos", owner, repo, "pulls", str(number), "reviews")
        # XXX[dmach]: commit_id has no effect; I thought it's going to approve if the commit matches with head and errors out otherwise
        json_data = {
            "event": "APPROVED",
            "body": msg,
            "commit_id": commit,
        }
        conn.request("POST", url, json_data=json_data)

        if schedule_merge:
            cls.add_comment(conn, owner, repo, number, msg="merge ok")

    @classmethod
    def decline_review(
        cls,
        conn: Connection,
        owner: str,
        repo: str,
        number: int,
        *,
        msg: str,
        commit: Optional[str] = None,
        reviewer: Optional[str] = None,
    ):
        """
        Decline review (request changes) in a pull request.
        """
        if reviewer:
            # group review bot is controlled via messages in comments
            msg = f"@{reviewer} : decline\n\n" + (msg or "")
            msg = msg.strip()
            cls.add_comment(conn, owner, repo, number, msg=msg)
            return

        url = conn.makeurl("repos", owner, repo, "pulls", str(number), "reviews")
        json_data = {
            "event": "REQUEST_CHANGES",
            "body": msg,
            "commit": commit,
        }
        conn.request("POST", url, json_data=json_data)

    @classmethod
    def merge(
        cls,
        conn: Connection,
        owner: str,
        repo: str,
        number: int,
        *,
        merge_when_checks_succeed: Optional[bool] = None,
    ) -> GiteaHTTPResponse:
        """
        Merge a pull request.

        :param merge_when_checks_succeed: Schedule the merge until all checks succeed.
        """
        from .exceptions import AutoMergeAlreadyScheduled

        url = conn.makeurl("repos", owner, repo, "pulls", str(number), "merge")
        json_data = {
            "Do": "merge",  # we're merging because we don't want to modify the commits by rebasing and we also want to keep information about the pull request in the merge commit
            "merge_when_checks_succeed": merge_when_checks_succeed,
        }
        try:
            conn.request("POST", url, json_data=json_data, context={"owner": owner, "repo": repo})
        except AutoMergeAlreadyScheduled:
            pass

    @classmethod
    def cancel_scheduled_merge(
        cls,
        conn: Connection,
        owner: str,
        repo: str,
        number: int,
    ) -> GiteaHTTPResponse:
        """
        Cancel scheduled merge of a pull request.
        """
        from .exceptions import GiteaException

        url = conn.makeurl("repos", owner, repo, "pulls", str(number), "merge")
        try:
            conn.request("DELETE", url, context={"owner": owner, "repo": repo})
        except GiteaException as e:
            # Gitea returns 404 when there's no scheduled merge or if the pull request doesn't exist
            # the error message is the same and it's not possible to distinguish between the two cases.
            if e.status != 404:
                raise

    @classmethod
    def close(
        cls,
        conn: Connection,
        owner: str,
        repo: str,
        number: int,
    ) -> "PullRequest":
        """
        Close a pull request.
        """
        url = conn.makeurl("repos", owner, repo, "pulls", str(number))
        json_data = {
            "state": "closed",
        }
        response = conn.request("PATCH", url, json_data=json_data, context={"owner": owner, "repo": repo})
        obj = cls(response.json(), response=response, conn=conn)
        return obj

    @classmethod
    def reopen(
        cls,
        conn: Connection,
        owner: str,
        repo: str,
        number: int,
    ) -> "PullRequest":
        """
        Reopen a pull request.
        """
        url = conn.makeurl("repos", owner, repo, "pulls", str(number))
        json_data = {
            "state": "open",
        }
        response = conn.request("PATCH", url, json_data=json_data, context={"owner": owner, "repo": repo})
        obj = cls(response.json(), response=response, conn=conn)
        return obj

    @classmethod
    def _get_label_id(cls, conn: Connection, owner: str, repo: str, label_name: str) -> Optional[int]:
        """Helper to get the ID of a label by its name."""
        url = conn.makeurl("repos", owner, repo, "labels")
        response = conn.request("GET", url)
        labels = response.json()
        for label in labels:
            if label["name"] == label_name:
                return label["id"]
        return None

    @classmethod
    def add_labels(
        cls,
        conn: Connection,
        owner: str,
        repo: str,
        number: int,
        labels: List[str],
    ) -> Optional["GiteaHTTPResponse"]:
        """
        Add one or more labels to a pull request.

        :param conn: Gitea Connection instance.
        :param owner: Owner of the repo.
        :param repo: Name of the repo.
        :param number: Number of the pull request.
        :param labels: A list of label names to add.
        """
        label_ids = []
        for label_name in labels:
            label_id = cls._get_label_id(conn, owner, repo, label_name)
            if label_id:
                label_ids.append(label_id)

        if not label_ids:
            # Avoid making a request if no valid labels were found
            return None

        url = conn.makeurl("repos", owner, repo, "issues", str(number), "labels")
        json_data = {
            "labels": label_ids,
        }
        return conn.request("POST", url, json_data=json_data)

    @classmethod
    def remove_label(
        cls,
        conn: Connection,
        owner: str,
        repo: str,
        number: int,
        label_name: str,
    ) -> "GiteaHTTPResponse":
        """
        Remove a label from a pull request.

        :param conn: Gitea Connection instance.
        :param owner: Owner of the repo.
        :param repo: Name of the repo.
        :param number: Number of the pull request.
        :param label_name: The name of the label to remove.
        """
        label_id = cls._get_label_id(conn, owner, repo, label_name)
        if not label_id:
            raise ValueError(f"Label '{label_name}' not found in repo {owner}/{repo}")

        url = conn.makeurl("repos", owner, repo, "issues", str(number), "labels", str(label_id))
        return conn.request("DELETE", url)