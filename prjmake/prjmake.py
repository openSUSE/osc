# Copyright (C) 2016 Ericsson AB
# This program is free software; it may be used, copied, modified
# and distributed under the terms of the GNU General Public Licence,
# either version 2, or version 3 (at your option).
#

from osc import cmdln
from osc import core
from oscpluginprjmake import *
import os
import sys
try:
    from lxml import etree as ET
except ImportError:
    from xml.etree import ElementTree as ET

def validate_params(self, opts, args):
    if not is_project_dir(os.getcwd()):
        raise oscerr.NoWorkingCopy("Current directory not an osc project")
    if opts.workdir:
        if not os.path.isdir(opts.workdir):
            raise oscerr.WrongArgs('%s is not a directory' % opts.workdir)
        if not os.access(opts.workdir, os.W_OK):
            raise oscerr.WrongArgs('%s is not writable' % opts.workdir)
    if opts.preload:
        if opts.dry_run:
            raise oscerr.WrongArgs('Cannot set --dry-run with --preload')
        if opts.offline:
            raise oscerr.WrongArgs('Cannot set --offline with --preload')
    if opts.offline:
        if opts.clean:
            raise oscerr.WrongArgs('Cannot set --clean with --offline')
        if opts.preload:
            raise oscerr.WrongArgs('Cannot set --preload with --offline')
    if opts.add_repo:
        if opts.clean:
            raise oscerr.WrongArgs('Cannot set --clean with --add-repo')
    if opts.noinit:
        if not utils.is_buildroot_unique():
            raise oscerr.WrongArgs(
                'Buildroot not unique per package, cannot use --noinit')

def read_project_settings(self, sts, opts, args):
    project = store_read_project(os.getcwd())
    sts.set('projectdir', os.getcwd())
    apiurl = self.get_api_url()
    sts.set('apiurl', apiurl)
    if not opts.workdir:
        workdir = os.path.join(os.getcwd(), '.osc', '_prjmake')
    else:
        workdir = os.path.abspath(opts.workdir)
    sts.set('workdir', workdir)
    if not os.path.exists(workdir):
        os.makedirs(workdir)
    if opts.clean:
        utils.clean(workdir)
    (repo, arch, args_pkg, args_ra) = utils.repo_arch_magic(
        project, apiurl, workdir, opts.preload, opts.offline, args)
    if repo is None or arch is None:
        raise oscerr.WrongArgs(
            'Unable to parse repository and arch from parameters: %s' % args_ra)
    print 'Building for %s %s' % (repo, arch)
    sts.set('repo', repo)
    sts.set('arch', arch)

    for pkg in args_pkg:
        if not is_package_dir(pkg) or pkg == "_project":
            raise oscerr.NoWorkingCopy("%s is not a package directory" % pkg)

    if opts.exclude:
        excludes = opts.exclude
    else:
        excludes = []
    sts.set('excludes', excludes)

    pkgs_changed_names = []
    for pkg in args_pkg:
        # Remove trailing slash from autocomplete
        if pkg.endswith("/"):
            pkg = pkg[:-1]
        if pkg in sts.get('excludes'):
            continue
        state = utils.get_package_state(os.getcwd(), pkg)
        if state == 'deleted' or state == 'unknown':
            raise oscerr.WrongArgs('%s has %s state, cannot continue'
                % (pkg, state))
        pkgs_changed_names.append(pkg)
    # Read all packages and specfiles for changed packages
    packages = utils.read_packages(self, sts)
    sts.set('packages', packages)
    pkgs_changed = []
    for pkgname in pkgs_changed_names:
        pkgs_changed.append(packages[packages.index(os.path.abspath(
            os.path.join(os.getcwd(), pkgname)))])
    sts.set('pkgs_changed', pkgs_changed)
    bindir = os.path.join(workdir, '_binaries',
        repo, arch)
    if not os.path.exists(bindir):
        os.makedirs(bindir)
    sts.set('bindir', bindir)
    buildinfodir = os.path.join(workdir, '_buildinfos',
        repo, arch)
    if not os.path.exists(buildinfodir):
        os.makedirs(buildinfodir)
    sts.set('buildinfodir', buildinfodir)

