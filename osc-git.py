#!/usr/bin/env python3

import sys

import osc.commandline
import osc.commands_git
from osc import oscerr
from osc.output import print_msg


class OscGitMainCommand(osc.commandline.MainCommand):
    name = "osc-git"

    MODULES = (
        ("osc.commands_git", osc.commands_git.__path__[0]),
    )

    def init_arguments(self):
        pass

    def post_parse_args(self, args):
        pass

    @classmethod
    def main(cls, argv=None, run=True):
        """
        Initialize OscMainCommand, load all commands and run the selected command.
        """
        cmd = cls()
        cmd.load_commands()
        if run:
            args = cmd.parse_args(args=argv)
            exit_code = cmd.run(args)
            sys.exit(exit_code)
        else:
            args = None
        return cmd, args


def main():
    try:
        OscGitMainCommand.main()
    except oscerr.OscBaseError as e:
        print_msg(str(e), print_to="error")
        sys.exit(1)


if __name__ == "__main__":
    main()
