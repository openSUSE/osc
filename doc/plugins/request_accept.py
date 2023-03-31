import osc.commandline


class RequestAcceptCommand(osc.commandline.OscCommand):
    """
    Accept request
    """

    name = "accept"
    parent = "RequestCommand"

    def init_arguments(self):
        self.add_argument(
            "id",
            type=int,
        )

    def run(self, args):
        print(f"Accepting request '{args.id}'")
