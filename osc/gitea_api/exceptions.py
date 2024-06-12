import http.client
import json
import re
from typing import Optional
from typing import Tuple


class GiteaException(Exception):
    def __init__(self, response: http.client.HTTPResponse):
        self.response = response

    @property
    def code(self):
        return self.response.code

    @property
    def reason(self):
        return self.response.reason

    @property
    def body(self):
        return self.response.read().decode("utf-8")

    @property
    def data(self):
        return json.load(self.response)

    def __str__(self):
        result = f"{self.code} {self.reason}"
        if self.body:
            result += f": {self.body}"
        return result


class GiteaBranchExists(GiteaException):
    def __init__(
        self, response: http.client.HTTPResponse, owner: str, repo: str, branch: str
    ):
        super().__init__(response)
        self.owner = owner
        self.repo = repo
        self.branch = branch

    def __str__(self):
        result = f"{self.code} {self.reason}: The branch '{self.branch}' already exists in {self.owner}/{self.repo}"
        return result


class GiteaForkExists(GiteaException):
    def __init__(self, response: http.client.HTTPResponse):
        super().__init__(response)
        regex = re.compile(r".*fork path: (?P<owner>[^/]+)/(?P<repo>[^\]]+)\].*")
        match = regex.match(self.data["message"])
        self.owner = match.groupdict()["owner"]
        self.repo = match.groupdict()["repo"]

    def __str__(self):
        result = f"{self.code} {self.reason}: The fork '{self.owner}/{self.repo}' already exists"
        return result
