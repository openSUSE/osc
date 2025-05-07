import os
import shutil
import unittest
import unittest.mock

from osc.commands_git.pr_create import get_editor_command


class TestGitEditor(unittest.TestCase):

    def test_default(self):
        with unittest.mock.patch.dict(os.environ, {"EDITOR": ""}):
            c = get_editor_command("test")
        self.assertEqual(c, ["/usr/bin/vim", "test"])

    def test_custom(self):
        with unittest.mock.patch.dict(os.environ, {"EDITOR": "nano"}):
            c = get_editor_command("test")
        self.assertEqual(c, ["/usr/bin/nano", "test"])

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


if shutil.which("nano") != "/usr/bin/nano":
    TestGitEditor = unittest.skip("nano is not /usr/bin/nano")(TestGitEditor)
elif shutil.which("vim") != "/usr/bin/vim":
    TestGitEditor = unittest.skip("vim is not /usr/bin/vim")(TestGitEditor)

if __name__ == "__main__":
    unittest.main()
