import unittest

from osc.gitea_api import Branch


class TestGiteaApiBranch(unittest.TestCase):
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

    def test_split_id(self):
        self.assertEqual(Branch.split_id("owner/repo:branch"), ("owner", "repo", "branch"))

        self.assertEqual(
            Branch.split_id("owner:branch", repo_optional=True),
            ("owner", None, "branch")
        )

        self.assertEqual(
            Branch.split_id(":branch", owner_optional=True, repo_optional=True),
            (None, None, "branch")
        )

        with self.assertRaises(ValueError):
            Branch.split_id("owner:branch")

        with self.assertRaises(ValueError):
            Branch.split_id(":branch")

        with self.assertRaises(ValueError):
            Branch.split_id(":branch", owner_optional=True)

        with self.assertRaises(ValueError):
            Branch.split_id("invalid")


if __name__ == "__main__":
    unittest.main()
