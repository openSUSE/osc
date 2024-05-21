import osc.commandline


class PersonSearchCommand(osc.commandline.OscCommand):
    """
    Search a person (user)
    """

    name = "search"
    parent = "PersonCommand"

    def init_arguments(self):
        self.add_argument(
            "--login",
            help="Search by a login.",
        )
        self.add_argument(
            "--login-contains",
            metavar="SUBSTR",
            help="Search by a substring in a login.",
        )
        self.add_argument(
            "--realname-contains",
            metavar="SUBSTR",
            help="Search by a substring in a realname.",
        )
        self.add_argument(
            "--email",
            help="Search by an email address.",
        )
        self.add_argument(
            "--email-contains",
            metavar="SUBSTR",
            help="Search by a substring in an email address.",
        )

    def run(self, args):
        from .. import obs_api

        persons = obs_api.Person.search(
            args.apiurl,
            login=args.login,
            login__contains=args.login_contains,
            realname__contains=args.realname_contains,
            email=args.email,
            email__contains=args.email_contains,
        )

        for person in persons:
            print(person.to_human_readable_string())
            print()
