==================
git-obs Quickstart
==================

``git-obs`` is a command-line client for interacting with Git repositories
within a Gitea instance that is part of an Open Build Service (OBS).

This quickstart guide uses the openSUSE OBS instance as an example.
You may need to adjust the specific values (like URLs) to match your own OBS instance.


Logins
======

Before executing any ``git-obs`` commands, you need to configure your
credentials, also known as logins.  These logins are shared with the ``tea``
client and are stored in ``~/.config/tea/config.yml``.

.. note::
    See ``git-obs login --help`` for all commands related to managing login entries.


Create a Gitea token
--------------------

- Visit your Gitea user's Applications settings page (Profile picture -> Settings -> Applications):
  `https://src.opensuse.org/user/settings/applications <https://src.opensuse.org/user/settings/applications>`_
- Generate a new token with a descriptive name and the necessary permissions.
  For typical use, the following permissions should be sufficient:

  - issue: read and write
  - organization: read
  - repository: read and write
  - user: read and write

- Once you hit the "Generate Token" button, the page reloads and the token appears in the blue rectangle on top.
  This is the only chance to copy it because it will never show up again.

Add your SSH key
------------------

- Visit your Gitea user's "SSH / GPG Keys" settings page (Profile picture -> Settings -> "SSH / GPG Keys"):
  `https://src.opensuse.org/user/settings/keys <https://src.opensuse.org/user/settings/keys>`_
- Add Key name and as Content the public SSH key content (e.g., from `~/.ssh/id_rsa.pub`)

  .. note::
      For HTTP Signature authentication, ``git-obs`` only supports ``RSA`` and ``ed25519`` keys.

Add a login entry to the git-obs configuration file
---------------------------------------------------

- Run the following command, replacing the placeholders with your actual values::

    git-obs login add opensuse --url https://src.opensuse.org --user USER [--token TOKEN] [--set-as-default]

- If the ``--token`` option in the command above is omitted,
  the command will prompt you to enter the token securely.

- Alternatively, you can configure a login to authenticate Gitea API requests
  by signing them with an SSH key. This method, known as HTTP Signature, is an
  alternative to using a Gitea token. Before using this method, ensure you have
  added your public SSH key to your Gitea account settings.

  - Using an SSH key file::

        git-obs login add opensuse --url https://src.opensuse.org --user USER --ssh-key /path/to/your/private_key --ssh-key-agent-pub 'SHA256:XXXXXXX'

  - Using an SSH agent (for example with a hardware token)::

        git-obs login add opensuse --url https://src.opensuse.org --user USER --ssh-agent --ssh-key-agent-pub 'SHA256:XXXXXXX'

  The ``--ssh-key-agent-pub`` argument specifies the public key's signature.

Using the login entries
-----------------------

By default, ``git-obs`` will use the default login entry (if configured).
To use a specific login entry, use the ``-G LOGIN`` command-line parameter. For example::

    git-obs -G opensuse repo clone OWNER/REPO


SSH Keys
========

Using SSH keys for authentication is a common and secure practice for Git clients.

.. note::
    See ``git-obs ssh-key --help`` for all commands related to managing login entries.

Use one of the following commands to upload your public SSH key to the Gitea server::

    git-obs ssh-key add --key PUBLIC_KEY_DATA
    git-obs ssh-key add --key-path PUBLIC_KEY_PATH


Using git with token auth instead of SSH keys
=============================================

It is possible to use Gitea token for both communicating with the Gitea API
and also for authenticating the git command.


To use token auth for git operations, switch git from using SSH to http(s)::

    git-obs login update <login> --new-git-uses-http=1

and add the following entry to ~/.config/git/config or ~/.gitconfig::

    [credential "https://src.example.com"]
        helper = "git-obs -G <login> login gitcredentials-helper"


Workflow: Making changes to packages
====================================

This workflow outlines the steps to make changes to packages using ``git-obs``.

.. note::
    See ``git-obs repo --help`` and ``git-obs pr --help``
    for all commands related to managing repositories and pull requests.


1. **Fork the repository:**

    .. code::

        git-obs -G opensuse repo fork OWNER/REPO

2. **Clone your fork:**

    .. code::

        git-obs -G opensuse repo clone FORK_OWNER/REPO

    .. note::
        The ``git-obs repo clone`` command automatically configures additional Git remotes:

        - If cloning a fork, it sets a ``parent`` remote pointing to the repository you forked from.
        - If cloning a repository you forked from, it sets a ``fork`` remote pointing to your fork.

3. **Make changes:**

  - Navigate into the cloned repository directory
  - Make a branch
  - Switch to the new branch
  - Make changes to the package sources
  - Commit your changes
  - Push your commits

4. **Create a Pull Request:**

.. code::

    git-obs -G opensuse pr create [--title TEXT] [--description TEXT]

If ``--title`` or ``--description`` are not provided, ``git-obs`` will open a text editor for you to enter them interactively.


Workflow: Retrieving sources of an existing pull request
--------------------------------------------------------

1. **Clone the repository:**

.. code::

    git-obs -G opensuse repo clone OWNER/REPO


2. **Navigate to the repository:**

.. code::

    cd REPO

3. **Checkout the pull request:**

.. code::

    git-obs -G opensuse pr checkout PULL_NUMBER [--force]

4. **Set metadata:**

.. note::
   This always needs to be done after switching to a new branch.

