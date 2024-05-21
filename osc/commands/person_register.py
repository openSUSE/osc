import osc.commandline


class PersonRegisterCommand(osc.commandline.OscCommand):
    """
    Register a new person (user)
    """

    name = "register"
    parent = "PersonCommand"

    def init_arguments(self):
        self.add_argument(
            "--login",
            required=True,
            help="Login.",
        )
        self.add_argument(
            "--realname",
            required=True,
            help="Real name of the person.",
        )
        self.add_argument(
            "--email",
            required=True,
            help="Email address.",
        )
        self.add_argument(
            "--password",
            help="Password. An interactive prompt is shown if password is not specified.",
        )
        self.add_argument(
            "--note",
            help="Any notes about the person.",
        )
        self.add_argument(
            "--state",
            help="State of the account. Defaults to 'unconfirmed'.",
        )

    def run(self, args):
        from osc import obs_api
        from osc.util.helper import raw_input

        if args.password:
            password = args.password
        else:
            password = raw_input(f"Enter password for {args.login}@{args.apiurl}: ")

        obs_api.Person.cmd_register(
            args.apiurl,
            login=args.login,
            realname=args.realname,
            email=args.email,
            password=password,
            note=args.note,
            state=args.state,
        )