def parse_make_options(self, sts, opts):

    make_opts = []

    if opts.preload:
        sts.set('preload', True)
        make_opts += ['--preload']
    else:
        sts.set('preload', False)

    if opts.offline:
        sts.set('offline', True)
        make_opts += ['--offline']
    else:
        sts.set('offline', False)

    if opts.noinit:
        make_opts += ['--noinit']

    if not opts.noinit and not opts.preload:
        make_opts += ['--clean']

    if opts.add_repo:
        make_opts += ['-p', os.path.join(sts.get('workdir'), '_binaries',
            opts.add_repo, sts.get('arch'))]

    if opts.prefer_pkgs:
        for d in opts.prefer_pkgs:
            make_opts += ['-p', os.path.abspath(d)]

    if opts.trust_all_projects:
        make_opts += ['--trust-all-projects']

    if opts.no_verify:
        make_opts += ['--noverify']

    if opts.extra_pkgs:
        for p in opts.extra_pkgs:
            make_opts += ['-x', p]

    if opts.define:
        for d in opts.define:
            make_opts += ['--define', d]

    if opts._with:
        for wi in opts._with:
            make_opts += ['--with', wi]

    if opts.without:
        for wo in opts.without:
            make_opts += ['--without', wo]

    if opts.debuginfo:
        make_opts += ['--debuginfo']

    if opts.disable_debuginfo:
        make_opts += ['--disable_debuginfo']

    if opts.nopreinstallimage:
        make_opts += ['--nopreinstallimage']

    if opts.progress:
        sts.set('progress', True)
    else:
        sts.set('progress', False)

    sts.set('makeopts', make_opts)

def read_misc_options(self, sts, opts):
    if opts.download_jobs:
        sts.set('download-jobs', opts.download_jobs)
    else:
        sts.set('download-jobs', 4)
    if opts.autowipe:
        sts.set('autowipe', True)
    else:
        sts.set('autowipe', False)

def validate_settings(self, sts):
    max_dl_jobs = 24
    set_dl_jobs = sts.get('download-jobs')
    if set_dl_jobs > max_dl_jobs:
        print('Maximum of %s download jobs allowed' % max_dl_jobs)
        sys.exit(1)
    elif set_dl_jobs < 1:
        print('Minimum of 1 download jobs allowed')
        sys.exit(1)

def parse_arguments(self, opts, *args):
    self.validate_params(opts, args)
    sts = settings.Settings()
    self.read_project_settings(sts, opts, args)
    self.parse_make_options(sts, opts)
    self.read_misc_options(sts, opts)
    self.validate_settings(sts)
    sts.set('buildorder_calc_mode', 'buildinfo')

    # Setup full project build if no changed packages are provided
    if len(sts.get('pkgs_changed')) == 0:
        sts.set('pkgs_changed', sts.get('packages'))
        disable_mode = 'all'
    else:
        disable_mode = 'dependencies'
    sts.set('disable_mode', disable_mode)

    return sts

def get_order(self, packages, sts):
    if self.bi_thread is None:
        try:
            self.bi_thread = buildinfothread.BuildInfoThread(sts)
            self.bi_thread.start()
            if self.bi_thread.wait_for_stage(1):
                print 'Failed to load dependency information'
                raise self.bi_thread.get_error()
            disables = self.bi_thread.get_disables()
            packages_old = sts.get('packages')
            sts.set('packages', packages)
            bo = buildorder.BuildOrder(sts)
            deps = bo.build_dep_graph()
            sts.set('packages', packages_old)
            order = bo.calc_buildorder(deps, deps.keys())
            return [p for p in order if not disables.has_key(p)]
        except KeyboardInterrupt as i:
            self.bi_thread.interrupt()
            self.bi_thread.join()
            raise i
    else:
        try:
            if self.bi_thread.wait_for_stage(2):
                print 'Failed to load dependency information'
                raise self.bi_thread_get_error()
            self.bi_thread.join()
            disables = self.bi_thread.get_disables()
            packages_old = sts.get('packages')
            sts.set('packages', packages)
            bo = buildorder.BuildOrder(sts)
            deps = bo.build_dep_graph()
            sts.set('packages', packages_old)
            order = bo.calc_buildorder(deps, sts.get('pkgs_changed'))
            return [p for p in order if not disables.has_key(p)]
        except KeyboardInterrupt as i:
            self.bi_thread.interrupt()
            self.bi_thread.join()
            raise i

def main_build_loop(self, state, dry_run=False):
    order = state.buildorder
    sts = state.settings
    bindir = sts.get('bindir')

    total = len(order)
    while state.index < total:
        pkg = order[state.index]
        if dry_run:
            rc = 0
            print("Building: %s" % pkg)
        else:
            rc = utils.osc_make_pkg(pkg, state.index + 1, total, sts)
        if rc:
            if sts.get('preload'):
                print('Preload failed for %s' % pkg)
                sys.exit(1)
            print('Build failed for %s' % pkg)
            print('Packages are available in %s' % bindir)
            print('\nUse osc prjmake --continue to resume building')
            state.save(os.path.join(sts.get('workdir'), '_state'))
            sys.exit(1)
        elif sts.get('autowipe'):
            utils.osc_wipe(pkg, sts)
        state.index += 1
    if sts.get('preload'):
        print('Preload completed.')
    else:
        print('All %s builds succeeded' % total)
        print('Packages are available in %s' % bindir)

