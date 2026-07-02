import contextlib
import unittest
from unittest.mock import patch

from urllib3 import HTTPResponse

from osc.gitea_api import (
    Branch,
    Fork,
    Issue,
    Login,
    PullRequest,
    PullRequestReview,
    Repo,
    SSHKey,
    User,
)
from osc.gitea_api.connection import Connection
from osc.gitea_api.exceptions import MovedPermanently

# Sample response for GET pullrequest:
# it doesn't really make sense for the other entities, but are mostly interested
# in the context passed to Exception's __init__ anyway, so the response
# itself is only important for its status code.
RESPONSE_301 = HTTPResponse(
    status=301,
    body=b'<a href="/api/v1/repos/new-owner/repo/pulls/1">Moved Permanently</a>.\n\n',
    headers={
        "content-type": "text/html; charset=utf-8",
        "location": "/api/v1/repos/new-owner/repo/pulls/1",
    },
)


@contextlib.contextmanager
def patch_connection(connection: Connection, response: HTTPResponse):
    with patch.object(connection.conn, "getresponse", new=lambda: response):
        with patch.object(connection.conn, "request"):
            yield


class TestGiteaResponseToException(unittest.TestCase):
    """Test that a 301 response properly raises MovedPermanently across all API entities"""

    def setUp(self):
        self.connection = Connection(
            login=Login(name="mock", user="mock", url="https://mock.src.suse.de")
        )

    # --- PullRequest ---

    def test_pull_request_get_301(self):
        with patch_connection(self.connection, response=RESPONSE_301):
            with self.assertRaises(MovedPermanently):
                PullRequest.get(
                    repo="test", number=1, owner="ADMIN", conn=self.connection
                )

    def test_pull_request_list_301(self):
        with patch_connection(self.connection, response=RESPONSE_301):
            with self.assertRaises(MovedPermanently):
                PullRequest.list(owner="ADMIN", repo="test", conn=self.connection)

    def test_pull_request_close_301(self):
        with patch_connection(self.connection, response=RESPONSE_301):
            with self.assertRaises(MovedPermanently):
                PullRequest.close(
                    owner="ADMIN", repo="test", number=1, conn=self.connection
                )

    def test_pull_request_reopen_301(self):
        with patch_connection(self.connection, response=RESPONSE_301):
            with self.assertRaises(MovedPermanently):
                PullRequest.reopen(
                    owner="ADMIN", repo="test", number=1, conn=self.connection
                )

    def test_pull_request_add_comment_301(self):
        with patch_connection(self.connection, response=RESPONSE_301):
            with self.assertRaises(MovedPermanently):
                PullRequest.add_comment(
                    owner="ADMIN",
                    repo="test",
                    number=1,
                    msg="hello",
                    conn=self.connection,
                )

    def test_pull_request_get_patch_301(self):
        with patch_connection(self.connection, response=RESPONSE_301):
            with self.assertRaises(MovedPermanently):
                PullRequest.get_patch(
                    owner="ADMIN", repo="test", number=1, conn=self.connection
                )

    # --- PullRequestReview ---

    def test_pull_request_review_get_301(self):
        with patch_connection(self.connection, response=RESPONSE_301):
            with self.assertRaises(MovedPermanently):
                PullRequestReview.get(
                    owner="ADMIN",
                    repo="test",
                    number=1,
                    review_id=1,
                    conn=self.connection,
                )

    def test_pull_request_review_list_301(self):
        with patch_connection(self.connection, response=RESPONSE_301):
            with self.assertRaises(MovedPermanently):
                PullRequestReview.list(
                    owner="ADMIN", repo="test", number=1, conn=self.connection
                )

    # --- Repo ---

    def test_repo_get_301(self):
        with patch_connection(self.connection, response=RESPONSE_301):
            with self.assertRaises(MovedPermanently):
                Repo.get(owner="ADMIN", repo="test", conn=self.connection)

    def test_repo_list_org_repos_301(self):
        with patch_connection(self.connection, response=RESPONSE_301):
            with self.assertRaises(MovedPermanently):
                Repo.list_org_repos(owner="ADMIN", conn=self.connection)

    def test_repo_list_my_repos_301(self):
        with patch_connection(self.connection, response=RESPONSE_301):
            with self.assertRaises(MovedPermanently):
                Repo.list_my_repos(conn=self.connection)

    # --- Branch ---

    def test_branch_get_301(self):
        with patch_connection(self.connection, response=RESPONSE_301):
            with self.assertRaises(MovedPermanently):
                Branch.get(
                    owner="ADMIN", repo="test", branch="main", conn=self.connection
                )

    def test_branch_list_301(self):
        with patch_connection(self.connection, response=RESPONSE_301):
            with self.assertRaises(MovedPermanently):
                Branch.list(owner="ADMIN", repo="test", conn=self.connection)

    def test_branch_create_301(self):
        with patch_connection(self.connection, response=RESPONSE_301):
            with self.assertRaises(MovedPermanently):
                Branch.create(
                    owner="ADMIN",
                    repo="test",
                    new_branch_name="new-branch",
                    conn=self.connection,
                )

    # --- Fork ---

    def test_fork_list_301(self):
        with patch_connection(self.connection, response=RESPONSE_301):
            with self.assertRaises(MovedPermanently):
                Fork.list(owner="ADMIN", repo="test", conn=self.connection)

    def test_fork_create_301(self):
        with patch_connection(self.connection, response=RESPONSE_301):
            with self.assertRaises(MovedPermanently):
                Fork.create(owner="ADMIN", repo="test", conn=self.connection)

    # --- User ---

    def test_user_get_current_301(self):
        with patch_connection(self.connection, response=RESPONSE_301):
            with self.assertRaises(MovedPermanently):
                User.get(conn=self.connection)

    def test_user_get_by_name_301(self):
        with patch_connection(self.connection, response=RESPONSE_301):
            with self.assertRaises(MovedPermanently):
                User.get(username="ADMIN", conn=self.connection)

    # --- SSHKey ---

    def test_ssh_key_get_301(self):
        with patch_connection(self.connection, response=RESPONSE_301):
            with self.assertRaises(MovedPermanently):
                SSHKey.get(id=1, conn=self.connection)

    def test_ssh_key_list_301(self):
        with patch_connection(self.connection, response=RESPONSE_301):
            with self.assertRaises(MovedPermanently):
                SSHKey.list(conn=self.connection)

    def test_ssh_key_delete_301(self):
        with patch_connection(self.connection, response=RESPONSE_301):
            with self.assertRaises(MovedPermanently):
                SSHKey.delete(id=1, conn=self.connection)

    # --- Issue ---

    def test_issue_create_301(self):
        with patch_connection(self.connection, response=RESPONSE_301):
            with self.assertRaises(MovedPermanently):
                Issue.create(
                    owner="ADMIN",
                    repo="test",
                    title="test issue",
                    body="test body",
                    conn=self.connection,
                )


if __name__ == "__main__":
    unittest.main()
