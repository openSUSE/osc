import unittest

from osc.gitea_api import PullRequest


class TestGiteaApiPullRequest(unittest.TestCase):
    def test_object_pull_request(self):
        data = {
            "number": 1,
            "url": "https://example.com/base-owner/base-repo",
            "title": "title",
            "body": "body",
            "state": "state",
            "user": {
                "login": "alice",
                "full_name": "Alice",
                "email": "alice@example.com",
            },
            "allow_maintainer_edit": False,
            "draft": False,
            "merged": False,
            "base": {
                "ref": "base-branch",
                "sha": "base-commit",
                "repo": {
                    "owner": {
                        "login": "base-owner",
                    },
                    "name": "base-repo",
                    "ssh_url": "base-ssh-url",
                },
            },
            "head": {
                "ref": "head-branch",
                "sha": "head-commit",
                "repo": {
                    "owner": {
                        "login": "head-owner",
                    },
                    "name": "head-repo",
                    "ssh_url": "head-ssh-url",
                },
            },
        }
        obj = PullRequest(data)
        self.assertEqual(obj.is_pull_request, True)
        self.assertEqual(obj.id, "base-owner/base-repo#1")
        self.assertEqual(obj.url, "https://example.com/base-owner/base-repo")
        self.assertEqual(obj.number, 1)
        self.assertEqual(obj.title, "title")
        self.assertEqual(obj.body, "body")
        self.assertEqual(obj.state, "state")
        self.assertEqual(obj.user, "alice")
        self.assertEqual(obj.user_obj.login, "alice")
        self.assertEqual(obj.draft, False)
        self.assertEqual(obj.merged, False)
        self.assertEqual(obj.allow_maintainer_edit, False)

        self.assertEqual(obj.base_owner, "base-owner")
        self.assertEqual(obj.base_repo, "base-repo")
        self.assertEqual(obj.base_branch, "base-branch")
        self.assertEqual(obj.base_commit, "base-commit")
        self.assertEqual(obj.base_ssh_url, "base-ssh-url")

        self.assertEqual(obj.head_owner, "head-owner")
        self.assertEqual(obj.head_repo, "head-repo")
        self.assertEqual(obj.head_branch, "head-branch")
        self.assertEqual(obj.head_commit, "head-commit")
        self.assertEqual(obj.head_ssh_url, "head-ssh-url")

    def test_object_issue(self):
        data = {
            "number": 1,
            "url": "https://example.com/base-owner/base-repo",
            "title": "title",
            "body": "body",
            "state": "state",
            "user": {
                "login": "alice",
                "full_name": "Alice",
                "email": "alice@example.com",
            },
            "repository": {
                "owner": "base-owner",
                "name": "base-repo",
            },
        }
        obj = PullRequest(data)
        self.assertEqual(obj.is_pull_request, False)
        self.assertEqual(obj.id, "base-owner/base-repo#1")
        self.assertEqual(obj.url, "https://example.com/base-owner/base-repo")
        self.assertEqual(obj.number, 1)
        self.assertEqual(obj.title, "title")
        self.assertEqual(obj.body, "body")
        self.assertEqual(obj.state, "state")
        self.assertEqual(obj.user, "alice")
        self.assertEqual(obj.user_obj.login, "alice")
        self.assertEqual(obj.draft, None)
        self.assertEqual(obj.merged, None)
        self.assertEqual(obj.allow_maintainer_edit, None)

        self.assertEqual(obj.base_owner, "base-owner")
        self.assertEqual(obj.base_repo, "base-repo")
        self.assertEqual(obj.base_branch, None)
        self.assertEqual(obj.base_commit, None)
        self.assertEqual(obj.base_ssh_url, None)

        self.assertEqual(obj.head_owner, None)
        self.assertEqual(obj.head_repo, None)
        self.assertEqual(obj.head_branch, None)
        self.assertEqual(obj.head_commit, None)
        self.assertEqual(obj.head_ssh_url, None)


