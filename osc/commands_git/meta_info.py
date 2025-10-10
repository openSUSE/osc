import osc.commandline_git


class MetaInfoCommand(osc.commandline_git.GitObsCommand):
    """
    Resolve and print metadata about the current checkout
    """

    name = "info"
    parent = "MetaCommand"

    def init_arguments(self):
        group = self.parser.add_mutually_exclusive_group()
        group.add_argument(
            "--type",
            action="store_true",
            help="Print type",
        )
        group.add_argument(
            "--apiurl",
            action="store_true",
            help="Print apiurl",
        )
        group.add_argument(
            "--project",
            action="store_true",
            help="Print project",
        )
        group.add_argument(
            "--package",
            action="store_true",
            help="Print package",
        )
        group.add_argument(
            "--branch",
            action="store_true",
            help="Print branch",
        )
        group.add_argument(
            "--commit",
            action="store_true",
            help="Print commit",
        )
        group.add_argument(
            "--remote",
            action="store_true",
            help="Print remote",
        )
        group.add_argument(
            "--remote-url",
            action="store_true",
            help="Print remote_url",
        )
        group.add_argument(
            "--export",
            action="store_true",
            help="Show json objects instead of human readable text",
        )

    def run(self, args):
        from osc.git_scm.store import GitStore

        store = GitStore(".")
        result = {
            "type": store.type,
            "apiurl": store.apiurl,
            "project": store.project,
            "package": store.package,
            "branch": store._git.current_branch,
            "commit": store._git.get_branch_head(),
            "remote": store._git.get_current_remote(),
            "remote_url": store._git.get_remote_url(),
        }
        if args.export:
            import json

            print(json.dumps(result, indent=4))
        elif args.type:
            print(result["type"] or "")
        elif args.apiurl:
            print(result["apiurl"] or "")
        elif args.project:
            print(result["project"] or "")
        elif args.package:
            print(result["package"] or "")
        elif args.branch:
            print(result["branch"] or "")
        elif args.commit:
            print(result["commit"] or "")
        elif args.remote:
            print(result["remote"] or "")
        elif args.remote_url:
            print(result["remote_url"] or "")
        else:
            from osc.output import KeyValueTable

            table = KeyValueTable(min_key_length=10)
            for key, value in result.items():
                table.add(key, value)
            print(str(table))
