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

        ssh_key_obj_list = gitea_api.SSHKey.list(self.gitea_conn)
        for ssh_key_obj in ssh_key_obj_list:
            print(ssh_key_obj.to_human_readable_string())
            print()
