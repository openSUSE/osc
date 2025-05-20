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

        git.fetch()

        if pr_number:
            # checkout the pull request and check if HEAD matches head/sha from Gitea
            pr_branch = git.fetch_pull_request(pr_number, force=True)
            git.switch(pr_branch)
            head_commit = git.get_branch_head()
            assert head_commit == commit, f"HEAD of the current branch '{pr_branch}' is '{head_commit}' but the Gitea pull request points to '{commit}'"
        elif branch:
            git.switch(branch)
            if not git.branch_contains_commit(commit=commit):
                raise RuntimeError(f"Branch '{branch}' doesn't contain commit '{commit}'")
            git.reset(commit, hard=True)
        else:
            raise ValueError("Either 'pr_number' or 'branch' must be specified")

    def run(self, args):
        import json
        from osc import gitea_api
        from osc import obs_api
        from osc.util.xml import xml_indent
        from osc.util.xml import ET

        self.print_gitea_settings()

        pull_request_ids = args.id

        for pr_id in pull_request_ids:
            owner, repo, number = gitea_api.PullRequest.split_id(pr_id)
            pr_data = gitea_api.PullRequest.get(self.gitea_conn, owner, repo, number).json()
            path = os.path.join(owner, repo, str(number))

            base_owner = pr_data["base"]["repo"]["owner"]["login"]
            base_repo = pr_data["base"]["repo"]["name"]
            base_branch = pr_data["base"]["ref"]
            base_sha = pr_data["base"]["sha"]

            head_owner = pr_data["head"]["repo"]["owner"]["login"]
            head_repo = pr_data["head"]["repo"]["name"]
            head_branch = pr_data["head"]["ref"]
            head_sha = pr_data["head"]["sha"]

            reviews_data = gitea_api.PullRequest.get_reviews(self.gitea_conn, owner, repo, number).json()

            state_map = {
                "APPROVED": "accepted",
                "REQUEST_CHANGES": "declined",
                "REQUEST_REVIEW": "review",  # or "new"?
            }

            review_list = []
            for review_data in reviews_data:
                review_list.append(
                    {
                        "state": state_map[review_data["state"]],
                        "who": review_data["user"]["login"] if review_data["user"] else f"@{review_data['team']['name']}",
                        "created": review_data["submitted_at"],
                        "when": review_data["updated_at"],
                        "comment": review_data["body"],
                    }
                )

            req = obs_api.Request(
                id=pr_id,
                title=pr_data["title"],
                description=pr_data["body"],
                creator=pr_data["user"]["login"],
                # each pull request maps to only one action
                action_list=[
                    {
                        "type": "submit",
                        "source": {
                            "project": head_owner,
                            "package": head_repo,
                            "rev": head_sha,
                        },
                        "target": {
                            "project": base_owner,
                            "package": base_repo,
                        },
                    },
                ],
                review_list=review_list,
            )

            # HACK: changes to request XML that are not compatible with OBS
            req_xml = req.to_xml()

            req_xml_action = req_xml.find("action")
            assert req_xml_action is not None
            req_xml_action.attrib["type"] = "gitea-pull-request"
            req_xml_action.insert(0, ET.Comment("The type='gitea-pull-request' attribute value is a custom extension to the OBS XML schema."))

            req_xml_action_source = req_xml_action.find("source")
            assert req_xml_action_source is not None
            req_xml_action_source.append(ET.Comment("The 'branch' attribute is a custom extension to the OBS XML schema."))
            req_xml_action_source.attrib["branch"] = head_branch

            req_xml_action_target = req_xml_action.find("target")
            assert req_xml_action_target is not None
            req_xml_action_target.append(ET.Comment("The 'rev' and 'branch' attributes are custom extensions to the OBS XML schema."))
            req_xml_action_target.attrib["rev"] = base_sha
            req_xml_action_target.attrib["branch"] = base_branch

            metadata_dir = os.path.join(path, "metadata")
            os.makedirs(metadata_dir, exist_ok=True)

            with open(os.path.join(metadata_dir, "obs-request.xml"), "wb") as f:
                xml_indent(req_xml)
                ET.ElementTree(req_xml).write(f, encoding="utf-8")

            with open(os.path.join(metadata_dir, "pr.json"), "w", encoding="utf-8") as f:
                json.dump(pr_data, f, indent=4, sort_keys=True)

            with open(os.path.join(metadata_dir, "base.json"), "w", encoding="utf-8") as f:
                json.dump(pr_data["base"], f, indent=4, sort_keys=True)

            with open(os.path.join(metadata_dir, "head.json"), "w", encoding="utf-8") as f:
                json.dump(pr_data["head"], f, indent=4, sort_keys=True)

            with open(os.path.join(metadata_dir, "reviews.json"), "w", encoding="utf-8") as f:
                json.dump(reviews_data, f, indent=4, sort_keys=True)

            base_dir = os.path.join(path, "base")
            self.clone_or_update(owner, repo, branch=base_branch, commit=base_sha, directory=base_dir)

            head_dir = os.path.join(path, "head")
            self.clone_or_update(owner, repo, pr_number=number, commit=head_sha, directory=head_dir, reference=base_dir)
