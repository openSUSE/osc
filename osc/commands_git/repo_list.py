import sys

import osc.commandline_git


class RepoListCommand(osc.commandline_git.GitObsCommand):
    """
    List repos

    Required permissions:
        read:organization
        read:user
    """

    name = "list"
    parent = "RepoCommand"

    def init_arguments(self):
        self.parser.add_argument(
            "--org",
            dest="org_list",
            action="append",
            help="List repos owned by the specified organizations",
        )
        self.parser.add_argument(
            "--user",
            dest="user_list",
            action="append",
            help="List repos owned by the specified users",
        )
        self.add_argument(
            "--export",
            action="store_true",
            help="Show json objects instead of human readable text",
        )

    def run(self, args):
        from osc import gitea_api

        if not args.org_list and not args.user_list:
            self.parser.error("Please specify at least one --org or --user option")

        self.print_gitea_settings()

        repo_obj_list = []

        for org in sorted(set(args.org_list or [])):
            repo_obj_list += gitea_api.Repo.list_org_repos(self.gitea_conn, org)

        for user in sorted(set(args.user_list or [])):
            repo_obj_list += gitea_api.Repo.list_user_repos(self.gitea_conn, user)

        if args.export:
            print(gitea_api.json_dumps(repo_obj_list, indent=4, sort_keys=True))
        else:
            for repo_obj in sorted(repo_obj_list):
                print(f"{repo_obj.owner}/{repo_obj.repo}")

        print("", file=sys.stderr)
        print(f"Total repos: {len(repo_obj_list)}", file=sys.stderr)
