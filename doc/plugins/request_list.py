import osc.commandline


class RequestListCommand(osc.commandline.OscCommand):
    """
    List requests
    """

    name = "list"
    parent = "RequestCommand"

    def run(self, args):
        print("Listing requests")
