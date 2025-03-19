import subprocess

import osc.commandline_git


class PullRequestCheckoutCommand(osc.commandline_git.GitObsCommand):
    """
    Check out a pull request
    """

    name = "checkout"
    parent = "PullRequestCommand"

    def init_arguments(self):
        from osc.commandline_git import complete_checkout_pr

        self.add_argument(
            "pull",
            type=int,
            help="Number of the pull request",
        ).completer = complete_checkout_pr
        self.add_argument(
            "-f",
            "--force",
            action="store_true",
            help="Reset the existing local branch to the latest state of the pull request",
        )

    def run(self, args):
        from osc import gitea_api

        self.print_gitea_settings()

        git = gitea_api.Git(".")
        owner, repo = git.get_owner_repo()

        pr = gitea_api.PullRequest.get(self.gitea_conn, owner, repo, args.pull).json()

        head_ssh_url = pr["head"]["repo"]["ssh_url"]
        head_owner = pr["head"]["repo"]["owner"]["login"]
        head_branch = pr["head"]["ref"]

        try:
            git.add_remote(head_owner, head_ssh_url)
        except subprocess.CalledProcessError as e:
            # TODO: check if the remote url matches
            if e.returncode != 3:
                # returncode 3 means that the remote exists; see `man git-remote`
                raise
        git.fetch(head_owner)

        local_branch = git.fetch_pull_request(args.pull, force=args.force)

        # LFS data may not be accessible in the "origin" remote, we need to allow searching in all remotes
        git.set_config("lfs.remote.searchall", "1")

        # configure branch for `git push`
        git.set_config(f"branch.{local_branch}.remote", head_owner)
        git.set_config(f"branch.{local_branch}.pushRemote", head_owner)
        git.set_config(f"branch.{local_branch}.merge", f"refs/heads/{head_branch}")

        # allow `git push` with no arguments to push to a remote branch that is named differently than the local branch
        git.set_config("push.default", "upstream")

        git.switch(local_branch)
