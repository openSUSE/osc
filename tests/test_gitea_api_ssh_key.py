import unittest

from osc.gitea_api import SSHKey


class TestGiteaApiSSHKey(unittest.TestCase):
    def test_object(self):
        data = {
            "id": 1,
            "key": "ssh-rsa ZXhhbXBsZS1zc2gta2V5Cg==",
            "title": "key title",
        }
        obj = SSHKey(data)
        self.assertEqual(obj.id, 1)
        self.assertEqual(obj.key, "ssh-rsa ZXhhbXBsZS1zc2gta2V5Cg==")
        self.assertEqual(obj.title, "key title")


if __name__ == "__main__":
    unittest.main()
