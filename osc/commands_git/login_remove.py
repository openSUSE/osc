import osc.commandline


class LoginRemoveCommand(osc.commandline.OscCommand):
    """
    Remove a Gitea credentials entry
    """

    name = "remove"
    parent = "LoginCommand"

    def init_arguments(self):
        self.parser.add_argument("name")

    def run(self, args):
        from osc import gitea_api
        from osc.output import print_msg

        print_msg(f"Removing a Gitea credentials entry with name '{args.name}' ...", print_to="stderr")

        conf = gitea_api.Config()
        print_msg(f" * Config path: {conf.path}", print_to="stderr")

        conf.remove_login(args.name)

        print_msg(f" * Entry removed", print_to="stderr")
