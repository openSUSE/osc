import sys

import osc.commandline_git


class StoreShowCommand(osc.commandline_git.GitObsCommand):
    """
    List metadata in store
    """

    name = "list"
    parent = "StoreCommand"

    def init_arguments(self):
        self.add_argument(
            "--all-branches",
            action="store_true",
            help="Show metadata for all branches",
        )
        self.add_argument(
            "--defaults",
            action="store_true",
            help="Show default metadata",
        )

    def run(self, args):
        from osc import gitea_api
        from osc.git_scm import GitStore
        from osc.output import KeyValueTable

        store = GitStore(".")
        # all branches vs current
        all_options = store._all_options()

        if args.all_branches:
            branch = None
        elif args.defaults:
            branch = "*"
        else:
            git = gitea_api.Git(store.abspath)
            branch = git.current_branch

        # XXX: doesn't show anything when there are no options for the branch

        # defines order
        all_names = ["project", "package", "apiurl"]
        # TODO: last-buildroot, build-repositories, scmurl

        table = KeyValueTable(min_key_length=20)

        for opt_branch, values in sorted(all_options.items()):
            if branch and branch != opt_branch:
                continue
            table.add("Branch", opt_branch, color="bold")
            for name in all_names:
                value = values.get(name, None)
                use_default = False
                if value is None:
                    value = all_options.get("*", {}).get(name, None)
                    if value is not None:
                        use_default = True
                default_str = f" (from defaults)" if use_default else ""
                value = value if value else ""
                table.add(f"  {name}", f"{value}{default_str}")
            table.newline()

        print(str(table))
