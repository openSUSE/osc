import os
import subprocess
from typing import Optional

from .connection import Connection
from .connection import GiteaHTTPResponse
from .exceptions import BranchDoesNotExist
from .exceptions import BranchExists
from .exceptions import ForkExists
from .exceptions import GiteaException
from .user import get_user


def get_repo(
    conn: Connection,
    owner: str,
    repo: str,
) -> GiteaHTTPResponse:
    """
    Retrieve details about a repository.

    :param conn: Gitea ``Connection`` instance.
    :param owner: Owner of the repo.
    :param repo: Name of the repo.
    """
    url = conn.makeurl("repos", owner, repo)
    return conn.request("GET", url)


def get_branch(
    conn: Connection,
    owner: str,
    repo: str,
    branch: str,
) -> GiteaHTTPResponse:
    """
    Retrieve details about a repository.

    :param conn: Gitea ``Connection`` instance.
    :param owner: Owner of the repo.
    :param repo: Name of the repo.
    :param branch: Name of the branch.
    """
    url = conn.makeurl("repos", owner, repo, "branches", branch)
    try:
        return conn.request("GET", url)
    except GiteaException as e:
        if e.status == 404:
            raise BranchDoesNotExist(e.response, owner, repo, branch) from None
        raise


def branch_repo(
    conn: Connection,
    owner: str,
    repo: str,
    *,
    old_ref_name: Optional[str] = None,
    new_branch_name: str,
    exist_ok: bool = False,
) -> GiteaHTTPResponse:
    """
    Create a new branch in a repository.

    :param conn: Gitea ``Connection`` instance.
    :param owner: Owner of the repo.
    :param repo: Name of the repo.
    :param old_ref_name: Name of the old branch/tag/commit to create from.
    :param new_branch_name: Name of the branch to create.
    :param exist_ok: A ``BranchExists`` exception is raised when the target exists. Set to ``True`` to avoid throwing the exception.
    """
    json_data = {
        "new_branch_name": new_branch_name,
        "old_ref_name": old_ref_name,
    }
    url = conn.makeurl("repos", owner, repo, "branches")
    try:
        return conn.request("POST", url, json_data=json_data)
    except GiteaException as e:
        if e.status == 409:
            if exist_ok:
                return get_branch(conn, owner, repo, new_branch_name)
            raise BranchExists(e.response, owner, repo, new_branch_name) from None
        raise


def list_branches(
    conn: Connection,
    owner: str,
    repo: str,
) -> GiteaHTTPResponse:
    url = conn.makeurl("repos", owner, repo, "branches")
    # XXX: returns 'null' when there are no branches; an empty list would be a better API
    return conn.request("GET", url)


def fork_repo(
    conn: Connection,
    owner: str,
    repo: str,
    *,
    new_repo_name: Optional[str] = None,
    target_org: Optional[str] = None,
    exist_ok: bool = False,
) -> GiteaHTTPResponse:
    """
    Fork a repository.

    :param conn: Gitea ``Connection`` instance.
    :param owner: Owner of the repo.
    :param repo: Name of the repo.
    :param new_repo_name: Name of the forked repository.
    :param target_org: Name of the organization, if forking into organization.
    :param exist_ok: A ``ForkExists`` exception is raised when the target exists. Set to ``True`` to avoid throwing the exception.
    """

    json_data = {
        "name": new_repo_name,
        "organization": target_org,
    }
    url = conn.makeurl("repos", owner, repo, "forks")
    try:
        return conn.request("POST", url, json_data=json_data)
    except GiteaException as e:
        # use ForkExists exception to parse fork_owner and fork_repo from the response
        fork_exists_exception = ForkExists(e.response, owner, repo)
        if e.status == 409:
            if exist_ok:
                return get_repo(conn, fork_exists_exception.fork_owner, fork_exists_exception.fork_repo)
            raise fork_exists_exception from None
        raise


def list_forks(
    conn: Connection,
    owner: str,
    repo: str,
) -> GiteaHTTPResponse:
    url = conn.makeurl("repos", owner, repo, "forks")
    return conn.request("GET", url)


def clone_repo(
    conn: Connection,
    owner: str,
    repo: str,
    *,
    directory: Optional[str] = None,
    cwd: Optional[str] = None,
    anonymous: bool = False,
    add_remotes: bool = False,
) -> str:
    """
    Clone a repository, return absolute path to it.

    :param conn: Gitea ``Connection`` instance.
    :param owner: Owner of the repo.
    :param repo: Name of the repo.
    :param directory: The name of a new directory to clone into. Defaults to the repo name.
    :param cwd: Working directory. Defaults to the current working directory.
    :param anonymous: Whether to use``clone_url`` for an anonymous access or use authenticated ``ssh_url``.
    :param add_remotes: Determine and add 'parent' or 'fork' remotes to the cloned repo.
    """

    cwd = os.path.abspath(cwd) if cwd else os.getcwd()
    directory = directory if directory else repo
    # it's perfectly fine to use os.path.join() here because git can take an absolute path
    directory_abspath = os.path.join(cwd, directory)

    repo_data = get_repo(conn, owner, repo).json()
    clone_url = repo_data["clone_url"] if anonymous else repo_data["ssh_url"]

    remotes = {}
    if add_remotes:
        user = get_user(conn).json()
        if repo_data["owner"]["login"] == user["login"]:
            # we're cloning our own repo, setting remote to the parent (if exists)
            parent = repo_data["parent"]
            remotes["parent"] = parent["clone_url"] if anonymous else parent["ssh_url"]
        else:
            # we're cloning someone else's repo, setting remote to our fork (if exists)
            forks = list_forks(conn, owner, repo).json()
            forks = [i for i in forks if i["owner"]["login"] == user["login"]]
            if forks:
                assert len(forks) == 1
                fork = forks[0]
                remotes["fork"] = fork["clone_url"] if anonymous else fork["ssh_url"]

    # clone
    cmd = ["git", "clone", clone_url, directory]
    subprocess.run(cmd, cwd=cwd, check=True)

    # setup remotes
    for name, url in remotes.items():
        cmd = ["git", "-C", directory_abspath, "remote", "add", name, url]
        subprocess.run(cmd, cwd=cwd, check=True)

    return directory_abspath
