import osc.commandline_git


class SSHKeyListCommand(osc.commandline_git.GitObsCommand):
    """
    """

    name = "list"
    parent = "SSHKeyCommand"

    def init_arguments(self):
        pass

    def run(self, args):
        from osc import gitea_api

        self.print_gitea_settings()

        for i in gitea_api.SSHKey.list(self.gitea_conn).json():
            print(gitea_api.SSHKey.to_human_readable_string(i))
            print()
