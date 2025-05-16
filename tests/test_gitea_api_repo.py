import unittest

from osc.gitea_api import Repo


class TestGiteaApiRepo(unittest.TestCase):
    def test_object(self):
        data = {
            "owner": {
                "login": "owner",
            },
            "name": "repo",
            "clone_url": "https://example.com/owner/repo",
            "ssh_url": "gitea:example.com:owner/repo",
            "default_branch": "default-branch",
            "parent": {
                "owner": {
                    "login": "parent-owner",
                },
                "name": "parent-repo",
                "clone_url": "https://example.com/parent-owner/parent-repo",
                "ssh_url": "gitea:example.com:parent-owner/parent-repo",
            },
        }
        obj = Repo(data)
        self.assertEqual(obj.owner, "owner")
        self.assertEqual(obj.owner_obj.login, "owner")
        self.assertEqual(obj.repo, "repo")
        self.assertEqual(obj.clone_url, "https://example.com/owner/repo")
        self.assertEqual(obj.ssh_url, "gitea:example.com:owner/repo")
        self.assertEqual(obj.default_branch, "default-branch")

        self.assertEqual(obj.parent_obj.owner, "parent-owner")
        self.assertEqual(obj.parent_obj.owner_obj.login, "parent-owner")
        self.assertEqual(obj.parent_obj.repo, "parent-repo")
        self.assertEqual(obj.parent_obj.clone_url, "https://example.com/parent-owner/parent-repo")
        self.assertEqual(obj.parent_obj.ssh_url, "gitea:example.com:parent-owner/parent-repo")


if __name__ == "__main__":
    unittest.main()
