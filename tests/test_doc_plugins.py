"""
These tests make sure that the examples in the documentation
about osc plugins are not outdated.
"""


import os
import unittest


from osc.commandline import MainCommand
from osc.commandline import OscMainCommand


PLUGINS_DIR = os.path.join(os.path.dirname(__file__), "..", "doc", "plugins")


class TestMainCommand(MainCommand):
    name = "osc-test"
    MODULES = (
        ("test.osc.commands", PLUGINS_DIR),
    )


class TestPopProjectPackageFromArgs(unittest.TestCase):
    def test_load_commands(self):
        """
        Test if all plugins from the tutorial can be properly loaded
        """
        main = TestMainCommand()
        main.load_commands()

    def test_simple(self):
        """
        Test the 'simple' command
        """
        main = TestMainCommand()
        main.load_commands()
        args = main.parse_args(["simple", "arg1", "arg2"])
        self.assertEqual(args.command, "simple")
        self.assertEqual(args.bool_option, False)
        self.assertEqual(args.arguments, ["arg1", "arg2"])

    def test_request_list(self):
        """
        Test the 'request list' command
        """
        main = TestMainCommand()
        main.load_commands()
        args = main.parse_args(["request", "list"])
        self.assertEqual(args.command, "list")
        self.assertEqual(args.message, None)

    def test_request_accept(self):
        """
        Test the 'request accept' command
        """
        main = TestMainCommand()
        main.load_commands()
        args = main.parse_args(["request", "accept", "-m", "a message", "12345"])
        self.assertEqual(args.command, "accept")
        self.assertEqual(args.message, "a message")
        self.assertEqual(args.id, 12345)

    def test_plugin_locations(self):
        osc_paths = [i[1] for i in OscMainCommand.MODULES]
        # skip the first line with osc.commands
        osc_paths = osc_paths[1:]

        path = os.path.join(PLUGINS_DIR, "plugin_locations.rst")
        with open(path, "r") as f:
            # s
            doc_paths = f.readlines()
            # skip the first line with osc.commands
            doc_paths = doc_paths[1:]
            doc_paths = [i.lstrip(" -") for i in doc_paths]
            doc_paths = [i.rstrip("\n") for i in doc_paths]

        self.assertEqual(doc_paths, osc_paths)
