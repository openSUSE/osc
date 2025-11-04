import os
from typing import Optional

import osc.commandline_git


class PullRequestDumpCommand(osc.commandline_git.GitObsCommand):
    """
    Dump a pull request to disk

    Return codes:
    - 0:   default return code
    - 1-9: reserved for error states
    - 11:  pull request(s) skipped due to no longer being open
    """
    # NOTE: the return codes are according to `git-obs pr review interactive`

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

        if not os.path.exists(os.path.join(directory, ".git")):
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
        assert git_owner.lower() == owner.lower(), f"owner does not match: {git_owner} != {owner}"
        assert git_repo.lower() == repo.lower(), f"repo does not match: {git_repo} != {repo}"

        if pr_number:
            # ``git reset`` is required for fetching the pull request into an existing branch correctly
            # without it, ``git submodule status`` is broken and returns old data
            git.reset()
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
        import shutil
        import sys
        from osc import gitea_api
        from osc import obs_api
        from osc.output import tty
        from osc.util.xml import xml_indent
        from osc.util.xml import ET

        self.print_gitea_settings()

        skipped = []
        pull_request_ids = args.id

        for pr_id in pull_request_ids:
            owner, repo, number = gitea_api.PullRequest.split_id(pr_id)
            pr_obj = gitea_api.PullRequest.get(self.gitea_conn, owner, repo, number)

            if pr_obj.state != "open":
                skipped.append(f"{owner}/{repo}#{number}")
                continue

            path = args.subdir_fmt.format(
                pr=pr_obj,
                login_name=self.gitea_login.name,
                login_user=self.gitea_login.user,
            )
            # sanitize path for os.path.join()
            path = path.strip("/")

            metadata_dir = os.path.join(path, "metadata")
            try:
                with open(os.path.join(metadata_dir, "pr.json")) as f:
                    pr_data = json.load(f)
                    if pr_data["updated_at"] == pr_obj.updated_at:
                        # no update, skip the dump
                        continue
            except FileNotFoundError:
                # no local metadata cached, we can't skip the dump
                pass

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
                        "created": review_obj.created_at,
                        "when": review_obj.updated_at,
                        "comment": review_obj.body,
                    }
                )

            # store timeline as <history/> entries
            timeline = gitea_api.IssueTimelineEntry.list(self.gitea_conn, owner, repo, number)
            xml_history_list = []
            for entry in timeline:
                if entry.is_empty():
                    xml_history_list.append(
                        {
                            "who": "",
                            "when": "",
                            "description": "ERROR: Gitea returned ``None`` instead of a timeline entry",
                            "comment": "",
                        }
                    )
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

            try:
                # remove old metadata first to ensure that we never keep any of the old files on an update
                shutil.rmtree(metadata_dir)
            except FileNotFoundError:
                pass
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

            submodule_diff = {
                "added": {},
                "removed": {},
                "unchanged": {},
                "changed": {},
            }

            # TODO: determine if the submodules point to packages or something else; submodules may point to arbitrary git repos such as other packages, projects or anything else
            all_submodules = sorted(set(base_submodules) | set(head_submodules))
            for i in all_submodules:

                if i in base_submodules:
                    url = base_submodules[i].get("url", "")
                    if not url.startswith("../../"):
                        print(f"Warning: incorrect path '{url}' in base submodule '{i}'", file=sys.stderr)

                if i in head_submodules:
                    url = head_submodules[i].get("url", "")
                    if not url.startswith("../../"):
                        print(f"Warning: incorrect path '{url}' in head submodule '{i}'", file=sys.stderr)

                if i in base_submodules and i not in head_submodules:
                    submodule_diff["removed"][i] = base_submodules[i]
                elif i not in base_submodules and i in head_submodules:
                    submodule_diff["added"][i] = head_submodules[i]
                else:
                    for key in ["branch", "path", "url"]:
                        # we don't expect migrating packages to another paths, branches etc.
                        if key not in base_submodules[i] and key in head_submodules[i]:
                            # we allow adding new keys in the pull request to fix missing data
                            pass
                        else:
                            base_value = base_submodules[i].get(key, None)
                            head_value = head_submodules[i].get(key, None)
                            assert base_value == head_value, f"Submodule metadata has changed: key='{key}', base_value='{base_value}', head_value='{head_value}'"

                    base_commit = base_submodules[i].get("commit","")
                    head_commit = head_submodules[i].get("commit","")

                    if base_commit == head_commit:
                        submodule_diff["unchanged"][i] = base_submodules[i]
                        continue

                    # we expect the data to be identical in base and head with the exception of the commit
                    # we also drop `commit` and add `base_commit` and `head_commit`
                    data = base_submodules[i].copy()
                    if base_commit:
                        del data["commit"]
                    data["base_commit"] = base_commit
                    data["head_commit"] = head_commit
                    submodule_diff["changed"][i] = data

            with open(os.path.join(metadata_dir, "submodules-diff.json"), "w", encoding="utf-8") as f:
                json.dump(submodule_diff, f, indent=4, sort_keys=True)

            referenced_pull_requests = {}
            for ref_owner, ref_repo, ref_number in pr_obj.parse_pr_references():
                ref_id = f"{ref_owner}/{ref_repo}#{ref_number}"
                referenced_pr_obj = gitea_api.PullRequest.get(self.gitea_conn, ref_owner, ref_repo, ref_number)
                referenced_pull_requests[ref_id] = referenced_pr_obj.dict()

            with open(
                os.path.join(metadata_dir, "referenced-pull-requests.json"),
                "w",
                encoding="utf-8",
            ) as f:
                json.dump(referenced_pull_requests, f, indent=4, sort_keys=True)

        if skipped:
            print(f"{tty.colorize('WARNING', 'yellow,bold')}: Skipped pull requests that were no longer open: {' '.join(skipped)}", file=sys.stderr)
            return 11

        return 0
