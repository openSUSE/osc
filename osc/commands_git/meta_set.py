import osc.commandline_git


class MetaSetCommand(osc.commandline_git.GitObsCommand):
    """
    Set metadata in store
    """

    name = "set"
    parent = "MetaCommand"

    def init_arguments(self):
        self.add_argument(
            "--apiurl",
            help="Set 'apiurl'",
        )
        self.add_argument(
            "--project",
            help="Set 'project'",
        )
        self.add_argument(
            "--package",
            help="Set 'package'",
        )
        self.add_argument(
            "--branch",
            help="Manage values for the specified branch (default: current branch)",
        )

    def run(self, args):
        from osc.git_scm import LocalGitStore

        store = LocalGitStore(".", check=False)
        branch = args.branch or store._git.current_branch

        # just retrieve keys from an authoritative source
        keys = list(store._read_meta(branch=branch).dict().keys())
        keys.remove("header")

        for key in keys:
            value = getattr(args, key, None)
            if value is None:
                continue
            # translate an empty string to None to unset the value
            setattr(store, key, value or None)
