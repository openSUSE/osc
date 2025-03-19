import getpass
import sys

import osc.commandline_git


class LoginAddCommand(osc.commandline_git.GitObsCommand):
    """
    Add a Gitea credentials entry
    """

    name = "add"
    parent = "LoginCommand"

    def init_arguments(self):
        from osc.commandline_git import complete_ssh_key_path

        self.parser.add_argument("name")
        self.parser.add_argument("--url", required=True)
        self.parser.add_argument("--user", required=True)
        self.parser.add_argument("--token", help="Omit or set to '-' to invoke a secure interactive prompt.")
        self.parser.add_argument("--ssh-key").completer = complete_ssh_key_path
        self.parser.add_argument("--set-as-default", action="store_true", default=None)

    def run(self, args):
        from osc import gitea_api

        print(f"Adding a Gitea credentials entry with name '{args.name}' ...", file=sys.stderr)
        print(f" * Config path: {self.gitea_conf.path}", file=sys.stderr)
        print("", file=sys.stderr)

        # TODO: try to authenticate to verify that the new entry works

        while not args.token or args.token == "-":
            args.token = getpass.getpass(prompt=f"Enter Gitea token for user '{args.user}': ")

        login = gitea_api.Login(name=args.name, url=args.url, user=args.user, token=args.token, ssh_key=args.ssh_key, default=args.set_as_default)
        self.gitea_conf.add_login(login)

        print("Added entry:")
        print(login.to_human_readable_string())
