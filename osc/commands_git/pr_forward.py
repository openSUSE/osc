import os
import shutil
import subprocess
import sys
import tempfile

import osc.commandline_git


class PullRequestForwardCommand(osc.commandline_git.GitObsCommand):
    """
    Forward sources from one branch to another (Fork -> Sync -> Push -> PR)
    """

    name = "forward"
    parent = "PullRequestCommand"

    def init_arguments(self):
        self.add_argument_owner_repo()
        self.add_argument(
            "source_branch",
            help="Source branch name (e.g. factory)",
        )
        self.add_argument(
            "target_branch",
            help="Target branch name (e.g. slfo-main)",
        )
        self.add_argument(
            "--workdir",
            help="Working directory for git operations (default: temporary directory)",
        )
        self.add_argument(
            "--no-cleanup",
            action="store_true",
            help="Do not remove the temporary directory after completion",
        )
        self.add_argument(
            "--dry-run",
            action="store_true",
            help="Do not actually create the pull request or push changes",
        )
        self.add_argument(
            "--source-url",
            help="URL of the source git repository (if different from upstream)",
        )
        self.add_argument(
            "--title",
            help="Pull request title",
        )
        self.add_argument(
            "--description",
            help="Pull request description (body)",
        )
        self.add_argument(
            "-e", "--edit",
            action="store_true",
            help="Open an editor to edit the pull request title and description.",
        )
        self.add_argument(
            "--allow-unrelated-histories",
            action="store_true",
            help="Allow merging unrelated histories",
        )

    def run(self, args):
        from osc import gitea_api

        self.print_gitea_settings()

        upstream_owner, upstream_repo = args.owner_repo
        source_branch = args.source_branch
        target_branch = args.target_branch

        # Fork if not exists
        print(f"Checking fork for {upstream_owner}/{upstream_repo} ...", file=sys.stderr)
        try:
            fork_obj = gitea_api.Fork.create(self.gitea_conn, upstream_owner, upstream_repo)
            fork_owner = fork_obj.owner
            fork_repo = fork_obj.repo
            print(f" * Fork created: {fork_owner}/{fork_repo}", file=sys.stderr)
        except gitea_api.ForkExists as e:
            fork_owner = e.fork_owner
            fork_repo = e.fork_repo
            print(f" * Fork already exists: {fork_owner}/{fork_repo}", file=sys.stderr)
        except gitea_api.RepoExists as e:
            fork_owner = e.owner
            fork_repo = e.repo
            print(f" * Repo already exists (assuming it is the fork): {fork_owner}/{fork_repo}", file=sys.stderr)

        # Get clone URLs
        upstream_repo_obj = gitea_api.Repo.get(self.gitea_conn, upstream_owner, upstream_repo)
        fork_repo_obj = gitea_api.Repo.get(self.gitea_conn, fork_owner, fork_repo)

        upstream_url = upstream_repo_obj.ssh_url
        fork_url = fork_repo_obj.ssh_url # Prefer SSH for push if possible

        # Setup Workdir
        repo_dir = None
        cleanup = False

        if args.workdir:
            # Smart detection of workdir
            # Case A: args.workdir IS the repo (has .git)
            if os.path.exists(os.path.join(args.workdir, ".git")):
                repo_dir = args.workdir
            # Case B: args.workdir contains the repo (args.workdir/repo/.git)
            elif os.path.exists(os.path.join(args.workdir, fork_repo, ".git")):
                repo_dir = os.path.join(args.workdir, fork_repo)
            # Case C: args.workdir is a parent dir, repo doesn't exist yet -> create args.workdir/repo
            else:
                repo_dir = os.path.join(args.workdir, fork_repo)
                os.makedirs(repo_dir, exist_ok=True)
        else:
            repo_dir = tempfile.mkdtemp(prefix="git-obs-forward-")
            cleanup = not args.no_cleanup

        print(f"Working in: {repo_dir}", file=sys.stderr)

        try:
            git = gitea_api.Git(repo_dir)

            # Clone / Init
            if not os.path.exists(os.path.join(repo_dir, ".git")):
                print(f"Cloning {fork_owner}/{fork_repo} ...", file=sys.stderr)
                git.clone(fork_url, directory=".")
            else:
                print(f"Using existing git repo in {repo_dir}", file=sys.stderr)

            # Configure LFS to autodetect remotes
            git._run_git(["config", "lfs.remote.autodetect", "true"])

            # Add Upstream
            current_remotes = git._run_git(["remote"]).splitlines()
            if "upstream" not in current_remotes:
                print(f"Adding upstream remote: {upstream_owner}/{upstream_repo} ({upstream_url})", file=sys.stderr)
                git.add_remote("upstream", upstream_url)
            else:
                git._run_git(["remote", "set-url", "upstream", upstream_url])

            # Fetch Upstream
            print("Fetching upstream ...", file=sys.stderr)
            git.fetch("upstream")

            # Determine Source Ref
            if args.source_url:
                source_url = args.source_url
                source_ref = f"source/{source_branch}"
                lfs_remote = "source"

                if "source" not in current_remotes:
                    print(f"Adding source remote: {source_url}", file=sys.stderr)
                    git.add_remote("source", source_url)
                else:
                    git._run_git(["remote", "set-url", "source", source_url])

                print("Fetching source ...", file=sys.stderr)
                git.fetch("source")
            else:
                source_url = git.get_remote_url("upstream")
                source_ref = f"upstream/{source_branch}"
                lfs_remote = "upstream"

            # Define a unique branch name for the forward operation
            try:
                source_commit_sha = git.get_branch_head(source_branch, remote="upstream")
            except subprocess.CalledProcessError as e:
                raise gitea_api.GitObsRuntimeError(f"Could not get SHA for {source_ref}: {e}")

            forward_branch = f"for/{target_branch}/forward-{source_commit_sha}"
            print(f"Using forward branch on fork: {forward_branch}", file=sys.stderr)

            # Optimize LFS fetch: fetch only objects for new commits
            # We identify commits in source_ref that are not in target_branch
            # and fetch LFS objects for them from the appropriate remote.
            print(f"Fetching LFS objects from {lfs_remote} for incoming commits ...", file=sys.stderr)

            try:
                # Get list of commits unique to source_branch that are not in target_branch
                commits = git._run_git(["rev-list", f"{lfs_remote}/{source_branch}", f"^{lfs_remote}/{target_branch}"]).splitlines()

                if commits:
                    print(f" * Found {len(commits)} commits to fetch LFS objects for.", file=sys.stderr)
                    # Loop through commits as requested
                    for commit in commits:
                        print(f"   Fetching LFS for commit {commit} ...", file=sys.stderr, end="\r")
                        git._run_git(["lfs", "fetch", lfs_remote, commit])
                    print("", file=sys.stderr)  # Newline after progress
                else:
                    print(" * No new commits to fetch LFS objects for.", file=sys.stderr)
            except subprocess.CalledProcessError as e:
                # Fallback or ignore if LFS fails/missing
                print(f"LFS fetch warning: {e}", file=sys.stderr)

            # Checkout forward branch (tracking upstream/target_branch)
            print(f"Creating/resetting forward branch '{forward_branch}' from 'upstream/{target_branch}'", file=sys.stderr)
            try:
                git._run_git(["checkout", "-B", forward_branch, f"upstream/{target_branch}"])
            except subprocess.CalledProcessError:
                raise gitea_api.GitObsRuntimeError(f"Failed to checkout upstream/{target_branch}. Does it exist?")

            # Check for unrelated histories
            try:
                # Returns non-zero if no common ancestor
                git._run_git(["merge-base", source_ref, forward_branch])
            except subprocess.CalledProcessError:
                if not args.allow_unrelated_histories:
                    raise gitea_api.GitObsRuntimeError(f"Unrelated histories in '{source_ref}' and 'upstream/{target_branch}'. Use --allow-unrelated-histories to merge.")

            # Determine PR message and merge commit message
            title = args.title or f"Sync with {source_branch} branch"
            description = args.description or f"URL: {source_url}\nBranch: {source_branch}\nCommit: {source_commit_sha}"

            if args.edit and not args.dry_run:
                from osc.gitea_api.common import edit_message

                template = (
                    f"{title}\n\n"
                    f"{description}\n\n"
                    f"# Please enter the pull request title and description.\n"
                    f"# The first line is the title, the rest (after a blank line) is the description.\n"
                    f"# Lines starting with '#' will be ignored.\n"
                )
                message = edit_message(template)

                # Filter out comments and strip whitespace
                lines = [line for line in message.split("\n") if not line.strip().startswith("#")]
                while lines and not lines[0].strip():
                    lines.pop(0)  # remove leading blank lines

                if not lines:
                    raise gitea_api.GitObsRuntimeError("Aborting due to empty message.")

                title = lines.pop(0).strip()
                if not title:
                    raise gitea_api.GitObsRuntimeError("Aborting due to empty title.")

                # remove blank lines between title and body
                while lines and not lines[0].strip():
                    lines.pop(0)

                description = "\n".join(lines).strip()

            # Merge Source Branch (Theirs)
            commit_message = f"{title}\n\n{description}"
            print(f"Merging {source_ref} into {forward_branch} with strategy 'theirs' ...", file=sys.stderr)
            try:
                merge_cmd = ["merge", "-X", "theirs"]
                if args.allow_unrelated_histories:
                    merge_cmd.append("--allow-unrelated-histories")
                merge_cmd.extend(["-m", commit_message, source_ref])
                git._run_git(merge_cmd)
            except subprocess.CalledProcessError as e:
                raise gitea_api.GitObsRuntimeError(f"Merge failed: {e}")

            # The git merge above only merges the sources while resolving conflicts,
            # but it doesn't remove any files that do not exist in the ref we're merging from.
            # Running git read-tree does the cleanup for us.
            print("Cleaning files not present in source ...", file=sys.stderr)
            git._run_git(["read-tree", "-u", "--reset", source_ref])

            if git.has_changes:
                # amend the staged changes to the merge commit
                git.commit(msg="", amend=True, no_edit=True)

            # Push to Fork
            if args.dry_run:
                print(f"[DRY RUN] Would push '{forward_branch}' to origin", file=sys.stderr)
            else:
                print(f"Pushing '{forward_branch}' to {fork_owner}/{fork_repo} ...", file=sys.stderr)
                try:
                    # Always force-push to the temporary forward branch
                    git.push("origin", forward_branch, force=True)
                except subprocess.CalledProcessError as e:
                    raise gitea_api.GitObsRuntimeError(f"Push failed: {e}")

            # Create PR
            if args.dry_run:
                print(f"[DRY RUN] Would create PR for branch '{forward_branch}': {title}", file=sys.stderr)
                return

            print("Creating Pull Request ...", file=sys.stderr)
            try:
                pr_obj = gitea_api.PullRequest.create(
                    self.gitea_conn,
                    target_owner=upstream_owner,
                    target_repo=upstream_repo,
                    target_branch=target_branch,
                    source_owner=fork_owner,
                    source_branch=forward_branch,
                    title=title,
                    description=description,
                )
                print("", file=sys.stderr)
                print("Pull request created:", file=sys.stderr)
                print(pr_obj.to_human_readable_string())
            except gitea_api.GiteaException as e:
                # Handle case where PR already exists
                if "pull request already exists" in str(e).lower():
                    print(f" * Pull request already exists.", file=sys.stderr)
                else:
                    raise

        finally:
            if cleanup:
                print(f"Cleaning up {repo_dir} ...", file=sys.stderr)
                shutil.rmtree(repo_dir)
