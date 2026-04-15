import osc.commandline_git


class FileMaintainershipMigrateCommand(osc.commandline_git.GitObsCommand):
    """
    Read _maintainership.json and convert it from legacy format to the current format
    """

    name = "migrate"
    parent = "FileMaintainershipCommand"

    def init_arguments(self):
        self.add_argument(
            "-i",
            "--in-place",
            action="store_true",
            default=False,
            help="Write the result back to the original file instead of printing to stdout",
        )
        self.add_argument(
            "path",
            nargs="?",
            default="_maintainership.json",
            help="Path to the _maintainership.json file (default: %(default)s)",
        )

    def run(self, args):
        from osc.gitea_api import maintainership

        with open(args.path, "r", encoding="utf-8") as f:
            data = f.read()

        obj = maintainership.Maintainership.from_string(data)

        if args.in_place:
            with open(args.path, "w", encoding="utf-8") as f:
                f.write(obj.to_string())
        else:
            print(obj.to_string())
