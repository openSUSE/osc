import os
from typing import Optional

import osc.commandline_git


class PullRequestDumpCommand(osc.commandline_git.GitObsCommand):
    """
    Dump a pull request to disk
    """

    name = "dump"
    parent = "PullRequestCommand"

    def init_arguments(self):
        from osc.commandline_git import complete_checkout_pr

        self.add_argument(
            "--subdir-fmt",
            metavar="FMT",
            default="{pr.base_owner}/{pr.base_repo}/{pr.number}",
            help=(
                "Formatting string for a subdir associated with each pull request\n"
                "(default: '{pr.base_owner}/{pr.base_repo}/{pr.number}')\n"
                "Available values:\n"
                "  - 'pr' object which is an instance of 'osc.gitea_api.PullRequest'\n"
                "  - 'login_name', 'login_user' from the currently used Gitea login entry"
            ),
        )

        self.add_argument(
            "id",
            nargs="+",
            help="Pull request ID in <owner>/<repo>#<number> format",
        ).completer = complete_checkout_pr

    def clone_or_update(
        self,
        owner: str,
        repo: str,
        *,
        pr_number: Optional[int] = None,
        branch: Optional[str] = None,
        commit: str,
        directory: str,
        reference: Optional[str] = None,
    ):
        from osc import gitea_api

        if not pr_number and not branch:
            raise ValueError("Either 'pr_number' or 'branch' must be specified")

        if not os.path.isdir(os.path.join(directory, ".git")):
            gitea_api.Repo.clone(
                self.gitea_conn,
                owner,
                repo,
                directory=directory,
                add_remotes=True,
                reference=reference,
            )

        git = gitea_api.Git(directory)
        git_owner, git_repo = git.get_owner_repo()
        assert git_owner == owner, f"owner does not match: {git_owner} != {owner}"
        assert git_repo == repo, f"repo does not match: {git_repo} != {repo}"

        if pr_number:
            # checkout the pull request and check if HEAD matches head/sha from Gitea
            pr_branch = git.fetch_pull_request(pr_number, commit=commit, force=True)
            git.switch(pr_branch)
            head_commit = git.get_branch_head()
            assert (
                head_commit == commit
            ), f"HEAD of the current branch '{pr_branch}' is '{head_commit}' but the Gitea pull request points to '{commit}'"
        elif branch:
            git.switch(branch)

            # run 'git fetch' only when the branch head is different to the expected commit
            head_commit = git.get_branch_head()
            if head_commit != commit:
                git.fetch()

            if not git.branch_contains_commit(commit=commit, remote="origin"):
                raise RuntimeError(f"Branch '{branch}' doesn't contain commit '{commit}'")
            git.reset(commit, hard=True)
        else:
            raise ValueError("Either 'pr_number' or 'branch' must be specified")

    def run(self, args):
        import json
        import re
        from osc import gitea_api
        from osc import obs_api
        from osc.util.xml import xml_indent
        from osc.util.xml import ET

        self.print_gitea_settings()

        pull_request_ids = args.id

        for pr_id in pull_request_ids:
            owner, repo, number = gitea_api.PullRequest.split_id(pr_id)
            pr_obj = gitea_api.PullRequest.get(self.gitea_conn, owner, repo, number)

            path = args.subdir_fmt.format(
                pr=pr_obj,
                login_name=self.gitea_login.name,
                login_user=self.gitea_login.user,
            )
            # sanitize path for os.path.join()
            path = path.strip("/")

            review_obj_list = pr_obj.get_reviews(self.gitea_conn)

            # see https://github.com/go-gitea/gitea/blob/main/modules/structs/pull_review.go - look for "type ReviewStateType string"
            state_map = {
                "APPROVED": "accepted",
                "REQUEST_CHANGES": "declined",
                "REQUEST_REVIEW": "new",  # review hasn't started
                "PENDING": "review",  # review is in progress
                "COMMENT": "deleted",  # just to make XML validation happy, we'll replace it with "comment" later
            }

            xml_review_list = []
            for review_obj in review_obj_list:
                xml_review_list.append(
                    {
                        "state": state_map[review_obj.state],
                        "who": review_obj.who,
                        "created": review_obj.submitted_at,
                        "when": review_obj.updated_at,
                        "comment": review_obj.body,
                    }
                )

            # store timeline as <history/> entries
            timeline = gitea_api.IssueTimelineEntry.list(self.gitea_conn, owner, repo, number)
            xml_history_list = []
            for entry in timeline:
                if entry.is_empty():
                    import sys
                    print(f"Warning ignoring empty IssueTimelineEntry", file=sys.stderr)
                    continue

                text, body = entry.format()
                if text is None:
                    continue
                xml_history_list.append(
                    {
                        "who": entry.user,
                        "when": gitea_api.dt_sanitize(entry.created_at),
                        "description": text,
                        "comment": body or "",
                    }
                )

            req = obs_api.Request(
                id=pr_id,
                title=pr_obj.title,
                description=pr_obj.body,
                creator=pr_obj.user,
                # each pull request maps to only one action
                action_list=[
                    {
                        "type": "submit",
                        "source": {
                            "project": pr_obj.head_owner,
                            "package": pr_obj.head_repo,
                            "rev": pr_obj.head_commit,
                        },
                        "target": {
                            "project": pr_obj.base_owner,
                            "package": pr_obj.base_repo,
                        },
                    },
                ],
                review_list=xml_review_list,
                history_list=xml_history_list,
            )

            # HACK: changes to request XML that are not compatible with OBS
            req_xml = req.to_xml()

            req_xml_action = req_xml.find("action")
            assert req_xml_action is not None
            req_xml_action.attrib["type"] = "gitea-pull-request"
            req_xml_action.insert(
                0,
                ET.Comment(
                    "The type='gitea-pull-request' attribute value is a custom extension to the OBS XML schema."
                ),
            )

            req_xml_action_source = req_xml_action.find("source")
            assert req_xml_action_source is not None
            req_xml_action_source.append(
                ET.Comment("The 'branch' attribute is a custom extension to the OBS XML schema.")
            )
            req_xml_action_source.attrib["branch"] = pr_obj.head_branch

            req_xml_action_target = req_xml_action.find("target")
            assert req_xml_action_target is not None
            req_xml_action_target.append(
                ET.Comment("The 'rev' and 'branch' attributes are custom extensions to the OBS XML schema.")
            )
            req_xml_action_target.attrib["rev"] = pr_obj.base_commit
            req_xml_action_target.attrib["branch"] = pr_obj.base_branch

            req_xml_review_list = req_xml.findall("review")
            for req_xml_review in req_xml_review_list:
                if req_xml_review.attrib["state"] == "deleted":
                    req_xml_review.attrib["state"] = "comment"
                    req_xml_review.insert(
                        0,
                        ET.Comment("The state='comment' attribute value is a custom extension to the OBS XML schema."),
                    )

            metadata_dir = os.path.join(path, "metadata")
            os.makedirs(metadata_dir, exist_ok=True)

            with open(os.path.join(metadata_dir, "obs-request.xml"), "wb") as f:
                xml_indent(req_xml)
                ET.ElementTree(req_xml).write(f, encoding="utf-8")

            with open(os.path.join(metadata_dir, "pr.json"), "w", encoding="utf-8") as f:
                json.dump(pr_obj._data, f, indent=4, sort_keys=True)

            with open(os.path.join(metadata_dir, "base.json"), "w", encoding="utf-8") as f:
                json.dump(pr_obj._data["base"], f, indent=4, sort_keys=True)

            with open(os.path.join(metadata_dir, "head.json"), "w", encoding="utf-8") as f:
                json.dump(pr_obj._data["head"], f, indent=4, sort_keys=True)

            with open(os.path.join(metadata_dir, "reviews.json"), "w", encoding="utf-8") as f:
                json.dump([i._data for i in review_obj_list], f, indent=4, sort_keys=True)

            with open(os.path.join(metadata_dir, "timeline.json"), "w", encoding="utf-8") as f:
                # the list doesn't come from Gitea API but is post-processed for our overall sanity
                json.dump(xml_history_list, f, indent=4, sort_keys=True)

            base_dir = os.path.join(path, "base")
            # we must use the `merge_base` instead of `head_commit`, because the latter changes after merging the PR and the `base` directory would contain incorrect data
            self.clone_or_update(owner, repo, branch=pr_obj.base_branch, commit=pr_obj.merge_base, directory=base_dir)

            head_dir = os.path.join(path, "head")
            self.clone_or_update(
                owner, repo, pr_number=pr_obj.number, commit=pr_obj.head_commit, directory=head_dir, reference=base_dir
            )

            with open(os.path.join(metadata_dir, "submodules-base.json"), "w", encoding="utf-8") as f:
                base_submodules = gitea_api.Git(base_dir).get_submodules()
                json.dump(base_submodules, f, indent=4, sort_keys=True)

            with open(os.path.join(metadata_dir, "submodules-head.json"), "w", encoding="utf-8") as f:
                head_submodules = gitea_api.Git(head_dir).get_submodules()
                json.dump(head_submodules, f, indent=4, sort_keys=True)

            # diff submodules

            submodule_diff = {
                "added": {},
                "removed": {},
                "unchanged": {},
                "changed": {},
            }

            # TODO: determine if the submodules point to packages or something else; submodules may point to arbitrary git repos such as other packages, projects or anything else
            all_submodules = sorted(set(base_submodules) | set(head_submodules))
            for i in all_submodules:
                if i in base_submodules and i not in head_submodules:
                    submodule_diff["removed"][i] = base_submodules[i]
                elif i not in base_submodules and i in head_submodules:
                    submodule_diff["added"][i] = head_submodules[i]
                else:
                    for key in ["branch", "path", "url"]:
                        # we don't expect migrating packages to another paths, branches etc.
                        assert base_submodules[i].get(key, None) == head_submodules[i].get(key, None)

                    if base_submodules[i]["commit"] == head_submodules[i]["commit"]:
                        submodule_diff["unchanged"][i] = base_submodules[i]
                        continue

                    # we expect the data to be identical in base and head with the exception of the commit
                    # we also drop `commit` and add `base_commit` and `head_commit`
                    data = base_submodules[i].copy()
                    del data["commit"]
                    data["base_commit"] = base_submodules[i]["commit"]
                    data["head_commit"] = head_submodules[i]["commit"]
                    submodule_diff["changed"][i] = data

            with open(os.path.join(metadata_dir, "submodules-diff.json"), "w", encoding="utf-8") as f:
                json.dump(submodule_diff, f, indent=4, sort_keys=True)

            linked_prs = {}

            # body may contain references with both https:// or without, which look indetical in UI. so we must handle both cases:
            for url in re.findall(r"https?://[^\s]+/pulls/\d+", pr_obj.body):
                if not self.gitea_conn.host in url:
                    print(f"ignoring PR {url}")
                    linked_prs[url] = None
                    continue

                print(f"Linking PR {url}...")
                _, _, linked_id = url.partition(self.gitea_conn.host + "/")

                try:
                    linked_owner, linked_repo, linked_number = gitea_api.PullRequest.split_id(linked_id)
                    linked_pr_obj = gitea_api.PullRequest.get(self.gitea_conn, linked_owner, linked_repo, linked_number)
                    if linked_pr_obj is None:
                        linked_prs[url] = None
                    else:
                        linked_prs[url] = linked_pr_obj.to_light_dict()
                except:
                    linked_prs[url] = None

            for m in re.findall(r"([^\s\/]+)\/([^\s\/]+)\#(\d+)", pr_obj.body):
                uri = f"{m[0]}/{m[1]}#{m[2]}"
                print(f"Linking PR {uri}...")

                try:
                    linked_pr_obj = gitea_api.PullRequest.get(self.gitea_conn, m[0], m[1], m[2])
                    if linked_pr_obj is None:
                        linked_prs[uri] = None
                    else:
                        linked_prs[uri] = linked_pr_obj.to_light_dict()
                except:
                    linked_prs[uri] = None

            with open(
                os.path.join(metadata_dir, "referenced-pull-requests.json"),
                "w",
                encoding="utf-8",
            ) as f:
                json.dump(linked_prs, f, indent=4, sort_keys=True)
