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
            help="Target project pull request to modify (format: <owner>/<repo>#<pull-request-number>). If not specified, a new pull request will be created.",
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
            "--remove-pr-references",
            action="store_true",
            help="Remove 'PR:' references from the source project pull requests",
        )

        self.add_argument(
            "--force",
            action="store_true",
            help="Allow force-push to the branch associated with the pull request",
        )

        self.add_argument_owner_repo_pull(
            dest="pr_list",
            metavar="pr_id",
            nargs="*",
            help="List of project pull request to be merged into the target project pull request (format: <owner>/<repo>#<pull-request-number>)",
        ).completer = osc.commandline_git.complete_pr

        self.add_argument_owner_repo(
            dest="--target-repo",
            help="Target repo (format: <owner>/<repo>). Requires --source-owner."
        )

        self.add_argument(
            "--source-owner",
            action="append",
            help="Source owner (e.g. a devel project)",
        )

        self.add_argument(
            "--no-ssh-strict-host-key-checking",
            action="store_true",
            help="Set 'StrictHostKeyChecking no' ssh option",
        )

        self.add_argument(
            "--cache-dir",
            help="Path to a git cache.",
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

        if args.pr_list and args.target_repo:
            self.parser.error("--target-repo conflicts with a list of pull request IDs")

        if args.target_repo and not args.source_owner:
            self.parser.error("--target-repo requires --source-owner")

        if not args.pr_list and not args.target_repo:
            self.parser.error("Either a list of pull request IDs or --target-repo with --source-owner are required")

        cache_dir = os.path.abspath(args.cache_dir) if args.cache_dir else None

        self.print_gitea_settings()

        pr_obj_list = []
        pr_references = []
        if args.target_repo:
            target_owner, target_repo = args.target_repo
            pr_obj_list = gitea_api.PullRequest.list(self.gitea_conn, target_owner, target_repo, source_owners=args.source_owner)
            pr_list = [(i.base_owner, i.base_repo, i.number) for i in pr_obj_list]
            if args.target:
                # explicitly remove the target PR from the pr_list
                pr_list = [i for i in pr_list if i != args.target]
        else:
            target_owner = None
            target_repo = None
            pr_list = args.pr_list

        target_branch = None
        for owner, repo, number in args.pr_list:
            pr_obj = gitea_api.PullRequest.get(self.gitea_conn, owner, repo, number)

            if pr_obj.state != "open":
                # we don't care about the state of the package pull requests - they can be merged already
                raise gitea_api.GitObsRuntimeError(f"Pull request {owner}/{repo}#{number} is not open (the state is '{pr_obj.state}')")

            # test that all PRs go to the same branch
            if target_owner is None:
                target_owner = pr_obj.base_owner
            else:
                assert target_owner == pr_obj.base_owner, f"{target_owner} != {pr_obj.base_owner}"

            if target_repo is None:
                target_repo = pr_obj.base_repo
            else:
                assert target_repo == pr_obj.base_repo, f"{target_repo} != {pr_obj.base_repo}"

            if target_branch is None:
                target_branch = pr_obj.base_branch
            else:
                assert target_branch == pr_obj.base_branch, f"{target_branch} != {pr_obj.base_branch}"

            if gitea_api.StagingPullRequestWrapper.BACKLOG_LABEL not in pr_obj.labels:
                raise gitea_api.GitObsRuntimeError(f"Pull request {owner}/{repo}#{number} is missing the '{gitea_api.StagingPullRequestWrapper.BACKLOG_LABEL}' label.")

            pr_obj_list.append(pr_obj)
            pr_references.extend(pr_obj.parse_pr_references())

        # deduplicate entries
        pr_references = sorted(set(pr_references))

        # create title
        if args.title:
            title = args.title
        else:
            updated_packages = sorted([i[1] for i in pr_references])
            # TODO: it would be nice to mention the target OBS project
            # we keep only the first ``max_packages``, because the title might get too long quite easily
            max_packages = 5
            updated_packages_str = ", ".join(sorted(updated_packages)[:max_packages])
            if len(updated_packages) > max_packages:
                updated_packages_str += f" + {len(updated_packages) - max_packages} more"
            title = f"Update packages: {updated_packages_str}"

        if args.target:
            target_owner, target_repo, target_number = args.target
            target_pr_obj = gitea_api.PullRequest.get(self.gitea_conn, target_owner, target_repo, target_number)

            # extend the 'PR: ' references in the target pull request
            target_pr_obj._data["body"] = gitea_api.PullRequest.add_pr_references(target_pr_obj.body, pr_references)

            # update description of the target pull request in Gitea
            # it is crucial to allow maintainer edits so the bot can push the related PRs
            target_pr_obj = gitea_api.PullRequest.set(
                self.gitea_conn,
                target_pr_obj.base_owner,
                target_pr_obj.base_repo,
                int(target_pr_obj.number),
                title=title,
                description=target_pr_obj.body,
                allow_maintainer_edit=True,
            )

            # update labels
            try:
                gitea_api.PullRequest.add_labels(
                    self.gitea_conn,
                    target_pr_obj.base_owner,
                    target_pr_obj.base_repo,
                    int(target_pr_obj.number),
                    labels=[gitea_api.StagingPullRequestWrapper.INPROGRESS_LABEL],
                )
            except Exception as e:
                print(f"Unable to add the '{gitea_api.StagingPullRequestWrapper.INPROGRESS_LABEL}' label to pull request {pr_obj.id}: {e}")

            try:
                if gitea_api.StagingPullRequestWrapper.BACKLOG_LABEL in target_pr_obj.labels:
                    gitea_api.PullRequest.remove_labels(
                        self.gitea_conn,
                        target_pr_obj.base_owner,
                        target_pr_obj.base_repo,
                        int(target_pr_obj.number),
                        labels=[gitea_api.StagingPullRequestWrapper.BACKLOG_LABEL],
                    )
            except Exception as e:
                print(f"Unable to remove the '{gitea_api.StagingPullRequestWrapper.BACKLOG_LABEL}' label from pull request {pr_obj.id}: {e}")

        else:
            has_push_access = False
            if not args.fork_owner:
                target_repo_obj = gitea_api.Repo.get(self.gitea_conn, target_owner, target_repo)
                # determine if we have write access to the target repo and create the branch there if possible
                if target_repo_obj.can_push:
                    print(f"You have push access to the target repository {target_owner}/{target_repo}, the pull request will be created from a branch in the target repository.")
                    has_push_access = True

            fork_branch = args.fork_branch if args.fork_branch else f"for/{target_branch}/group-{datetime.datetime.now().strftime('%Y-%m-%d_%H-%M-%S')}"

            if has_push_access:
                fork_owner = target_owner
                fork_repo = target_repo
            else:
                user_obj = gitea_api.User.get(self.gitea_conn)
                fork_owner = args.fork_owner if args.fork_owner else user_obj.login

                fork_repo = None
                forks = gitea_api.Fork.list(self.gitea_conn, target_owner, target_repo)
                for repo in forks:
                    if repo.owner.lower() == fork_owner.lower():
                        fork_repo = repo.repo
                if not fork_repo:
                    raise gitea_api.GitObsRuntimeError(f"Cannot find a matching fork of {target_owner}/{target_repo} for user {fork_owner}")

            # create the branch
            if has_push_access:
                gitea_api.Branch.create(self.gitea_conn, target_owner, target_repo, old_ref_name=target_branch, new_branch_name=fork_branch)
            else:
                fork_repo_obj = gitea_api.Repo.get(self.gitea_conn, fork_owner, fork_repo)
                with TemporaryDirectory(prefix="git-obs-staging_", dir=".") as temp_dir:
                    # we need to create a branch that matches the target branch using git; Gitea doesn't have any API for that
                    clone_dir = gitea_api.Repo.clone(
                        self.gitea_conn,
                        fork_owner,
                        fork_repo,
                        directory=os.path.join(temp_dir, f"{fork_owner}_{fork_repo}"),
                        add_remotes=False,
                        cache_directory=cache_dir,
                        ssh_private_key_path=self.gitea_conn.login.ssh_key,
                        ssh_strict_host_key_checking=not(args.no_ssh_strict_host_key_checking),
                    )
                    clone_git = gitea_api.Git(clone_dir)
                    clone_git._run_git(["fetch", "origin", f"{target_branch}:{fork_branch}", "--force", "--update-head-ok", "--depth=1"])
                    clone_git.switch(fork_branch)
                    clone_git.add_remote("fork", fork_repo_obj.ssh_url)
                    clone_git.push(remote="fork", branch=fork_branch, set_upstream=True, force=args.force)

            # target project pull request wasn't specified, let's create it
            desc = gitea_api.PullRequest.add_pr_references("", pr_references)
            target_pr_obj = gitea_api.PullRequest.create(
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

            # it is crucial to allow maintainer edits so the bot can push the related PRs
            target_pr_obj = gitea_api.PullRequest.set(
                self.gitea_conn,
                target_pr_obj.base_owner,
                target_pr_obj.base_repo,
                int(target_pr_obj.number),
                allow_maintainer_edit=True,
            )

        for pr_obj in pr_obj_list:
            if args.remove_pr_references:
                try:
                    # remove the 'PR:' references from the original pull request
                    refs = pr_obj.parse_pr_references()
                    body = gitea_api.PullRequest.remove_pr_references(pr_obj.body, refs)
                    pr_obj.set(self.gitea_conn, pr_obj.base_owner, pr_obj.base_repo, pr_obj.number, description=body)
                except Exception as e:
                    print(f"Unable to remove 'PR:' references from pull request {pr_obj.id}: {e}")

            try:
                # close the pull request that was merged into the target
                gitea_api.PullRequest.close(self.gitea_conn, pr_obj.base_owner, pr_obj.base_repo, pr_obj.number)
            except Exception as e:
                print(f"Unable to close pull request {pr_obj.id}: {e}")

        print()
        print(target_pr_obj.to_human_readable_string())

        print()
        print("Staging project pull requests have been successfully merged")
