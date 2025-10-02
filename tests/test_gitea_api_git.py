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

    def test_urljoin(self):
        # https url
        url = "https://example.com/owner/repo.git"
        result = Git.urljoin(url, "subdir")
        self.assertEqual(result, "https://example.com/owner/repo.git/subdir")

        # https url, one level back
        url = "https://example.com/owner/repo.git"
        result = Git.urljoin(url, "../another-repo.git")
        self.assertEqual(result, "https://example.com/owner/another-repo.git")

        # https url, two levels back
        url = "https://example.com/owner/repo.git"
        result = Git.urljoin(url, "../../another-owner/another-repo.git")
        self.assertEqual(result, "https://example.com/another-owner/another-repo.git")

        # https url, relative path
        url = "https://example.com/owner/repo.git"
        with self.assertRaises(ValueError):
            Git.urljoin(url, "../../../another-repo.git")

        # ssh url
        url = "user@example.com:owner/repo.git"
        result = Git.urljoin(url, "subdir")
        self.assertEqual(result, "user@example.com:owner/repo.git/subdir")

        # ssh url, one level back
        url = "user@example.com:owner/repo.git"
        result = Git.urljoin(url, "../another-repo.git")
        self.assertEqual(result, "user@example.com:owner/another-repo.git")

        # ssh url, two levels back
        url = "user@example.com:owner/repo.git"
        result = Git.urljoin(url, "../../another-owner/another-repo.git")
        self.assertEqual(result, "user@example.com:another-owner/another-repo.git")

        # ssh url, relative path
        url = "user@example.com:owner/repo.git"
        with self.assertRaises(ValueError):
            Git.urljoin(url, "../../../another-repo.git")


if __name__ == "__main__":
    unittest.main()
