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
        self.parser.add_argument("--new-git-uses-http", help="Git uses http(s) instead of SSH", choices=["0", "1", "yes", "no"], default=None)
        self.parser.add_argument("--set-as-default", action="store_true", help="Set the login entry as default")

    def run(self, args):
        print(f"Updating a Gitea credentials entry with name '{args.name}' ...", file=sys.stderr)
        print(f" * Config path: {self.gitea_conf.path}", file=sys.stderr)
        print("", file=sys.stderr)

        # TODO: try to authenticate to verify that the updated entry works

        original_login_obj = self.gitea_conf.get_login(args.name)
        print("Original entry:")
        print(original_login_obj.to_human_readable_string())

        if args.new_token == "-":
            print(file=sys.stderr)
            while not args.new_token or args.new_token == "-":
                args.new_token = getpass.getpass(prompt=f"Enter a new Gitea token for user '{args.new_user or original_login_obj.user}': ")

        if args.new_token and not re.match(r"^[0-9a-f]{40}$", args.new_token):
            self.parser.error("Invalid token format, 40 hexadecimal characters expected")

        if args.new_git_uses_http in ("0", "no"):
            new_git_uses_http = False
        elif args.new_git_uses_http in ("1", "yes"):
            new_git_uses_http = True
        else:
            new_git_uses_http = None

        updated_login_obj = self.gitea_conf.update_login(
            args.name,
            new_name=args.new_name,
            new_url=args.new_url,
            new_user=args.new_user,
            new_token=args.new_token,
            new_ssh_key=args.new_ssh_key,
            new_git_uses_http=new_git_uses_http,
            set_as_default=args.set_as_default,
        )
        print("")
        print("Updated entry:")
        print(updated_login_obj.to_human_readable_string())
