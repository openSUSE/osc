import osc.commandline_git


class PullRequestCommentCommand(osc.commandline_git.GitObsCommand):
    """
    Comment pull requests
    """

    name = "comment"
    parent = "PullRequestCommand"

    def init_arguments(self):
        self.add_argument(
            "id",
            nargs="+",
            help="Pull request ID in <owner>/<repo>#<number> format",
        )
        self.add_argument(
            "-m",
            "--message",
            help="Text of the comment",
        )

    def run(self, args):
        from osc import gitea_api
        from osc.output import tty

        pull_request_ids = args.id

        if args.message:
            message = args.message
        else:
            template = "\n".join(
                [
                    "\n",
                    "# Commenting the following pull requests:",
                    "\n".join([f"# {pr_id}" for pr_id in pull_request_ids]),
                    "\n",
                ]
            )
            message = gitea_api.edit_message(template=template)
            # remove comments
            message = "\n".join([i for i in message.splitlines() if not i.startswith("#")])

        # strip leading and trailing spaces
        message = message.strip()

        if not message:
            raise RuntimeError("Aborting operation due to empty message.")

        self.print_gitea_settings()

        print(tty.colorize("Message:", "bold"))
        print(message)
        print()

        for pr_id in pull_request_ids:
            print(f"Adding a comment to pull request {pr_id} ...")

            owner, repo, number = gitea_api.PullRequest.split_id(pr_id)
            gitea_api.PullRequest.add_comment(
                self.gitea_conn,
                owner,
                repo,
                number,
                msg=message,
            )
