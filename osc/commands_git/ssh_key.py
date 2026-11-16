import osc.commandline_git


class SSHKeyCommand(osc.commandline_git.GitObsCommand):
    """
    Manage public SSH keys

    Add, list, or remove public SSH keys associated with your Gitea account.

    Examples:
        git-obs ssh-key add --key-path ~/.ssh/id_ed25519.pub
        git-obs ssh-key list
        git-obs ssh-key remove 123
    """

    name = "ssh-key"

    def init_arguments(self):
        pass

    def run(self, args):
        self.parser.print_help()
