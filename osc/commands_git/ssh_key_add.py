import os

import osc.commandline_git


class SSHKeyAddCommand(osc.commandline_git.GitObsCommand):
    """
    """

    name = "add"
    parent = "SSHKeyCommand"

    def init_arguments(self):
        from osc.commandline_git import complete_ssh_key_path

        group = self.parser.add_mutually_exclusive_group(required=True)
        group.add_argument(
            "--key",
            help="SSH public key",
        )
        group.add_argument(
            "--key-path",
            metavar="PATH",
            help="Path to the SSH public key",
        ).completer = complete_ssh_key_path

    def run(self, args):
        from osc import gitea_api

        self.print_gitea_settings()

        if args.key:
            key = args.key
        else:
            with open(os.path.expanduser(args.key_path)) as f:
                key = f.read().strip()

        response = gitea_api.SSHKey.create(self.gitea_conn, key)
        print("Added entry:")
        print(gitea_api.SSHKey.to_human_readable_string(response.json()))
