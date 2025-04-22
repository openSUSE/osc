import getpass
import re
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

        self.parser.add_argument("name", help="The name of the login entry to be added")
        self.parser.add_argument("--url", help="Gitea URL, for example https://example.com", required=True)
        self.parser.add_argument("--user", help="Gitea username", required=True)
        self.parser.add_argument("--token", help="Gitea access token; omit or set to '-' to invoke a secure interactive prompt")
        self.parser.add_argument("--ssh-key", metavar="PATH", help="Path to a private SSH key").completer = complete_ssh_key_path
        self.parser.add_argument("--set-as-default", help="Set the new login entry as default", action="store_true", default=None)

    def run(self, args):
        from osc import gitea_api

        print(f"Adding a Gitea credentials entry with name '{args.name}' ...", file=sys.stderr)
        print(f" * Config path: {self.gitea_conf.path}", file=sys.stderr)
        print("", file=sys.stderr)

        # TODO: try to authenticate to verify that the new entry works

        while not args.token or args.token == "-":
            args.token = getpass.getpass(prompt=f"Enter Gitea token for user '{args.user}': ")

        if not re.match(r"^[0-9a-f]{40}$", args.token):
            self.parser.error("Invalid token format, 40 hexadecimal characters expected")

        login = gitea_api.Login(name=args.name, url=args.url, user=args.user, token=args.token, ssh_key=args.ssh_key, default=args.set_as_default)
        self.gitea_conf.add_login(login)

        print("Added entry:")
        print(login.to_human_readable_string())
