import osc.commandline


class LoginListCommand(osc.commandline.OscCommand):
    """
    List Gitea credentials entries
    """

    name = "list"
    parent = "LoginCommand"

    def init_arguments(self):
        self.parser.add_argument("--show-tokens", action="store_true", help="Show tokens in the output")

    def run(self, args):
        from osc import gitea_api

        conf = gitea_api.Config()
        for login in conf.list_logins():
            print(login.to_human_readable_string(show_token=args.show_tokens))
            print()
