import os

import osc.commandline_git


class StagingGroupCommand(osc.commandline_git.GitObsCommand):
    """
    Group multiple staging project pull requests into a target staging project pull request
    """

    name = "group"
    parent = "StagingCommand"

    def init_arguments(self):
        self.add_argument_owner_repo_pull(
            dest="--target",
            help="Target project pull request to modify. If not specified, a new pull request will be created.",
        ).completer = osc.commandline_git.complete_pr

        self.add_argument(
            "--title",
            help="Title of the new pull request. Defaults to 'Update packages: <pkg> [pkg] ...'. Conflicts with --target.",
        )

        self.add_argument(
            "--fork-owner",
            help="Owner of the fork used to create a new pull request. Defaults to the currently logged user. Conflicts with --target.",
        )

        self.add_argument(
            "--fork-branch",
            help="Branch in the fork used to create a new pull request. Defaults to 'for/<target_branch>/group-YYYY-MM-DD_HH-MM-SS'. Conflicts with --target."
        )

        self.add_argument(
            "--force",
            action="store_true",
            help="Allow force-push to the branch associated with the pull request",
        )

        self.add_argument_owner_repo_pull(
            dest="pr_list",
            nargs="+",
            help="List of project pull request to be merged into the target project pull request",
        ).completer = osc.commandline_git.complete_pr

        self.add_argument(
            "--cache-dir",
            help="Path to a git cache.",
        )

        self.add_argument(
            "--keep-temp-dir",
            action="store_true",
            help="Don't delete the temporary directory with git checkouts",
        )

    def run(self, args):
        import datetime
        from osc import gitea_api
        from osc.gitea_api.common import TemporaryDirectory

        if args.target in args.pr_list:
            self.parser.error("Target pull request was found among pull requests for merging")

        if args.title and args.target:
            self.parser.error("--title conflicts with --target")

        if args.fork_owner and args.target:
            self.parser.error("--fork-owner conflicts with --target")

        if args.fork_branch and args.target:
            self.parser.error("--fork-branch conflicts with --target")

        cache_dir = os.path.abspath(args.cache_dir) if args.cache_dir else None

        self.print_gitea_settings()

        with TemporaryDirectory(prefix="git-obs-staging_", dir=".", delete=not args.keep_temp_dir) as temp_dir:
            user_obj = gitea_api.User.get(self.gitea_conn)

            if args.target:
                target_owner, target_repo, target_number = args.target
                pr_obj = gitea_api.PullRequest.get(self.gitea_conn, target_owner, target_repo, target_number)
                # # to update a pull request, we either need to be its creator or an admin in the repo
                # if not (pr_obj._data["base"]["repo"]["permissions"]["admin"] or pr_obj.user == user_obj.login):
                #     raise gitea_api.GitObsRuntimeError(f"You don't have sufficient permissions to modify pull request {target_owner}/{target_repo}#{target_number}")

            # get pull request data from gitea
            pr_map = {}
            for owner, repo, number in args.pr_list:
                pr = gitea_api.StagingPullRequestWrapper(self.gitea_conn, owner, repo, number, topdir=temp_dir, cache_directory=cache_dir)
                pr_map[(owner, repo, number)] = pr

            # run checks
            target_owner = None
            target_repo = None
            target_branch = None
            for owner, repo, number in args.pr_list:
                pr = pr_map[(owner, repo, number)]

                if pr.pr_obj.state != "open":
                    # we don't care about the state of the package pull requests - they can be merged already
                    raise gitea_api.GitObsRuntimeError(f"Pull request {owner}/{repo}#{number} is not open (the state is '{pr.pr_obj.state}')")

                # if not (pr.pr_obj._data["base"]["repo"]["permissions"]["admin"] or pr.pr_obj.user == user_obj.login):
                #     raise gitea_api.GitObsRuntimeError(f"You don't have sufficient permissions to modify pull request {owner}/{repo}#{number}")

                if gitea_api.StagingPullRequestWrapper.BACKLOG_LABEL not in pr.pr_obj.labels:
                    raise gitea_api.GitObsRuntimeError(f"Pull request {owner}/{repo}#{number} is missing the '{gitea_api.StagingPullRequestWrapper.BACKLOG_LABEL}' label.")

                # test that all PRs go to the same branch
                if target_owner is None:
                    target_owner = pr.pr_obj.base_owner
                else:
                    assert target_owner == pr.pr_obj.base_owner, f"{target_owner} != {pr.pr_obj.base_owner}"

                if target_repo is None:
                    target_repo = pr.pr_obj.base_repo
                else:
                    assert target_repo == pr.pr_obj.base_repo, f"{target_repo} != {pr.pr_obj.base_repo}"

                if target_branch is None:
                    target_branch = pr.pr_obj.base_branch
                else:
                    assert target_branch == pr.pr_obj.base_branch, f"{target_branch} != {pr.pr_obj.base_branch}"

            # clone the git repos, cache submodule data
            for owner, repo, number in args.pr_list:
                pr = pr_map[(owner, repo, number)]
                pr.clone()

            # run checks #2
            for owner, repo, number in args.pr_list:
                pr = pr_map[(owner, repo, number)]
                if not pr.package_pr_map:
                    # TODO: we don't know if the submodules are packages or not, we should cross-reference those with _manifest
                    raise gitea_api.GitObsRuntimeError(f"Pull request {owner}/{repo}#{number} doesn't have any submodules changed.")

            if not args.target:
                fork_owner = args.fork_owner if args.fork_owner else user_obj.login
                # dates in ISO 8601 format cannot be part of a valid branch name, we need a custom format
                fork_branch = args.fork_branch if args.fork_branch else f"for/{target_branch}/group-{datetime.datetime.now().strftime('%Y-%m-%d_%H-%M-%S')}"

                fork_repo = None
                forks = gitea_api.Fork.list(self.gitea_conn, target_owner, target_repo)
                for repo in forks:
                    if repo.owner.lower() == fork_owner.lower():
                        fork_repo = repo.repo
                if not fork_repo:
                    raise gitea_api.GitObsRuntimeError(f"Cannot find a matching fork of {target_owner}/{target_repo}")

                clone_dir = gitea_api.Repo.clone(
                    self.gitea_conn,
                    fork_owner,
                    fork_repo,
                    directory=os.path.join(temp_dir, f"{fork_owner}_{fork_repo}"),
                    add_remotes=True,
                    cache_directory=cache_dir,
                    ssh_private_key_path=self.gitea_conn.login.ssh_key,
                )
                clone_git = gitea_api.Git(clone_dir)
                clone_git.fetch()
                clone_git._run_git(["fetch", "origin", f"{target_branch}:{fork_branch}", "--force", "--update-head-ok"])
                clone_git.switch(fork_branch)
                clone_git.push(remote="origin", branch=fork_branch, set_upstream=True, force=args.force)

                # target project pull request wasn't specified, let's create it
                desc = ""
                updated_packages = []
                for owner, repo, number in args.pr_list:
                    pr = pr_map[(owner, repo, number)]
                    for (pkg_owner, pkg_repo, pkg_number), pr_obj in pr.package_pr_map.items():
                        desc += f"PR: {pkg_owner}/{pkg_repo}!{pkg_number}\n"
                        updated_packages.append(os.path.basename(pr.submodules_by_owner_repo[pkg_owner, pkg_repo]["path"]))

                # TODO: it would be nice to mention the target OBS project
                # we keep only the first ``max_packages``, because the title might get too long quite easily
                max_packages = 5
                updated_packages_str = ", ".join(sorted(updated_packages)[:max_packages])
                if len(updated_packages) > max_packages:
                    updated_packages_str += f" + {len(updated_packages) - max_packages} more"
                title = args.title if args.title else f"Update packages: {updated_packages_str}"

                pr_obj = gitea_api.PullRequest.create(
                    self.gitea_conn,
                    target_owner=target_owner,
                    target_repo=target_repo,
                    target_branch=target_branch,
                    source_owner=fork_owner,
                    # source_repo is not required because the information lives in Gitea database
                    source_branch=fork_branch,
                    title=title,
                    description=desc,
                    labels=[gitea_api.StagingPullRequestWrapper.INPROGRESS_LABEL],
                )
                target_number = pr_obj.number

            # clone the git repos, cache submodule data
            target = gitea_api.StagingPullRequestWrapper(self.gitea_conn, target_owner, target_repo, target_number, topdir=temp_dir, cache_directory=cache_dir)
            target.clone()
            for owner, repo, number in args.pr_list:
                pr = pr_map[(owner, repo, number)]
                pr.clone()

            # locally merge package pull requests to the target project pull request (don't change anything on server yet)
            for owner, repo, number in args.pr_list:
                pr = pr_map[(owner, repo, number)]
                target.merge(pr)

            # push to git repo associated with the target pull request
            target.git.push(remote="fork", branch=f"pull/{target.pr_obj.number}:{target.pr_obj.head_branch}")
            # update target pull request
            if args.target:
                # if args.target is not set, we've created a new pull request with all 'PR:' references included
                # if args.target is set (which is the case here), we need to update the description with the newly added 'PR:' references
                target.pr_obj.set(self.gitea_conn, target_owner, target_repo, target_number, description=target.pr_obj.body)

            for owner, repo, number in args.pr_list:
                pr = pr_map[(owner, repo, number)]
                try:
                    # apply the removed 'PR:' reference to the package pull request
                    pr.pr_obj.set(self.gitea_conn, owner, repo, number, description=pr.pr_obj.body)
                except Exception as e:
                    print(f"Unable to remove 'PR:' references from pull request {owner}/{repo}#{number}: {e}")

                # close the pull request that was merged into the target
                try:
                    gitea_api.PullRequest.close(self.gitea_conn, owner, repo, number)
                except Exception as e:
                    print(f"Unable to close pull request {owner}/{repo}#{number}: {e}")

        print()
        print(target.pr_obj.to_human_readable_string())

        print()
        print("Staging project pull requests have been successfully merged")

        if args.keep_temp_dir:
            print()
            print(f"Temporary files are available here: {temp_dir}")
