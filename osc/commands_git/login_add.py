import getpass
import os
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
        self.parser.add_argument("--ssh-agent", action="store_true", help="Use ssh-agent for authentication")
        self.parser.add_argument("--ssh-key-agent-pub", help="Public SSH key signature for ssh-agent authentication")
        self.parser.add_argument("--git-uses-http", action="store_true", help="Git uses http(s) instead of SSH", default=None)
        self.parser.add_argument("--quiet", action="store_true", help="Mute unnecessary output when using this login entry")
        self.parser.add_argument("--set-as-default", help="Set the new login entry as default", action="store_true", default=None)

    def run(self, args):
        from osc import gitea_api

        print(f"Adding a Gitea credentials entry with name '{args.name}' ...", file=sys.stderr)
        print(f" * Config path: {self.gitea_conf.path}", file=sys.stderr)
        print("", file=sys.stderr)

        # TODO: try to authenticate to verify that the new entry works

        if not (args.ssh_key or args.ssh_agent) or not args.ssh_key_agent_pub:
            self.parser.error("For SSH authentication, either --ssh-key or --ssh-agent must be specified together with --ssh-key-agent-pub")
        elif (args.ssh_key and args.ssh_agent) or (args.ssh_key and args.token) or (args.ssh_agent and args.token):
            self.parser.error("SSH authentication cannot be used together with token authentication, and --ssh-key and --ssh-agent cannot be used together")
            
        ssh_login = (args.ssh_key or args.ssh_agent) and args.ssh_key_agent_pub 
        
        if args.ssh_key:
            from cryptography.hazmat.primitives import serialization
            
            if not os.path.isfile(args.ssh_key):
                self.parser.error(f"SSH key file '{args.ssh_key}' does not exist")
            if not os.access(args.ssh_key, os.R_OK):
                self.parser.error(f"SSH key file '{args.ssh_key}' is not readable")
            with open(args.ssh_key, "rb") as key_file:
                try:
                    serialization.load_ssh_private_key(key_file.read(), password=None)
                except Exception:
                    self.parser.error(f"SSH key file '{args.ssh_key}' is not a valid SSH private key")
                    
        if not ssh_login:
            while not args.token or args.token == "-":
                args.token = getpass.getpass(prompt=f"Enter Gitea token for user '{args.user}': ")

            if args.token and not re.match(r"^[0-9a-f]{40}$", args.token):
                self.parser.error("Invalid token format, 40 hexadecimal characters expected")

        login_obj = gitea_api.Login(
            name=args.name,
            url=args.url,
            user=args.user,
            token=args.token,
            ssh_key=args.ssh_key,
            ssh_agent=args.ssh_agent,
            ssh_key_agent_pub=args.ssh_key_agent_pub,
            git_uses_http=args.git_uses_http,
            default=args.set_as_default,
        )
        self.gitea_conf.add_login(login_obj)

        print("Added entry:")
        print(login_obj.to_human_readable_string())