@cmdln.option('-w', '--workdir', metavar='WORKDIR',
    help='Working directory for prjmake, defaults to .osc in project dir.')
@cmdln.option('-d', '--dry-run', action='store_true',
    help='Only calculate packages that need to be built')
@cmdln.option('--clean', action='store_true',
    help='Clean buildinfos and binaries before builds')
@cmdln.option('--exclude', metavar='PACKAGE', action='append',
    help='Do not build PACKAGE. Can be given multiple times.')
@cmdln.option('--noinit', action='store_true',
    help='Run all builds with --noinit. Requires reqular project build first.')
@cmdln.option('-a', '--add-repo', metavar='REPOSITORY',
    help='Use rpm packages from previous builds of the selected REPOSITORY.')
@cmdln.option('--progress', action='store_true',
    help='Display build progress in window title using control characters.')
# Autowipe option requires osc chroot --wipe support
@cmdln.option('--autowipe', action='store_true',
    help='Automatically wipe buildroot after builds.')
@cmdln.option('--download-jobs', metavar='JOBS', type="int",
    help='Number of parallel buildinfo download jobs, the default is 4.')
@cmdln.option('--continue', action='store_true', dest='_continue',
    help='Continue from last failure if able.')
# Options copied from osc build:
@cmdln.option('--trust-all-projects', action='store_true',
    help='trust packages from all projects')
@cmdln.option('-p', '--prefer-pkgs', metavar='DIRECTORY', action='append',
    help='Use rpm packages from DIRECTORY for prjmake builds.')
@cmdln.option('--preload', action='store_true',
    help='Preload all files into the cache for offline operation.')
@cmdln.option('--offline', action='store_true',
    help='Do an offline project build. Requires that you run --preload first.')
@cmdln.option('--no-verify', '--noverify', action='store_true',
    help='Skip signature verification of packages used for build.')
@cmdln.option('-x', '--extra-pkgs', metavar='PAC', action='append',
    help='Add this package when installing the build-root')
@cmdln.option('--with', metavar='X', dest='_with', action='append',
    help='enable feature X for build')
@cmdln.option('--without', metavar='X', action='append',
    help='disable feature X for build')
@cmdln.option('--define', metavar='\'X Y\'', action='append',
    help='define macro X with value Y')
@cmdln.option('--debuginfo', action='store_true',
    help='also build debuginfo sub-packages')
@cmdln.option('--disable-debuginfo', action='store_true',
    help='disable build of debuginfo packages')
@cmdln.option('-i', '--nopreinstallimage', action='store_true',
    help='Don\'t use preinstall images for creating build root.')
def do_prjmake(self, subcmd, opts, *args):
    """${cmd_name}: Build given packages and all packages that depend
    on given packages. If no packages are given, a full project build is
    done according to server side enables/disables.

    Usage:
        ${cmd_name} [OPTIONS] REPO ARCH [PACKAGE ...]

    ${cmd_option_list}
    """

    state = buildstate.State()
    if opts.workdir:
        statefile = os.path.join(os.path.abspath(opts.workdir), '_state')
    else:
        statefile = os.path.join(os.getcwd(), '.osc', '_prjmake', '_state')

    if opts._continue:
        if not os.path.exists(statefile):
            print('No state file %s, cannot --continue' % statefile)
            sys.exit(1)
        print('\nResuming with --continue, all other arguments ignored.')
        state.load(statefile)
        state.delete(statefile)
    else:
        # Normal prjmake
        sts = self.parse_arguments(opts, *args)
        pkgs_changed = sts.get('pkgs_changed')
        packages = sts.get('packages')
        apiurl = sts.get('apiurl')
        repo = sts.get('repo')
        bindir = sts.get('bindir')
        state.delete(statefile)

        self.bi_thread = None
        order = self.get_order(pkgs_changed, sts)
        if len(order) == 0:
            raise oscerr.WrongArgs('No enabled packages for %s' % repo)
        if opts.dry_run:
            rc = 0
            print "Building: %s" % order[0]
        else:
            rc = utils.osc_make_pkg(order[0], 1, 'unknown', sts)
            if rc:
                self.bi_thread.interrupt()
                self.bi_thread.join()
                print 'Build failed for %s' % order[0]
                print 'Packages are available in %s' % bindir
                sys.exit(1)
            elif sts.get('autowipe'):
                utils.osc_wipe(order[0], sts)

        order = self.get_order(packages, sts)
        state.buildorder = order
        state.settings = sts
        state.index = 1

    self.main_build_loop(state, opts.dry_run)

# vim: et ts=4 sw=4