.. code::

    git-obs -G opensuse meta pull
    # or
    git-obs meta set [--apiurl=...] [--project=...] [--package=...]


5. **Use osc or git-obs with the local checkout**

.. code::

    osc build
    osc repos
    ...


Workflow: Forwarding sources between branches (``git-obs pr forward``)
----------------------------------------------------------------------

The ``git-obs pr forward`` command is the Git-native counterpart to ``osc sr``
across branches or code streams (for example, promoting changes from ``factory``
to a downstream release branch such as ``slfo-main`` or ``16.0``).

How it works:
~~~~~~~~~~~~~

1. **Reuses your existing fork:**
   Checks whether you already have a fork of the target repository under your
   Gitea account. If so, it reuses your existing fork without creating redundant
   repositories or affecting other remotes.

2. **Guarantees safety of your existing work:**
   The command never modifies your default branch (``main`` / ``master``) or
   any ongoing work in your other branches. Instead, it creates a dedicated,
   isolated branch specifically for the forward operation:

   .. code::

       for/<target_branch>/forward-<source_commit_sha>

   *(e.g., ``for/slfo-main/forward-7f9a2b...``)*

   Only this namespaced branch is pushed to your remote fork.

3. **Performs clean, automated synchronization:**
   The operation executes inside an isolated temporary directory. It integrates
   the changes, verifies file additions and deletions, and synchronizes any
   associated Git LFS assets.

4. **Leaves no litter on your filesystem:**
   The temporary directory is deleted automatically as soon as the command
   finishes. No residual files are left behind unless you explicitly specify
   ``--no-cleanup`` or designate a custom ``--workdir``.

5. **Submits the Pull Request:**
   Once the branch is pushed to your fork, a standard Gitea Pull Request is
   opened against the upstream target branch.


Understanding the merge modes (``--mode``):
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

When forwarding sources between branches that may have evolved separately,
you can select how changes should be reconciled:

- **``auto`` (recommended):**
  The best choice for routine forwarding. If the target branch has not diverged
  from the source branch, it simply fast-forwards without adding unnecessary merge
  commits. If the branches have diverged, it merges the source changes and
  ensures the resulting file tree matches the source state.

- **``sync``:**
  Closest to traditional OBS behavior (``osc sr``). Rather than reconciling
  disparate Git commit histories, this mode creates a single synchronization
  commit that brings the destination package contents into exact alignment with
  the source branch state. This is particularly useful when forwarding across
  distribution releases or between branches that have diverged significantly,
  ensuring the target cleanly reflects the source package without history conflicts.

- **``fast-forward``:**
  Applies changes only if the target branch can be cleanly fast-forwarded to
  the source branch. If the target branch contains independent commits not present
  in the source, the command halts without making changes. Use this when you
  strictly require a linear commit history.

- **``merge``:**
  Integrates changes by creating a merge commit on the target branch. If conflicts
  arise, incoming changes from the source take precedence, and files deleted in
  the source are cleanly removed from the target.

- **``merge-unrelated``:**
  Behaves like ``merge``, but permits combining branches that do not share a common
  historical ancestor (such as branches initialized independently in different repositories).


Usage examples:
~~~~~~~~~~~~~~~

Forward package changes from ``factory`` to ``slfo-main``:

.. code::

    git-obs -G opensuse pr forward products/slfo factory slfo-main --mode auto

Preview all planned actions without modifying remotes or creating a PR (dry-run):

.. code::

    git-obs -G opensuse pr forward products/slfo factory slfo-main --mode auto --dry-run

Provide a custom title and interactively edit the PR message:

.. code::

    git-obs -G opensuse pr forward products/slfo factory slfo-main --mode auto --title "Sync slfo-main with Factory" --edit


Workflow: Querying pull requests
--------------------------------

The following command lists all pull requests that are assigned to you for review, either directly or through group membership::

    git-obs -G opensuse pr search --review-requested


Workflow: Reviewing pull requests
---------------------------------

To start an interactive review session, run::

    git-obs -G opensuse pr review

``git-obs`` will:

  - Iterate through each pull request awaiting your review
  - Display the pull request details in a pager
  - Offer actions such as:

    - Approving the review
    - Requesting changes
    - Adding comments
    - etc.

Enhanced features
~~~~~~~~~~~~~~~~~

- **tardiff** - archives within the pull request are extracted, and their diffs are displayed
- **issue references** - TBD
- **patch references** - TBD

.. note::
    The ``git-obs pr review`` command utilizes a cache in ``~/.cache/git-obs/`` to store data, potentially including large tarballs and their diffs.

    - **Disk Space:** If you need to free up disk space, you can safely delete the contents of this cache directory.
    - **Troubleshooting:** If you encounter issues, especially with the **tardiff** functionality, clearing the cache can sometimes resolve the problems.


TODOs
=====
- Display comments
- Display state of all reviews and names of the reviewers
- Add an action to close a request without merging + provide a comment with justification with such action


Known issues
============
- If you request changes, the pull request disappears from the review query.
  Someone has to re-request the review by clicking in the Gitea web UI.
- If you're supposed to merge pull requests after completing the review,
  it's better to wait until the others are finished reviewing,
  because by approving the review, the pull request disappears from the review queue
  and it's difficult to get to the list of PRs that need to be merged.
- Reviews by groups/teams are not handled well.
  If you approve, the team disappears and gets replaced with your login.
  Then is not possible to search for such the team reviews and for example monitor
  re-review requests during a team member's absence.
