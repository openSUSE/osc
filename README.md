[![unit tests](https://github.com/openSUSE/osc/actions/workflows/tests.yaml/badge.svg)](https://github.com/openSUSE/osc/actions/workflows/tests.yaml)
[![docs](https://readthedocs.org/projects/opensuse-commander/badge/?version=latest)](https://opensuse-commander.readthedocs.io/en/latest/?badge=latest)
[![codecov](https://codecov.io/gh/openSUSE/osc/branch/master/graph/badge.svg)](https://codecov.io/gh/openSUSE/osc)
[![code climate](https://github.com/openSUSE/osc/actions/workflows/codeql.yml/badge.svg)](https://github.com/openSUSE/osc/actions/workflows/codeql.yml)
[![contributors](https://img.shields.io/github/contributors/openSUSE/osc.svg)](https://github.com/openSUSE/osc/graphs/contributors)


# openSUSE Commander

openSUSE Commander (osc) is a command-line interface to the
[Open Build Service (OBS)](https://github.com/openSUSE/open-build-service/).


## Installation

RPM packages are available in the [openSUSE:Tools](http://download.opensuse.org/repositories/openSUSE:/Tools/) repository.

    zypper addrepo --repo http://download.opensuse.org/repositories/openSUSE:/Tools/openSUSE_Tumbleweed/openSUSE:Tools.repo
    zypper install osc

**Unstable** RPM packages are available in the [OBS:Server:Unstable](http://download.opensuse.org/repositories/OBS:/Server:/Unstable/) repository.

    zypper addrepo --repo http://download.opensuse.org/repositories/OBS:/Server:/Unstable/openSUSE_Factory/OBS:Server:Unstable.repo
    zypper install osc

To install from git, do

    ./setup.py build
    ./setup.py install

Alternatively, you can directly use `./osc-wrapper.py` from the source directory,
which is easier if you develop on osc.


## Configuration

When you use osc for the first time, it will ask you for your username and
password, and store it in `~/.config/osc/oscrc`.


## Keyrings

Osc can store passwords in keyrings instead of `~/.config/osc/oscrc`.
To use them, you need python3-keyring with a backend of your choice installed:
 - kwalletd5 (A pasword manager for KDE)
 - secrets (A password manager for GNOME)
 - python3-keyring-keyutils (A python-keyring backend for the kernel keyring)

If you want to switch to using a keyring you need to delete apiurl section
from `~/.config/osc/oscrc` and you will be asked for credentials again,
which will be then stored in the keyring application.


## Usage

For more details please check the [openSUSE wiki](https://en.opensuse.org/openSUSE:OSC).

To list existing content on the server

    osc ls                              # list projects
    osc ls Apache                       # list packages in a project
    osc ls Apache subversion            # list files of package of a project

Check out content

    osc co Apache                       # entire project
    osc co Apache subversion            # a package
    osc co Apache subversion foo        # single file

Update a working copy

     osc up
     osc up [pac_dir]                   # update a single package by its path
     osc up *                           # from within a project dir, update all packages
     osc up                             # from within a project dir, update all packages
                                        #   AND check out all newly added packages

If an update can't be merged automatically, a file is in `C` (conflict)
state, and conflicts are marked with special `<<<<<<<` and `>>>>>>>` lines.
After manually resolving the problem, use

    osc resolved foo

Upload change content

    osc ci                              # current dir
    osc ci <dir>
    osc ci file1 file2 ...

Show the status (which files have been changed locally)

    osc st
    osc st <directory>
    osc st file1 file2 ...

Mark files to be added or removed on the next 'checkin'

    osc add file1 file2 ...
    osc rm file1 file2 ...

Adds all new files in local copy and removes all disappeared files

    osc addremove

Generates a diff, to view the changes

    osc diff                            # current dir
    osc diff file1 file2 ...

Shows the build results of the package

    osc results
    osc results [repository]

Shows the log file of a package (you need to be inside a package directory)

    osc log <repository> <arch>

Shows the URLs of .repo files which are packages sources for Yum/YaST/smart

    osc repourls [dir]

Triggers a package rebuild for all repositories/architectures of a package

    osc rebuildpac [dir]

Shows available repository/build targets

    osc repository

Shows the configured repository/build targets of a project

    osc repository <project>

Shows meta information

    osc meta Apache
    osc meta Apache subversion
    osc id username

Edit meta information
(Creates new package/project if it doesn't exist)

    osc editmeta Apache
    osc editmeta Apache subversion

Update package meta data with metadata taken from spec file

    osc updatepacmetafromspec <dir>

There are other commands, which you may not need (they may be useful in scripts)

    osc repos
    osc buildconfig
    osc buildinfo

Locally build a package (see 'osc help build' for more info)

    osc build <repo> <arch> specfile [--clean|--noinit]

Update a package to a different sources (directory foo_package_source)

    cp -a foo_package_source foo
    cd foo
    osc init <prj> <pac>
    osc addremove
    osc ci
    cd $OLDPWD
    rm -r foo


## Contributing

Report [issues](https://github.com/openSUSE/osc/issues)
or submit [pull-requests](https://github.com/openSUSE/osc/pulls)
to the [osc](https://github.com/openSUSE/osc/issues) project on GitHub.


## Testing

Unit tests can be run from a git checkout by executing

    ./setup.py test
