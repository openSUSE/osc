import sys

import osc.commandline_git


class LoginRemoveCommand(osc.commandline_git.GitObsCommand):
    """
    Remove a Gitea credentials entry
    """

    name = "remove"
    parent = "LoginCommand"

    def init_arguments(self):
        self.parser.add_argument("name")

    def run(self, args):
        print(f"Removing a Gitea credentials entry with name '{args.name}' ...", file=sys.stderr)
        print(f" * Config path: {self.gitea_conf.path}", file=sys.stderr)
        print("", file=sys.stderr)

        login = self.gitea_conf.remove_login(args.name)

        print("Removed entry:")
        print(login.to_human_readable_string())
