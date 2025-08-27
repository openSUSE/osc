import sys

import osc.commandline_git


class StoreSetCommand(osc.commandline_git.GitObsCommand):
    """
    Set metadata in store
    """

    name = "set"
    parent = "StoreCommand"

    def init_arguments(self):
        self.add_argument(
            "--project",
            help="Set 'project'",
        )
        self.add_argument(
            "--package",
            help="Set 'package'",
        )
        self.add_argument(
            "--apiurl",
            help="Set 'apiurl'",
        )
        self.add_argument(
            "--branch",
            help="Manage values for the specified branch (default: current branch)",
        )
        self.add_argument(
            "--defaults",
            help="Manage default values",
        )
        # TODO: define priorities: parent dir with project, _ObsPrj on server, value in git, default value in git?

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
                store._set_option("defaults", name, branch=name)
            else:
                store._set_option(name, value, branch=branch)
