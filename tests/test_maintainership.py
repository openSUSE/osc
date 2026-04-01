import unittest
import json

from osc.gitea_api import Maintainership


class TestMaintainership(unittest.TestCase):
    def test_from_string_v1(self):
        data = {
            "header": {
                "document": "obs-maintainers",
                "version": "1.0"
            },
            "project": {
                "users": ["project_owner1", "project_owner2"],
                "groups": ["project-maintainer-group"]
            },
            "packages": {
                "package1": {
                    "users": ["alice", "bob"],
                    "groups": ["pkg1-maintainers"]
                },
                "package2": {
                    "users": ["charlie"],
                    "groups": ["pkg2-maintainers"]
                }
            }
        }
        m = Maintainership.from_string(json.dumps(data))

        self.assertEqual(m.get_project_maintainers_users(), ["project_owner1", "project_owner2"])
        self.assertEqual(m.get_project_maintainers_groups(), ["project-maintainer-group"])
        self.assertEqual(m.get_project_maintainers(), ["project_owner1", "project_owner2", "@project-maintainer-group"])

        self.assertEqual(m.get_package_maintainers_users("package1"), ["alice", "bob"])
        self.assertEqual(m.get_package_maintainers_groups("package1"), ["pkg1-maintainers"])
        self.assertEqual(m.get_package_maintainers("package1"), ["alice", "bob", "@pkg1-maintainers"])

        self.assertEqual(m.get_user_packages("alice"), ["package1"])
        self.assertEqual(m.get_user_packages("charlie"), ["package2"])
        self.assertEqual(m.get_group_packages("pkg1-maintainers"), ["package1"])

    def test_from_string_legacy(self):
        data = {
            "": ["project-maintainer"],
            "package1": ["alice"],
            "package2": ["bob", "@group"]
        }
        m = Maintainership.from_string(json.dumps(data))

        self.assertEqual(m.get_project_maintainers_users(), ["project-maintainer"])
        self.assertEqual(m.get_project_maintainers_groups(), [])
        self.assertEqual(m.get_project_maintainers(), ["project-maintainer"])

        self.assertEqual(m.get_package_maintainers_users("package1"), ["alice"])
        self.assertEqual(m.get_package_maintainers_groups("package1"), [])
        self.assertEqual(m.get_package_maintainers("package1"), ["alice"])

        self.assertEqual(m.get_package_maintainers_users("package2"), ["bob"])
        self.assertEqual(m.get_package_maintainers_groups("package2"), ["group"])
        self.assertEqual(m.get_package_maintainers("package2"), ["bob", "@group"])

        self.assertEqual(m.get_user_packages("alice"), ["package1"])
        self.assertEqual(m.get_user_packages("bob"), ["package2"])
        self.assertEqual(m.get_group_packages("group"), ["package2"])

    def test_empty_and_missing(self):
        m = Maintainership.from_string("{}")
        self.assertEqual(m.get_project_maintainers_users(), [])
        self.assertRaises(ValueError, m.get_package_maintainers_users, "nonexistent")
        self.assertRaises(ValueError, m.get_user_packages, "nobody")


if __name__ == "__main__":
    unittest.main()
