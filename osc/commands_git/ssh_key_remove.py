import sys

import osc.commandline_git


class SSHKeyRemoveCommand(osc.commandline_git.GitObsCommand):
    """
    """

    name = "remove"
    parent = "SSHKeyCommand"

    def init_arguments(self):
        self.parser.add_argument(
            "id",
            type=int,
            help="Id of the SSH public key",
        )

    def run(self, args):
        from osc import gitea_api

        self.print_gitea_settings()

        print(f"Removing ssh key with id='{args.id}' ...", file=sys.stderr)
        ssh_key_obj = gitea_api.SSHKey.get(self.gitea_conn, args.id)
        gitea_api.SSHKey.delete(self.gitea_conn, args.id)

        print("Removed entry:")
        print(ssh_key_obj.to_human_readable_string())
