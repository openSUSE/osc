import osc.commandline_git


class StagingRemoveCommand(osc.commandline_git.GitObsCommand):
    """
    Remove package pull requests from a project pull request
    """
    name = "remove"
    parent = "StagingCommand"

    def init_arguments(self):
        self.add_argument_owner_repo_pull(
            dest="target",
            help="Project pull request to modify",
        ).completer = osc.commandline_git.complete_pr

        self.add_argument_owner_repo_pull(
            dest="pr_list",
            nargs="+",
            help="List of package pull requests to be removed from the project pull request",
        ).completer = osc.commandline_git.complete_pr

        self.add_argument(
            "--close-removed",
            action="store_true",
            help="Close pull requests after removing their references",
        )

        self.add_argument(
            "--keep-temp-dir",
            action="store_true",
            help="Don't delete the temporary directory with git checkouts",
        )

    def run(self, args):
        from osc import gitea_api
        from osc.gitea_api.common import TemporaryDirectory

        target_owner, target_repo, target_number = args.target

        if args.target in args.pr_list:
            self.parser.error("Target pull request was found among pull requests for removal")

        self.print_gitea_settings()

        with TemporaryDirectory(prefix="git-obs-staging_", dir=".", delete=not args.keep_temp_dir) as temp_dir:
            # get pull request data from gitea
            target = gitea_api.StagingPullRequestWrapper(self.gitea_conn, target_owner, target_repo, target_number, topdir=temp_dir)

            # check if the specified references match actual references in the project pull request
            refs = target.pr_obj.parse_pr_references()
            refs = [(owner.lower(), repo.lower(), number) for owner, repo, number in refs]
            missing_refs = []
            for owner, repo, number in args.pr_list:
                if (owner, repo, number) not in refs:
                    missing_refs.append(f"{owner}/{repo}#{number}")
            if missing_refs:
                msg = f"The following pull requests are not referenced in the project pull request: {', '.join(missing_refs)}"
                raise gitea_api.GitObsRuntimeError(msg)

            # get pull request data from gitea
            pr_map = {}
            for owner, repo, number in args.pr_list:
                pr = gitea_api.StagingPullRequestWrapper(self.gitea_conn, owner, repo, number, topdir=temp_dir)
                pr_map[(owner.lower(), repo.lower(), number)] = pr

            # clone the git repos, cache submodule data
            target.clone()
            target.clone_base()

            # locally remove package pull requests from the target project pull request (don't change anything on server yet)
            for owner, repo, number in args.pr_list:
                pr = pr_map[(owner.lower(), repo.lower(), number)]
                target.remove(pr)

            # push to git repo associated with the target pull request
            target.git.push(remote="fork", branch=f"pull/{target.pr_obj.number}:{target.pr_obj.head_branch}")
            # update target pull request
            target.pr_obj.set(self.gitea_conn, target_owner, target_repo, target_number, description=target.pr_obj.body)

            if args.close_removed:
                for owner, repo, number in args.pr_list:
                    pr = pr_map[(owner.lower(), repo.lower(), number)]
                    # close the removed package pull request
                    try:
                        gitea_api.PullRequest.close(self.gitea_conn, owner, repo, number)
                    except Exception as e:
                        print(f"Unable to close pull request {owner}/{repo}#{number}: {e}")

        print()
        print(target.pr_obj.to_human_readable_string())

        print()
        print("Package pull requests have been successfully removed from the staging project pull request")

        if args.keep_temp_dir:
            print()
            print(f"Temporary files are available here: {temp_dir}")
