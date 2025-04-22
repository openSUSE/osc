import getpass
import re
import sys

import osc.commandline_git


class LoginUpdateCommand(osc.commandline_git.GitObsCommand):
    """
    Update a Gitea credentials entry
    """

    name = "update"
    parent = "LoginCommand"

    def init_arguments(self):
        from osc.commandline_git import complete_ssh_key_path

        self.parser.add_argument("name", help="The name of the login entry to be updated")
        self.parser.add_argument("--new-name", help="New name of the login entry")
        self.parser.add_argument("--new-url", metavar="URL", help="New Gitea URL, for example https://example.com",)
        self.parser.add_argument("--new-user", metavar="USER", help="Gitea username")
        self.parser.add_argument("--new-token", metavar="TOKEN", help="Gitea access token; set to '-' to invoke a secure interactive prompt")
        self.parser.add_argument("--new-ssh-key", metavar="PATH", help="Path to a private SSH key").completer = complete_ssh_key_path
        self.parser.add_argument("--set-as-default", action="store_true", help="Set the login entry as default")

    def run(self, args):
        print(f"Updating a Gitea credentials entry with name '{args.name}' ...", file=sys.stderr)
        print(f" * Config path: {self.gitea_conf.path}", file=sys.stderr)
        print("", file=sys.stderr)

        # TODO: try to authenticate to verify that the updated entry works

        original_login = self.gitea_conf.get_login(args.name)
        print("Original entry:")
        print(original_login.to_human_readable_string())

        if args.new_token == "-":
            print(file=sys.stderr)
            while not args.new_token or args.new_token == "-":
                args.new_token = getpass.getpass(prompt=f"Enter a new Gitea token for user '{args.new_user or original_login.user}': ")

        if not re.match(r"^[0-9a-f]{40}$", args.new_token):
            self.parser.error("Invalid token format, 40 hexadecimal characters expected")

        updated_login = self.gitea_conf.update_login(
            args.name,
            new_name=args.new_name,
            new_url=args.new_url,
            new_user=args.new_user,
            new_token=args.new_token,
            new_ssh_key=args.new_ssh_key,
            set_as_default=args.set_as_default,
        )
        print("")
        print("Updated entry:")
        print(updated_login.to_human_readable_string())
