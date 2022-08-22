import os
import subprocess


def get_git_archive_version():
    """
    Return version that is set by git during `git archive`.
    The returned format is equal to what `git describe --tags` returns.
    """
    # the `version` variable contents get substituted during `git archive`
    # it requires adding this to .gitattributes: <path to this file> export-subst
    version = "$Format:%(describe:tags=true)$"
    if version.startswith(("$", "%")):
        # "$": version hasn't been substituted during `git archive`
        # "%": "Format:" and "$" characters get removed from the version string (a GitHub bug?)
        return None
    return version


def get_git_version():
    """
    Determine version from git repo by calling `git describe --tags`.
    """
    cmd = ["git", "describe", "--tags"]
    # run the command from the place where this file is placed
    # to ensure that we're in a git repo
    cwd = os.path.dirname(__file__)
    try:
        proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, cwd=cwd)
    except OSError:
        # `git` command not found
        return None
    stdout, _ = proc.communicate()

    if proc.returncode != 0:
        return None

    version = stdout.strip().decode("utf-8")
    return version


def get_version(version):
    """
    Get the most relevant version of the software:
    1. the version set during `git archive`
    2. the version from the git tags by calling `git describe --tags`
    3. the version explicitly specified in the source code

    The version conforms PEP 440.
    """
    # use version from the archive
    git_version = get_git_archive_version()

    # use version from the git repo
    if not git_version:
        git_version = get_git_version()

    # unable to determine version from git
    if not git_version:
        return version

    if "-" not in git_version:
        git_tag = git_version
        git_commits = None
        git_hash = None
    else:
        git_tag, git_commits, git_hash = git_version.rsplit("-", 2)
        git_commits = int(git_commits)
        # remove the 'g' prefix from hash
        git_hash = git_hash[1:]

    # removing "~" because it is not an allowed character in git tags
    # and also because the normalized form is (for example) 1.0.0b0
    if version and git_tag != version.replace("~", ""):
        # Git tag doesn't correspond with version specified in the source code.
        # The most common reason is that forks do not have their tags in sync with upstream.
        # In that case just return the version specified in the source code.
        return version

    result = git_tag
    if git_hash:
        result += f"+{git_commits}.git.{git_hash}"

    return result
