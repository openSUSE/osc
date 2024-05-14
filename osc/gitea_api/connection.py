import http.client
import json
import urllib.parse
from typing import List
from typing import Optional
from typing import Tuple
from typing import Union

import urllib3

from .exceptions import GiteaBranchExists
from .exceptions import GiteaException
from .exceptions import GiteaForkExists


class GiteaConnection:
    def __init__(self, url: str, auth_token: Optional[str] = None):
        self.url = url
        self.auth_token = auth_token

        parsed_url = urllib.parse.urlparse(self.url, scheme="https")
        if parsed_url.scheme == "http":
            ConnectionClass = urllib3.connection.HTTPConnection
        elif parsed_url.scheme == "https":
            ConnectionClass = urllib3.connection.HTTPSConnection
        else:
            raise ValueError(f"Unsupported scheme in Gitea url '{url}'")

        self.conn = ConnectionClass(host=parsed_url.hostname, port=parsed_url.port)

        if parsed_url.scheme == "https":
            # needed to avoid: AttributeError: 'HTTPSConnection' object has no attribute 'assert_hostname'. Did you mean: 'server_hostname'?
            self.conn.set_cert()

    def _request(
        self, method, url, json_data: Optional[dict] = None
    ) -> Tuple[http.client.HTTPResponse, Union[dict, list]]:
        headers = {
            "Content-Type": "application/json",
        }
        if self.auth_token:
            headers["Authorization"] = f"token {self.auth_token}"

        if json_data:
            json_data = dict(
                ((key, value) for key, value in json_data.items() if value is not None)
            )

        body = json.dumps(json_data) if json_data else None

        self.conn.request(method, url, body, headers)
        response = self.conn.getresponse()

        if response.code // 100 != 2:
            raise GiteaException(response)

        return response, json.load(response)

    def _makeurl(self, *path: List[str]):
        path = ["", "api", "v1"] + [urllib.parse.quote(i, safe="/:") for i in path]
        path_str = "/".join(path)
        return path_str

    def branch(
        self,
        owner: str,
        repo: str,
        *,
        new_branch_name: str,
        old_ref_name: Optional[str] = None,
    ):
        """
        Create a new branch in a repository.

        :param owner: Owner of the repo.
        :param repo: Name of the repo.
        :param new_branch_name: Name of the branch to create.
        :param old_ref_name: Name of the old branch/tag/commit to create from.
        """
        json_data = {
            "new_branch_name": new_branch_name,
            "old_ref_name": old_ref_name,
        }
        url = self._makeurl("repos", owner, repo, "branches")
        try:
            return self._request("POST", url, json_data=json_data)
        except GiteaException as e:
            if e.code == 409:
                raise GiteaBranchExists(e.response, owner, repo, new_branch_name)
            raise

    def fork(
        self,
        owner: str,
        repo: str,
        *,
        new_repo_name: Optional[str] = None,
        target_org: Optional[str] = None,
    ):
        """
        Fork a repository.

        :param owner: Owner of the repo.
        :param repo: Name of the repo.
        :param new_repo_name: Name of the forked repository.
        :param target_org: Name of the organization, if forking into organization.
        """

        json_data = {
            "name": new_repo_name,
            "organization": target_org,
        }
        url = self._makeurl("repos", owner, repo, "forks")
        try:
            return self._request("POST", url, json_data=json_data)
        except GiteaException as e:
            if e.code == 409:
                raise GiteaForkExists(e.response)
            raise
