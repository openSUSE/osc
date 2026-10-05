import os
import unittest
from unittest.mock import patch

from osc.gitea_api.conf import Config


class TestGiteaApiConfig(unittest.TestCase):
    def test_xdg_config_home(self):
        with patch.dict(os.environ, {"XDG_CONFIG_HOME": "/custom/config"}, clear=True):
            self.assertEqual(Config().path, "/custom/config/tea/config.yml")

    def test_default_config_home(self):
        with patch.dict(os.environ, {}, clear=True):
            self.assertEqual(Config().path, os.path.expanduser("~/.config/tea/config.yml"))

    def test_empty_config_home(self):
        with patch.dict(os.environ, {"XDG_CONFIG_HOME": ""}, clear=True):
            self.assertEqual(Config().path, os.path.expanduser("~/.config/tea/config.yml"))

    def test_relative_config_home(self):
        with patch.dict(os.environ, {"XDG_CONFIG_HOME": "relative/config"}, clear=True):
            with patch("os.getcwd", return_value="/worktree"):
                self.assertEqual(Config().path, "/worktree/relative/config/tea/config.yml")

    def test_tilde_config_home(self):
        with patch.dict(os.environ, {"XDG_CONFIG_HOME": "~/foo"}, clear=True):
            self.assertEqual(Config().path, os.path.expanduser("~/foo/tea/config.yml"))

    def test_explicit_path_takes_precedence(self):
        with patch.dict(os.environ, {"XDG_CONFIG_HOME": "/custom/config"}, clear=True):
            self.assertEqual(Config("~/custom-tea.yml").path, os.path.expanduser("~/custom-tea.yml"))
