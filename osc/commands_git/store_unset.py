import sys

import osc.commandline_git


class StoreUnsetCommand(osc.commandline_git.GitObsCommand):
    """
    Unset metadata in store
    """

    name = "unset"
    parent = "StoreCommand"

    def init_arguments(self):
        self.add_argument("--project", action="store_true")
        self.add_argument("--package")
        self.add_argument("--apiurl")
        # self.add_argument("--default", action="store_true")

    def run(self, args):
        from osc import gitea_api
        from osc.git_scm import GitStore

        store = GitStore(".")

        branch = args.branch
        if not branch:
            git = gitea_api.Git(store.abspath)
            branch = git.current_branch

        # TODO: move to store
        all_names = ["project", "package", "apiurl"]

        for name in all_names:
            value = getattr(args, name)
            if not value:
                continue
            if args.defaults:
                store._unset_option("defaults", branch=name)
            else:
                store._set_option(name, branch=branch)
