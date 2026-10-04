import os
import shutil
import subprocess
import tempfile
import unittest

from osc.gitea_api import TarDiff


@unittest.skipIf(not shutil.which("git"), "The 'git' executable is not available")
class TestGiteaApiTarDiff(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.mkdtemp(prefix="osc_test_tardiff_")

    def tearDown(self):
        try:
            shutil.rmtree(self.tmpdir)
        except OSError:
            pass

    def test_init_recreates_stale_sha1_cache(self):
        subprocess.check_call(["git", "init", "-q"], cwd=self.tmpdir)
        with open(os.path.join(self.tmpdir, "stale.txt"), "w", encoding="utf-8") as f:
            f.write("stale cache contents")

        TarDiff(self.tmpdir)

        object_format = subprocess.check_output(
            ["git", "rev-parse", "--show-object-format"],
            cwd=self.tmpdir,
            encoding="utf-8",
        ).strip()
        self.assertEqual(object_format, "sha256")
        self.assertFalse(os.path.exists(os.path.join(self.tmpdir, "stale.txt")))


if __name__ == "__main__":
    unittest.main()
