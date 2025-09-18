import osc.commandline_git


class MetaListCommand(osc.commandline_git.GitObsCommand):
    """
    List metadata in store
    """

    name = "list"
    parent = "MetaCommand"

    def init_arguments(self):
        self.parser.add_argument(
            "--branch",
            help="Manage values for the specified branch (default: current branch)",
        )

    def run(self, args):
        from osc.git_scm import GitStore
        from osc.output import KeyValueTable

        store = GitStore(".")
        branch = args.branch or store._git.current_branch
        meta = store._read_meta(branch=branch).dict()
        meta.pop("header", None)

        table = KeyValueTable(min_key_length=10)
        table.add("Branch", branch, color="bold")
        for key, value in meta.items():
            table.add(key, value)
        print(str(table))
