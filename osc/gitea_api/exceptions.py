import inspect
import json
import re
from typing import Optional

from .. import oscerr
from .connection import GiteaHTTPResponse


def response_to_exception(response: GiteaHTTPResponse, *, context: Optional[dict] = None):
    """
    Throw an appropriate exception based on the contents of ``response``.
    Raise generic ``GiteaException`` if no exception matches the ``response``.

    Caveats:
    - Gitea doesn't return any machine parseable data, everything is plain text
    - the errors are sometimes described in the ``message``, sometimes in the list of ``errors``
    - in some cases, it's required to provide additional context to the request, that is passed to the raised exception,
      for example: ``conn.request("GET", url, context={"owner": owner, "repo": repo})``
    """
    try:
        data = response.json()
        messages = [data["message"]] + (data.get("errors", None) or [])
    except json.JSONDecodeError:
        messages = [response.data.decode("utf-8")]

    for cls in EXCEPTION_CLASSES:
        if cls.RESPONSE_STATUS is not None and cls.RESPONSE_STATUS != response.status:
            continue

        for regex in cls.RESPONSE_MESSAGE_RE:
            for message in messages:
                match = regex.match(message)
                if match:
                    kwargs = context.copy() if context else {}
                    kwargs.update(match.groupdict())
                    return cls(response, **kwargs)

    return GiteaException(response)


class GiteaException(oscerr.OscBaseError):
    RESPONSE_STATUS: Optional[int] = None
    RESPONSE_MESSAGE_RE: list

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


class MovedPermanently(GiteaException):
    RESPONSE_STATUS = 301
    RESPONSE_MESSAGE_RE = [
        re.compile(r"(?P<message>.*)"),
    ]

    def __init__(self, response: GiteaHTTPResponse, message: str):
        super().__init__(response)
        self.message = message

    def __str__(self):
        result = (
            f"{self.RESPONSE_STATUS} Moved Permanently: {self.message}\n"
            " * Change Gitea URL to the actual location of the service\n"
            " * Check Gitea URL for errors and typos such as https:// vs http://"
        )
        return result


class BranchDoesNotExist(GiteaException):
    RESPONSE_STATUS = 404
    # modules/git/error.go:   return fmt.Sprintf("branch does not exist [name: %s]", err.Name)
    RESPONSE_MESSAGE_RE = [
        re.compile(r"branch does not exist \[name: (?P<branch>.+)\]"),
    ]

    def __init__(self, response: GiteaHTTPResponse, owner: str, repo: str, branch: str):
        super().__init__(response)
        self.owner = owner
        self.repo = repo
        self.branch = branch

    def __str__(self):
        result = f"Repo '{self.owner}/{self.repo}' does not contain branch '{self.branch}'"
        return result


class BranchExists(GiteaException):
    RESPONSE_STATUS = 409
    # models/git/branch.go:   return fmt.Sprintf("branch already exists [name: %s]", err.BranchName)
    # routers/api/v1/repo/branch.go:                  ctx.APIError(http.StatusConflict, "The branch already exists.")
    RESPONSE_MESSAGE_RE = [
        re.compile(r"branch already exists \[name: (?P<branch>.+)\]"),
        re.compile(r"The branch already exists\."),
    ]

    def __init__(self, response: GiteaHTTPResponse, owner: str, repo: str, branch: str):
        super().__init__(response)
        self.owner = owner
        self.repo = repo
        self.branch = branch

    def __str__(self):
        result = f"Repo '{self.owner}/{self.repo}' already contains branch '{self.branch}'"
        return result


class ForkExists(GiteaException):
    RESPONSE_STATUS = 409
    # services/repository/fork.go:    return fmt.Sprintf("repository is already forked by user [uname: %s, repo path: %s, fork path: %s]", err.Uname, err.RepoName, err.ForkName)
    RESPONSE_MESSAGE_RE = [
        re.compile(r"repository is already forked by user \[uname: .+, repo path: (?P<owner>.+)/(?P<repo>.+), fork path: (?P<fork_owner>.+)/(?P<fork_repo>.+)\]"),
    ]

    def __init__(self, response: GiteaHTTPResponse, owner: str, repo: str, fork_owner: str, fork_repo: str):
        super().__init__(response)
        self.owner = owner
        self.repo = repo
        self.fork_owner = fork_owner
        self.fork_repo = fork_repo

    def __str__(self):
        result = f"Repo '{self.owner}/{self.repo}' is already forked as '{self.fork_owner}/{self.fork_repo}'"
        return result


class RepoExists(GiteaException):
    RESPONSE_STATUS = 409
    # models/repo/update.go:  return fmt.Sprintf("repository already exists [uname: %s, name: %s]", err.Uname, err.Name)
    RESPONSE_MESSAGE_RE = [
        re.compile(r"^repository already exists \[uname: (?P<owner>.+), name: (?P<repo>.+)\]"),
    ]

    def __init__(self, response: GiteaHTTPResponse, owner: str, repo: str):
        super().__init__(response)
        self.owner = owner
        self.repo = repo

    def __str__(self):
        result = f"Repo '{self.owner}/{self.repo}' already exists"
        return result


class InvalidSshPublicKey(oscerr.OscBaseError):
    def __str__(self):
        return "Invalid public ssh key"


# gather all exceptions from this module that inherit from GiteaException
EXCEPTION_CLASSES = [i for i in globals().values() if hasattr(i, "RESPONSE_MESSAGE_RE") and inspect.isclass(i) and issubclass(i, GiteaException)]
