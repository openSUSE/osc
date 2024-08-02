import osc.commandline


class LoginAddCommand(osc.commandline.OscCommand):
    """
    Add a Gitea credentials entry
    """

    name = "add"
    parent = "LoginCommand"

    def init_arguments(self):
        self.parser.add_argument("name")
        self.parser.add_argument("--url", required=True)
        self.parser.add_argument("--user", required=True)
        self.parser.add_argument("--token", required=True)
        self.parser.add_argument("--set-as-default", action="store_true")

    def run(self, args):
        from osc import gitea_api

        print_msg(f"Adding a Gitea credentials entry with name '{args.name}' ...", print_to="stderr")

        conf = gitea_api.GiteaConfig()
        print_msg(f" * Config path: {conf.path}", print_to="stderr")

        login = gitea_api.Login(name=args.name, url=args.url, user=args.user, token=args.token)
        conf.add_login(login)

        print_msg(" * Entry added", print_to="stderr")
