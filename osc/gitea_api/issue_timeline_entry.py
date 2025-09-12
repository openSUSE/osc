from typing import List
from typing import Optional

from .common import GiteaModel
from .common import dt_sanitize
from .connection import Connection
from .pr_review import PullRequestReview
from .user import User


class IssueTimelineEntry(GiteaModel):
    @property
    def type(self) -> str:
        return self._data["type"]

    @property
    def body(self) -> str:
        return self._data["body"]

    @property
    def user(self) -> str:
        return self._data["user"]["login"]

    @property
    def user_obj(self) -> User:
        return User(self._data["user"], response=self._response)

    @property
    def created_at(self) -> str:
        return self._data["created_at"]

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
    def review_id(self) -> Optional[int]:
        return self._data["review_id"]

    @property
    def review_obj(self) -> Optional[PullRequestReview]:
        from .exceptions import PullRequestReviewDoesNotExist

        if not self.review_id:
            return None
        try:
            return PullRequestReview.get(self._conn, self.pr_owner, self.pr_repo, self.pr_number, str(self.review_id))
        except PullRequestReviewDoesNotExist:
            # reviews can be removed from the database, but their IDs remain in other places
            return None

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

    def is_empty(self) -> bool:
        if self._data:
            return not self._data.get("type", False)
        return True

    def format(self):
        handler = getattr(self, f"_format_{self.type}", None)
        if handler is None:
            return (self.type, self.body)
        if not callable(handler):
            raise TypeError(f"Handler for {self.type} is not callable")
        return handler()  # pylint: disable=not-callable

    def _format_assignees(self):
        if self._data["removed_assignee"]:
            return f"unassigned the pull request from {self._data['assignee']['login']}", None
        return f"assigned the pull request to {self._data['assignee']['login']}", None

    def _format_change_target_branch(self):
        return f"changed target branch from '{self._data['old_ref']}' to '{self._data['new_ref']}'", None

    def _format_change_title(self):
        return "changed title", f"from '{self._data['old_title']}' to '{self._data['new_title']}'"

    def _format_comment(self):
        return "commented", self.body

    def _format_comment_ref(self):
        return "referenced the pull request", self._data["ref_comment"]["html_url"]

    def _format_commit_ref(self):
        import urllib.parse
        from osc.util import xml as osc_xml

        node = osc_xml.xml_fromstring(self.body)
        assert node.tag == "a"

        netloc = self._conn.host
        if self._conn.port:
            netloc += f":{self._conn.port}"
        url = urllib.parse.urlunsplit((self._conn.scheme, netloc, node.attrib["href"], "", ""))
        body = f"{url}\n{node.text}".strip()

        return f"referenced the pull request from commit", body

    def _format_close(self):
        return "closed the pull request", self.body

    def _format_delete_branch(self):
        return f"deleted branch '{self._data['old_ref']}'", None

    def _format_dismiss_review(self):
        return f"dismissed {self.review_obj.user}'s review", self.body

    def _format_merge_pull(self):
        from .pr import PullRequest

        pr_obj = PullRequest.get(self._conn, self.pr_owner, self.pr_repo, self.pr_number)
        return f"merged commit {pr_obj.merge_commit} to {pr_obj.base_branch}", None

    def _format_pull_cancel_scheduled_merge(self):
        return "canceled auto merging the pull request when all checks succeed", None

    def _format_pull_push(self):
        import json

        data = json.loads(self.body)
        len_commits = len(data["commit_ids"])
        return f"{'force-' if data['is_force_push'] else ''}pushed {len_commits} commit{'s' if len_commits > 1 else ''}", None

    def _format_pull_ref(self):
        return "referenced the pull request", f"{self._data['ref_issue']['html_url']}\n{self._data['ref_issue']['title']}"

    def _format_pull_scheduled_merge(self):
        return "scheduled the pull request to auto merge when all checks succeed", None

    def _format_reopen(self):
        return "reopened the pull request", self.body

    def _format_review(self):
        messages = {
            "APPROVED": "approved",
            "REQUEST_CHANGES": "declined",
            "COMMENTED": "commented",
        }
        msg = messages.get(self.review_obj.state, self.review_obj.state)
        return f"{msg} the review", self.body

    def _format_review_request(self):
        action = "removed" if self._data["removed_assignee"] else "requested"

        if self._data["assignee"]:
            reviewer = self._data["assignee"]["login"]
            if self._data["assignee"]["id"] == -1:
                reviewer += " (DELETED)"
        elif self._data["assignee_team"]:
            reviewer = self._data["assignee_team"]["name"]
        else:
            reviewer = "Ghost Team (DELETED)"

        return f"{action} review from {reviewer}", self.body

    # unused; we are not interested in these types of entries

    def _format_added_deadline(self):
        return None, None

    def _format_modified_deadline(self):
        return None, None

    def _format_removed_deadline(self):
        return None, None

    def _format_pin(self):
        return None, None

    def _format_unpin(self):
        return None, None

    def _format_change_time_estimate(self):
        return None, None

    def _format_project(self):
        return None, None

    def _format_project_board(self):
        return None, None

    def _format_start_tracking(self):
        return None, None

    def _format_stop_tracking(self):
        return None, None

    def _format_add_time_manual(self):
        return None, None

    def _format_delete_time_manual(self):
        return None, None

    def _format_cancel_tracking(self):
        return None, None

    def _format_label(self):
        return None, None

    def _format_milestone(self):
        return None, None

    def _format_lock(self):
        return None, None

    def _format_unlock(self):
        return None, None

    def _format_add_dependency(self):
        return None, None

    def _format_remove_dependency(self):
        return None, None

    # TODO: find a reproducer for formatting the following entries
    # def _format_issue_ref(self):
    # def _format_code(self):
    # def _format_change_issue_ref(self):

    @classmethod
    def list(
        cls,
        conn: Connection,
        owner: str,
        repo: str,
        number: int,
    ) -> List["IssueTimelineEntry"]:
        """
        List issue timeline entries (applicable to issues and pull request).
        HACK: the resulting list may contain instances wrapping ``None`` instead of dictionary with data!

        :param conn: Gitea ``Connection`` instance.
        :param owner: Owner of the repo.
        :param repo: Name of the repo.
        :param number: Number of the pull request in owner/repo.
        """
        q = {
            "limit": -1,
        }
        url = conn.makeurl("repos", owner, repo, "issues", str(number), "timeline", query=q)
        response = conn.request("GET", url)
        obj_list = [cls(i, response=response, conn=conn, check_data=False) for i in response.json() or []]
        return obj_list
