# Copyright (C) 2016 Ericsson AB
# This program is free software; it may be used, copied, modified
# and distributed under the terms of the GNU General Public Licence,
# either version 2, or version 3 (at your option).
#

import os
import shutil
import sys
import glob
import hashlib
from urllib2 import HTTPError
from osc import core
from osc import conf
from oscpluginprjmake import datatypes
try:
    from lxml import etree as ET
except ImportError:
    from xml.etree import ElementTree as ET

# Returns the list of repositories for this project
def read_repositories(apiurl, prj, workdir, preload, offline):
    repos = []
    metafile = os.path.join(workdir, '_meta')
    if not os.path.exists(metafile):
        if offline:
            print 'Missing %s for offline build' % metafile
            sys.exit(1)
        fd = open(metafile, 'w+')
        try:
            fd.write(''.join(core.show_project_meta(apiurl, prj)))
        except HTTPError as e:
            reason = get_http_error_reason(e)
            raise core.oscerr.OscIOError(e,
                'Failed to download project meta for %s: %s' % (prj, reason))
        fd.close()
    try:
        xml_meta = ET.parse(metafile)
    except IOError:
        print "Cannot read file '%s'" % metafile
        sys.exit(1)
    except:
        # We have to use generic except due to different exceptions in
        # lxml and etree.
        print 'Corrupted file: %s' % metafile
        sys.exit(1)

    for r in xml_meta.findall('repository'):
        for arch in r.findall('arch'):
            repos += [(r.get('name'), arch.text)]
    return repos

# Filter given list of repositories to match name
# and/or arch. Returns a tuple containing lists of
# names and archs of the filtered repositories.
def match_repository(repositories, arg_name = None, arg_arch = None):
    repos = []
    for (repo, arch) in repositories:
        if ((arg_name is None or arg_name == repo) and
            (arg_arch is None or arg_arch == arch)):
            repos += [(repo, arch)]

    return repos

# Try to imitate parse_repoarchdescr from osc commandline
# on project level...
# Prefers repository argument to be before arch, but both ways can match.
# Returns first match of repo and arch or default repo/arch. 'args_pkg'
# is the argument list with possible repo and arch removed. 'args_ra' contains
# the possible repo and arch arguments. Raises oscerr.WrongArgs when invalid
# arguments are given.
# This logic means that a project cannot contain a package with a name
# that matches a repository name or build architecture.
def repo_arch_magic(prj, apiurl, workdir, preload, offline, args):
    repo = arch = None
    repositories = read_repositories(apiurl, prj, workdir, preload, offline)
    args_pkg = []
    args_ra = []
    for arg in args:
        if core.is_package_dir(arg):
            args_pkg += [arg]
        else:
            args_ra += [arg]
    if len(args_ra) == 0:
        repos = match_repository(repositories)
        if len(repos) != 1:
            raise core.oscerr.WrongArgs('No repository or arch specified')
    elif len(args_ra) == 1: # One argument, can be repo or arch
        repos = match_repository(repositories, arg_name = args_ra[0])
        if len(repos) == 0:
            repos = match_repository(repositories,
                arg_arch = args_ra[0])
    elif len(args_ra) == 2: # Two arguments, can be any order
        repos = match_repository(repositories, args_ra[0], args_ra[1])
        if len(repos) == 0:
            repos = match_repository(repositories,
                args_ra[1], args_ra[0])
    # Fail if we have multiple or no matches
    if len(repos) > 1:
        raise core.oscerr.WrongArgs(
            'Multiple choices for repository or arch %s' % args_ra[0])
    elif len(repos) == 0:
        if len(args_ra) == 1:
            raise core.oscerr.WrongArgs(
                'Unable to match repository or arch with %s' % args_ra[0])
        else:
            raise core.oscerr.WrongArgs(
                'Unable to match repository and arch with %s and %s'
                % (args_ra[0], args_ra[1]))
    else:
        (repo, arch) = repos[0]

    return (repo, arch, args_pkg, args_ra)

