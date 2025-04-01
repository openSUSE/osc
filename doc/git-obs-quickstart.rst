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
  For typical use, ``read,write`` permissions for ``repository`` and ``user`` should be sufficient.
- Once you hit the "Generate Token" button, the page reloads and the token appears in the blue rectangle on top.
  This is the only chance to copy it because it will never show up again.


Add a login entry to the git-obs configuration file
---------------------------------------------------

- Run the following command, replacing the placeholders with your actual values::

    git-obs login add opensuse --url https://src.opensuse.org --user USER [--token TOKEN] [--set-as-default]

- If the ``--token`` option in the command above is omitted,
  the command will prompt you to enter the token securely.


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
