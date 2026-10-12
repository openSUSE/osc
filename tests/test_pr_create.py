import contextlib
import io
import unittest
from unittest.mock import MagicMock, patch

from osc import gitea_api
from osc.commands_git.pr_create import PullRequestCreateCommand


class TestPullRequestCreateTargetBranch(unittest.TestCase):
    def setUp(self):
        self.cmd = PullRequestCreateCommand.__new__(PullRequestCreateCommand)
        self.cmd.parent = MagicMock()
        self.cmd.parent.main_command = MagicMock()
        self.cmd.parent.main_command.gitea_conn = MagicMock()

    def _call_create_pr(self, source_branch, target_branch, branch_exists_on_target=True):
        args = MagicMock()
        args.source_owner = "alice"
        args.source_repo = "pkg"
        args.source_branch = source_branch
        args.source = None
        args.target_owner = "upstream"
        args.target_repo = "pkg"
        args.target_branch = target_branch
        args.target = None
        args.self = False
        args.title = "Test PR"
        args.description = "Test Desc"
        args.dry_run = False
        args.allow_empty = False
        args.allow_maintainer_edit = "0"

        with patch.object(
            gitea_api.Repo, "get_fork_tree_root", return_value="root"
        ), patch.object(
            gitea_api.Repo, "get"
        ) as mock_repo_get, patch.object(
            gitea_api.Branch, "get"
        ) as mock_branch_get, patch.object(
            gitea_api.PullRequest, "create"
        ) as mock_pr_create:
            src_repo = MagicMock(parent_obj=None, default_branch="main")
            tgt_repo = MagicMock(parent_obj=None, default_branch="factory")
            mock_repo_get.side_effect = lambda conn, owner, repo: src_repo if owner == "alice" else tgt_repo

            src_branch_obj = MagicMock(commit="c1", name=source_branch)

            def branch_get_side_effect(conn, owner, repo, branch):
                if owner == "alice":
                    return src_branch_obj
                if not branch_exists_on_target and branch == source_branch:
                    raise gitea_api.BranchDoesNotExist(MagicMock(), owner, repo, branch)
                return MagicMock(commit="c0", name=branch)

            mock_branch_get.side_effect = branch_get_side_effect

            with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
                self.cmd._create_pr(args)
            return mock_pr_create.call_args.kwargs["target_branch"]

    def test_fallback_to_default_branch_when_source_branch_missing(self):
        target = self._call_create_pr(source_branch="new-feat", target_branch=None, branch_exists_on_target=False)
        self.assertEqual(target, "factory")

    def test_target_matches_source_branch_when_it_exists(self):
        target = self._call_create_pr(source_branch="new-feat", target_branch=None, branch_exists_on_target=True)
        self.assertEqual(target, "new-feat")

    def test_for_prefix_branch(self):
        target = self._call_create_pr(source_branch="for/staging/my-feat", target_branch=None)
        self.assertEqual(target, "staging")

    def test_explicit_target_branch(self):
        target = self._call_create_pr(source_branch="my-feat", target_branch="production")
        self.assertEqual(target, "production")


if __name__ == "__main__":
    unittest.main()
