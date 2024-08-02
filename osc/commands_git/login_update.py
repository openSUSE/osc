import osc.commandline


class LoginUpdateCommand(osc.commandline.OscCommand):
    """
    Update a Gitea credentials entry
    """

    name = "update"
    parent = "LoginCommand"

    def init_arguments(self):
        self.parser.add_argument("name")
        self.parser.add_argument("--new-name")
        self.parser.add_argument("--new-url")
        self.parser.add_argument("--new-user")
        self.parser.add_argument("--new-token")
        self.parser.add_argument("--set-as-default", action="store_true")

    def run(self, args):
        from osc import gitea_api

        print_msg(f"Updating a Gitea credentials entry with name '{args.name}' ...", print_to="stderr")

        conf = gitea_api.GiteaConfig()
        print_msg(f" * Config path: {conf.path}", print_to="stderr")

        conf.update_login(
            args.name,
            new_name=args.new_name,
            new_url=args.new_url,
            new_user=args.new_user,
            new_token=args.new_token,
            set_as_default=args.set_as_default,
        )

        print_msg(f" * Entry updated", print_to="stderr")
