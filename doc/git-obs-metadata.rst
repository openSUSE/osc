================
git-obs Metadata
================

After cloning a git repo, we only have a remote URL.
That is not sufficient data for running commands as ``osc build``
and we need to provide information that binds the current checkout
with a build environment that is a project in an OBS instance.

Since we don't want to be providing the values by hand any time we run
``osc`` or ``git-obs``, we need to store the information.

Using ``git config`` turned to be quite cumbersome, because
we need to store relatively large files such as buildinfo and buildconfig.

We ended up using the following locations:

  - ``.git/obs/<branch>/meta.json`` for metadata
  - ``.git/obs/<branch>/cache/*`` for buildconfig, buildinfo, last_buildroot and any other disposable files


Resolving metadata
==================

The following sections describe the order in which individual fields should be resolved.
The actual code and workflow are different.
All the metadata that should be retrieved from Gitea need to be manually stored
using ``git-obs -G <login> meta pull`` into the local metadata store.


Project checkout
----------------

- ``apiurl``

  - read ``obs_apiurl`` from ``.git/obs/<branch>/meta.yaml``
  - read ``obs_apiurl`` from ``_manifest`` (should be the default)
  - read ``_apiurl`` from ``.osc`` that is next to ``.git``
  - read ``obs_apiurl`` from Gitea

    - repo: ``obs/configuration``
    - file: ``configuration.yaml``
    - branch: ``main``

- ``project``

  - read ``obs_project`` from ``.git/obs/<branch>/meta.yaml``
  - read ``obs_project`` from ``_manifest`` (should be the default)
  - read ``_project`` from ``.osc`` that is next to ``.git``

- ``package``
  - not applicable


Standalone package checkout
---------------------------

- ``apiurl``

  - read ``obs_apiurl`` from  ``.git/obs/<branch>/meta.yaml``
  - read ``obs_apiurl`` from Gitea

    - repo: ``<owner>/_ObsPrj``
    - file: ``_manifest``
    - branch: matching the current branch of the package

  - read ``obs_apiurl`` from Gitea

    - repo: ``obs/configuration``
    - file: ``configuration.yaml``
    - branch: main

- ``project``

  - read ``obs_project`` from ``.git/obs/<branch>/meta.yaml``
  - read ``obs_project`` from Gitea

    - repo: ``<owner>/_ObsPrj``
    - file: ``_manifest``
    - branch: matching the current branch of the package

- ``package``

  - read ``obs_package`` from ``.git/obs/<branch>/meta.yaml``
  - read ``repo`` from the current remote URL
  - use the directory name


Preconditions for the following scenarios
-----------------------------------------

- Project in the parent directory tree must be detected first.
- The package must be located under a location specified in project's ``_manifest``.


Package checkout in a project checkout (package lives in a submodule)
---------------------------------------------------------------------

- ``apiurl``

  - read ``obs_apiurl`` from ``.git/obs/<branch>/meta.yaml``
  - read ``obs_apiurl`` from the parent "Project checkout" (see above)

    - branch: current
    - the project checkout lives in the directory tree above the current git's topdir

- ``project``

  - read ``obs_project`` from ``.git/obs/<branch>/meta.yaml``
  - read ``obs_project`` from the parent "Project checkout" (see above)

    - branch: current
    - the project checkout lives in the directory tree above the current git's topdir

- ``package``

  - read ``obs_package`` from ``.git/obs/<branch>/meta.yaml``
  - read ``repo`` from the current remote URL
  - use the directory name


Package directory in a project checkout (package lives in the project)
----------------------------------------------------------------------

- ``apiurl``

  - read ``obs_apiurl`` from ``.git/obs/<branch>/meta.yaml``
  - read ``obs_apiurl`` from the parent "Project checkout" (see above)

    - branch: current
    - the project checkout lives in the same git repo

- ``project``

  - read ``obs_project`` from ``.git/obs/<branch>/meta.yaml``
  - read ``obs_project`` from the parent "Project checkout" (see above)

    - branch: current
    - the project checkout lives in the same git repo

- ``package``

  - use the directory name
