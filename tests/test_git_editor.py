import os
import shutil
import unittest
import unittest.mock

from osc.gitea_api.common import get_editor_command


vim_executable = shutil.which("vim")
nano_executable = shutil.which("nano")


class TestGitEditor(unittest.TestCase):

    @unittest.skipIf(vim_executable is None, "vim executable not found")
    def test_default(self):
        with unittest.mock.patch.dict(os.environ, {"EDITOR": ""}):
            c = get_editor_command("test")
        self.assertEqual(c, [vim_executable, "test"])

    @unittest.skipIf(nano_executable is None, "nano executable not found")
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

    def test_visual(self):
        with unittest.mock.patch.dict(os.environ, { "VISUAL": "/usr/bin/emacs", "EDITOR": "/usr/bin/mycmd" }):
            c = get_editor_command("test")
        self.assertEqual(c, ["/usr/bin/emacs", "test"])


if __name__ == "__main__":
    unittest.main()
