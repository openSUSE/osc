import unittest

from osc.gitea_api import Branch


class TestGiteaApiPullRequest(unittest.TestCase):
    def test_object(self):
        data = {
            "name": "branch",
            "commit": {
                "id": "commit",
            },
        }
        obj = Branch(data)
        self.assertEqual(obj.name, "branch")
        self.assertEqual(obj.commit, "commit")


if __name__ == "__main__":
    unittest.main()
