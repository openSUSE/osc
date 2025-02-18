import os
import subprocess
import sys
from typing import Optional

import osc.commandline_git


NEW_COMMENT_TEMPLATE = """

#
# Lines starting with '#' will be ignored.
#
# Adding a comment to pull request {owner}/{repo}#{number}
#
"""


DECLINE_REVIEW_TEMPLATE = """

#
# Lines starting with '#' will be ignored.
#
# Requesting changes for pull request {owner}/{repo}#{number}
#
"""


class PullRequestReviewCommand(osc.commandline_git.GitObsCommand):
    """
    """

    name = "review"
    parent = "PullRequestCommand"

    def init_arguments(self):
        self.add_argument(
            "id",
            nargs="*",
            help="Pull request ID in <owner>/<repo>#<number> format",
        )

    def run(self, args):
        from osc import gitea_api
        from osc.output import get_user_input

        if args.id:
            # TODO: deduplicate, skip those that do not require a review (print to stderr)
            pull_request_ids = args.id
        else:
            # keep only the list of pull request IDs, throw search results away
            # because the search returns issues instead of pull requests
            data = gitea_api.PullRequest.search(self.gitea_conn, review_requested=True).json()
            # TODO: priority ordering?
            data = sorted(data, key=gitea_api.PullRequest.cmp)
            pull_request_ids = [f"{i['repository']['full_name']}#{i['number']}" for i in data]
            del data

        skipped_drafts = 0

        for pr_index, pr_id in enumerate(pull_request_ids):
            self.print_gitea_settings()

            owner, repo, number = gitea_api.PullRequest.split_id(pr_id)
            pr_data = gitea_api.PullRequest.get(self.gitea_conn, owner, repo, number).json()

            if pr_data["draft"]:
                # we don't want to review drafts, they will change
                skipped_drafts += 1
                continue

            self.clone_git(owner, repo, number)
            self.view(owner, repo, number, pr_index=pr_index, pr_count=len(pull_request_ids), pr_data=pr_data)

            while True:
                # TODO: print at least some context because the PR details disappear after closing less
                reply = get_user_input(
                    f"Select a review action for '{pr_id}':",
                    answers={
                        "a": "approve",
                        "d": "decline",
                        "m": "comment",
                        "v": "view again",
                        "s": "skip",
                        "x": "exit",
                    },
                    default_answer="s",
                )
                if reply == "a":
                    self.approve(owner, repo, number)
                    break
                elif reply == "d":
                    self.decline(owner, repo, number)
                    break
                elif reply == "m":
                    self.comment(owner, repo, number)
                    break
                elif reply == "v":
                    self.view(owner, repo, number, pr_index=pr_index, pr_count=len(pull_request_ids), pr_data=pr_data)
                elif reply == "s":
                    break
                elif reply == "x":
                    return
                else:
                    raise RuntimeError(f"Unhandled reply: {reply}")

        if skipped_drafts:
            print(file=sys.stderr)
            print(f"Skipped drafts: {skipped_drafts}", file=sys.stderr)

    def approve(self, owner: str, repo: str, number: int):
        from osc import gitea_api
        gitea_api.PullRequest.approve_review(self.gitea_conn, owner, repo, number)

    def decline(self, owner: str, repo: str, number: int):
        from osc import gitea_api
        from .pr_create import edit_message

        message = edit_message(template=DECLINE_REVIEW_TEMPLATE.format(**locals()))

        # remove comments
        message = "\n".join([i for i in message.splitlines() if not i.startswith("#")])

        # strip leading and trailing spaces
        message = message.strip()

        gitea_api.PullRequest.decline_review(self.gitea_conn, owner, repo, number, msg=message)

    def comment(self, owner: str, repo: str, number: int):
        from osc import gitea_api
        from .pr_create import edit_message

        message = edit_message(template=NEW_COMMENT_TEMPLATE.format(**locals()))

        # remove comments
        message = "\n".join([i for i in message.splitlines() if not i.startswith("#")])

        # strip leading and trailing spaces
        message = message.strip()

        gitea_api.PullRequest.add_comment(self.gitea_conn, owner, repo, number, msg=message)

    def get_git_repo_path(self, owner: str, repo: str, number: int):
        path = os.path.join("~", ".cache", "git-obs", "reviews", self.gitea_login.name, f"{owner}_{repo}_{number}")
        path = os.path.expanduser(path)
        return path

    def clone_git(self, owner: str, repo: str, number: int):
        from osc import gitea_api

        repo_data = gitea_api.Repo.get(self.gitea_conn, owner, repo).json()
        clone_url = repo_data["ssh_url"]

        # TODO: it might be good to have a central cache for the git repos to speed cloning up
        path = self.get_git_repo_path(owner, repo, number)
        git = gitea_api.Git(path)
        if os.path.isdir(path):
            git.fetch()
        else:
            os.makedirs(path, exist_ok=True)
            git.clone(clone_url, directory=path, quiet=False)
        git.fetch_pull_request(number, force=True)

    def view(self, owner: str, repo: str, number: int, *, pr_index: int, pr_count: int, pr_data: Optional[dict] = None):
        from osc import gitea_api
        from osc.core import highlight_diff
        from osc.output import sanitize_text
        from osc.output import tty

        if pr_data is None:
            pr_data = gitea_api.PullRequest.get(self.gitea_conn, owner, repo, number).json()

        # the process works with bytes rather than with strings
        # because the diffs may contain character sequences that cannot be decoded as utf-8 strings
        proc = subprocess.Popen(["less"], stdin=subprocess.PIPE)
        assert proc.stdin is not None

        # heading
        heading = tty.colorize(f"[{pr_index + 1}/{pr_count}] Reviewing pull request '{owner}/{repo}#{number}'...\n", "yellow,bold")
        proc.stdin.write(heading.encode("utf-8"))
        proc.stdin.write(b"\n")

        # pr details
        pr = gitea_api.PullRequest.to_human_readable_string(pr_data)
        proc.stdin.write(pr.encode("utf-8"))
        proc.stdin.write(b"\n")
        proc.stdin.write(b"\n")

        # patch
        proc.stdin.write(tty.colorize("Patch:\n", "bold").encode("utf-8"))
        patch = gitea_api.PullRequest.get_patch(self.gitea_conn, owner, repo, number).data
        patch = sanitize_text(patch)
        patch = highlight_diff(patch)
        proc.stdin.write(patch)
        proc.stdin.write(b"\n")

        # tardiff
        proc.stdin.write(tty.colorize("Archive diffs:\n", "bold").encode("utf-8"))
        tardiff_chunks = self.tardiff(owner, repo, number, pr_data=pr_data)
        for chunk in tardiff_chunks:
            chunk = sanitize_text(chunk)
            chunk = highlight_diff(chunk)
            try:
                proc.stdin.write(chunk)
            except BrokenPipeError:
                # user exits less before all data is written
                break

        proc.communicate()

    def get_tardiff_path(self):
        path = os.path.join("~", ".cache", "git-obs", "tardiff")
        path = os.path.expanduser(path)
        return path

    def tardiff(self, owner: str, repo: str, number: int, *, pr_data: dict):
        from osc import gitea_api

        src_commit = pr_data["head"]["sha"]
        dst_commit = pr_data["base"]["sha"]

        path = self.get_git_repo_path(owner, repo, number)
        git = gitea_api.Git(path)

        # the repo might be outdated, make sure the commits are available
        git.fetch()

        src_archives = git.lfs_ls_files(ref=src_commit)
        dst_archives = git.lfs_ls_files(ref=dst_commit)

        def map_archives_by_name(archives: list):
            result = {}
            for fn, sha in archives:
                name = fn.rsplit("-", 1)[0]
                assert name not in result
                result[name] = (fn, sha)
            return result

        src_archives_by_name = map_archives_by_name(src_archives)
        dst_archives_by_name = map_archives_by_name(dst_archives)
        all_names = sorted(set(src_archives_by_name) | set(dst_archives_by_name))

        path = self.get_tardiff_path()
        td = gitea_api.TarDiff(path)

        for name in all_names:
            src_archive = src_archives_by_name.get(name, (None, None))
            dst_archive = dst_archives_by_name.get(name, (None, None))

            if src_archive[0]:
                td.add_archive(src_archive[0], src_archive[1], git.lfs_cat_file(src_archive[0], ref=src_commit))

            if dst_archive[0]:
                td.add_archive(dst_archive[0], dst_archive[1], git.lfs_cat_file(dst_archive[0], ref=dst_commit))

            # TODO: max output length / max lines; in such case, it would be great to list all the changed files at least
            yield from td.diff_archives(*dst_archive, *src_archive)
