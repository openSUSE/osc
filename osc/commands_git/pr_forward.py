import os
import shutil
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
            "-f",
            "--force",
            action="store_true",
            help="Force push to the fork (overwrite remote branch history)",
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

    def run(self, args):
        from osc import gitea_api
        from osc.output import tty

        self.print_gitea_settings()

        upstream_owner, upstream_repo = args.owner_repo
        source_branch = args.source_branch
        target_branch = args.target_branch
        source_url = args.source_url

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
            if os.path.isdir(os.path.join(args.workdir, ".git")):
                repo_dir = args.workdir
            # Case B: args.workdir contains the repo (args.workdir/repo/.git)
            elif os.path.isdir(os.path.join(args.workdir, fork_repo, ".git")):
                repo_dir = os.path.join(args.workdir, fork_repo)
            # Case C: args.workdir is a parent dir, repo doesn't exist yet -> create args.workdir/repo
            else:
                repo_dir = os.path.join(args.workdir, fork_repo)
                if not os.path.exists(repo_dir):
                    os.makedirs(repo_dir)
        else:
            repo_dir = tempfile.mkdtemp(prefix="git-obs-forward-")
            cleanup = not args.no_cleanup

        print(f"Working in: {repo_dir}", file=sys.stderr)

        try:
            git = gitea_api.Git(repo_dir)

            # Clone / Init
            if not os.path.exists(os.path.join(repo_dir, ".git")):
                print(f"Cloning {fork_owner}/{fork_repo} ...", file=sys.stderr)
                try:
                    git.clone(fork_url, directory=".")
                except Exception as e:
                     raise e
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
            if source_url:
                if "source" not in current_remotes:
                    print(f"Adding source remote: {source_url}", file=sys.stderr)
                    git.add_remote("source", source_url)
                else:
                    git._run_git(["remote", "set-url", "source", source_url])
                
                print("Fetching source ...", file=sys.stderr)
                git.fetch("source")
                source_ref = f"source/{source_branch}"
            else:
                try:
                    # Generic fetch for upstream in case we need history objects?
                    # But per request, we should optimize.
                    # Let's rely on the loop below.
                    pass
                except Exception:
                    pass
                source_ref = f"upstream/{source_branch}"

            # Optimize LFS fetch: fetch only objects for new commits
            # We identify commits in source_ref that are not in target_branch
            # and fetch LFS objects for them from the appropriate remote.
            lfs_remote = "source" if source_url else "upstream"
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
                    print("", file=sys.stderr) # Newline after progress
                else:
                    print(" * No new commits to fetch LFS objects for.", file=sys.stderr)
            except Exception as e:
                # Fallback or ignore if LFS fails/missing
                print(f"LFS fetch warning: {e}", file=sys.stderr)

            # Checkout Target Branch (tracking upstream)
            print(f"Checking out target branch: {target_branch} (tracking upstream/{target_branch})", file=sys.stderr)
            try:
                git._run_git(["checkout", "-B", target_branch, f"upstream/{target_branch}"])
            except Exception:
                print(f"{tty.colorize('ERROR', 'red,bold')}: Failed to checkout upstream/{target_branch}. Does it exist?", file=sys.stderr)
                sys.exit(1)

            # Merge Source Branch (Theirs)
            print(f"Merging {source_ref} with strategy 'theirs' ...", file=sys.stderr)
            try:
                git._run_git(["merge", "-X", "theirs", "--allow-unrelated-histories", "--no-edit", source_ref])
            except Exception as e:
                print(f"{tty.colorize('ERROR', 'red,bold')}: Merge failed: {e}", file=sys.stderr)
                sys.exit(1)

            # Clean files not in Source
            print("Cleaning files not present in source ...", file=sys.stderr)
            
            # Get list of files in source (recurse)
            source_files_output = git._run_git(["ls-tree", "-r", "--name-only", source_ref])
            source_files = set(source_files_output.splitlines())

            # Get list of files in current HEAD
            head_files_output = git._run_git(["ls-tree", "-r", "--name-only", "HEAD"])
            head_files = set(head_files_output.splitlines())

            files_to_remove = list(head_files - source_files)
            
            if files_to_remove:
                print(f"Removing {len(files_to_remove)} files not present in {source_branch} ...", file=sys.stderr)
                # Batching git rm to avoid command line length limits
                chunk_size = 100
                for i in range(0, len(files_to_remove), chunk_size):
                    chunk = files_to_remove[i : i + chunk_size]
                    git._run_git(["rm", "-f", "--"] + chunk)
                
                git.commit(f"Clean files not present in {source_branch}")
            else:
                print("No extra files to clean.", file=sys.stderr)

            # Push to Fork
            if args.dry_run:
                print("[DRY RUN] Would push to origin", file=sys.stderr)
            else:
                print(f"Pushing to {fork_owner}/{fork_repo} ...", file=sys.stderr)
                try:
                    git.push("origin", target_branch, force=args.force)
                except Exception as e:
                    print(f"{tty.colorize('ERROR', 'red,bold')}: Push failed: {e}", file=sys.stderr)
                    if not args.force:
                        print(f"{tty.colorize('HINT', 'yellow,bold')}: The local branch has diverged from the remote branch.", file=sys.stderr)
                        print(f"{tty.colorize('HINT', 'yellow,bold')}: This is expected when forwarding/resetting a branch.", file=sys.stderr)
                        print(f"{tty.colorize('HINT', 'yellow,bold')}: Run with --force to overwrite your fork's branch.", file=sys.stderr)
                    sys.exit(1)

            # Create PR
            title = args.title or f"Forward {source_branch} to {target_branch}"
            description = args.description or f"Automated forward of {source_branch} to {target_branch} using git-obs."
            
            if args.dry_run:
                print(f"[DRY RUN] Would create PR: {title}", file=sys.stderr)
                return

            print("Creating Pull Request ...", file=sys.stderr)
            try:
                pr_obj = gitea_api.PullRequest.create(
                    self.gitea_conn,
                    target_owner=upstream_owner,
                    target_repo=upstream_repo,
                    target_branch=target_branch,
                    source_owner=fork_owner,
                    source_branch=target_branch,
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
