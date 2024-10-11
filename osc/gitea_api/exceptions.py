import re

from .. import oscerr
from .connection import GiteaHTTPResponse


class GiteaException(oscerr.OscBaseError):
    def __init__(self, response: GiteaHTTPResponse):
        self.response = response

    @property
    def status(self):
        return self.response.status

    @property
    def reason(self):
        return self.response.reason

    def __str__(self):
        result = f"{self.status} {self.reason}"
        if self.response.data:
            result += f": {self.response.data}"
        return result


class BranchDoesNotExist(GiteaException):
    def __init__(self, response: GiteaHTTPResponse, owner: str, repo: str, branch: str):
        super().__init__(response)
        self.owner = owner
        self.repo = repo
        self.branch = branch

    def __str__(self):
        result = f"Repo '{self.owner}/{self.repo}' does not contain branch '{self.branch}'"
        return result


class BranchExists(GiteaException):
    def __init__(self, response: GiteaHTTPResponse, owner: str, repo: str, branch: str):
        super().__init__(response)
        self.owner = owner
        self.repo = repo
        self.branch = branch

    def __str__(self):
        result = f"Repo '{self.owner}/{self.repo}' already contains branch '{self.branch}'"
        return result


class ForkExists(GiteaException):
    def __init__(self, response: GiteaHTTPResponse, owner: str, repo: str):
        super().__init__(response)
        self.owner = owner
        self.repo = repo

        regex = re.compile(r".*fork path: (?P<owner>[^/]+)/(?P<repo>[^\]]+)\].*")
        match = regex.match(self.response.json()["message"])
        assert match is not None
        self.fork_owner = match.groupdict()["owner"]
        self.fork_repo = match.groupdict()["repo"]

    def __str__(self):
        result = f"Repo '{self.owner}/{self.repo}' is already forked as '{self.fork_owner}/{self.fork_repo}'"
        return result


class InvalidSshPublicKey(oscerr.OscBaseError):
    def __str__(self):
        return "Invalid public ssh key"
