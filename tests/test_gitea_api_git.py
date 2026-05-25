import os
import shutil
import subprocess
import tempfile
import unittest

from osc.gitea_api import Git


@unittest.skipIf(not shutil.which("git"), "The 'git' executable is not available")
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

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp(prefix="osc_test_")

    def tearDown(self):
        try:
            shutil.rmtree(self.tmpdir)
        except OSError:
            pass

    def test_detect_git_normal(self):
        subprocess.check_call(["git", "init", "-q"], cwd=self.tmpdir)
        is_bare, git_dir, top_dir = Git.detect_git(self.tmpdir)
        self.assertFalse(is_bare)
        self.assertEqual(git_dir, os.path.join(self.tmpdir, ".git"))
        self.assertEqual(top_dir, self.tmpdir)

        g = Git(self.tmpdir)
        self.assertFalse(g.is_bare)
        self.assertEqual(g.git_dir, os.path.join(self.tmpdir, ".git"))
        self.assertEqual(g.topdir, self.tmpdir)

    def test_detect_git_subdir(self):
        subprocess.check_call(["git", "init", "-q"], cwd=self.tmpdir)
        subdir = os.path.join(self.tmpdir, "subdir")
        os.mkdir(subdir)
        is_bare, git_dir, top_dir = Git.detect_git(subdir)
        self.assertFalse(is_bare)
        self.assertEqual(git_dir, os.path.join(self.tmpdir, ".git"))
        self.assertEqual(top_dir, self.tmpdir)

        g = Git(subdir)
        self.assertFalse(g.is_bare)
        self.assertEqual(g.git_dir, os.path.join(self.tmpdir, ".git"))
        self.assertEqual(g.topdir, self.tmpdir)

    def test_detect_git_inside_git_dir(self):
        subprocess.check_call(["git", "init", "-q"], cwd=self.tmpdir)
        git_dir_path = os.path.join(self.tmpdir, ".git")
        is_bare, git_dir, top_dir = Git.detect_git(git_dir_path)
        self.assertFalse(is_bare)
        self.assertEqual(git_dir, git_dir_path)
        self.assertEqual(top_dir, self.tmpdir)

        g = Git(git_dir_path)
        self.assertFalse(g.is_bare)
        self.assertEqual(g.git_dir, git_dir_path)
        self.assertEqual(g.topdir, self.tmpdir)

    def test_detect_git_inside_git_subdir(self):
        subprocess.check_call(["git", "init", "-q"], cwd=self.tmpdir)
        git_subdir = os.path.join(self.tmpdir, ".git", "hooks")
        is_bare, git_dir, top_dir = Git.detect_git(git_subdir)
        self.assertFalse(is_bare)
        self.assertEqual(git_dir, os.path.join(self.tmpdir, ".git"))
        self.assertEqual(top_dir, self.tmpdir)

        g = Git(git_subdir)
        self.assertFalse(g.is_bare)
        self.assertEqual(g.git_dir, os.path.join(self.tmpdir, ".git"))
        self.assertEqual(g.topdir, self.tmpdir)

    def test_detect_git_bare(self):
        subprocess.check_call(["git", "init", "--bare", "-q"], cwd=self.tmpdir)
        is_bare, git_dir, top_dir = Git.detect_git(self.tmpdir)
        self.assertTrue(is_bare)
        self.assertEqual(git_dir, self.tmpdir)
        self.assertEqual(top_dir, self.tmpdir)

        g = Git(self.tmpdir)
        self.assertTrue(g.is_bare)
        self.assertEqual(g.git_dir, self.tmpdir)
        self.assertEqual(g.topdir, self.tmpdir)


if __name__ == "__main__":
    unittest.main()
