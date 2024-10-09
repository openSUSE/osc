import osc.commandline_git


class LoginListCommand(osc.commandline_git.GitObsCommand):
    """
    List Gitea credentials entries
    """

    name = "list"
    parent = "LoginCommand"

    def init_arguments(self):
        self.parser.add_argument("--show-tokens", action="store_true", help="Show tokens in the output")

    def run(self, args):
        for login in self.gitea_conf.list_logins():
            print(login.to_human_readable_string(show_token=args.show_tokens))
            print()
