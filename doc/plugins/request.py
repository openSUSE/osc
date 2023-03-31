import osc.commandline


class RequestCommand(osc.commandline.OscCommand):
    """
    Manage requests
    """

    name = "request"
    aliases = ["rq"]

    # arguments specified here will get inherited to all subcommands automatically
    def init_arguments(self):
        self.add_argument(
            "-m",
            "--message",
            metavar="TEXT",
        )