# Returns a string representing pkg state in project.
# State can be 'normal', 'added' or 'deleted'.
def get_package_state(projectdir, pkg):
    pkglist = os.path.join(projectdir, '.osc', '_packages')
    try:
        xml = ET.parse(pkglist)
    except IOError:
        print "Cannot read package file '%s'. Run osc repairwc" % pkglist
        sys.exit(1)
    except:
        # We have to use generic except due to different exceptions in
        # lxml and etree.
        print 'Corrupted file: %s' % pkglist
        sys.exit(1)
    package = None
    for package in xml.findall('package'):
        if package.get('name') == pkg:
            break
    if package is None:
        return 'unknown';
    state = package.get('state')
    if state == 'A':
        return 'added'
    elif state == 'D':
        return 'deleted'
    else:
        return 'normal'

# Find build descriptor for package. Uses logic similiar to
# parse_repoarchdescr. parse_repoarchdescr itself cannot be used
# since it wants to connect to server when guessing repo.
def find_specfile(self, pkgdir, sts):
    origdir = os.getcwd()
    os.chdir(pkgdir)
    descr = (glob.glob('*.spec') +
        glob.glob('*.dsc') + glob.glob('*.kiwi') + glob.glob('*.livebuild') +
        glob.glob('PKGBUILD') + glob.glob('build.collax'))
    extensions = ['spec', 'dsc', 'kiwi', 'livebuild']
    if len(descr) == 1:
        specfile = descr[0]
    else:
        cands = [i for i in descr for ext in extensions if os.path.basename(i)
            == '%s-%s.%s' % (pkgdir, sts.get('repo'), ext)]
        if len(cands) != 1:
            cands = [i for i in descr for ext in extensions if
                os.path.basename(i) == '%s.%s' % (pkgdir, ext)]
        if len(cands) == 1:
            specfile = cands[0]
        else:
            specfile = None
    if specfile is None:
        print('Cannot find specfile in %s (%s), excluding package.' %
            (pkgdir, sts.get('repo')))
        os.chdir(origdir)
        return None
    os.chdir(origdir)
    return os.path.join(origdir, pkgdir, specfile)

def file_to_string(filepath):
    try:
        fd = open(filepath)
        data = fd.read()
        fd.close
        return data
    except IOError as e:
        print(e)
        sys.exit(1)

# Read what packages we have checked out and where their specfiles are.
def read_packages(self, sts):
    packages = []
    for extfile in os.listdir(os.getcwd()):
        if not os.path.isdir(extfile):
            continue
        if extfile == "_project":
            continue
        if extfile in sts.get('excludes'):
            continue
        if core.is_package_dir(extfile):
            prjdir = os.getcwd()
            state = get_package_state(prjdir, extfile)
            if state == 'deleted' or state == 'unknown':
                continue
            specfile = find_specfile(self, extfile, sts)
            if specfile is None:
                continue
            package = datatypes.OBSPackage()
            package._pkgdir = os.path.abspath(extfile)
            package._name = file_to_string(os.path.join(
                package._pkgdir, '.osc', '_package')).strip()
            package._project = file_to_string(os.path.join(
                package._pkgdir, '.osc', '_project')).strip()
            package._specfile = specfile
            data = file_to_string(specfile)
            package._specfile_md5sum = hashlib.md5(data).hexdigest()
            packages.append(package)

    return packages

# Run osc make for package
def osc_make_pkg(package, progress, total, sts):
    apiurl = sts.get('apiurl')
    repo = sts.get('repo')
    arch = sts.get('arch')
    bindir = sts.get('bindir')
    prjdir = sts.get('projectdir')
    os.chdir(package._pkgdir)
    cmd = ['osc', '-A', apiurl]
    cmd += ['build']
    cmd += sts.get('makeopts')
    cmd += ['-k', bindir, '-p', bindir, repo, arch]

    if get_package_state(prjdir, package._name) == 'added':
        cmd += ['--local-package']

    if sys.stdout.isatty() and sts.get('progress'):
        print(b'\33]0;osc prjmake (%s/%s): %s\a' %
            (progress, total, package))
    rc = core.run_external(cmd[0], *cmd[1:])
    os.chdir(prjdir)
    if rc:
        return 1
    return 0

