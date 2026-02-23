import getpass
import os
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
        self.parser.add_argument("--new-ssh-agent", help="Use ssh-agent for authentication", choices=["0", "1", "yes", "no"], default=None)
        self.parser.add_argument("--new-ssh-key-agent-pub", help="Public SSH key signature for ssh-agent authentication")
        self.parser.add_argument("--new-git-uses-http", help="Git uses http(s) instead of SSH", choices=["0", "1", "yes", "no"], default=None)
        self.parser.add_argument("--new-quiet", help="Mute unnecessary output when using this login entry", choices=["0", "1", "yes", "no"], default=None)
        self.parser.add_argument("--set-as-default", action="store_true", help="Set the login entry as default")

    def _get_ssh_settings(self, args, original_login_obj):
        # Parse new_ssh_agent
        new_ssh_agent = None
        if args.new_ssh_agent in ("0", "no"):
            new_ssh_agent = False
        elif args.new_ssh_agent in ("1", "yes"):
            new_ssh_agent = True

        if args.new_ssh_key and new_ssh_agent:
            self.parser.error("Cannot specify both --new-ssh-key and --new-ssh-agent")

        # Determine final state
        final_ssh_key = original_login_obj.ssh_key
        final_ssh_agent = original_login_obj.ssh_agent
        final_ssh_key_agent_pub = original_login_obj.ssh_key_agent_pub

        if args.new_ssh_key:
            final_ssh_key = args.new_ssh_key
            # If setting a key, disable agent
            final_ssh_agent = False
        
        if new_ssh_agent is not None:
            final_ssh_agent = new_ssh_agent
            # If enabling agent, clear key
            if new_ssh_agent:
                final_ssh_key = None
        
        if args.new_ssh_key_agent_pub:
            final_ssh_key_agent_pub = args.new_ssh_key_agent_pub

        # Validate SSH configuration changes
        if args.new_ssh_key or args.new_ssh_agent:
            # If SSH is being enabled or modified, require the pub key
            if (final_ssh_key or final_ssh_agent) and not args.new_ssh_key_agent_pub:
                self.parser.error("For SSH authentication, either --new-ssh-key or --new-ssh-agent must be specified together with --new-ssh-key-agent-pub")

        if original_login_obj.ssh_agent and final_ssh_agent is False and not final_ssh_key:
             self.parser.error("Cannot switch from ssh-agent authentication to SSH key authentication without specifying a new SSH key")

        if original_login_obj.ssh_key and final_ssh_agent is True:
             print("Warning: switching from SSH key authentication to ssh-agent authentication, the specified SSH key will be deleted", file=sys.stderr)

        if original_login_obj.ssh_agent and args.new_ssh_key:
             print("Warning: switching from ssh-agent authentication to SSH key authentication, the ssh-agent setting will be disabled", file=sys.stderr)
        
        if (final_ssh_key or final_ssh_agent) and args.new_token:
            self.parser.error("Token authentication cannot be used together with SSH authentication")
            
        if args.new_ssh_key:
            from cryptography.hazmat.primitives import serialization
            
            if not os.path.isfile(args.new_ssh_key):
                self.parser.error(f"SSH key file '{args.new_ssh_key}' does not exist")
            if not os.access(args.new_ssh_key, os.R_OK):
                self.parser.error(f"SSH key file '{args.new_ssh_key}' is not readable")
            with open(args.new_ssh_key, "rb") as key_file:
                try:
                    serialization.load_ssh_private_key(key_file.read(), password=None)
                except Exception:
                    self.parser.error(f"SSH key file '{args.new_ssh_key}' is not a valid SSH private key")

        return final_ssh_key, final_ssh_agent, final_ssh_key_agent_pub

    def run(self, args):
        print(f"Updating a Gitea credentials entry with name '{args.name}' ...", file=sys.stderr)
        print(f" * Config path: {self.gitea_conf.path}", file=sys.stderr)
        print("", file=sys.stderr)

        # TODO: try to authenticate to verify that the updated entry works

        original_login_obj = self.gitea_conf.get_login(args.name)
        
        final_ssh_key, final_ssh_agent, final_ssh_key_agent_pub = self._get_ssh_settings(args, original_login_obj)

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
           
        if args.new_quiet in ("0", "no"):
            new_quiet = False
        elif args.new_quiet in ("1", "yes"):
            new_quiet = True
        else:
            new_quiet = None

        updated_login_obj = self.gitea_conf.update_login(
            args.name,
            new_name=args.new_name,
            new_url=args.new_url,
            new_user=args.new_user,
            new_token=args.new_token,
            new_ssh_key=final_ssh_key,
            new_ssh_agent=final_ssh_agent,
            new_ssh_key_agent_pub=final_ssh_key_agent_pub,
            new_git_uses_http=new_git_uses_http,
            new_quiet=new_quiet,
            set_as_default=args.set_as_default,
        )
        
        print("")
        print("Original entry:")
        print(original_login_obj.to_human_readable_string())
        print("")
        print("Updated entry:")
        print(updated_login_obj.to_human_readable_string())
