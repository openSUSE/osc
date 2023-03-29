import osc.commandline


class SimpleCommand(osc.commandline.OscCommand):
    """
    A command that does nothing

    More description
    of what the command does.
    """

    # command name
    name = "simple"

    # options and positional arguments
    def init_arguments(self):
        self.add_argument(
            "--bool-option",
            action="store_true",
            help="...",
        )
        self.add_argument(
            "arguments",
            metavar="arg",
            nargs="+",
            help="...",
        )

    # code of the command
    def run(self, args):
        print(f"Bool option is {args.bool_option}")
        print(f"Positional arguments are {args.arguments}")