# Run osc chroot --wipe for package.
def osc_wipe(package, sts):
    os.chdir(package._pkgdir)
    cmd = ['osc', 'chroot', '--wipe', '-f']
    rc = core.run_external(cmd[0], *cmd[1:])
    os.chdir(sts.get('projectdir'))
    if rc:
        print 'osc chroot --wipe failed for %s' % package
        return 1
    return 0

def has_state(xml, state, repo = None, arch = None):
    build = xml.find('build')
    if build is not None:
        for s in build.findall(state):
            s_repo = s.get('repository')
            s_arch = s.get('arch')
            if repo is not None and arch is not None:
                if s_repo == repo and s_arch == arch:
                    return 1
            elif s_repo is not None:
                if s_repo == repo:
                    return 1
            elif s_arch is not None:
                if s_arch == arch:
                    return 1
            else:
                return 1
    return 0

def is_pkg_enabled(sts, pkg):
    metafile = os.path.join(sts.get('workdir'), '_meta')
    if os.path.exists(metafile) and os.path.isfile(metafile):
        return offline_pkg_enabled(sts, pkg)
    elif sts.get('offline'):
        print 'Unable to find _meta file: %s' % metafile
        sys.exit(1)
    else:
        return online_pkg_enabled(sts, pkg)

def online_pkg_enabled(sts, pkg):
    enabled_repos = core.get_enabled_repos_of_package(
        sts.get('apiurl'), pkg._project, pkg._name)
    enabled = 0
    for repo in enabled_repos:
        if repo.name == sts.get('repo') and repo.arch == sts.get('arch'):
            enabled = 1
            break
    return enabled

# Parse enabled package information from meta files
def offline_pkg_enabled(sts, pkg):
    repo = sts.get('repo')
    arch = sts.get('arch')
    prj_meta = os.path.join(sts.get('workdir'), '_meta')
    prj_root = ET.parse(prj_meta)

    enabled = 1
    if has_state(prj_root, 'disable'):
        enabled = 0
    if has_state(prj_root, 'enable', arch):
        enabled = 1
    elif has_state(prj_root, 'disable', arch):
        enabled = 0
    if has_state(prj_root, 'enable', repo):
        enabled = 1
    elif has_state(prj_root, 'disable', repo):
        enabled = 0
    if has_state(prj_root, 'enable', repo, arch):
        enabled = 1
    elif has_state(prj_root, 'disable', repo, arch):
        enabled = 0

    pac_meta = os.path.join(pkg._pkgdir, '.osc', '_meta')
    pac_root = ET.parse(pac_meta)

    if has_state(pac_root, 'enable'):
        enabled = 1
    elif has_state(pac_root, 'disable'):
        enabled = 0
    if has_state(pac_root, 'enable', arch):
        enabled = 1
    elif has_state(pac_root, 'disable', arch):
        enabled = 0
    if has_state(pac_root, 'enable', repo):
        enabled = 1
    elif has_state(pac_root, 'disable', repo):
        enabled = 0
    if has_state(pac_root, 'enable', repo, arch):
        enabled = 1
    elif has_state(pac_root, 'disable', repo, arch):
        enabled = 0

    return enabled

def clean(workdir):
    bindir = os.path.join(workdir, '_binaries')
    bidir = os.path.join(workdir, '_buildinfos')
    metafile = os.path.join(workdir, '_meta')
    print 'Cleaning %s' % metafile
    if os.path.exists(metafile):
        os.remove(metafile)
    print 'Cleaning %s' % bindir
    if os.path.exists(bindir):
        shutil.rmtree(bindir)
    print 'Cleaning %s' % bidir
    if os.path.exists(bidir):
        shutil.rmtree(bidir)

def calc_total(buildorder, disables):
    total = 0
    for pkg in buildorder:
        if not disables.has_key(pkg):
            total += 1
    return total

def get_http_error_reason(error):
    if hasattr(error, 'reason'):
        return error.reason
    elif hasattr(error, 'msg'):
        return error.msg
    else:
        return 'HTTP %s' % error.code

def is_buildroot_unique():
    env = os.getenv('OSC_BUILD_ROOT')
    if env:
        build_root = env
    else:
        build_root = conf.config['build-root']

    return '%(package)s' in build_root

# vim: et sw=4 ts=4
