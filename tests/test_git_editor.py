import os
import shutil
import unittest
import unittest.mock

from osc.gitea_api.common import get_editor_command


vim_executable = shutil.which("vim")
nano_executable = shutil.which("nano")


class TestGitEditor(unittest.TestCase):

    def test_default(self):
        with unittest.mock.patch.dict(os.environ, {"EDITOR": ""}):
            c = get_editor_command("test")
        self.assertEqual(c, [vim_executable, "test"])

    def test_custom(self):
        with unittest.mock.patch.dict(os.environ, {"EDITOR": "nano"}):
            c = get_editor_command("test")
        self.assertEqual(c, [nano_executable, "test"])

    def test_custom_with_param(self):
        with unittest.mock.patch.dict(os.environ, {"EDITOR": "/usr/bin/emacs -nv"}):
            c = get_editor_command("test")
        self.assertEqual(c, ["/usr/bin/emacs", "-nv", "test"])

    def test_custom_with_params(self):
        with unittest.mock.patch.dict(os.environ, {"EDITOR": "/usr/bin/emacs -n -v "}):
            c = get_editor_command("test")
        self.assertEqual(c, ["/usr/bin/emacs", "-n", "-v", "test"])

    def test_custom_with_miltiword_params(self):
        with unittest.mock.patch.dict(os.environ, {"EDITOR": "/usr/bin/mycmd -A 'my fancy  parameter ' "}):
            c = get_editor_command("test")
        self.assertEqual(c, ["/usr/bin/mycmd", "-A", "my fancy  parameter ", "test"])


if nano_executable is None:
    TestGitEditor = unittest.skip("nano executable missing")(TestGitEditor)
elif vim_executable is None:
    TestGitEditor = unittest.skip("vim executable missing")(TestGitEditor)

if __name__ == "__main__":
    unittest.main()