class TestGiteaApiPullRequestUrlParsing(unittest.TestCase):
    def test_get_host_owner_repo_number_https_with_port(self):
        url = "https://git.example.com:3000/owner/repo/pulls/123"
        host, owner, repo, number = PullRequest.get_host_owner_repo_number(url)
        self.assertEqual(host, "https://git.example.com:3000")
        self.assertEqual(owner, "owner")
        self.assertEqual(repo, "repo")
        self.assertEqual(number, 123)

        self.assertTupleEqual(
            PullRequest.get_owner_repo_number(url),
            (owner, repo, number),
        )

    def test_get_host_owner_repo_number_https_without_port(self):
        url = "https://git.example.com/owner/repo/pulls/456"
        host, owner, repo, number = PullRequest.get_host_owner_repo_number(url)
        self.assertEqual(host, "https://git.example.com")
        self.assertEqual(owner, "owner")
        self.assertEqual(repo, "repo")
        self.assertEqual(number, 456)

        self.assertTupleEqual(
            PullRequest.get_owner_repo_number(url),
            (owner, repo, number),
        )

    def test_get_host_owner_repo_number_issues_endpoint(self):
        url = "https://git.example.com/owner/repo/issues/100"
        host, owner, repo, number = PullRequest.get_host_owner_repo_number(url)
        self.assertEqual(host, "https://git.example.com")
        self.assertEqual(owner, "owner")
        self.assertEqual(repo, "repo")
        self.assertEqual(number, 100)

        self.assertTupleEqual(
            PullRequest.get_owner_repo_number(url),
            (owner, repo, number),
        )

    def test_get_host_owner_repo_number_invalid_endpoint(self):
        url = "https://git.example.com/owner/repo/commits/abc123"
        with self.assertRaises(ValueError) as context:
            PullRequest.get_host_owner_repo_number(url)
        self.assertIn("doesn't point to a pull request or an issue", str(context.exception))

    def test_get_host_owner_repo_number_invalid_format(self):
        url = "https://git.example.com/owner/repo"
        with self.assertRaises(ValueError):
            PullRequest.get_host_owner_repo_number(url)


class TestGiteaApiPullRequestReferences(unittest.TestCase):
    PR_BODY = """
PR: foo/bar!1
PR:  foo/bar#2\r
text
PR: bar/baz#3
text

text
text
""".strip()

    def test_parse_pr_references(self):
        pr_obj = PullRequest({"body": self.PR_BODY})
        actual = pr_obj.parse_pr_references()
        expected = [
            ('foo', 'bar', 1),
            ('foo', 'bar', 2),
            ('bar', 'baz', 3),
        ]
        self.assertEqual(actual, expected)

    def test_add_pr_references(self):
        actual = PullRequest.add_pr_references(self.PR_BODY, [('xxx', 'xxx', 4), ('yyy', 'yyy', 5)])
        expected = """
PR: foo/bar!1
PR:  foo/bar#2\r
text
PR: bar/baz#3
PR: xxx/xxx!4
PR: yyy/yyy!5
text

text
text
""".strip()

        self.assertEqual(actual, expected)

    def test_add_pr_references_end(self):
        actual = PullRequest.add_pr_references(self.PR_BODY + "\nPR: a/b#123", [('xxx', 'xxx', 4), ('yyy', 'yyy', 5)])
        expected = """
PR: foo/bar!1
PR:  foo/bar#2\r
text
PR: bar/baz#3
text

text
text
PR: a/b#123
PR: xxx/xxx!4
PR: yyy/yyy!5
""".lstrip()

        self.assertEqual(actual, expected)

    def test_remove_pr_references(self):
        actual = PullRequest.remove_pr_references(self.PR_BODY, [("foo", "bar", 2)])
        expected = """
PR: foo/bar!1
text
PR: bar/baz#3
text

text
text
""".strip()
        self.assertEqual(actual, expected)


if __name__ == "__main__":
    unittest.main()
