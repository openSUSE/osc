import unittest

from osc.gitea_api import User


class TestGiteaApiUser(unittest.TestCase):
    def test_object(self):
        data = {
            "login": "alice",
            "full_name": "Alice",
            "email": "alice@example.com",
        }
        obj = User(data)
        self.assertEqual(obj.login, "alice")
        self.assertEqual(obj.full_name, "Alice")
        self.assertEqual(obj.email, "alice@example.com")
        self.assertEqual(obj.full_name_email, "Alice <alice@example.com>")
        self.assertEqual(obj.login_full_name_email, "alice (Alice <alice@example.com>)")


if __name__ == "__main__":
    unittest.main()
