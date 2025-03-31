import unittest

from osc.gitea_api import Git


class TestGiteaApiGit(unittest.TestCase):
    def test_urlparse(self):
        # https url without port
        url = "https://example.com/owner/repo.git"
        result = Git.urlparse(url)
        self.assertEqual(list(result), ['https', 'example.com', '/owner/repo.git', '', '', ''])

        # https url with port
        url = "https://example.com:1234/owner/repo.git"
        result = Git.urlparse(url)
        self.assertEqual(list(result), ['https', 'example.com:1234', '/owner/repo.git', '', '', ''])

        # url without scheme
        # urllib.parse.urlparse() would normally return ['', '', 'example.com/owner/repo.git', '', '', '']
        url = "example.com/owner/repo.git"
        result = Git.urlparse(url)
        self.assertEqual(list(result), ['', 'example.com', '/owner/repo.git', '', '', ''])

        # ssh url
        url = "user@example.com:owner/repo.git"
        result = Git.urlparse(url)
        self.assertEqual(list(result), ['', 'user@example.com', 'owner/repo.git', '', '', ''])

        # ssh url with port
        url = "user@example.com:1234:owner/repo.git"
        result = Git.urlparse(url)
        self.assertEqual(list(result), ['', 'user@example.com:1234', 'owner/repo.git', '', '', ''])


if __name__ == "__main__":
    unittest.main()
