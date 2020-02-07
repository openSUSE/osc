# Copyright (C) 2006 Novell Inc.  All rights reserved.
# This program is free software; it may be used, copied, modified
# and distributed under the terms of the GNU General Public Licence,
# either version 2, or version 3 (at your option).

from __future__ import print_function

from . import cmdln
from . import conf
from . import oscerr
import sys
import signal
import time
import imp
import inspect
import os
try:
    from urllib.parse import urlsplit
    from urllib.error import HTTPError
    ET_ENCODING = "unicode"
except ImportError:
    #python 2.x
    from urlparse import urlsplit
    from urllib2 import HTTPError
    ET_ENCODING = "utf-8"

from optparse import SUPPRESS_HELP

from .core import *
from .util import safewriter

try:
    from functools import cmp_to_key
except ImportError:
    from .util.helper import cmp_to_key

from operator import itemgetter

MAN_HEADER = r""".TH %(ucname)s "1" "%(date)s" "%(name)s %(version)s" "User Commands"
.SH NAME
%(name)s \- openSUSE build service command-line tool.
.SH SYNOPSIS
.B %(name)s
[\fIGLOBALOPTS\fR] \fISUBCOMMAND \fR[\fIOPTS\fR] [\fIARGS\fR...]
.br
.B %(name)s
\fIhelp SUBCOMMAND\fR
.SH DESCRIPTION
openSUSE build service command-line tool.
"""
MAN_FOOTER = r"""
.SH "SEE ALSO"
Type 'osc help <subcommand>' for more detailed help on a specific subcommand.
.PP
For additional information, see
 * http://en.opensuse.org/openSUSE:Build_Service_Tutorial
 * http://en.opensuse.org/openSUSE:OSC
.PP
You can modify osc commands, or roll your own, via the plugin API:
 * http://en.opensuse.org/openSUSE:OSC_plugins
.SH AUTHOR
osc was written by several authors. This man page is automatically generated.
"""

class Osc(cmdln.Cmdln):
    """Usage: osc [GLOBALOPTS] SUBCOMMAND [OPTS] [ARGS...]
    or: osc help SUBCOMMAND

    openSUSE build service command-line tool.
    Type 'osc help <subcommand>' for help on a specific subcommand.

    ${command_list}
    ${help_list}
    global ${option_list}
    For additional information, see
    * http://en.opensuse.org/openSUSE:Build_Service_Tutorial
    * http://en.opensuse.org/openSUSE:OSC

    You can modify osc commands, or roll your own, via the plugin API:
    * http://en.opensuse.org/openSUSE:OSC_plugins
    """
    name = 'osc'
    conf = None

    man_header = MAN_HEADER
    man_footer = MAN_FOOTER

    def __init__(self, *args, **kwargs):
        # the plugins have to be loaded before the
        # superclass' __init__ method is called
        self._load_plugins()
        cmdln.Cmdln.__init__(self, *args, **kwargs)
        cmdln.Cmdln.do_help.aliases.append('h')
        sys.stderr = safewriter.SafeWriter(sys.stderr)
        sys.stdout = safewriter.SafeWriter(sys.stdout)

    def get_version(self):
        return get_osc_version()

    def get_optparser(self):
        """this is the parser for "global" options (not specific to subcommand)"""

        optparser = cmdln.CmdlnOptionParser(self, version=get_osc_version())
        optparser.add_option('--debugger', action='store_true',
                      help='jump into the debugger before executing anything')
        optparser.add_option('--post-mortem', action='store_true',
                      help='jump into the debugger in case of errors')
        optparser.add_option('-t', '--traceback', action='store_true',
                      help='print call trace in case of errors')
        optparser.add_option('-H', '--http-debug', action='store_true',
                      help='debug HTTP traffic (filters some headers)')
        optparser.add_option('--http-full-debug', action='store_true',
                      help='debug HTTP traffic (filters no headers)')
        optparser.add_option('-d', '--debug', action='store_true',
                      help='print info useful for debugging')
        optparser.add_option('-A', '--apiurl', dest='apiurl',
                      metavar='URL/alias',
                      help='specify URL to access API server at or an alias')
        optparser.add_option('-c', '--config', dest='conffile',
                      metavar='FILE',
                      help='specify alternate configuration file')
        optparser.add_option('--no-keyring', action='store_true',
                      help='disable usage of desktop keyring system')
        optparser.add_option('--no-gnome-keyring', action='store_true',
                      help='disable usage of GNOME Keyring')
        optparser.add_option('-v', '--verbose', dest='verbose', action='count', default=0,
                      help='increase verbosity')
        optparser.add_option('-q', '--quiet',   dest='verbose', action='store_const', const=-1,
                      help='be quiet, not verbose')
        return optparser


    def postoptparse(self, try_again = True):
        """merge commandline options into the config"""
        try:
            conf.get_config(override_conffile = self.options.conffile,
                            override_apiurl = self.options.apiurl,
                            override_debug = self.options.debug,
                            override_http_debug = self.options.http_debug,
                            override_http_full_debug = self.options.http_full_debug,
                            override_traceback = self.options.traceback,
                            override_post_mortem = self.options.post_mortem,
                            override_no_keyring = self.options.no_keyring,
                            override_no_gnome_keyring = self.options.no_gnome_keyring,
                            override_verbose = self.options.verbose)
        except oscerr.NoConfigfile as e:
            print(e.msg, file=sys.stderr)
            print('Creating osc configuration file %s ...' % e.file, file=sys.stderr)
            apiurl = conf.DEFAULTS['apiurl']
            if self.options.apiurl:
                apiurl = self.options.apiurl
            conf.interactive_config_setup(e.file, apiurl)
            print('done', file=sys.stderr)
            if try_again:
                self.postoptparse(try_again = False)
        except oscerr.ConfigMissingApiurl as e:
            print(e.msg, file=sys.stderr)
            conf.interactive_config_setup(e.file, e.url, initial=False)
            if try_again:
                self.postoptparse(try_again = False)
        except oscerr.ConfigMissingCredentialsError as e:
            print(e.msg)
            print('Please enter new credentials.')
            conf.interactive_config_setup(e.file, e.url, initial=False)
            if try_again:
                self.postoptparse(try_again = False)

        self.options.verbose = conf.config['verbose']
        self.download_progress = None
        if conf.config.get('show_download_progress', False):
            from .meter import create_text_meter
            self.download_progress = create_text_meter()


    def get_cmd_help(self, cmdname):
        doc = self._get_cmd_handler(cmdname).__doc__
        doc = self._help_reindent(doc)
        doc = self._help_preprocess(doc, cmdname)
        doc = doc.rstrip() + '\n' # trim down trailing space
        return self._str(doc)

    def get_api_url(self):
        try:
            localdir = os.getcwd()
        except Exception as e:
            ## check for Stale NFS file handle: '.'
            try:
                os.stat('.')
            except Exception as ee:
                e = ee
            print("os.getcwd() failed: ", e, file=sys.stderr)
            sys.exit(1)

        if (is_package_dir(localdir) or is_project_dir(localdir)) and not self.options.apiurl:
            return store_read_apiurl(os.curdir)
        else:
            return conf.config['apiurl']

    # overridden from class Cmdln() to use config variables in help texts
    def _help_preprocess(self, help, cmdname):
        help_msg = cmdln.Cmdln._help_preprocess(self, help, cmdname)
        return help_msg % conf.config

    def _help_preprocess_cmd_name(self, help, cmdname=None):
        if cmdname is None:
            return help
        return cmdln.Cmdln._help_preprocess_cmd_name(self, help, cmdname)

    def _help_preprocess_cmd_option_list(self, help, cmdname=None):
        if cmdname is None:
            return help
        return cmdln.Cmdln._help_preprocess_cmd_option_list(self, help, cmdname)

    def _help_preprocess_cmd_usage(self, help, cmdname=None):
        if cmdname is None:
            return help
        return cmdln.Cmdln._help_preprocess_cmd_usage(self, help, cmdname)

    def do_init(self, subcmd, opts, project, package=None):
        """${cmd_name}: Initialize a directory as working copy

        Initialize an existing directory to be a working copy of an
        (already existing) buildservice project/package.

        (This is the same as checking out a package and then copying sources
        into the directory. It does NOT create a new package. To create a
        package, use 'osc meta pkg ... ...')

        You wouldn't normally use this command.

        To get a working copy of a package (e.g. for building it or working on
        it, you would normally use the checkout command. Use "osc help
        checkout" to get help for it.

        usage:
            osc init PRJ
            osc init PRJ PAC
        ${cmd_option_list}
        """

        apiurl = self.get_api_url()

        if not package:
            Project.init_project(apiurl, os.curdir, project, conf.config['do_package_tracking'])
            print('Initializing %s (Project: %s)' % (os.curdir, project))
        else:
            Package.init_package(apiurl, project, package, os.curdir)
            store_write_string(os.curdir, '_files', show_files_meta(apiurl, project, package) + '\n')
            print('Initializing %s (Project: %s, Package: %s)' % (os.curdir, project, package))

    @cmdln.alias('ls')
    @cmdln.alias('ll')
    @cmdln.alias('lL')
    @cmdln.alias('LL')
    @cmdln.option('-a', '--arch', metavar='ARCH',
                        help='specify architecture (only for binaries)')
    @cmdln.option('-r', '--repo', metavar='REPO',
                        help='specify repository (only for binaries)')
    @cmdln.option('-b', '--binaries', action='store_true',
                        help='list built binaries instead of sources')
    @cmdln.option('-e', '--expand', action='store_true',
                        help='expand linked package (only for sources)')
    @cmdln.option('-u', '--unexpand', action='store_true',
                        help='always work with unexpanded (source) packages')
    @cmdln.option('-v', '--verbose', action='store_true',
                        help='print extra information')
    @cmdln.option('-l', '--long', action='store_true', dest='verbose',
                        help='print extra information')
    @cmdln.option('-D', '--deleted', action='store_true',
                        help='show only the former deleted projects or packages')
    @cmdln.option('-M', '--meta', action='store_true',
                        help='list meta data files')
    @cmdln.option('-R', '--revision', metavar='REVISION',
                        help='specify revision (only for sources)')
    def do_list(self, subcmd, opts, *args):
        """${cmd_name}: List sources or binaries on the server

        Examples for listing sources:
           ls                          # list all projects (deprecated)
           ls /                        # list all projects
           ls .                        # take PROJECT/PACKAGE from current dir.
           ls PROJECT                  # list packages in a project
           ls PROJECT PACKAGE          # list source files of package of a project
           ls PROJECT PACKAGE <file>   # list <file> if this file exists
           ls -v PROJECT PACKAGE       # verbosely list source files of package
           ls -l PROJECT PACKAGE       # verbosely list source files of package
           ll PROJECT PACKAGE          # verbosely list source files of package
           LL PROJECT PACKAGE          # verbosely list source files of expanded link

        With --verbose, the following fields will be shown for each item:
           MD5 hash of file
           Revision number of the last commit
           Size (in bytes)
           Date and time of the last commit

        Examples for listing binaries:
           ls -b PROJECT               # list all binaries of a project
           ls -b PROJECT -a ARCH       # list ARCH binaries of a project
           ls -b PROJECT -r REPO       # list binaries in REPO
           ls -b PROJECT PACKAGE REPO ARCH

        Usage:
           ${cmd_name} [PROJECT [PACKAGE]]
           ${cmd_name} -b [PROJECT [PACKAGE [REPO [ARCH]]]]
        ${cmd_option_list}
        """

        args = slash_split(args)
        if subcmd == 'll':
            opts.verbose = True
        if subcmd == 'lL' or subcmd == 'LL':
            opts.verbose = True
            opts.expand = True

        project = None
        package = None
        fname = None
        if len(args) == 0:
            # For consistency with *all* other commands
            # this lists what the server has in the current wd.
            # CAUTION: 'osc ls -b' already works like this.
            pass
        if len(args) > 0:
            project = args[0]
            if project == '/':
                project = None
            if project == '.':
                cwd = os.getcwd()
                if is_project_dir(cwd):
                    project = store_read_project(cwd)
                elif is_package_dir(cwd):
                    project = store_read_project(cwd)
                    package = store_read_package(cwd)
        if len(args) > 1:
            package = args[1]
        if len(args) > 2:
            if opts.deleted:
                raise oscerr.WrongArgs("Too many arguments when listing deleted packages")
            if opts.binaries:
                if opts.repo:
                    if opts.repo != args[2]:
                        raise oscerr.WrongArgs("conflicting repos specified ('%s' vs '%s')"%(opts.repo, args[2]))
                else:
                    opts.repo = args[2]
            else:
                fname = args[2]

        if len(args) > 3:
            if not opts.binaries:
                raise oscerr.WrongArgs('Too many arguments')
            if opts.arch:
                if opts.arch != args[3]:
                    raise oscerr.WrongArgs("conflicting archs specified ('%s' vs '%s')"%(opts.arch, args[3]))
            else:
                opts.arch = args[3]


        if opts.binaries and opts.expand:
            raise oscerr.WrongOptions('Sorry, --binaries and --expand are mutual exclusive.')

        apiurl = self.get_api_url()

        # list binaries
        if opts.binaries:
            # ls -b toplevel doesn't make sense, so use info from
            # current dir if available
            if len(args) == 0:
                cwd = os.getcwd()
                if is_project_dir(cwd):
                    project = store_read_project(cwd)
                elif is_package_dir(cwd):
                    project = store_read_project(cwd)
                    package = store_read_package(cwd)

            if not project:
                raise oscerr.WrongArgs('There are no binaries to list above project level.')
            if opts.revision:
                raise oscerr.WrongOptions('Sorry, the --revision option is not supported for binaries.')

            repos = []

            if opts.repo and opts.arch:
                repos.append(Repo(opts.repo, opts.arch))
            elif opts.repo and not opts.arch:
                repos = [repo for repo in get_repos_of_project(apiurl, project) if repo.name == opts.repo]
            elif opts.arch and not opts.repo:
                repos = [repo for repo in get_repos_of_project(apiurl, project) if repo.arch == opts.arch]
            else:
                repos = get_repos_of_project(apiurl, project)

            results = []
            for repo in repos:
                results.append((repo, get_binarylist(apiurl, project, repo.name, repo.arch, package=package, verbose=opts.verbose)))

            for result in results:
                indent = ''
                if len(results) > 1:
                    print('%s/%s' % (result[0].name, result[0].arch))
                    indent = ' '

                if opts.verbose:
                    for f in result[1]:
                        if f.size is None and f.mtime is None:
                            print("%9s %12s %-40s" % ('unknown', 'unknown', f.name))
                        elif f.size is None and f.mtime is not None:
                            print("%9s %s %-40s" % ('unknown', shorttime(f.mtime), f.name))
                        elif f.size is not None and f.mtime is None:
                            print("%9d %12s %-40s" % (f.size, 'unknown', f.name))
                        else:
                            print("%9d %s %-40s" % (f.size, shorttime(f.mtime), f.name))
                else:
                    for f in result[1]:
                        print(indent+f)

        # list sources
        elif not opts.binaries:
            if not args:
                for prj in meta_get_project_list(apiurl, opts.deleted):
                    print(prj)

            elif len(args) == 1:
                if opts.verbose:
                    if self.options.verbose:
                        print('Sorry, the --verbose option is not implemented for projects.', file=sys.stderr)
                for pkg in meta_get_packagelist(apiurl, project, deleted = opts.deleted, expand = opts.expand):
                    print(pkg)

            elif len(args) == 2 or len(args) == 3:
                link_seen = False
                print_not_found = True
                rev = opts.revision
                for i in [ 1, 2 ]:
                    l = meta_get_filelist(apiurl,
                                      project,
                                      package,
                                      verbose=opts.verbose,
                                      expand=opts.expand,
                                      meta=opts.meta,
                                      deleted=opts.deleted,
                                      revision=rev)
                    link_seen = '_link' in l
                    if opts.verbose:
                        out = [ '%s %7s %9d %s %s' % (i.md5, i.rev, i.size, shorttime(i.mtime), i.name) \
                            for i in l if not fname or fname == i.name ]
                        if len(out) > 0:
                            print_not_found = False
                            print('\n'.join(out))
                    elif fname:
                        if fname in l:
                            print(fname)
                            print_not_found = False
                    else:
                        print('\n'.join(l))
                    if opts.expand or opts.unexpand or not link_seen:
                        break
                    m = show_files_meta(apiurl, project, package)
                    li = Linkinfo()
                    root = ET.fromstring(m)
                    li.read(root.find('linkinfo'))
                    if li.haserror():
                        raise oscerr.LinkExpandError(project, package, li.error)
                    project, package, rev = li.project, li.package, li.rev
                    if rev:
                        print('# -> %s %s (%s)' % (project, package, rev))
                    else:
                        print('# -> %s %s (latest)' % (project, package))
                    opts.expand = True
                if fname and print_not_found:
                    print('file \'%s\' does not exist' % fname)
                    return 1


    @cmdln.option('--extend-package-names', default=False, action="store_true",
                  help='Extend packages names with project name as suffix')
    def do_addcontainers(self, subcmd, opts, *args):
        """${cmd_name}: Add maintained containers for a give package

        The command adds all containers which are marked as maintained and contain
        an rpm originating from the specified source package.

        Examples:
            osc addcontainers [PROJECT PACKAGE]
        ${cmd_option_list}
        """

        args = slash_split(args)
        apiurl = self.get_api_url()
        localdir = os.getcwd()
        project = package = None
        if not args:
            if is_package_dir(localdir):
                project = store_read_project(localdir)
                package = store_read_package(localdir)
        elif len(args) == 2:
            project = args[0]
            package = args[1]

        if project == None or package == None:
            raise oscerr.WrongArgs('Either specify project and package or call it from a package working copy')

        query = {'cmd': 'addcontainers'}
        if opts.extend_package_names:
            query['extend_package_names'] = '1'

        print("Add containers...")
        url = makeurl(apiurl, ['source', project, package], query=query)
        f = http_POST(url)

    @cmdln.option('-s', '--skip-disabled', action='store_true',
                        help='Skip disabled channels. Otherwise the source gets added, but not the repositories.')
    @cmdln.option('-e', '--enable-all', action='store_true',
                        help='Enable all added channels including the ones disabled by default.')
    def do_addchannels(self, subcmd, opts, *args):
        """${cmd_name}: Add channels to project.

        The command adds all channels which are defined to be used for a given source package.
        The source link target is used to lookup the channels. The command can be
        used for a certain package or for all in the specified project.

        In case no channel is defined the operation is just returning.

        Examples:
            osc addchannels [PROJECT [PACKAGE]]
        ${cmd_option_list}
        """

        args = slash_split(args)
        apiurl = self.get_api_url()
        localdir = os.getcwd()
        channel = None
        if not args:
            if is_project_dir(localdir) or is_package_dir(localdir):
                project = store_read_project(localdir)
            elif is_package_dir(localdir):
                project = store_read_project(localdir)
                channel = store_read_package(localdir)
            else:
                raise oscerr.WrongArgs('Either specify project [package] or call it from a project/package working copy')
        else:
            project = args[0]

        query = {'cmd': 'addchannels'}

        if opts.enable_all and opts.skip_disabled:
            raise oscerr.WrongOptions('--enable-all and --skip-disabled options are mutually exclusive')
        elif opts.enable_all:
            query['mode'] = 'enable_all'
        elif opts.skip_disabled:
            query['mode'] = 'skip_disabled'

        print("Looking for channels...")
        url = makeurl(apiurl, ['source', project], query=query)
        if channel:
            url = makeurl(apiurl, ['source', project, channel], query=query)
        f = http_POST(url)

    @cmdln.alias('enablechannel')
    def do_enablechannels(self, subcmd, opts, *args):
        """${cmd_name}: Enables channels

        Enables existing channel packages in a project. Enabling means adding the
        needed repositories for building.
        The command can be used to enable a specific one or all channels of a project.

        Examples:
            osc enablechannels [PROJECT [CHANNEL_PACKAGE]]
        ${cmd_option_list}
        """

        args = slash_split(args)
        apiurl = self.get_api_url()
        localdir = os.getcwd()
        channel = None
        if not args:
            if is_project_dir(localdir):
                project = store_read_project(localdir)
            elif is_package_dir(localdir):
                project = store_read_project(localdir)
                channel = store_read_package(localdir)
            else:
                raise oscerr.WrongArgs('Either specify project [package] or call it from a project/package working copy')
        else:
            project = args[0]
            if len(args) > 1:
                channel = args[1]

        query = {}
        if channel:
            query['cmd'] = 'enablechannel'
        else:
            query = {'cmd': 'modifychannels', 'mode': 'enable_all'}

        print("Enable channel(s)...")
        url = makeurl(apiurl, ['source', project], query=query)
        if channel:
            url = makeurl(apiurl, ['source', project, channel], query=query)
        f = http_POST(url)

    @cmdln.option('-f', '--force', action='store_true',
                        help='force generation of new patchinfo file, do not update existing one.')
    def do_patchinfo(self, subcmd, opts, *args):
        """${cmd_name}: Generate and edit a patchinfo file.

        A patchinfo file describes the packages for an update and the kind of
        problem it solves.

        This command either creates a new _patchinfo or updates an existing one.

        Examples:
            osc patchinfo
            osc patchinfo [PROJECT [PATCH_NAME]]
        ${cmd_option_list}
        """

        args = slash_split(args)
        apiurl = self.get_api_url()
        project_dir = localdir = os.getcwd()
        patchinfo = 'patchinfo'
        if len(args) == 0:
            if is_project_dir(localdir):
                project = store_read_project(localdir)
                apiurl = self.get_api_url()
                for p in meta_get_packagelist(apiurl, project):
                    if p.startswith("_patchinfo") or p.startswith("patchinfo"):
                        patchinfo = p
            else:
                if is_package_dir(localdir):
                    project = store_read_project(localdir)
                    patchinfo = store_read_package(localdir)
                    apiurl = self.get_api_url()
                    if not os.path.exists('_patchinfo'):
                        sys.exit('Current checked out package has no _patchinfo. Either call it from project level or specify patch name.')
                else:
                    sys.exit('This command must be called in a checked out project or patchinfo package.')
        else:
            project = args[0]
            if len(args) > 1:
                patchinfo = args[1]

        filelist = None
        if patchinfo:
            try:
                filelist = meta_get_filelist(apiurl, project, patchinfo)
            except HTTPError:
                pass

        if opts.force or not filelist or not '_patchinfo' in filelist:
            print("Creating new patchinfo...")
            query = 'cmd=createpatchinfo&name=' + patchinfo
            if opts.force:
                query += "&force=1"
            url = makeurl(apiurl, ['source', project], query=query)
            f = http_POST(url)
            for p in meta_get_packagelist(apiurl, project):
                if p.startswith("_patchinfo") or p.startswith("patchinfo"):
                    patchinfo = p
        else:
            print("Update existing _patchinfo file...")
            query = 'cmd=updatepatchinfo'
            url = makeurl(apiurl, ['source', project, patchinfo], query=query)
            f = http_POST(url)

        # CAUTION:
        #  Both conf.config['checkout_no_colon'] and conf.config['checkout_rooted']
        #  fool this test:
        if is_package_dir(localdir):
            pac = Package(localdir)
            pac.update()
            filename = "_patchinfo"
        else:
            checkout_package(apiurl, project, patchinfo, prj_dir=project_dir)
            filename = project_dir + "/" + patchinfo + "/_patchinfo"

        run_editor(filename)

    @cmdln.alias('bsdevelproject')
    @cmdln.alias('dp')
    @cmdln.option('-r', '--raw', action='store_true', help='deprecated option')
    def do_develproject(self, subcmd, opts, *args):
        """${cmd_name}: print the devel project / package of a package

        Examples:
            osc develproject PRJ PKG
            osc develproject
        ${cmd_option_list}
        """
        args = slash_split(args)
        apiurl = self.get_api_url()

        if len(args) == 0:
            project = store_read_project(os.curdir)
            package = store_read_package(os.curdir)
        elif len(args) == 2:
            project = args[0]
            package = args[1]
        else:
            raise oscerr.WrongArgs('need Project and Package')

        devprj, devpkg = show_devel_project(apiurl, project, package)
        if devprj is None:
            print('%s / %s has no devel project' % (project, package))
        elif devpkg and devpkg != package:
            print("%s %s" % (devprj, devpkg))
        else:
            print(devprj)

    @cmdln.alias('sdp')
    @cmdln.option('-u', '--unset', action='store_true',
                  help='remove devel project')
    def do_setdevelproject(self, subcmd, opts, *args):
        """${cmd_name}: Set the devel project / package of a package

        Examples:
            osc setdevelproject [PRJ PKG] DEVPRJ [DEVPKG]
        ${cmd_option_list}
        """
        args = slash_split(args)
        apiurl = self.get_api_url()

        devprj, devpkg = None, None
        if len(args) == 3 or len(args) == 4:
            project, package = args[0], args[1]
            devprj = args[2]
            if len(args) == 4:
                devpkg = args[3]
        elif len(args) >= 1 and len(args) <= 2:
            project, package = store_read_project(os.curdir), store_read_package(os.curdir)
            devprj = args[0]
            if len(args) == 2:
                devpkg = args[1]
        else:
            if opts.unset:
                project, package = store_read_project(os.curdir), store_read_package(os.curdir)
            else:
                raise oscerr.WrongArgs('need at least DEVPRJ (and possibly DEVPKG)')

        set_devel_project(apiurl, project, package, devprj, devpkg)


    @cmdln.option('-c', '--create', action='store_true',
                        help='Create a new token')
    @cmdln.option('-d', '--delete', metavar='TOKENID',
                        help='Delete a token')
    @cmdln.option('-o', '--operation', metavar='OPERATION',
                        help='Default is "runservice", but "release" or "rebuild" can also be used')
    @cmdln.option('-t', '--trigger', metavar='TOKENSTRING',
                        help='Trigger the action of a token')
    def do_token(self, subcmd, opts, *args):
        """${cmd_name}: Show and manage authentication token

        Authentication token can be used to run specific commands without
        sending credentials.

        Usage:
            osc token
            osc token --create [--operation <OPERATION>] [<PROJECT> <PACKAGE>]
            osc token --delete <TOKENID>
            osc token --trigger <TOKENSTRING> [--operation <OPERATION>] [<PROJECT> <PACKAGE>]
        ${cmd_option_list}
        """

        args = slash_split(args)

        apiurl = self.get_api_url()
        url = apiurl + "/person/" + conf.get_apiurl_usr(apiurl) + "/token"

        if opts.create:
            print("Create a new token")
            url += "?cmd=create"
            if opts.operation:
                url += "&operation=" + opts.operation
            if len(args) > 1:
                url += "&project=" + args[0]
                url += "&package=" + args[1]

            f = http_POST(url)
            while True:
                buf = f.read(16384)
                if not buf:
                    break
                sys.stdout.write(decode_it(buf))

        elif opts.delete:
            print("Delete token")
            url += "/" + opts.delete
            http_DELETE(url)
        elif opts.trigger:
            print("Trigger token")
            operation = opts.operation or "runservice"
            url = apiurl + "/trigger/" + operation
            if len(args) > 1:
                url += "?project=" + args[0]
                url += "&package=" + args[1]
            req = URLRequest(url)
            req.get_method = lambda: "POST"
            req.add_header('Content-Type', 'application/octet-stream')
            req.add_header('Authorization', "Token "+opts.trigger)
            fd = urlopen(req, data=None)
            print(decode_it(fd.read()))
        else:
            if args and args[0] in ['create', 'delete', 'trigger']:
                raise oscerr.WrongArgs("Did you mean --" + args[0] + "?")
            # just list token
            for data in streamfile(url, http_GET):
                sys.stdout.write(decode_it(data))


    @cmdln.option('-a', '--attribute', metavar='ATTRIBUTE',
                        help='affect only a given attribute')
    @cmdln.option('--attribute-defaults', action='store_true',
                        help='include defined attribute defaults')
    @cmdln.option('--attribute-project', action='store_true',
                        help='include project values, if missing in packages ')
    @cmdln.option('--blame', action='store_true',
                        help='show author and time of each line')
    @cmdln.option('-f', '--force', action='store_true',
                        help='force the save operation, allows one to ignores some errors like depending repositories. For prj meta only.')
    @cmdln.option('-F', '--file', metavar='FILE',
                        help='read metadata from FILE, instead of opening an editor. '
                        '\'-\' denotes standard input. ')
    @cmdln.option('-r', '--revision', metavar='REV',
                        help='checkout given revision instead of head revision. For prj and prjconf meta only')
    @cmdln.option('-m', '--message', metavar='TEXT',
                        help='specify log message TEXT. For prj and prjconf meta only')
    @cmdln.option('-e', '--edit', action='store_true',
                        help='edit metadata')
    @cmdln.option('-c', '--create', action='store_true',
                        help='create attribute without values')
    @cmdln.option('-R', '--remove-linking-repositories', action='store_true',
                        help='Try to remove also all repositories building against remove ones.')
    @cmdln.option('-s', '--set', metavar='ATTRIBUTE_VALUES',
                        help='set attribute values')
    @cmdln.option('--delete', action='store_true',
                        help='delete a pattern or attribute')
    def do_meta(self, subcmd, opts, *args):
        """${cmd_name}: Show meta information, or edit it

        Show or edit build service metadata of type <prj|pkg|prjconf|user|pattern>.

        This command displays metadata on buildservice objects like projects,
        packages, or users. The type of metadata is specified by the word after
        "meta", like e.g. "meta prj".

        prj denotes metadata of a buildservice project.
        prjconf denotes the (build) configuration of a project.
        pkg denotes metadata of a buildservice package.
        user denotes the metadata of a user.
        group denotes the metadata of a group.
        pattern denotes installation patterns defined for a project.

        To list patterns, use 'osc meta pattern PRJ'. An additional argument
        will be the pattern file to view or edit.

        With the --edit switch, the metadata can be edited. Per default, osc
        opens the program specified by the environmental variable EDITOR with a
        temporary file. Alternatively, content to be saved can be supplied via
        the --file switch. If the argument is '-', input is taken from stdin:
        osc meta prjconf home:user | sed ... | osc meta prjconf home:user -F -

        For meta prj and prjconf updates optional commit messages can be applied with --message.

        When trying to edit a non-existing resource, it is created implicitly.


        Examples:
            osc meta prj PRJ
            osc meta pkg PRJ PKG
            osc meta pkg PRJ PKG -e

        Usage:
            osc meta <prj|prjconf> [-r|--revision REV] ARGS...
            osc meta <prj|pkg|prjconf|user|group|pattern> ARGS...
            osc meta <prj|pkg|prjconf|user|group|pattern> [-m|--message TEXT] -e|--edit ARGS...
            osc meta <prj|pkg|prjconf|user|group|pattern> [-m|--message TEXT] -F|--file ARGS...
            osc meta pattern --delete PRJ PATTERN
            osc meta attribute PRJ [PKG [SUBPACKAGE]] [--attribute ATTRIBUTE] [--create [--set <value_list>]|--delete|--set <value_list>]
        ${cmd_option_list}
        """

        args = slash_split(args)

        if not args or args[0] not in metatypes.keys():
            raise oscerr.WrongArgs('Unknown meta type. Choose one of %s.' \
                                               % ', '.join(metatypes))

        cmd = args[0]
        del args[0]

        if cmd in ['pkg']:
            min_args, max_args = 0, 2
        elif cmd in ['pattern']:
            min_args, max_args = 1, 2
        elif cmd in ['attribute']:
            min_args, max_args = 1, 3
        elif cmd in ['prj', 'prjconf']:
            min_args, max_args = 0, 1
        else:
            min_args, max_args = 1, 1

        if len(args) < min_args:
            raise oscerr.WrongArgs('Too few arguments.')
        if len(args) > max_args:
            raise oscerr.WrongArgs('Too many arguments.')

        apiurl = self.get_api_url()

        # Specific arguments
        #
        # If project or package arguments missing, assume to work
        # with project and/or package in current local directory.
        attributepath = []
        if cmd in ['prj', 'prjconf']:
            if len(args) < 1:
                apiurl = store_read_apiurl(os.curdir)
                project = store_read_project(os.curdir)
            else:
                project = args[0]

        elif cmd == 'pkg':
            if len(args) < 2:
                apiurl = store_read_apiurl(os.curdir)
                project = store_read_project(os.curdir)
                if len(args) < 1:
                    package = store_read_package(os.curdir)
                else:
                    package = args[0]
            else:
                project = args[0]
                package = args[1]

        elif cmd == 'attribute':
            project = args[0]
            if len(args) > 1:
                package = args[1]
            else:
                package = None
                if opts.attribute_project:
                    raise oscerr.WrongOptions('--attribute-project works only when also a package is given')
            if len(args) > 2:
                subpackage = args[2]
            else:
                subpackage = None
            attributepath.append('source')
            attributepath.append(project)
            if package:
                attributepath.append(package)
            if subpackage:
                attributepath.append(subpackage)
            attributepath.append('_attribute')
        elif cmd == 'user':
            user = args[0]
        elif cmd == 'group':
            group = args[0]
        elif cmd == 'pattern':
            project = args[0]
            if len(args) > 1:
                pattern = args[1]
            else:
                pattern = None
                # enforce pattern argument if needed
                if opts.edit or opts.file:
                    raise oscerr.WrongArgs('A pattern file argument is required.')

        if cmd not in ['prj', 'prjconf'] and (opts.message or opts.revision):
            raise oscerr.WrongOptions('options --revision and --message are only supported for the prj or prjconf subcommand')

        # show
        if not opts.edit and not opts.file and not opts.delete and not opts.create and not opts.set:
            if cmd == 'prj':
                sys.stdout.write(decode_it(b''.join(show_project_meta(apiurl, project, rev=opts.revision, blame=opts.blame))))
            elif cmd == 'pkg':
                sys.stdout.write(decode_it(b''.join(show_package_meta(apiurl, project, package, blame=opts.blame))))
            elif cmd == 'attribute':
                sys.stdout.write(decode_it(b''.join(show_attribute_meta(apiurl, project, package, subpackage,
                                         opts.attribute, opts.attribute_defaults, opts.attribute_project))))
            elif cmd == 'prjconf':
                sys.stdout.write(decode_it(b''.join(show_project_conf(apiurl, project, rev=opts.revision, blame=opts.blame))))
            elif cmd == 'user':
                r = get_user_meta(apiurl, user)
                if r:
                    sys.stdout.write(decode_it(r))
            elif cmd == 'group':
                r = get_group_meta(apiurl, group)
                if r:
                    sys.stdout.write(decode_it(r))
            elif cmd == 'pattern':
                if pattern:
                    r = show_pattern_meta(apiurl, project, pattern)
                    if r:
                        sys.stdout.write(''.join(r))
                else:
                    r = show_pattern_metalist(apiurl, project)
                    if r:
                        sys.stdout.write('\n'.join(r) + '\n')

        # edit
        if opts.edit and not opts.file:
            if cmd == 'prj':
                edit_meta(metatype='prj',
                          edit=True,
                          force=opts.force,
                          remove_linking_repositories=opts.remove_linking_repositories,
                          path_args=quote_plus(project),
                          apiurl=apiurl,
                          msg = opts.message,
                          template_args=({
                                  'name': project,
                                  'user': conf.get_apiurl_usr(apiurl)}))
            elif cmd == 'pkg':
                edit_meta(metatype='pkg',
                          edit=True,
                          path_args=(quote_plus(project), quote_plus(package)),
                          apiurl=apiurl,
                          template_args=({
                                  'name': package,
                                  'user': conf.get_apiurl_usr(apiurl)}))
            elif cmd == 'prjconf':
                edit_meta(metatype='prjconf',
                          edit=True,
                          path_args=quote_plus(project),
                          apiurl=apiurl,
                          msg = opts.message,
                          template_args=None)
            elif cmd == 'user':
                edit_meta(metatype='user',
                          edit=True,
                          path_args=(quote_plus(user)),
                          apiurl=apiurl,
                          template_args=({'user': user}))
            elif cmd == 'group':
                edit_meta(metatype='group',
                          edit=True,
                          path_args=(quote_plus(group)),
                          apiurl=apiurl,
                          template_args=({'group': group}))
            elif cmd == 'pattern':
                edit_meta(metatype='pattern',
                          edit=True,
                          path_args=(project, pattern),
                          apiurl=apiurl,
                          template_args=None)

        # create attribute entry
        if (opts.create or opts.set) and cmd == 'attribute':
            if not opts.attribute:
                raise oscerr.WrongOptions('no attribute given to create')
            values = ''
            if opts.set:
                opts.set = opts.set.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')
                for i in opts.set.split(','):
                    values += '<value>%s</value>' % i
            aname = opts.attribute.split(":")
            if len(aname) != 2:
                raise oscerr.WrongOptions('Given attribute is not in "NAMESPACE:NAME" style')
            d = '<attributes><attribute namespace=\'%s\' name=\'%s\' >%s</attribute></attributes>' % (aname[0], aname[1], values)
            url = makeurl(apiurl, attributepath)
            for data in streamfile(url, http_POST, data=d):
                sys.stdout.write(decode_it(data))

        # upload file
        if opts.file:

            if opts.file == '-':
                f = sys.stdin.read()
            else:
                try:
                    f = open(opts.file).read()
                except:
                    sys.exit('could not open file \'%s\'.' % opts.file)

            if cmd == 'prj':
                edit_meta(metatype='prj',
                          data=f,
                          edit=opts.edit,
                          force=opts.force,
                          remove_linking_repositories=opts.remove_linking_repositories,
                          apiurl=apiurl,
                          msg = opts.message,
                          path_args=quote_plus(project))
            elif cmd == 'pkg':
                edit_meta(metatype='pkg',
                          data=f,
                          edit=opts.edit,
                          apiurl=apiurl,
                          path_args=(quote_plus(project), quote_plus(package)))
            elif cmd == 'prjconf':
                edit_meta(metatype='prjconf',
                          data=f,
                          edit=opts.edit,
                          apiurl=apiurl,
                          msg = opts.message,
                          path_args=quote_plus(project))
            elif cmd == 'user':
                edit_meta(metatype='user',
                          data=f,
                          edit=opts.edit,
                          apiurl=apiurl,
                          path_args=(quote_plus(user)))
            elif cmd == 'group':
                edit_meta(metatype='group',
                          data=f,
                          edit=opts.edit,
                          apiurl=apiurl,
                          path_args=(quote_plus(group)))
            elif cmd == 'pattern':
                edit_meta(metatype='pattern',
                          data=f,
                          edit=opts.edit,
                          apiurl=apiurl,
                          path_args=(project, pattern))


        # delete
        if opts.delete:
            path = metatypes[cmd]['path']
            if cmd == 'pattern':
                path = path % (project, pattern)
                u = makeurl(apiurl, [path])
                http_DELETE(u)
            elif cmd == 'attribute':
                if not opts.attribute:
                    raise oscerr.WrongOptions('no attribute given to create')
                attributepath.append(opts.attribute)
                u = makeurl(apiurl, attributepath)
                for data in streamfile(u, http_DELETE):
                    sys.stdout.write(decode_it(data))
            else:
                raise oscerr.WrongOptions('The --delete switch is only for pattern metadata or attributes.')


    # TODO: rewrite and consolidate the current submitrequest/createrequest "mess"

    @cmdln.option('-m', '--message', metavar='TEXT',
                  help='specify message TEXT')
    @cmdln.option('-r', '--revision', metavar='REV',
                  help='specify a certain source revision ID (the md5 sum) for the source package')
    @cmdln.option('-s', '--supersede', metavar='REQUEST_ID',
                  help='Superseding another request by this one')
    @cmdln.option('--nodevelproject', action='store_true',
                  help='do not follow a defined devel project ' \
                       '(primary project where a package is developed)')
    @cmdln.option('--separate-requests', action='store_true',
                  help='Create multiple requests instead of a single one (when command is used for entire project)')
    @cmdln.option('--seperate-requests', action='store_true',
                  help='Deprecated (wrong spelling - see --separate-requests)')
    @cmdln.option('--cleanup', action='store_true',
                  help='remove package if submission gets accepted (default for home:<id>:branch projects)')
    @cmdln.option('--no-cleanup', action='store_true',
                  help='never remove source package on accept, but update its content')
    @cmdln.option('--no-update', action='store_true',
                  help='never touch source package on accept (will break source links)')
    @cmdln.option('--update-link', action='store_true',
                  help='This transfers the source including the _link file.')
    @cmdln.option('-d', '--diff', action='store_true',
                  help='show diff only instead of creating the actual request')
    @cmdln.option('--yes', action='store_true',
                  help='proceed without asking.')
    @cmdln.alias("sr")
    @cmdln.alias("submitreq")
    @cmdln.alias("submitpac")
    def do_submitrequest(self, subcmd, opts, *args):
        """${cmd_name}: Create request to submit source into another Project

        [See http://en.opensuse.org/openSUSE:Build_Service_Collaboration for information
        on this topic.]

        See the "request" command for showing and modifying existing requests.

        usage:
            osc submitreq [OPTIONS]
            osc submitreq [OPTIONS] DESTPRJ [DESTPKG]
            osc submitreq [OPTIONS] SOURCEPRJ SOURCEPKG DESTPRJ [DESTPKG]

            osc submitpac ... is a shorthand for osc submitreq --cleanup ...

        ${cmd_option_list}
        """
        def _check_service(root):
            serviceinfo = root.find('serviceinfo')
            if serviceinfo is not None:
                # code "running" is ok, because the api will choke when trying
                # to create the sr (if it is still running)
                if serviceinfo.get('code') not in ('running', 'succeeded'):
                    print('A service run for package %s %s:'
                          % (root.get('name'), serviceinfo.get('code')),
                          file=sys.stderr)
                    error = serviceinfo.find('error')
                    if error is not None:
                        print('\n'.join(error.text.split('\\n')))
                    sys.exit('\nPlease fix this first')


        if opts.cleanup and opts.no_cleanup:
            raise oscerr.WrongOptions('\'--cleanup\' and \'--no-cleanup\' are mutually exclusive')
        if opts.seperate_requests:
            # compatibility option will be removed in the future
            print('--seperate-requests is deprecated (use '
                  '--separate-requests)', file=sys.stderr)

        src_update = conf.config['submitrequest_on_accept_action'] or None
        # we should check here for home:<id>:branch and default to update, but that would require OBS 1.7 server

        if subcmd == 'submitpac' and not opts.no_cleanup:
            opts.cleanup = True

        if opts.cleanup:
            src_update = "cleanup"
        elif opts.no_cleanup:
            src_update = "update"
        elif opts.no_update:
            src_update = "noupdate"

        myreqs = []
        if opts.supersede:
            myreqs = [opts.supersede]

        args = slash_split(args)

        # remove this block later again
        oldcmds = ['create', 'list', 'log', 'show', 'decline', 'accept', 'delete', 'revoke']
        if args and args[0] in oldcmds:
            print("************************************************************************", file=sys.stderr)
            print("* WARNING: It looks that you are using this command with a             *", file=sys.stderr)
            print("*          deprecated syntax.                                          *", file=sys.stderr)
            print("*          Please run \"osc sr --help\" and \"osc rq --help\"              *", file=sys.stderr)
            print("*          to see the new syntax.                                      *", file=sys.stderr)
            print("************************************************************************", file=sys.stderr)
            if args[0] == 'create':
                args.pop(0)
            else:
                sys.exit(1)

        if len(args) > 4:
            raise oscerr.WrongArgs('Too many arguments.')

        if len(args) == 2 and is_project_dir(os.getcwd()):
            sys.exit('You can not specify a target package when submitting an entire project\n')

        apiurl = self.get_api_url()

        if len(args) < 2 and is_project_dir(os.getcwd()):
            if opts.diff:
                raise oscerr.WrongOptions('\'--diff\' is not supported in a project working copy')
            import cgi
            project = store_read_project(os.curdir)

            sr_ids = []

            target_project = None
            if len(args) == 1:
                target_project = args[0]
            if opts.separate_requests or opts.seperate_requests:
                for p in meta_get_packagelist(apiurl, project):
                    # get _link info from server, that knows about the local state ...
                    u = makeurl(apiurl, ['source', project, p])
                    f = http_GET(u)
                    root = ET.parse(f).getroot()
                    _check_service(root)
                    linkinfo = root.find('linkinfo')
                    if linkinfo == None:
                        if len(args) < 1:
                            print("Package ", p, " is not a source link and no target specified.")
                            sys.exit("This is currently not supported.")
                    else:
                        if linkinfo.get('error'):
                            print("Package ", p, " is a broken source link.")
                            sys.exit("Please fix this first")
                        t = linkinfo.get('project')
                        if t is None:
                            print("Skipping package ", p,  " since it is a source link pointing inside the project.")
                            continue 
                    print("Submitting package ", p)
                    try:
                        result = create_submit_request(apiurl, project, p, target_project, src_update=src_update)
                    except HTTPError as e:
                        if e.hdrs.get('X-Opensuse-Errorcode') == 'missing_action':
                            print("Package ", p, " no changes. Skipping...")
                            continue
                        raise
                    if not result:
                        sys.exit("submit request creation failed")
                    sr_ids.append(result)
            else:
                actionxml = ""
                options_block = "<options>"
                if src_update:
                    options_block += """<sourceupdate>%s</sourceupdate>""" % (src_update)
                if opts.update_link:
                    options_block  + """<updatelink>true</updatelink></options> """
                options_block += "</options>"
                target_prj_block = ""
                if target_project is not None:
                    target_prj_block = """<target project="%s"/>""" % target_project
                s = """<action type="submit"> <source project="%s" /> %s %s </action>"""  % \
                        (project, target_prj_block, options_block)
                actionxml += s
                xml = """<request> %s <state name="new"/> <description>%s</description> </request> """ % \
                        (actionxml, cgi.escape(opts.message or ""))
                u = makeurl(apiurl, ['request'], query='cmd=create&addrevision=1')
                f = http_POST(u, data=xml)

                root = ET.parse(f).getroot()
                sr_ids.append(root.get('id'))

            print("Request(s) created: ", end=' ')
            for i in sr_ids:
                print(i, end=' ')

            # was this project created by clone request ?
            u = makeurl(apiurl, ['source', project, '_attribute', 'OBS:RequestCloned'])
            f = http_GET(u)
            root = ET.parse(f).getroot()
            value = root.findtext('attribute/value')
            if value and not opts.yes:
                repl = ''
                print('\n\nThere are already following submit request: %s.' % \
                      ', '.join([str(i) for i in myreqs ]))
                repl = raw_input('\nSupersede the old requests? (y/n) ')
                if repl.lower() == 'y':
                    myreqs += [ value ]

            if len(myreqs) > 0:
                for req in myreqs:
                    change_request_state(apiurl, str(req), 'superseded',
                                             'superseded by %s' % result, result)

            sys.exit('Successfully finished')

        elif len(args) <= 2:
            # try using the working copy at hand
            p = findpacs(os.curdir)[0]
            src_project = p.prjname
            src_package = p.name
            if self.options.apiurl and self.options.apiurl != p.apiurl:
                print('The apiurl for the working copy of this package is %s' % p.apiurl)
                print('You cannot use this command with the -A %s option.' % self.options.apiurl)
                sys.exit(1)
            apiurl = p.apiurl
            if len(args) == 0 and p.islink():
                dst_project = p.linkinfo.project
                dst_package = p.linkinfo.package
            elif len(args) > 0:
                dst_project = args[0]
                if len(args) == 2:
                    dst_package = args[1]
                else:
                    if p.islink():
                        dst_package = p.linkinfo.package
                    else:
                        dst_package = src_package
            else:
                sys.exit('Package \'%s\' is not a source link, so I cannot guess the submit target.\n'
                         'Please provide it the target via commandline arguments.' % p.name)

            modified = [i for i in p.filenamelist if not p.status(i) in (' ', '?', 'S')]
            if len(modified) > 0 and not opts.yes:
                print('Your working copy has local modifications.')
                repl = raw_input('Proceed without committing the local changes? (y|N) ')
                if repl != 'y':
                    raise oscerr.UserAbort()
        elif len(args) >= 3:
            # get the arguments from the commandline
            src_project, src_package, dst_project = args[0:3]
            if len(args) == 4:
                dst_package = args[3]
            else:
                dst_package = src_package
        else:
            raise oscerr.WrongArgs('Incorrect number of arguments.\n\n' \
                  + self.get_cmd_help('request'))

        # check for failed source service
        u = makeurl(apiurl, ['source', src_project, src_package])
        f = http_GET(u)
        root = ET.parse(f).getroot()
        _check_service(root)

        if not opts.nodevelproject:
            devloc = None
            try:
                devloc, _ = show_devel_project(apiurl, dst_project, dst_package)
            except HTTPError:
                print("""\
Warning: failed to fetch meta data for '%s' package '%s' (new package?) """ \
                    % (dst_project, dst_package), file=sys.stderr)

            if devloc and \
               dst_project != devloc and \
               src_project != devloc:
                print("""\
A different project, %s, is defined as the place where development
of the package %s primarily takes place.
Please submit there instead, or use --nodevelproject to force direct submission.""" \
                % (devloc, dst_package))
                if not opts.diff:
                    sys.exit(1)

        rev = opts.revision
        if not rev:
            # get _link info from server, that knows about the local state ...
            u = makeurl(apiurl, ['source', src_project, src_package], query="expand=1")
            f = http_GET(u)
            root = ET.parse(f).getroot()
            linkinfo = root.find('linkinfo')
            if linkinfo == None:
                rev = root.get('rev')
            else:
                if linkinfo.get('project') != dst_project or linkinfo.get('package') != dst_package:
                    # the submit target is not link target. use merged md5sum references to
                    # avoid not mergable sources when multiple request from same source get created.
                    rev = root.get('srcmd5')

        rdiff = None
        if opts.diff or not opts.message:
            try:
                rdiff = b'old: %s/%s\nnew: %s/%s rev %s\n' % (dst_project.encode(), dst_package.encode(), src_project.encode(), src_package.encode(), str(rev).encode())
                rdiff += server_diff(apiurl,
                                dst_project, dst_package, None,
                                src_project, src_package, rev, True)
            except:
                rdiff = b''

        if opts.diff:
            run_pager(rdiff)
            return
        if rdiff is not None:
            rdiff = decode_it(rdiff)

        supersede_existing = False
        reqs = []
        if not opts.supersede:
            (supersede_existing, reqs) = check_existing_requests(apiurl,
                                                                 src_project,
                                                                 src_package,
                                                                 dst_project,
                                                                 dst_package,
                                                                 not opts.yes)
            if not supersede_existing:
               (supersede_existing, reqs) = check_existing_maintenance_requests(apiurl,
                                                                 src_project,
                                                                 [src_package],
                                                                 dst_project, None,
                                                                 not opts.yes)
        if not opts.message:
            difflines = []
            doappend = False
            changes_re = re.compile(r'^--- .*\.changes ')
            for line in rdiff.split('\n'):
                if line.startswith('--- '):
                    if changes_re.match(line):
                        doappend = True
                    else:
                        doappend = False
                if doappend:
                    difflines.append(line)
            opts.message = edit_message(footer=rdiff, template='\n'.join(parse_diff_for_commit_message('\n'.join(difflines))))

        result = create_submit_request(apiurl,
                                       src_project, src_package,
                                       dst_project, dst_package,
                                       opts.message, orev=rev,
				       src_update=src_update, dst_updatelink=opts.update_link)

        print('created request id', result)
        if conf.config['print_web_links']:
            root = ET.fromstring(b''.join(show_configuration(apiurl)))
            node = root.find('obs_url')
            if node is None or not node.text:
                raise oscerr.APIError('obs_url configuration element expected')
            obs_url = node.text
            print('%s/request/show/%s' % (obs_url, result))

        if supersede_existing:
            for req in reqs:
                change_request_state(apiurl, req.reqid, 'superseded',
                                     'superseded by %s' % result, result)

        if opts.supersede:
            change_request_state(apiurl, opts.supersede, 'superseded',
                                 opts.message or '', result)

    def _actionparser(self, opt_str, value, parser):
        value = []
        if not hasattr(parser.values, 'actiondata'):
            setattr(parser.values, 'actiondata', [])
        if parser.values.actions == None:
            parser.values.actions = []

        rargs = parser.rargs
        while rargs:
            arg = rargs[0]
            if ((arg[:2] == "--" and len(arg) > 2) or
                    (arg[:1] == "-" and len(arg) > 1 and arg[1] != "-")):
                break
            else:
                value.append(arg)
                del rargs[0]

        parser.values.actions.append(value[0])
        del value[0]
        parser.values.actiondata.append(value)

    def _submit_request(self, args, opts, options_block):
        actionxml = ""
        apiurl = self.get_api_url()
        if len(args) == 0 and is_project_dir(os.getcwd()):
            # submit requests for multiple packages are currently handled via multiple requests
            # They could be also one request with multiple actions, but that avoids to accepts parts of it.
            project = store_read_project(os.curdir)

            pi = []
            pac = []
            targetprojects = []
            # loop via all packages for checking their state
            for p in meta_get_packagelist(apiurl, project):
                if p.startswith("_patchinfo:"):
                    pi.append(p)
                else:
                    # get _link info from server, that knows about the local state ...
                    u = makeurl(apiurl, ['source', project, p])
                    f = http_GET(u)
                    root = ET.parse(f).getroot()
                    linkinfo = root.find('linkinfo')
                    if linkinfo == None:
                        print("Package ", p, " is not a source link.")
                        sys.exit("This is currently not supported.")
                    if linkinfo.get('error'):
                        print("Package ", p, " is a broken source link.")
                        sys.exit("Please fix this first")
                    t = linkinfo.get('project')
                    if t:
                        rdiff = b''
                        try:
                            rdiff = server_diff(apiurl, t, p, opts.revision, project, p, None, True)
                        except:
                            rdiff = b''

                        if rdiff != b'':
                            targetprojects.append(t)
                            pac.append(p)
                        else:
                            print("Skipping package ", p,  " since it has no difference with the target package.")
                    else:
                        print("Skipping package ", p,  " since it is a source link pointing inside the project.")

            # loop via all packages to do the action
            for p in pac:
                s = """<action type="submit"> <source project="%s" package="%s"  rev="%s"/> <target project="%s" package="%s"/> %s </action>"""  % \
                       (project, p, opts.revision or show_upstream_rev(apiurl, project, p), t, p, options_block)
                actionxml += s

            # create submit requests for all found patchinfos
            for p in pi:
                for t in targetprojects:
                    s = """<action type="submit"> <source project="%s" package="%s" /> <target project="%s" package="%s" /> %s </action>"""  % \
                           (project, p, t, p, options_block)
                    actionxml += s

            return actionxml, []

        elif len(args) <= 2:
            # try using the working copy at hand
            p = findpacs(os.curdir)[0]
            src_project = p.prjname
            src_package = p.name
            if len(args) == 0 and p.islink():
                dst_project = p.linkinfo.project
                dst_package = p.linkinfo.package
            elif len(args) > 0:
                dst_project = args[0]
                if len(args) == 2:
                    dst_package = args[1]
                else:
                    dst_package = src_package
            else:
                sys.exit('Package \'%s\' is not a source link, so I cannot guess the submit target.\n'
                         'Please provide it the target via commandline arguments.' % p.name)

            modified = [i for i in p.filenamelist if p.status(i) != ' ' and p.status(i) != '?']
            if len(modified) > 0:
                print('Your working copy has local modifications.')
                repl = raw_input('Proceed without committing the local changes? (y|N) ')
                if repl != 'y':
                    sys.exit(1)
        elif len(args) >= 3:
            # get the arguments from the commandline
            src_project, src_package, dst_project = args[0:3]
            if len(args) == 4:
                dst_package = args[3]
            else:
                dst_package = src_package
        else:
            raise oscerr.WrongArgs('Incorrect number of arguments.\n\n' \
                  + self.get_cmd_help('request'))

        if not opts.nodevelproject:
            devloc = None
            try:
                devloc, _ = show_devel_project(apiurl, dst_project, dst_package)
            except HTTPError:
                print("""\
Warning: failed to fetch meta data for '%s' package '%s' (new package?) """ \
                    % (dst_project, dst_package), file=sys.stderr)

            if devloc and \
               dst_project != devloc and \
               src_project != devloc:
                print("""\
A different project, %s, is defined as the place where development
of the package %s primarily takes place.
Please submit there instead, or use --nodevelproject to force direct submission.""" \
                % (devloc, dst_package))
                sys.exit(1)

        reqs = get_request_list(apiurl, dst_project, dst_package, req_type='submit', req_state=['new', 'review'])
        user = conf.get_apiurl_usr(apiurl)
        myreqs = [ i for i in reqs if i.state.who == user and i.reqid != opts.supersede ]
        repl = 'y'
        if len(myreqs) > 0 and not opts.yes:
            print('You already created the following submit request: %s.' % \
                  ', '.join([i.reqid for i in myreqs ]))
            repl = raw_input('Supersede the old requests? (y/n/c) ')
            if repl.lower() == 'c':
                print('Aborting', file=sys.stderr)
                sys.exit(1)
            elif repl.lower() != 'y':
                myreqs = []

        actionxml = """<action type="submit"> <source project="%s" package="%s"  rev="%s"/> <target project="%s" package="%s"/> %s </action>"""  % \
                (src_project, src_package, opts.revision or show_upstream_rev(apiurl, src_project, src_package), dst_project, dst_package, options_block)
        if opts.supersede:
            myreqs.append(opts.supersede)

        #print 'created request id', result
        return actionxml, myreqs

    def _delete_request(self, args, opts):
        if len(args) < 1:
            raise oscerr.WrongArgs('Please specify at least a project.')
        if len(args) > 2:
            raise oscerr.WrongArgs('Too many arguments.')

        package = ""
        if len(args) > 1:
            package = """package="%s" """ % (args[1])
        actionxml = """<action type="delete"> <target project="%s" %s/> </action> """ % (args[0], package)
        return actionxml

    def _changedevel_request(self, args, opts):
        if len(args) > 4:
            raise oscerr.WrongArgs('Too many arguments.')

        if len(args) == 0 and is_package_dir('.') and find_default_project():
            wd = os.curdir
            devel_project = store_read_project(wd)
            devel_package = package = store_read_package(wd)
            project = find_default_project(self.get_api_url(), package)
        else:
            if len(args) < 3:
                raise oscerr.WrongArgs('Too few arguments.')

            devel_project = args[2]
            project = args[0]
            package = args[1]
            devel_package = package
            if len(args) > 3:
                devel_package = args[3]

        actionxml = """ <action type="change_devel"> <source project="%s" package="%s" /> <target project="%s" package="%s" /> </action> """ % \
                (devel_project, devel_package, project, package)

        return actionxml

    def _add_me(self, args, opts):
        if len(args) > 3:
            raise oscerr.WrongArgs('Too many arguments.')
        if len(args) < 2:
            raise oscerr.WrongArgs('Too few arguments.')

        apiurl = self.get_api_url()

        user = conf.get_apiurl_usr(apiurl)
        role = args[0]
        project = args[1]
        actionxml = """ <action type="add_role"> <target project="%s" /> <person name="%s" role="%s" /> </action> """ % \
                (project, user, role)

        if len(args) > 2:
            package = args[2]
            actionxml = """ <action type="add_role"> <target project="%s" package="%s" /> <person name="%s" role="%s" /> </action> """ % \
                (project, package, user, role)

        if get_user_meta(apiurl, user) == None:
            raise oscerr.WrongArgs('osc: an error occurred.')

        return actionxml

    def _add_user(self, args, opts):
        if len(args) > 4:
            raise oscerr.WrongArgs('Too many arguments.')
        if len(args) < 3:
            raise oscerr.WrongArgs('Too few arguments.')

        apiurl = self.get_api_url()

        user = args[0]
        role = args[1]
        project = args[2]
        actionxml = """ <action type="add_role"> <target project="%s" /> <person name="%s" role="%s" /> </action> """ % \
                (project, user, role)

        if len(args) > 3:
            package = args[3]
            actionxml = """ <action type="add_role"> <target project="%s" package="%s" /> <person name="%s" role="%s" /> </action> """ % \
                (project, package, user, role)

        if get_user_meta(apiurl, user) == None:
            raise oscerr.WrongArgs('osc: an error occured.')

        return actionxml

    def _add_group(self, args, opts):
        if len(args) > 4:
            raise oscerr.WrongArgs('Too many arguments.')
        if len(args) < 3:
            raise oscerr.WrongArgs('Too few arguments.')

        apiurl = self.get_api_url()

        group = args[0]
        role = args[1]
        project = args[2]
        actionxml = """ <action type="add_role"> <target project="%s" /> <group name="%s" role="%s" /> </action> """ % \
                (project, group, role)

        if len(args) > 3:
            package = args[3]
            actionxml = """ <action type="add_role"> <target project="%s" package="%s" /> <group name="%s" role="%s" /> </action> """ % \
                (project, package, group, role)

        if get_group_meta(apiurl, group) == None:
            raise oscerr.WrongArgs('osc: an error occured.')

        return actionxml

    def _set_bugowner(self, args, opts):
        if len(args) > 3:
            raise oscerr.WrongArgs('Too many arguments.')
        if len(args) < 2:
            raise oscerr.WrongArgs('Too few arguments.')

        apiurl = self.get_api_url()

        user = args[0]
        project = args[1]
        package = ""
        if len(args) > 2:
            package =  """package="%s" """ % (args[2])

        if user.startswith('group:'):
            group = user.replace('group:', '')
            actionxml = """ <action type="set_bugowner"> <target project="%s" %s /> <group name="%s" /> </action> """ % \
                    (project, package, group)
            if get_group_meta(apiurl, group) == None:
                raise oscerr.WrongArgs('osc: an error occurred.')
        else:
            actionxml = """ <action type="set_bugowner"> <target project="%s" %s /> <person name="%s" /> </action> """ % \
                    (project, package, user)
            if get_user_meta(apiurl, user) == None:
                raise oscerr.WrongArgs('osc: an error occured.')


        return actionxml

    @cmdln.option('-a', '--action', action='callback', callback = _actionparser, dest = 'actions',
                  help='specify action type of a request, can be : submit/delete/change_devel/add_role/set_bugowner')
    @cmdln.option('-m', '--message', metavar='TEXT',
                  help='specify message TEXT')
    @cmdln.option('-r', '--revision', metavar='REV',
                  help='for "create", specify a certain source revision ID (the md5 sum)')
    @cmdln.option('-s', '--supersede', metavar='REQUEST_ID',
                  help='Superseding another request by this one')
    @cmdln.option('--nodevelproject', action='store_true',
                  help='do not follow a defined devel project ' \
                       '(primary project where a package is developed)')
    @cmdln.option('--cleanup', action='store_true',
                  help='remove package if submission gets accepted (default for home:<id>:branch projects)')
    @cmdln.option('--no-cleanup', action='store_true',
                  help='never remove source package on accept, but update its content')
    @cmdln.option('--no-update', action='store_true',
                  help='never touch source package on accept (will break source links)')
    @cmdln.option('--yes', action='store_true',
                  help='proceed without asking.')
    @cmdln.alias("creq")
    def do_createrequest(self, subcmd, opts, *args):
        """${cmd_name}: create multiple requests with a single command

        usage:
            osc creq [OPTIONS] [
                -a submit SOURCEPRJ SOURCEPKG DESTPRJ [DESTPKG]
                -a delete PROJECT [PACKAGE]
                -a change_devel PROJECT PACKAGE DEVEL_PROJECT [DEVEL_PACKAGE]
                -a add_me ROLE PROJECT [PACKAGE]
                -a add_group GROUP ROLE PROJECT [PACKAGE]
                -a add_role USER ROLE PROJECT [PACKAGE]
                -a set_bugowner USER PROJECT [PACKAGE]
                ]

            Option -m works for all types of request, the rest work only for submit.
        example:
            osc creq -a submit -a delete home:someone:branches:openSUSE:Tools -a change_devel openSUSE:Tools osc home:someone:branches:openSUSE:Tools -m ok

            This will submit all modified packages under current directory, delete project home:someone:branches:openSUSE:Tools and change the devel project to home:someone:branches:openSUSE:Tools for package osc in project openSUSE:Tools.
        ${cmd_option_list}
        """
        src_update = conf.config['submitrequest_on_accept_action'] or None
        # we should check here for home:<id>:branch and default to update, but that would require OBS 1.7 server
        if opts.cleanup:
            src_update = "cleanup"
        elif opts.no_cleanup:
            src_update = "update"
        elif opts.no_update:
            src_update = "noupdate"

        options_block = ""
        if src_update:
            options_block = """<options><sourceupdate>%s</sourceupdate></options> """ % (src_update)

        args = slash_split(args)

        apiurl = self.get_api_url()

        i = 0
        actionsxml = ""
        supersede = []
        for ai in opts.actions:
            if ai == 'submit':
                args = opts.actiondata[i]
                i = i+1
                actions, to_supersede = self._submit_request(args, opts, options_block)
                actionsxml += actions
                supersede.extend(to_supersede)
            elif ai == 'delete':
                args = opts.actiondata[i]
                actionsxml += self._delete_request(args, opts)
                i = i+1
            elif ai == 'change_devel':
                args = opts.actiondata[i]
                actionsxml += self._changedevel_request(args, opts)
                i = i+1
            elif ai == 'add_me':
                args = opts.actiondata[i]
                actionsxml += self._add_me(args, opts)
                i = i+1
            elif ai == 'add_group':
                args = opts.actiondata[i]
                actionsxml += self._add_group(args, opts)
                i = i+1
            elif ai == 'add_role':
                args = opts.actiondata[i]
                actionsxml += self._add_user(args, opts)
                i = i+1
            elif ai == 'set_bugowner':
                args = opts.actiondata[i]
                actionsxml += self._set_bugowner(args, opts)
                i = i+1
            else:
                raise oscerr.WrongArgs('Unsupported action %s' % ai)
        if actionsxml == "":
            sys.exit('No actions need to be taken.')

        if not opts.message:
            opts.message = edit_message()

        import cgi
        xml = """<request> %s <state name="new"/> <description>%s</description> </request> """ % \
              (actionsxml, cgi.escape(opts.message or ""))
        u = makeurl(apiurl, ['request'], query='cmd=create')
        f = http_POST(u, data=xml)

        root = ET.parse(f).getroot()
        rid = root.get('id')
        for srid in supersede:
            change_request_state(apiurl, srid, 'superseded',
                                 'superseded by %s' % rid, rid)
        return rid


    @cmdln.option('-m', '--message', metavar='TEXT',
                  help='specify message TEXT')
    @cmdln.option('-r', '--role', metavar='role',
                   help='specify user role (default: maintainer)')
    @cmdln.alias("reqbugownership")
    @cmdln.alias("requestbugownership")
    @cmdln.alias("reqmaintainership")
    @cmdln.alias("reqms")
    @cmdln.alias("reqbs")
    def do_requestmaintainership(self, subcmd, opts, *args):
        """${cmd_name}: requests to add user as maintainer or bugowner

        usage:
            osc requestmaintainership                            # for current user in checked out package
            osc requestmaintainership USER                       # for specified user in checked out package
            osc requestmaintainership PROJECT                    # for current user if cwd is not a checked out package
            osc requestmaintainership PROJECT group:NAME         # request for specified group
            osc requestmaintainership PROJECT PACKAGE            # for current user
            osc requestmaintainership PROJECT PACKAGE USER       # request for specified user
            osc requestmaintainership PROJECT PACKAGE group:NAME # request for specified group

            osc requestbugownership ...                          # accepts same parameters but uses bugowner role

        ${cmd_option_list}
        """
        import cgi
        args = slash_split(args)
        apiurl = self.get_api_url()

        if len(args) == 2:
            project = args[0]
            package = args[1]
            if package.startswith('group:'):
                user = package
                package = None
            else:
                user = conf.get_apiurl_usr(apiurl)
        elif len(args) == 3:
            project = args[0]
            package = args[1]
            user = args[2]
        elif len(args) < 2 and is_package_dir(os.curdir):
            project = store_read_project(os.curdir)
            package = store_read_package(os.curdir)
            if len(args) == 0:
                user = conf.get_apiurl_usr(apiurl)
            else:
                user = args[0]
        elif len(args) == 1:
            user = conf.get_apiurl_usr(apiurl)
            project = args[0]
            package = None
        else:
            raise oscerr.WrongArgs('Wrong number of arguments.')

        role = 'maintainer'
        if subcmd in ( 'reqbugownership', 'requestbugownership', 'reqbs' ):
            role = 'bugowner'
        if opts.role:
            role = opts.role
        if not role in ('maintainer', 'bugowner'):
            raise oscerr.WrongOptions('invalid \'--role\': either specify \'maintainer\' or \'bugowner\'')
        if not opts.message:
            opts.message = edit_message()

        r = Request()
        if user.startswith('group:'):
           group = user.replace('group:', '')
           if role == 'bugowner':
               r.add_action('set_bugowner', tgt_project=project, tgt_package=package,
                 group_name=group)
           else:
               r.add_action('add_role', tgt_project=project, tgt_package=package,
                 group_name=group, group_role=role)
        elif role == 'bugowner':
            r.add_action('set_bugowner', tgt_project=project, tgt_package=package,
              person_name=user)
        else:
            r.add_action('add_role', tgt_project=project, tgt_package=package,
              person_name=user, person_role=role)
        r.description = cgi.escape(opts.message or '')
        r.create(apiurl)
        print(r.reqid)

    @cmdln.option('-m', '--message', metavar='TEXT',
                  help='specify message TEXT')
    @cmdln.option('-r', '--repository', metavar='REPOSITORY',
                  help='specify repository')
    @cmdln.option('--all', action='store_true',
                        help='deletes entire project with packages inside')
    @cmdln.option('--accept-in-hours', metavar='HOURS',
                  help='specify time when request shall get accepted automatically. Only works with write permissions in target.')
    @cmdln.alias("dr")
    @cmdln.alias("dropreq")
    @cmdln.alias("droprequest")
    @cmdln.alias("deletereq")
    def do_deleterequest(self, subcmd, opts, *args):
        """${cmd_name}: Request to delete (or 'drop') a package or project

        usage:
            osc deletereq [-m TEXT]                     # works in checked out project/package
            osc deletereq [-m TEXT] PROJECT PACKAGE
            osc deletereq [-m TEXT] PROJECT [--all|--repository REPOSITORY]
        ${cmd_option_list}
        """
        import cgi

        args = slash_split(args)

        project = None
        package = None
        repository = None

        if len(args) > 2:
            raise oscerr.WrongArgs('Too many arguments.')
        elif len(args) == 1:
            project = args[0]
        elif len(args) == 2:
            project = args[0]
            package = args[1]
        elif is_project_dir(os.getcwd()):
            project = store_read_project(os.curdir)
        elif is_package_dir(os.getcwd()):
            project = store_read_project(os.curdir)
            package = store_read_package(os.curdir)
        else:
            raise oscerr.WrongArgs('Please specify at least a project.')

        if not opts.all and package is None and not opts.repository:
            raise oscerr.WrongOptions('No package name has been provided. Use --all option, if you want to request to delete the entire project.')

        if opts.repository:
            repository = opts.repository

        if not opts.message:
            import textwrap
            if package is not None:
                footer = textwrap.TextWrapper(width = 66).fill(
                         'please explain why you like to delete package %s of project %s'
                          % (package, project))
            else:
                footer = textwrap.TextWrapper(width = 66).fill(
                         'please explain why you like to delete project %s' % project)
            opts.message = edit_message(footer)

        r = Request()
        r.add_action('delete', tgt_project=project, tgt_package=package, tgt_repository=repository)
        r.description = cgi.escape(opts.message)
        if opts.accept_in_hours:
          r.accept_at_in_hours(int(opts.accept_in_hours))
        r.create(self.get_api_url())
        print(r.reqid)


    @cmdln.option('-m', '--message', metavar='TEXT',
                  help='specify message TEXT')
    @cmdln.alias("cr")
    @cmdln.alias("changedevelreq")
    def do_changedevelrequest(self, subcmd, opts, *args):
        """${cmd_name}: Create request to change the devel package definition.

        [See http://en.opensuse.org/openSUSE:Build_Service_Collaboration
        for information on this topic.]

        See the "request" command for showing and modifying existing requests.

        osc changedevelrequest PROJECT PACKAGE DEVEL_PROJECT [DEVEL_PACKAGE]
        """
        import cgi

        if len(args) == 0 and is_package_dir('.') and find_default_project():
            wd = os.curdir
            devel_project = store_read_project(wd)
            devel_package = package = store_read_package(wd)
            project = find_default_project(self.get_api_url(), package)
        elif len(args) < 3:
            raise oscerr.WrongArgs('Too few arguments.')
        elif len(args) > 4:
            raise oscerr.WrongArgs('Too many arguments.')
        else:
            devel_project = args[2]
            project = args[0]
            package = args[1]
            devel_package = package
            if len(args) == 4:
                devel_package = args[3]

        if not opts.message:
            import textwrap
            footer = textwrap.TextWrapper(width = 66).fill(
                     'please explain why you like to change the devel project of %s/%s to %s/%s'
                     % (project, package, devel_project, devel_package))
            opts.message = edit_message(footer)

        r = Request()
        r.add_action('change_devel', src_project=devel_project, src_package=devel_package,
            tgt_project=project, tgt_package=package)
        r.description = cgi.escape(opts.message)
        r.create(self.get_api_url())
        print(r.reqid)


    @cmdln.option('-d', '--diff', action='store_true',
                  help='generate a diff')
    @cmdln.option('-u', '--unified', action='store_true',
                  help='output the diff in the unified diff format')
    @cmdln.option('--no-devel', action='store_true',
                  help='Do not attempt to forward to devel project')
    @cmdln.option('-m', '--message', metavar='TEXT',
                  help='specify message TEXT')
    @cmdln.option('-t', '--type', metavar='TYPE',
                  help='limit to requests which contain a given action type (submit/delete/change_devel/add_role/set_bugowner/maintenance_incident/maintenance_release)')
    @cmdln.option('-a', '--all', action='store_true',
                        help='all states. Same as\'-s all\'')
    @cmdln.option('-f', '--force', action='store_true',
                        help='enforce state change, can be used to ignore open reviews')
    @cmdln.option('-s', '--state', default='',  # default is 'all' if no args given, 'declined,new,review' otherwise
                        help='only list requests in one of the comma separated given states (new/review/accepted/revoked/declined) or "all" [default="declined,new,review", or "all", if no args given]')
    @cmdln.option('-D', '--days', metavar='DAYS',
                        help='only list requests in state "new" or changed in the last DAYS. [default=%(request_list_days)s]')
    @cmdln.option('-U', '--user', metavar='USER',
                        help='requests or reviews limited for the specified USER')
    @cmdln.option('-G', '--group', metavar='GROUP',
                        help='requests or reviews limited for the specified GROUP')
    @cmdln.option('-P', '--project', metavar='PROJECT',
                        help='requests or reviews limited for the specified PROJECT')
    @cmdln.option('-p', '--package', metavar='PACKAGE',
                        help='requests or reviews limited for the specified PACKAGE, requires also a PROJECT')
    @cmdln.option('-b', '--brief', action='store_true', default=False,
                        help='print output in list view as list subcommand')
    @cmdln.option('-M', '--mine', action='store_true',
                        help='only show requests created by yourself')
    @cmdln.option('-B', '--bugowner', action='store_true',
                        help='also show requests about packages where I am bugowner')
    @cmdln.option('-e', '--edit', action='store_true',
                        help='edit a submit action')
    @cmdln.option('-i', '--interactive', action='store_true',
                        help='interactive review of request')
    @cmdln.option('--or-revoke', action='store_true',
                        help='For automation scripts: accepts (if using with accept argument) a request when it is in new or review state. Or revoke it when it got declined. Otherwise just do nothing.')
    @cmdln.option('--non-interactive', action='store_true',
                        help='non-interactive review of request')
    @cmdln.option('--exclude-target-project', action='append',
                        help='exclude target project from request list')
    @cmdln.option('--incoming', action='store_true',
                        help='Show only requests where the project is target')
    @cmdln.option('--involved-projects', action='store_true',
                        help='show all requests for project/packages where USER is involved')
    @cmdln.option('--target-package-filter', metavar='TARGET_PACKAGE_FILTER',
                        help='only list requests for the packages matching the package filter. A (python) regular expression is expected.')
    @cmdln.option('--source-buildstatus', action='store_true',
                        help='print the buildstatus of the source package (only works with "show" and the interactive review)')
    @cmdln.alias("rq")
    @cmdln.alias("review")
    # FIXME: rewrite this mess and split request and review
    def do_request(self, subcmd, opts, *args):
        """${cmd_name}: Show or modify requests and reviews

        [See http://en.opensuse.org/openSUSE:Build_Service_Collaboration
        for information on this topic.]

        The 'request' command has the following sub commands:

        "list" lists open requests attached to a project or package or person.
        Uses the project/package of the current directory if none of
        -M, -U USER, project/package are given.

        "log" will show the history of the given ID

        "show" will show the request itself, and generate a diff for review, if
        used with the --diff option. The keyword show can be omitted if the ID is numeric.

        "decline" will change the request state to "declined"

        "reopen" will set the request back to new or review.

        "setincident" will direct "maintenance" requests into specific incidents

        "supersede" will supersede one request with another existing one.

        "revoke" will set the request state to "revoked"

        "accept" will change the request state to "accepted" and will trigger
        the actual submit process. That would normally be a server-side copy of
        the source package to the target package.

        "approve" marks a requests in "review" state as approved. This request will get accepted
        automatically when the last review got accepted.

        "checkout" will checkout the request's source package ("submit" requests only).

        "prioritize" change the priority of a request to either "critical", "important", "moderate" or "low"


        The 'review' command has the following sub commands:

        "list" lists open requests that need to be reviewed by the
        specified user or group

        "add" adds a person or group as reviewer to a request

        "accept" mark the review positive

        "decline" mark the review negative. A negative review will
        decline the request.

        usage:
            osc request list [-M] [-U USER] [-s state] [-D DAYS] [-t type] [-B] [PRJ [PKG]]
            osc request log ID
            osc request [show] [-d] [-b] ID

            osc request accept [-m TEXT] ID
            osc request approve [-m TEXT] ID
            osc request cancelapproval [-m TEXT] ID
            osc request decline [-m TEXT] ID
            osc request revoke [-m TEXT] ID
            osc request reopen [-m TEXT] ID
            osc request setincident [-m TEXT] ID INCIDENT
            osc request supersede [-m TEXT] ID SUPERSEDING_ID
            osc request approvenew [-m TEXT] PROJECT
            osc request prioritize [-m TEXT] ID PRIORITY

            osc request checkout/co ID
            osc request clone [-m TEXT] ID

            osc review show [-d] [-b] ID
            osc review list [-U USER] [-G GROUP] [-P PROJECT [-p PACKAGE]] [-s state]
            osc review add [-m TEXT] [-U USER] [-G GROUP] [-P PROJECT [-p PACKAGE]] ID
            osc review accept [-m TEXT] [-U USER] [-G GROUP] [-P PROJECT [-p PACKAGE]] ID
            osc review decline [-m TEXT] [-U USER] [-G GROUP] [-P PROJECT [-p PACKAGE]] ID
            osc review reopen [-m TEXT] [-U USER] [-G GROUP] [-P PROJECT [-p PACKAGE]] ID
            osc review supersede [-m TEXT] [-U USER] [-G GROUP] [-P PROJECT [-p PACKAGE]] ID SUPERSEDING_ID

        ${cmd_option_list}
        """

        args = slash_split(args)

        if opts.all and opts.state:
            raise oscerr.WrongOptions('Sorry, the options \'--all\' and \'--state\' ' \
                    'are mutually exclusive.')
        if opts.mine and opts.user:
            raise oscerr.WrongOptions('Sorry, the options \'--user\' and \'--mine\' ' \
                    'are mutually exclusive.')
        if opts.interactive and opts.non_interactive:
            raise oscerr.WrongOptions('Sorry, the options \'--interactive\' and ' \
                    '\'--non-interactive\' are mutually exclusive')

        if not args:
            args = [ 'list' ]
            opts.mine = 1
            if opts.state == '':
                opts.state = 'all'

        if opts.state == '' and subcmd != 'review':
            opts.state = 'declined,new,review'

        if opts.incoming:
            conf.config['include_request_from_project'] = False

        if args[0] == 'help':
            return self.do_help(['help', 'request'])

        cmds = ['list', 'ls', 'log', 'show', 'decline', 'reopen', 'clone', 'accept', 'approve', 'cancelapproval',
                'approvenew', 'wipe', 'setincident', 'supersede', 'revoke', 'checkout', 'co', 'priorize', 'prioritize']
        if subcmd != 'review' and args[0] not in cmds:
            raise oscerr.WrongArgs('Unknown request action %s. Choose one of %s.' \
                                               % (args[0], ', '.join(cmds)))
        cmds = ['show', 'list', 'add', 'decline', 'accept', 'reopen', 'supersede']
        if subcmd == 'review' and args[0] not in cmds:
            raise oscerr.WrongArgs('Unknown review action %s. Choose one of %s.' \
                                               % (args[0], ', '.join(cmds)))

        cmd = args[0]
        del args[0]
        if cmd == 'ls':
            cmd = "list"

        apiurl = self.get_api_url()

        if cmd in ['list']:
            min_args, max_args = 0, 2
        elif cmd in ['supersede', 'setincident', 'prioritize', 'priorize']:
            min_args, max_args = 2, 2
        else:
            min_args, max_args = 1, 1
        if len(args) < min_args:
            raise oscerr.WrongArgs('Too few arguments.')
        if len(args) > max_args:
            raise oscerr.WrongArgs('Too many arguments.')
        if cmd in ['add'] and not opts.user and not opts.group and not opts.project:
            raise oscerr.WrongArgs('No reviewer specified.')

        source_buildstatus = conf.config['request_show_source_buildstatus'] or opts.source_buildstatus

        reqid = None
        supersedid = None
        if cmd == 'list' or cmd == 'approvenew':
            package = None
            project = None
            if len(args) > 0:
                project = args[0]
            elif opts.project:
                project = opts.project
                if opts.package:
                    package = opts.package
            elif not opts.mine and not opts.user and not opts.group:
                try:
                    project = store_read_project(os.curdir)
                    package = store_read_package(os.curdir)
                except oscerr.NoWorkingCopy:
                    pass

            if len(args) > 1:
                package = args[1]
        elif cmd == 'supersede':
            reqid = args[0]
            supersedid = args[1]
        elif cmd == 'setincident':
            reqid = args[0]
            incident = args[1]
        elif cmd in ['prioritize', 'priorize']:
            reqid = args[0]
            priority = args[1]
        elif cmd in ['log', 'add', 'show', 'decline', 'reopen', 'clone', 'accept', 'wipe', 'revoke', 'checkout',
                     'co', 'approve', 'cancelapproval']:
            reqid = args[0]

        # clone all packages from a given request
        if cmd in ['clone']:
            # should we force a message?
            print('Cloned packages are available in project: %s' % clone_request(apiurl, reqid, opts.message))

        # approve request
        elif cmd == 'approve' or cmd == 'cancelapproval':
            query = { 'cmd': cmd }
            url = makeurl(apiurl, ['request', reqid], query)
            r = http_POST(url, data=opts.message)
            print(ET.parse(r).getroot().get('code'))

        # change incidents
        elif cmd == 'setincident':
            query = { 'cmd': 'setincident', 'incident': incident }
            url = makeurl(apiurl, ['request', reqid], query)
            r = http_POST(url, data=opts.message)
            print(ET.parse(r).getroot().get('code'))

        # change priority
        elif cmd in ['prioritize', 'priorize']:
            query = { 'cmd': 'setpriority', 'priority': priority }
            url = makeurl(apiurl, ['request', reqid], query)
            r = http_POST(url, data=opts.message)
            print(ET.parse(r).getroot().get('code'))

        # add new reviewer to existing request
        elif cmd in ['add'] and subcmd == 'review':
            query = { 'cmd': 'addreview' }
            if opts.user:
                query['by_user'] = opts.user
            if opts.group:
                query['by_group'] = opts.group
            if opts.project:
                query['by_project'] = opts.project
            if opts.package:
                query['by_package'] = opts.package
            url = makeurl(apiurl, ['request', reqid], query)
            if not opts.message:
                opts.message = edit_message()
            r = http_POST(url, data=opts.message)
            print(ET.parse(r).getroot().get('code'))

        # list and approvenew
        elif cmd == 'list' or cmd == 'approvenew':
            states = ('new', 'accepted', 'revoked', 'declined', 'review', 'superseded')
            who = ''
            if cmd == 'approvenew':
                states = ('new')
                results = get_request_list(apiurl, project, package, '', ['new'])
            else:
                state_list = opts.state.split(',')
                if state_list == ['']:
                    state_list = ()
                if opts.all:
                    state_list = ['all']
                else:
                    for s in state_list:
                        if not s in states and not s == 'all':
                            raise oscerr.WrongArgs('Unknown state \'%s\', try one of %s' % (s, ','.join(states)))
                if opts.mine:
                    who = conf.get_apiurl_usr(apiurl)
                if opts.user:
                    who = opts.user

                ## FIXME -B not implemented!
                if opts.bugowner:
                    if (self.options.debug):
                        print('list: option --bugowner ignored: not impl.')

                if subcmd == 'review':
                    # FIXME: do the review list for the user and for all groups he belong to
                    results = get_review_list(apiurl, project, package, who, opts.group, opts.project, opts.package, state_list,
                                              opts.type)
                else:
                    if opts.involved_projects:
                        who = who or conf.get_apiurl_usr(apiurl)
                        results = get_user_projpkgs_request_list(apiurl, who, req_state=state_list,
                                                                 req_type=opts.type, exclude_projects=opts.exclude_target_project or [])
                    else:
                        results = get_request_list(apiurl, project, package, who,
                                                   state_list, opts.type, opts.exclude_target_project or [])

            # Check if project actually exists if result list is empty
            if not results:
                if project:
                    msg = 'No results for %(kind)s %(entity)s'
                    emsg = '%(kind)s %(entity)s does not exist'
                    d = {'entity': [project], 'kind': 'project'}
                    meth = show_project_meta
                    if package:
                        d['kind'] = 'package'
                        d['entity'].append(package)
                        meth = show_package_meta
                    try:
                        entity = d['entity']
                        d['entity'] = '/'.join(entity)
                        meth(apiurl, *entity)
                        print(msg % d)
                    except HTTPError:
                        print(emsg % d)
                else:
                    print('No results')
                return

            # we must not sort the results here, since the api is doing it already "the right way"
            days = opts.days or conf.config['request_list_days']
            since = ''
            try:
                days = float(days)
            except ValueError:
                days = 0
            if days > 0:
                since = time.strftime('%Y-%m-%dT%H:%M:%S', time.localtime(time.time()-days*24*3600))

            skipped = 0
            ## bs has received 2009-09-20 a new xquery compare() function
            ## which allows us to limit the list inside of get_request_list
            ## That would be much faster for coolo. But counting the remainder
            ## would not be possible with current xquery implementation.
            ## Workaround: fetch all, and filter on client side.

            ## FIXME: date filtering should become implemented on server side


            if opts.target_package_filter:
                filter_pattern = re.compile(opts.target_package_filter)
            for result in results:
                filtered = False
                for action in result.actions:
                    if action.type == 'group' or not opts.target_package_filter:
                        continue
                    if action.tgt_package is not None and not filter_pattern.match(action.tgt_package):
                        filtered = True
                        break
                if not filtered:
                    if days == 0 or result.state.when > since or result.state.name == 'new':
                        if (opts.interactive or conf.config['request_show_interactive']) and not opts.non_interactive:
                            ignore_reviews = subcmd != 'review'
                            request_interactive_review(apiurl, result, group=opts.group,
                                                       ignore_reviews=ignore_reviews,
                                                       source_buildstatus=source_buildstatus)
                        else:
                            print(result.list_view(), '\n')
                    else:
                        skipped += 1
            if skipped:
                print("There are %d requests older than %s days.\n" % (skipped, days))

            if cmd == 'approvenew':
                print("\n *** Approve them all ? [y/n] ***")
                if sys.stdin.read(1) == "y":

                    if not opts.message:
                        opts.message = edit_message()
                    for result in results:
                        print(result.reqid, ": ", end=' ')
                        r = change_request_state(apiurl,
                                result.reqid, 'accepted', opts.message or '', force=opts.force)
                        print('Result of change request state: %s' % r)
                else:
                    print('Aborted...', file=sys.stderr)
                    raise oscerr.UserAbort()

        elif cmd == 'log':
            for l in get_request_log(apiurl, reqid):
                print(l)

        # show
        elif cmd == 'show':
            r = get_request(apiurl, reqid)
            if opts.brief:
                print(r.list_view())
            elif opts.edit:
                if not r.get_actions('submit'):
                    raise oscerr.WrongOptions('\'--edit\' not possible ' \
                        '(request has no \'submit\' action)')
                return request_interactive_review(apiurl, r, 'e')
            elif (opts.interactive or conf.config['request_show_interactive']) and not opts.non_interactive:
                ignore_reviews = subcmd != 'review'
                return request_interactive_review(apiurl, r, group=opts.group,
                                                  ignore_reviews=ignore_reviews,
                                                  source_buildstatus=source_buildstatus)
            else:
                print(r)
                print_comments(apiurl, 'request', reqid)
            if source_buildstatus:
                sr_actions = r.get_actions('submit')
                if not sr_actions:
                    raise oscerr.WrongOptions( '\'--source-buildstatus\' not possible ' \
                        '(request has no \'submit\' actions)')
                for action in sr_actions:
                    print('Buildstatus for \'%s/%s\':' % (action.src_project, action.src_package))
                    print('\n'.join(get_results(apiurl, action.src_project, action.src_package)))
            if opts.diff:
                diff = b''
                try:
                    # works since OBS 2.1
                    diff = request_diff(apiurl, reqid)
                except HTTPError as e:
                    # for OBS 2.0 and before
                    sr_actions = r.get_actions('submit')
                    if not r.get_actions('submit') and not r.get_actions('maintenance_incident') and not r.get_actions('maintenance_release'):
                        raise oscerr.WrongOptions('\'--diff\' not possible (request has no supported actions)')
                    for action in sr_actions:
                        diff += b'old: %s/%s\nnew: %s/%s\n' % (action.src_project.encode(), action.src_package.encode(),
                            action.tgt_project.encode(), action.tgt_package.encode())
                        diff += submit_action_diff(apiurl, action)
                        diff += b'\n\n'
                run_pager(diff, tmp_suffix='')

        # checkout
        elif cmd == 'checkout' or cmd == 'co':
            r = get_request(apiurl, reqid)
            sr_actions = r.get_actions('submit', 'maintenance_release')
            if not sr_actions:
                raise oscerr.WrongArgs('\'checkout\' not possible (request has no \'submit\' actions)')
            for action in sr_actions:
                checkout_package(apiurl, action.src_project, action.src_package, \
                    action.src_rev, expand_link=True, prj_dir=action.src_project)

        else:
            state_map = {'reopen' : 'new', 'accept' : 'accepted', 'decline' : 'declined', 'wipe' : 'deleted', 'revoke' : 'revoked', 'supersede' : 'superseded'}
            # Change review state only
            if subcmd == 'review':
                if not opts.message:
                    opts.message = edit_message()
                if cmd in ['accept', 'decline', 'reopen', 'supersede']:
                    if opts.user or opts.group or opts.project or opts.package:
                        r = change_review_state(apiurl, reqid, state_map[cmd], opts.user, opts.group, opts.project,
                                opts.package, opts.message or '', supersed=supersedid)
                        print(r)
                    else:
                        rq = get_request(apiurl, reqid)
                        if rq.state.name in ['new', 'review']:
                            for review in rq.reviews:  # try all, but do not fail on error
                                try:
                                    r = change_review_state(apiurl, reqid, state_map[cmd], review.by_user, review.by_group,
                                            review.by_project, review.by_package, opts.message or '', supersed=supersedid)
                                    print(r)
                                except HTTPError as e:
                                    body = e.read()
                                    if e.code in [403]:
                                       if review.by_user:
                                           print('No permission on review by user %s:' % review.by_user)
                                       if review.by_group:
                                           print('No permission on review by group %s' % review.by_group)
                                       if review.by_package:
                                           print('No permission on review by package %s / %s' % (review.by_project, review.by_package))
                                       elif review.by_project:
                                           print('No permission on review by project %s' % review.by_project)
                                    print(e, file=sys.stderr)
                        else:
                            print('Request is closed, please reopen the request first before changing any reviews.')
            # Change state of entire request
            elif cmd in ['reopen', 'accept', 'decline', 'wipe', 'revoke', 'supersede']:
                rq = get_request(apiurl, reqid)
                if opts.or_revoke:
                    if rq.state.name == "declined":
                        cmd = "revoke"
                    elif rq.state.name != "new" and rq.state.name != "review":
                        return 0
                if rq.state.name == state_map[cmd]:
                    repl = raw_input("\n *** The state of the request (#%s) is already '%s'. Change state anyway?  [y/n] *** " % \
                                     (reqid, rq.state.name))
                    if repl.lower() != 'y':
                        print('Aborted...', file=sys.stderr)
                        raise oscerr.UserAbort()

                if not opts.message:
                    tmpl = change_request_state_template(rq, state_map[cmd])
                    opts.message = edit_message(template=tmpl)
                try:
                    r = change_request_state(apiurl,
                             reqid, state_map[cmd], opts.message or '', supersed=supersedid, force=opts.force)
                    print('Result of change request state: %s' % r)
                except HTTPError as e:
                    print(e, file=sys.stderr)
                    details = e.hdrs.get('X-Opensuse-Errorcode')
                    if details:
                        print(details, file=sys.stderr)
                    root = ET.fromstring(e.read())
                    summary = root.find('summary')
                    if not summary is None:
                        print(summary.text)
                    if opts.or_revoke:
                        if e.code in [ 400, 403, 404, 500 ]:
                            print('Revoking it ...')
                            r = change_request_state(apiurl,
                                reqid, 'revoked', opts.message or '', supersed=supersedid, force=opts.force)
                    sys.exit(1)


                # check for devel instances after accepted requests
                if cmd in ['accept']:
                    import cgi
                    sr_actions = rq.get_actions('submit')
                    for action in sr_actions:
                        u = makeurl(apiurl, ['/search/package'], {
                              'match' : "([devel/[@project='%s' and @package='%s']])" % (action.tgt_project, action.tgt_package)
                              })
                        f = http_GET(u)
                        root = ET.parse(f).getroot()
                        if root.findall('package') and not opts.no_devel:
                            for node in root.findall('package'):
                                project = node.get('project')
                                package = node.get('name')
                                # skip it when this is anyway a link to me
                                link_url = makeurl(apiurl, ['source', project, package])
                                links_to_project = links_to_package = None
                                try:
                                    file = http_GET(link_url)
                                    root = ET.parse(file).getroot()
                                    link_node = root.find('linkinfo')
                                    if link_node != None:
                                        links_to_project = link_node.get('project') or project
                                        links_to_package = link_node.get('package') or package
                                except HTTPError as e:
                                    if e.code != 404:
                                        print('Cannot get list of files for %s/%s: %s' % (project, package, e), file=sys.stderr)
                                except SyntaxError as e:
                                    print('Cannot parse list of files for %s/%s: %s' % (project, package, e), file=sys.stderr)
                                if links_to_project == action.tgt_project and links_to_package == action.tgt_package:
                                    # links to my request target anyway, no need to forward submit
                                    continue

                                print(project, end=' ')
                                if package != action.tgt_package:
                                    print("/", package, end=' ')
                                repl = raw_input('\nForward this submit to it? ([y]/n)')
                                if repl.lower() == 'y' or repl == '':
                                    (supersede, reqs) = check_existing_requests(apiurl, action.tgt_project, action.tgt_package,
                                                                                project, package)
                                    msg = "%s (forwarded request %s from %s)" % (rq.description, reqid, rq.creator)
                                    rid = create_submit_request(apiurl, action.tgt_project, action.tgt_package,
                                                                project, package, cgi.escape(msg))
                                    print(msg)
                                    print("New request #", rid)
                                    for req in reqs:
                                        change_request_state(apiurl, req.reqid, 'superseded',
                                                             'superseded by %s' % rid, rid)

    # editmeta and its aliases are all deprecated
    @cmdln.alias("editprj")
    @cmdln.alias("createprj")
    @cmdln.alias("editpac")
    @cmdln.alias("createpac")
    @cmdln.alias("edituser")
    @cmdln.alias("usermeta")
    @cmdln.hide(1)
    def do_editmeta(self, subcmd, opts, *args):
        """${cmd_name}:

        Obsolete command to edit metadata. Use 'meta' now.

        See the help output of 'meta'.
        """

        print("This command is obsolete. Use 'osc meta <metatype> ...'.", file=sys.stderr)
        print("See 'osc help meta'.", file=sys.stderr)
        return 2


    @cmdln.option('-r', '--revision', metavar='rev',
                  help='use the specified revision.')
    @cmdln.option('-R', '--use-plain-revision', action='store_true',
                  help='Do not expand revision the specified or latest rev')
    @cmdln.option('-u', '--unset', action='store_true',
                  help='remove revision in link, it will point always to latest revision')
    def do_setlinkrev(self, subcmd, opts, *args):
        """${cmd_name}: Updates a revision number in a source link.

        This command adds or updates a specified revision number in a source link.
        The current revision of the source is used, if no revision number is specified.

        usage:
            osc setlinkrev
            osc setlinkrev PROJECT [PACKAGE]
        ${cmd_option_list}
        """

        args = slash_split(args)
        apiurl = self.get_api_url()
        package = None
        rev = parseRevisionOption(opts.revision)[0] or ''
        if opts.unset:
            rev = None

        if len(args) == 0:
            p = findpacs(os.curdir)[0]
            project = p.prjname
            package = p.name
            apiurl = p.apiurl
            if not p.islink():
                sys.exit('Local directory is no checked out source link package, aborting')
        elif len(args) == 2:
            project = args[0]
            package = args[1]
        elif len(args) == 1:
            project = args[0]
        else:
            raise oscerr.WrongArgs('Incorrect number of arguments.\n\n' \
                  + self.get_cmd_help('setlinkrev'))

        if package:
            packages = [package]
        else:
            packages = meta_get_packagelist(apiurl, project)

        for p in packages:
            rev = set_link_rev(apiurl, project, p, revision=rev,
                               expand=not opts.use_plain_revision)
            if rev is None:
                print('removed revision from link')
            else:
                print('set revision to %s for package %s' % (rev, p))


    def do_linktobranch(self, subcmd, opts, *args):
        """${cmd_name}: Convert a package containing a classic link with patch to a branch

        This command tells the server to convert a _link with or without a project.diff
        to a branch. This is a full copy with a _link file pointing to the branched place.

        usage:
            osc linktobranch                    # can be used in checked out package
            osc linktobranch PROJECT PACKAGE
        ${cmd_option_list}
        """
        args = slash_split(args)
        apiurl = self.get_api_url()

        if len(args) == 0:
            wd = os.curdir
            project = store_read_project(wd)
            package = store_read_package(wd)
            update_local_dir = True
        elif len(args) < 2:
            raise oscerr.WrongArgs('Too few arguments (required none or two)')
        elif len(args) > 2:
            raise oscerr.WrongArgs('Too many arguments (required none or two)')
        else:
            project = args[0]
            package = args[1]
            update_local_dir = False

        # execute
        link_to_branch(apiurl, project, package)
        if update_local_dir:
            pac = Package(wd)
            pac.update(rev=pac.latest_rev())


    @cmdln.option('-m', '--message', metavar='TEXT',
                  help='specify message TEXT')
    def do_detachbranch(self, subcmd, opts, *args):
        """${cmd_name}: replace a link with its expanded sources

        If a package is a link it is replaced with its expanded sources. The link
        does not exist anymore.

        usage:
            osc detachbranch                    # can be used in package working copy
            osc detachbranch PROJECT PACKAGE
        ${cmd_option_list}
        """
        args = slash_split(args)
        apiurl = self.get_api_url()
        if len(args) == 0:
            project = store_read_project(os.curdir)
            package = store_read_package(os.curdir)
        elif len(args) == 2:
            project, package = args
        elif len(args) > 2:
            raise oscerr.WrongArgs('Too many arguments (required none or two)')
        else:
            raise oscerr.WrongArgs('Too few arguments (required none or two)')

        try:
            copy_pac(apiurl, project, package, apiurl, project, package, expand=True, comment=opts.message)
        except HTTPError as e:
            root = ET.fromstring(show_files_meta(apiurl, project, package, 'latest', expand=False))
            li = Linkinfo()
            li.read(root.find('linkinfo'))
            if li.islink() and li.haserror():
                raise oscerr.LinkExpandError(project, package, li.error)
            elif not li.islink():
                print('package \'%s/%s\' is no link' % (project, package), file=sys.stderr)
            else:
                raise e


    @cmdln.option('-C', '--cicount', choices=['add', 'copy', 'local'],
                  help='cicount attribute in the link, known values are add, copy, and local, default in buildservice is currently add.')
    @cmdln.option('-c', '--current', action='store_true',
                  help='link fixed against current revision.')
    @cmdln.option('-r', '--revision', metavar='rev',
                  help='link the specified revision.')
    @cmdln.option('-f', '--force', action='store_true',
                  help='overwrite an existing link file if it is there.')
    @cmdln.option('-d', '--disable-publish', action='store_true',
                  help='disable publishing of the linked package')
    @cmdln.option('-N', '--new-package', action='store_true',
                  help='create a link to a not yet existing package')
    def do_linkpac(self, subcmd, opts, *args):
        """${cmd_name}: "Link" a package to another package

        A linked package is a clone of another package, but plus local
        modifications. It can be cross-project.

        The DESTPAC name is optional; the source packages' name will be used if
        DESTPAC is omitted.

        Afterwards, you will want to 'checkout DESTPRJ DESTPAC'.

        To add a patch, add the patch as file and add it to the _link file.
        You can also specify text which will be inserted at the top of the spec file.

        See the examples in the _link file.

        NOTE: In case you want to fix or update another package, you should use the 'branch'
              command. A branch has correct repositories (and a link) setup up by default and
              will be cleaned up automatically after it was submitted back.

        usage:
            osc linkpac SOURCEPRJ SOURCEPAC DESTPRJ [DESTPAC]
        ${cmd_option_list}
        """

        args = slash_split(args)
        apiurl = self.get_api_url()

        if not args or len(args) < 3:
            raise oscerr.WrongArgs('Incorrect number of arguments.\n\n' \
                  + self.get_cmd_help('linkpac'))

        rev, dummy = parseRevisionOption(opts.revision)
        vrev = None

        src_project = args[0]
        src_package = args[1]
        dst_project = args[2]
        if len(args) > 3:
            dst_package = args[3]
        else:
            dst_package = src_package

        if src_project == dst_project and src_package == dst_package:
            raise oscerr.WrongArgs('Error: source and destination are the same.')

        if src_project == dst_project and not opts.cicount:
            # in this case, the user usually wants to build different spec
            # files from the same source
            opts.cicount = "copy"

        if opts.current and not opts.new_package:
            rev, vrev = show_upstream_rev_vrev(apiurl, src_project, src_package, expand=True)
            if rev == None or len(rev) < 32:
                # vrev is only needed for srcmd5 and OBS instances < 2.1.17 do not support it
                vrev = None

        if rev and not checkRevision(src_project, src_package, rev):
            print('Revision \'%s\' does not exist' % rev, file=sys.stderr)
            sys.exit(1)

        link_pac(src_project, src_package, dst_project, dst_package, opts.force, rev, opts.cicount, opts.disable_publish, opts.new_package, vrev)

    @cmdln.option('--nosources', action='store_true',
                  help='ignore source packages when copying build results to destination project')
    @cmdln.option('-m', '--map-repo', metavar='SRC=TARGET[,SRC=TARGET]',
                  help='Allows repository mapping(s) to be given as SRC=TARGET[,SRC=TARGET]')
    @cmdln.option('-d', '--disable-publish', action='store_true',
                  help='disable publishing of the aggregated package')
    def do_aggregatepac(self, subcmd, opts, *args):
        """${cmd_name}: "Aggregate" a package to another package

        Aggregation of a package means that the build results (binaries) of a
        package are basically copied into another project.
        This can be used to make packages available from building that are
        needed in a project but available only in a different project. Note
        that this is done at the expense of disk space. See
        http://en.opensuse.org/openSUSE:Build_Service_Tips_and_Tricks#link_and_aggregate
        for more information.

        The DESTPAC name is optional; the source packages' name will be used if
        DESTPAC is omitted.

        usage:
            osc aggregatepac SOURCEPRJ SOURCEPAC DESTPRJ [DESTPAC]
        ${cmd_option_list}
        """

        args = slash_split(args)

        if not args or len(args) < 3:
            raise oscerr.WrongArgs('Incorrect number of arguments.\n\n' \
                  + self.get_cmd_help('aggregatepac'))

        src_project = args[0]
        src_package = args[1]
        dst_project = args[2]
        if len(args) > 3:
            dst_package = args[3]
        else:
            dst_package = src_package

        if src_project == dst_project and src_package == dst_package:
            raise oscerr.WrongArgs('Error: source and destination are the same.')

        repo_map = {}
        if opts.map_repo:
            for pair in opts.map_repo.split(','):
                src_tgt = pair.split('=')
                if len(src_tgt) != 2:
                    raise oscerr.WrongOptions('map "%s" must be SRC=TARGET[,SRC=TARGET]' % opts.map_repo)
                repo_map[src_tgt[0]] = src_tgt[1]

        aggregate_pac(src_project, src_package, dst_project, dst_package, repo_map, opts.disable_publish, opts.nosources)


    @cmdln.option('-c', '--client-side-copy', action='store_true',
                        help='do a (slower) client-side copy')
    @cmdln.option('-k', '--keep-maintainers', action='store_true',
                        help='keep original maintainers. Default is remove all and replace with the one calling the script.')
    @cmdln.option('-K', '--keep-link', action='store_true',
                        help='If the target package is a link, the link is kept, but may be updated. If the source package is a link, its expanded version is considered.')
    @cmdln.option('-d', '--keep-develproject', action='store_true',
                        help='keep develproject tag in the package metadata')
    @cmdln.option('-r', '--revision', metavar='rev',
                        help='copy the specified revision.')
    @cmdln.option('-t', '--to-apiurl', metavar='URL',
                        help='URL of destination api server. Default is the source api server.')
    @cmdln.option('-m', '--message', metavar='TEXT',
                  help='specify message TEXT')
    @cmdln.option('-e', '--expand', action='store_true',
                        help='if the source package is a link then copy the expanded version of the link')
    def do_copypac(self, subcmd, opts, *args):
        """${cmd_name}: Copy a package

        A way to copy package to somewhere else.

        It can be done across buildservice instances, if the -t option is used.
        In that case, a client-side copy and link expansion are implied.

        Using --client-side-copy always involves downloading all files, and
        uploading them to the target.

        The DESTPAC name is optional; the source packages' name will be used if
        DESTPAC is omitted.

        usage:
            osc copypac SOURCEPRJ SOURCEPAC DESTPRJ [DESTPAC]
        ${cmd_option_list}
        """

        args = slash_split(args)

        if not args or len(args) < 3:
            raise oscerr.WrongArgs('Incorrect number of arguments.\n\n' \
                  + self.get_cmd_help('copypac'))

        src_project = args[0]
        src_package = args[1]
        dst_project = args[2]
        if len(args) > 3:
            dst_package = args[3]
        else:
            dst_package = src_package

        src_apiurl = conf.config['apiurl']
        if opts.to_apiurl:
            dst_apiurl = conf.config['apiurl_aliases'].get(opts.to_apiurl, opts.to_apiurl)
        else:
            dst_apiurl = src_apiurl

        if src_apiurl != dst_apiurl:
            opts.client_side_copy = True
            opts.expand = True

        rev, dummy = parseRevisionOption(opts.revision)

        if opts.message:
            comment = opts.message
        else:
            if not rev:
                rev = show_upstream_rev(src_apiurl, src_project, src_package)
            comment = 'osc copypac from project:%s package:%s revision:%s' % ( src_project, src_package, rev )
            if opts.keep_link:
                comment += ", using keep-link"
            if opts.expand:
                comment += ", using expand"
            if opts.client_side_copy:
                comment += ", using client side copy"

        if src_project == dst_project and \
           src_package == dst_package and \
           not rev and \
           src_apiurl == dst_apiurl:
            raise oscerr.WrongArgs('Source and destination are the same.')

        r = copy_pac(src_apiurl, src_project, src_package,
                     dst_apiurl, dst_project, dst_package,
                     client_side_copy=opts.client_side_copy,
                     keep_maintainers=opts.keep_maintainers,
                     keep_develproject=opts.keep_develproject,
                     expand=opts.expand,
                     revision=rev,
                     comment=comment,
                     keep_link=opts.keep_link)
        print(decode_it(r))


    @cmdln.option('-r', '--repo', metavar='REPO',
                        help='Release only binaries from the specified repository')
    @cmdln.option('--target-project', metavar='TARGETPROJECT',
                  help='Release only to specified project')
    @cmdln.option('--target-repository', metavar='TARGETREPOSITORY',
                  help='Release only to specified repository')
    @cmdln.option('--set-release', metavar='RELEASETAG',
                  help='rename binaries during release using this release tag')
    @cmdln.option('--no-delay', action='store_true',
                  help="Don't put the release job in a queue to be run later, but immediately run it. Thus the next call to osc prjresult will reflect it. Otherwise there is no way to know if it is finished or didn't start yet.")
    def do_release(self, subcmd, opts, *args):
        """${cmd_name}: Release sources and binaries

        This command is used to transfer sources and binaries without rebuilding them.
        It requires defined release targets set to trigger="manual". Please refer the
        release management chapter in the OBS book for details.

        usage:
            osc release [ SOURCEPROJECT [ SOURCEPACKAGE ] ]

        ${cmd_option_list}
        """

        args = slash_split(args)
        apiurl = self.get_api_url()

        source_project = source_package = None

        if len(args) > 2:
            raise oscerr.WrongArgs('Too many arguments.')

        if len(args) == 0:
            if is_package_dir(os.curdir):
               source_project = store_read_project(os.curdir)
               source_package = store_read_package(os.curdir)
            elif is_project_dir(os.curdir):
               source_project = store_read_project(os.curdir)
            else:
               raise oscerr.WrongArgs('Too few arguments.')
        if len(args) > 0:
            source_project = args[0]
        if len(args) > 1:
            source_package = args[1]

        query = { 'cmd': 'release' }
        if opts.target_project:
            query["target_project"] = opts.target_project
        if opts.target_repository:
            query["target_repository"] = opts.target_repository
        if opts.repo:
            query["repository"] = opts.repo
        if opts.set_release:
            query["setrelease"] = opts.set_release
        if opts.no_delay:
            query["nodelay"] = "1"
        baseurl = ['source', source_project]
        if source_package:
            baseurl.append(source_package)
        url = makeurl(apiurl, baseurl, query=query)
        f = http_POST(url)
        while True:
            buf = f.read(16384)
            if not buf:
                break
            sys.stdout.write(decode_it(buf))


    @cmdln.option('-m', '--message', metavar='TEXT',
                        help='specify message TEXT')
    def do_releaserequest(self, subcmd, opts, *args):
        """${cmd_name}: Create a request for releasing a maintenance update.

        [See http://openbuildservice.org/help/manuals/obs-reference-guide/cha.obs.maintenance_setup.html
         for information on this topic.]

        This command is used by the maintenance team to start the release process of a maintenance update.
        This includes usually testing based on the defined reviewers of the update project.

        usage:
            osc releaserequest [ SOURCEPROJECT ]

        ${cmd_option_list}
        """

        # FIXME: additional parameters can be a certain repo list to create a partitial release

        args = slash_split(args)
        apiurl = self.get_api_url()

        source_project = None

        if len(args) > 1:
            raise oscerr.WrongArgs('Too many arguments.')

        if len(args) == 0 and is_project_dir(os.curdir):
            source_project = store_read_project(os.curdir)
        elif len(args) == 0:
            raise oscerr.WrongArgs('Too few arguments.')
        if len(args) > 0:
            source_project = args[0]

        if not opts.message:
            opts.message = edit_message()

        r = create_release_request(apiurl, source_project, opts.message)
        print(r.reqid)



    @cmdln.option('-a', '--attribute', metavar='ATTRIBUTE',
                        help='Use this attribute to find default maintenance project (default is OBS:MaintenanceProject)')
    @cmdln.option('--noaccess', action='store_true',
                        help='Create a hidden project')
    @cmdln.option('-m', '--message', metavar='TEXT',
                        help='specify message TEXT')
    def do_createincident(self, subcmd, opts, *args):
        """${cmd_name}: Create a maintenance incident

        [See http://openbuildservice.org/help/manuals/obs-reference-guide/cha.obs.maintenance_setup.html
        for information on this topic.]

        This command is asking to open an empty maintenance incident. This can usually only be done by a responsible
        maintenance team.
        Please see the "mbranch" command on how to full such a project content and
        the "patchinfo" command how add the required maintenance update information.

        usage:
            osc createincident [ MAINTENANCEPROJECT ]
        ${cmd_option_list}
        """

        args = slash_split(args)
        apiurl = self.get_api_url()
        maintenance_attribute = conf.config['maintenance_attribute']
        if opts.attribute:
            maintenance_attribute = opts.attribute

        source_project = target_project = None

        if len(args) > 1:
            raise oscerr.WrongArgs('Too many arguments.')

        if len(args) == 1:
            target_project = args[0]
        else:
            xpath = 'attribute/@name = \'%s\'' % maintenance_attribute
            res = search(apiurl, project_id=xpath)
            root = res['project_id']
            project = root.find('project')
            if project is None:
                sys.exit('Unable to find defined OBS:MaintenanceProject project on server.')
            target_project = project.get('name')
            print('Using target project \'%s\'' % target_project)

        query = { 'cmd': 'createmaintenanceincident' }
        if opts.noaccess:
            query["noaccess"] = 1
        url = makeurl(apiurl, ['source', target_project], query=query)
        r = http_POST(url, data=opts.message)
        project = None
        for i in ET.fromstring(r.read()).findall('data'):
            if i.get('name') == 'targetproject':
                project = i.text.strip()
        if project:
            print("Incident project created: ", project)
        else:
            print(ET.parse(r).getroot().get('code'))
            print(ET.parse(r).getroot().get('error'))


    @cmdln.option('-a', '--attribute', metavar='ATTRIBUTE',
                        help='Use this attribute to find default maintenance project (default is OBS:MaintenanceProject)')
    @cmdln.option('-m', '--message', metavar='TEXT',
                        help='specify message TEXT')
    @cmdln.option('--release-project', metavar='RELEASEPROJECT',
                        help='Specify the release project')
    @cmdln.option('--enforce-branching', action='store_true',
                  help='submit from a fresh branched project')
    @cmdln.option('--no-cleanup', action='store_true',
                  help='do not remove source project on accept')
    @cmdln.option('--cleanup', action='store_true',
                  help='do remove source project on accept')
    @cmdln.option('--incident', metavar='INCIDENT',
                        help='specify incident number to merge in')
    @cmdln.option('--incident-project', metavar='INCIDENT_PROJECT',
                        help='specify incident project to merge in')
    @cmdln.option('-s', '--supersede', metavar='REQUEST_ID',
                  help='Superseding another request by this one')
    @cmdln.alias("mr")
    def do_maintenancerequest(self, subcmd, opts, *args):
        """${cmd_name}: Create a request for starting a maintenance incident.

        [See http://openbuildservice.org/help/manuals/obs-reference-guide/cha.obs.maintenance_setup.html
        for information on this topic.]

        This command is asking the maintenance team to start a maintenance incident based on a
        created maintenance update. Please see the "mbranch" command on how to create such a project and
        the "patchinfo" command how add the required maintenance update information.

        usage:
            osc maintenancerequest [ SOURCEPROJECT [ SOURCEPACKAGES RELEASEPROJECT ] ]
            osc maintenancerequest .

        The 2nd line when issued within a package directory provides a short cut to submit a single
        package (the one in the current directory) from the project of this package to be submitted
        to the release project this package links to. This syntax is only valid when specified from
        a package subdirectory.
        ${cmd_option_list}
        """
        #FIXME: the follow syntax would make more sense and would obsolete the --release-project parameter
        #       but is incompatible with the current one
        # osc maintenancerequest [ SOURCEPROJECT [ RELEASEPROJECT [ SOURCEPACKAGES ] ]

        args = slash_split(args)
        apiurl = self.get_api_url()
        maintenance_attribute = conf.config['maintenance_attribute']
        if opts.attribute:
            maintenance_attribute = opts.attribute

        source_project = target_project = release_project = opt_sourceupdate = None
        source_packages = []

        if len(args) == 0 and (is_project_dir(os.curdir) or is_package_dir(os.curdir)):
            source_project = store_read_project(os.curdir)
        elif len(args) == 0:
            raise oscerr.WrongArgs('Too few arguments.')
        if len(args) > 0:
            if len(args) == 1 and args[0] == '.':
                if is_package_dir(os.curdir):
                    source_project = store_read_project(os.curdir)
                    source_packages = [store_read_package(os.curdir)]
                    p = Package(os.curdir)
                    release_project = p.linkinfo.project
                else:
                    raise oscerr.WrongArgs('No package directory')
            else:
                source_project = args[0]
        if len(args) > 1:
            if len(args) == 2:
                sys.exit('Source package defined, but no release project.')
            source_packages = args[1:]
            release_project = args[-1]
            source_packages.remove(release_project)
        if opts.cleanup:
            opt_sourceupdate = 'cleanup'
        if not opts.no_cleanup:
            default_branch = 'home:%s:branches:' % (conf.get_apiurl_usr(apiurl))
            if source_project.startswith(default_branch):
                opt_sourceupdate = 'cleanup'

        if opts.release_project:
            release_project = opts.release_project

        if opts.incident_project:
            target_project = opts.incident_project
        else:
            xpath = 'attribute/@name = \'%s\'' % maintenance_attribute
            res = search(apiurl, project_id=xpath)
            root = res['project_id']
            project = root.find('project')
            if project is None:
                sys.exit('Unable to find defined OBS:MaintenanceProject project on server.')
            target_project = project.get('name')
            if opts.incident:
                target_project += ":" + opts.incident
            release_in = ''
            if release_project is not None:
                release_in = '. (release in \'%s\')' % release_project
            print('Using target project \'%s\'%s' % (target_project, release_in))

        if not opts.message:
            opts.message = edit_message()

        supersede_existing = False
        reqs = []
        if not opts.supersede:
            (supersede_existing, reqs) = check_existing_maintenance_requests(apiurl,
                                                                 source_project,
                                                                 source_packages,
                                                                 target_project,
                                                                 None) # unspecified release project

        r = create_maintenance_request(apiurl, source_project, source_packages, target_project, release_project, opt_sourceupdate, opts.message, opts.enforce_branching)
        print(r.reqid)

        if supersede_existing:
            for req in reqs:
                change_request_state(apiurl, req.reqid, 'superseded',
                                     'superseded by %s' % r.reqid, r.reqid)

        if opts.supersede:
            change_request_state(apiurl, opts.supersede, 'superseded',
                                 opts.message or '', r.reqid)


    @cmdln.option('-c', '--checkout', action='store_true',
                        help='Checkout branched package afterwards ' \
                                '(\'osc bco\' is a shorthand for this option)' )
    @cmdln.option('-a', '--attribute', metavar='ATTRIBUTE',
                        help='Use this attribute to find affected packages (default is OBS:Maintained)')
    @cmdln.option('-u', '--update-project-attribute', metavar='UPDATE_ATTRIBUTE',
                        help='Use this attribute to find update projects (default is OBS:UpdateProject) ')
    @cmdln.option('--dryrun', action='store_true',
                        help='Just simulate the action and report back the result.')
    @cmdln.option('--noaccess', action='store_true',
                        help='Create a hidden project')
    @cmdln.option('--nodevelproject', action='store_true',
                        help='do not follow a defined devel project ' \
                             '(primary project where a package is developed)')
    @cmdln.option('--version', action='store_true',
                        help='print version of maintained package')
    @cmdln.alias('sm')
    @cmdln.alias('maintained')
    def do_mbranch(self, subcmd, opts, *args):
        """${cmd_name}: Search or branch multiple instances of a package

        This command is used for searching all relevant instances of packages
        and creating links of them in one project.
        This is esp. used for maintenance updates. It can also be used to branch
        all packages marked before with a given attribute.

        [See http://en.opensuse.org/openSUSE:Build_Service_Concept_Maintenance
        for information on this topic.]

        The branched package will live in
            home:USERNAME:branches:ATTRIBUTE:PACKAGE
        if nothing else specified.

        If osc maintained or sm is issued only the relevant instances of a
        package will be shown. No branch will be created. This is similar
        to osc mbranch --dryrun.

        usage:
            osc sm [SOURCEPACKAGE] [-a ATTRIBUTE]
            osc mbranch [ SOURCEPACKAGE [ TARGETPROJECT ] ]
        ${cmd_option_list}
        """
        args = slash_split(args)
        apiurl = self.get_api_url()
        tproject = None

        maintained_attribute = conf.config['maintained_attribute']
        if opts.attribute:
            maintained_attribute = opts.attribute
        maintained_update_project_attribute = conf.config['maintained_update_project_attribute']
        if opts.update_project_attribute:
            maintained_update_project_attribute = opts.update_project_attribute

        if not len(args) or len(args) > 2:
            raise oscerr.WrongArgs('Wrong number of arguments.')
        if len(args) >= 1:
            package = args[0]
        if len(args) >= 2:
            tproject = args[1]

        if subcmd == 'sm' or subcmd == 'maintained':
            opts.dryrun = 1

        result = attribute_branch_pkg(apiurl, maintained_attribute, maintained_update_project_attribute, \
                                 package, tproject, noaccess = opts.noaccess, nodevelproject=opts.nodevelproject, dryrun=opts.dryrun)

        if result is None:
            print('ERROR: Attribute branch call came not back with a project.', file=sys.stderr)
            sys.exit(1)

        if opts.dryrun:
            for r in result.findall('package'):
                line="%s/%s"%(r.get('project'), r.get('package'))
                if opts.version:
                    sr = get_source_rev(apiurl, r.get('project'), r.get('package'))
                    version = sr.get('version')
                    if not version or version == 'unknown':
                        version = 'unknown'
                    line = line + (' (version: %s)' % version)
                for d in r.findall('devel'):
                   line+=" using sources from %s/%s"%(d.get('project'), d.get('package'))
                print(line)
            return

        apiopt = ''
        if conf.get_configParser().get('general', 'apiurl') != apiurl:
            apiopt = '-A %s ' % apiurl
        print('A working copy of the maintenance branch can be checked out with:\n\n' \
              'osc %sco %s' \
                    % (apiopt, result))

        if opts.checkout:
            Project.init_project(apiurl, result, result, conf.config['do_package_tracking'])
            print(statfrmt('A', result))

            # all packages
            for package in meta_get_packagelist(apiurl, result):
                try:
                    checkout_package(apiurl, result, package, expand_link = True, prj_dir = result)
                except:
                    print('Error while checkout package:\n', package, file=sys.stderr)

            if conf.config['verbose']:
                print('Note: You can use "osc delete" or "osc submitpac" when done.\n')


    @cmdln.alias('branchco')
    @cmdln.alias('bco')
    @cmdln.alias('getpac')
    @cmdln.option('--nodevelproject', action='store_true',
                        help='do not follow a defined devel project ' \
                             '(primary project where a package is developed)')
    @cmdln.option('-c', '--checkout', action='store_true',
                        help='Checkout branched package afterwards using "co -e -S"' \
                                '(\'osc bco\' is a shorthand for this option)' )
    @cmdln.option('-f', '--force', default=False, action="store_true",
                  help='force branch, overwrite target')
    @cmdln.option('--add-repositories', default=False, action="store_true",
                  help='Add repositories to target project (happens by default when project is new)')
    @cmdln.option('--extend-package-names', default=False, action="store_true",
                  help='Extend packages names with project name as suffix')
    @cmdln.option('--noaccess', action='store_true',
                        help='Create a hidden project')
    @cmdln.option('-m', '--message', metavar='TEXT',
                        help='specify message TEXT')
    @cmdln.option('-M', '--maintenance', default=False, action="store_true",
                        help='Create project and package in maintenance mode')
    @cmdln.option('-N', '--new-package', action='store_true',
                  help='create a branch pointing to a not yet existing package')
    @cmdln.option('-r', '--revision', metavar='rev',
                        help='branch against a specific revision')
    @cmdln.option('--linkrev', metavar='linkrev',
                        help='specify the used revision in the link target.')
    @cmdln.option('--add-repositories-block', metavar='add_repositories_block',
                        help='specify the used block strategy for new repositories')
    @cmdln.option('--add-repositories-rebuild', metavar='add_repositories_rebuild',
                        help='specify the used rebuild strategy for new repositories')
    def do_branch(self, subcmd, opts, *args):
        """${cmd_name}: Branch a package

        [See http://en.opensuse.org/openSUSE:Build_Service_Collaboration
        for information on this topic.]

        Create a source link from a package of an existing project to a new
        subproject of the requesters home project (home:branches:)

        The branched package will live in
            home:USERNAME:branches:PROJECT/PACKAGE
        if nothing else specified.

        With getpac or bco, the branched package will come from one of
            %(getpac_default_project)s
        (list of projects from oscrc:getpac_default_project)
        if nothing else is specfied on the command line.

        In case of branch errors, where the source has currently merge
        conflicts use --linkrev=base option.

        usage:
            osc branch
            osc branch SOURCEPROJECT SOURCEPACKAGE
            osc branch SOURCEPROJECT SOURCEPACKAGE TARGETPROJECT
            osc branch SOURCEPROJECT SOURCEPACKAGE TARGETPROJECT TARGETPACKAGE
            osc getpac SOURCEPACKAGE
            osc bco ...
        ${cmd_option_list}
        """

        if subcmd == 'getpac' or subcmd == 'branchco' or subcmd == 'bco':
            opts.checkout = True
        args = slash_split(args)
        tproject = tpackage = None

        if (subcmd == 'getpac' or subcmd == 'bco') and len(args) == 1:
            def_p = find_default_project(self.get_api_url(), args[0])
            print('defaulting to %s/%s' % (def_p, args[0]), file=sys.stderr)
            # python has no args.unshift ???
            args = [ def_p, args[0] ]

        if len(args) == 0 and is_package_dir('.'):
            args = (store_read_project('.'), store_read_package('.'))

        if len(args) < 2 or len(args) > 4:
            raise oscerr.WrongArgs('Wrong number of arguments.')

        apiurl = self.get_api_url()

        expected = 'home:%s:branches:%s' % (conf.get_apiurl_usr(apiurl), args[0])
        if len(args) >= 3:
            expected = tproject = args[2]
        if len(args) >= 4:
            tpackage = args[3]

        try:
          exists, targetprj, targetpkg, srcprj, srcpkg = \
                branch_pkg(apiurl, args[0], args[1],
                           nodevelproject=opts.nodevelproject, rev=opts.revision,
                           linkrev=opts.linkrev,
                           target_project=tproject, target_package=tpackage,
                           return_existing=opts.checkout, msg=opts.message or '',
                           force=opts.force, noaccess=opts.noaccess,
                           add_repositories=opts.add_repositories,
                           add_repositories_block=opts.add_repositories_block,
                           add_repositories_rebuild=opts.add_repositories_rebuild,
                           extend_package_names=opts.extend_package_names,
                           missingok=opts.new_package,
                           maintenance=opts.maintenance)
        except oscerr.NotMissing as e:
          print('NOTE: Package target exists already via project links, link will point to given project.')
          print('      A submission will initialize a new instance.')
          exists, targetprj, targetpkg, srcprj, srcpkg = \
                branch_pkg(apiurl, args[0], args[1],
                           nodevelproject=opts.nodevelproject, rev=opts.revision,
                           linkrev=opts.linkrev,
                           target_project=tproject, target_package=tpackage,
                           return_existing=opts.checkout, msg=opts.message or '',
                           force=opts.force, noaccess=opts.noaccess,
                           add_repositories=opts.add_repositories,
                           add_repositories_block=opts.add_repositories_block,
                           add_repositories_rebuild=opts.add_repositories_rebuild,
                           extend_package_names=opts.extend_package_names,
                           missingok=False,
                           maintenance=opts.maintenance,
                           newinstance=opts.new_package)

        if exists:
            print('Using existing branch project: %s' % targetprj, file=sys.stderr)

        devloc = None
        if not exists and (srcprj != args[0] or srcpkg != args[1]):
            try:
                root = ET.fromstring(b''.join(show_attribute_meta(apiurl, args[0], None, None,
                    conf.config['maintained_update_project_attribute'], False, False)))
                # this might raise an AttributeError
                uproject = root.find('attribute').find('value').text
                print('\nNote: The branch has been created from the configured update project: %s' \
                    % uproject)
            except (AttributeError, HTTPError) as e:
                devloc = srcprj
                print('\nNote: The branch has been created of a different project,\n' \
                      '              %s,\n' \
                      '      which is the primary location of where development for\n' \
                      '      that package takes place.\n' \
                      '      That\'s also where you would normally make changes against.\n' \
                      '      A direct branch of the specified package can be forced\n' \
                      '      with the --nodevelproject option.\n' % devloc)

        package = targetpkg or args[1]
        if opts.checkout:
            checkout_package(apiurl, targetprj, package, server_service_files=False,
                             expand_link=True, prj_dir=targetprj)
            if conf.config['verbose']:
                print('Note: You can use "osc delete" or "osc submitpac" when done.\n')
        else:
            apiopt = ''
            if conf.get_configParser().get('general', 'apiurl') != apiurl:
                apiopt = '-A %s ' % apiurl
            print('A working copy of the branched package can be checked out with:\n\n' \
                  'osc %sco %s/%s' \
                      % (apiopt, targetprj, package))
        print_request_list(apiurl, args[0], args[1])
        if devloc:
            print_request_list(apiurl, devloc, srcpkg)


    @cmdln.option('-m', '--message', metavar='TEXT',
                  help='specify log message TEXT')
    def do_undelete(self, subcmd, opts, *args):
        """${cmd_name}: Restores a deleted project or package on the server.

        The server restores a package including the sources and meta configuration.
        Binaries remain to be lost and will be rebuild.

        usage:
           osc undelete PROJECT
           osc undelete PROJECT PACKAGE [PACKAGE ...]

        ${cmd_option_list}
        """

        args = slash_split(args)
        if len(args) < 1:
            raise oscerr.WrongArgs('Missing argument.')

        msg = ''
        if opts.message:
            msg = opts.message
        else:
            msg = edit_message()

        apiurl = self.get_api_url()
        prj = args[0]
        pkgs = args[1:]

        if pkgs:
            for pkg in pkgs:
                undelete_package(apiurl, prj, pkg, msg)
        else:
            undelete_project(apiurl, prj, msg)


    @cmdln.option('-r', '--recursive', action='store_true',
                        help='deletes a project with packages inside')
    @cmdln.option('-f', '--force', action='store_true',
                        help='deletes a project where other depends on')
    @cmdln.option('-m', '--message', metavar='TEXT',
                  help='specify log message TEXT')
    def do_rdelete(self, subcmd, opts, *args):
        """${cmd_name}: Delete a project or packages on the server.

        As a safety measure, project must be empty (i.e., you need to delete all
        packages first). Also, packages must have no requests pending (i.e., you need
        to accept/revoke such requests first).
        If you are sure that you want to remove this project and all
        its packages use \'--recursive\' switch.
        It may still not work because other depends on it. If you want to ignore this as
        well use \'--force\' switch.

        usage:
           osc rdelete [-r] [-f] PROJECT [PACKAGE]

        ${cmd_option_list}
        """

        args = slash_split(args)
        if len(args) < 1 or len(args) > 2:
            raise oscerr.WrongArgs('Wrong number of arguments')

        apiurl = self.get_api_url()
        prj = args[0]

        msg = ''
        if opts.message:
            msg = opts.message
        else:
            msg = edit_message()

        # empty arguments result in recursive project delete ...
        if not len(prj):
            raise oscerr.WrongArgs('Project argument is empty')

        if len(args) > 1:
            pkg = args[1]

            if not len(pkg):
                raise oscerr.WrongArgs('Package argument is empty')

            ## FIXME: core.py:commitDelPackage() should have something similar
            rlist = get_request_list(apiurl, prj, pkg)
            for rq in rlist:
                print(rq)
            if len(rlist) >= 1 and not opts.force:
                print('Package has pending requests. Deleting the package will break them. '\
                      'They should be accepted/declined/revoked before deleting the package. '\
                      'Or just use \'--force\'.', file=sys.stderr)
                sys.exit(1)

            delete_package(apiurl, prj, pkg, opts.force, msg)

        elif (not opts.recursive) and len(meta_get_packagelist(apiurl, prj)) >= 1:
            print('Project contains packages. It must be empty before deleting it. ' \
                                'If you are sure that you want to remove this project and all its ' \
                                'packages use the \'--recursive\' switch.', file=sys.stderr)
            sys.exit(1)
        else:
            delete_project(apiurl, prj, opts.force, msg)


    @cmdln.option('-m', '--message', metavar='TEXT',
                  help='specify log message TEXT')
    def do_lock(self, subcmd, opts, project, package=None):
        """${cmd_name}: Locks a project or package.

        usage:
           osc lock PROJECT [PACKAGE]

        ${cmd_option_list}
        """
        apiurl = self.get_api_url()
        kind = 'prj'
        path_args = (project,)
        if package is not None:
            kind = 'pkg'
            path_args = (project, package)
        meta = meta_exists(kind, path_args, create_new=False, apiurl=apiurl)
        root = ET.fromstring(b''.join(meta))
        if root.find('lock') is not None:
            print('Already locked', file=sys.stderr)
            sys.exit(1)
        # alternatively, we could also use the set_flag api call
        # instead of manually manipulating the xml
        lock = ET.SubElement(root, 'lock')
        ET.SubElement(lock, 'enable')
        meta = ET.tostring(root)
        edit_meta(kind, path_args=path_args, data=meta, msg=opts.message)


    @cmdln.option('-m', '--message', metavar='TEXT',
                  help='specify log message TEXT')
    def do_unlock(self, subcmd, opts, *args):
        """${cmd_name}: Unlocks a project or package

        Unlocks a locked project or package. A comment is required.

        usage:
           osc unlock PROJECT [PACKAGE]

        ${cmd_option_list}
        """

        args = slash_split(args)
        if len(args) < 1 or len(args) > 2:
            raise oscerr.WrongArgs('Wrong number of arguments')

        apiurl = self.get_api_url()
        prj = args[0]

        msg = ''
        if opts.message:
            msg = opts.message
        else:
            msg = edit_message()

        # empty arguments result in recursive project delete ...
        if not len(prj):
            raise oscerr.WrongArgs('Project argument is empty')

        if len(args) > 1:
            pkg = args[1]

            if not len(pkg):
                raise oscerr.WrongArgs('Package argument is empty')

            unlock_package(apiurl, prj, pkg, msg)

        else:
            unlock_project(apiurl, prj, msg)


    @cmdln.hide(1)
    def do_deletepac(self, subcmd, opts, *args):
        """${cmd_name}:

        Obsolete command to delete package. Use 'delete' or 'rdelete' now.

        See the help output of 'delete' and 'rdelete'.
        """

        print("""Command deletepac is obsolete !

                 Please use either
                   osc delete       for checked out packages or projects
                 or
                   osc rdelete      for server side operations.""", file=sys.stderr)

        return 2

    @cmdln.hide(1)
    @cmdln.option('-f', '--force', action='store_true',
                        help='deletes a project and its packages')
    def do_deleteprj(self, subcmd, opts, project):
        """${cmd_name}:

        Obsolete command to delete project. Use 'rdelete' now.

        See the help output of 'rdelete'.
        """

        print("This command is obsolete. Use 'osc rdelete <project>'.", file=sys.stderr)
        print("See 'osc help rdelete'.", file=sys.stderr)
        return 2

    @cmdln.alias('metafromspec')
    @cmdln.alias('updatepkgmetafromspec')
    @cmdln.option('', '--specfile', metavar='FILE',
                      help='Path to specfile. (if you pass more than working copy this option is ignored)')
    def do_updatepacmetafromspec(self, subcmd, opts, *args):
        """${cmd_name}: Update package meta information from a specfile

        ARG, if specified, is a package working copy.

        ${cmd_usage}
        ${cmd_option_list}
        """

        args = parseargs(args)
        if opts.specfile and len(args) == 1:
            specfile = opts.specfile
        else:
            specfile = None
        pacs = findpacs(args)
        for p in pacs:
            p.read_meta_from_spec(specfile)
            p.update_package_meta()


    @cmdln.alias('linkdiff')
    @cmdln.alias('ldiff')
    @cmdln.alias('di')
    @cmdln.option('-c', '--change', metavar='rev',
                        help='the change made by revision rev (like -r rev-1:rev).'
                             'If rev is negative this is like -r rev:rev-1.')
    @cmdln.option('-r', '--revision', metavar='rev1[:rev2]',
                        help='If rev1 is specified it will compare your working copy against '
                             'the revision (rev1) on the server. '
                             'If rev1 and rev2 are specified it will compare rev1 against rev2 '
                             '(NOTE: changes in your working copy are ignored in this case)')
    @cmdln.option('-M', '--meta', action='store_true',
                        help='operate on meta files')
    @cmdln.option('-p', '--plain', action='store_true',
                        help='output the diff in plain (not unified) diff format')
    @cmdln.option('-l', '--link', action='store_true',
                        help='(osc linkdiff): compare against the base revision of the link')
    @cmdln.option('--missingok', action='store_true',
                        help='do not fail if the source or target project/package does not exist on the server')
    @cmdln.option('-u', '--unexpand', action='store_true',
                        help='Local changes only, ignore changes in linked package sources')
    def do_diff(self, subcmd, opts, *args):
        """${cmd_name}: Generates a diff

        Generates a diff, comparing local changes against the repository
        server.

        ${cmd_usage}
                ARG, if specified, is a filename to include in the diff.
                Default: all files.

            osc diff --link
            osc linkdiff
                Compare current checkout directory against the link base.

            osc diff --link PROJ PACK
            osc linkdiff PROJ PACK
                Compare a package against the link base (ignoring working copy changes).

        ${cmd_option_list}
        """

        if (subcmd == 'ldiff' or subcmd == 'linkdiff'):
            opts.link = True
        args = parseargs(args)

        pacs = None
        if not opts.link or not len(args) == 2:
            pacs = findpacs(args)


        if opts.link:
            query = { 'rev': 'latest' }
            if pacs:
                u = makeurl(pacs[0].apiurl, ['source', pacs[0].prjname, pacs[0].name], query=query)
            else:
                u = makeurl(self.get_api_url(), ['source', args[0], args[1]], query=query)
            f = http_GET(u)
            root = ET.parse(f).getroot()
            linkinfo = root.find('linkinfo')
            if linkinfo == None:
                raise oscerr.APIError('package is not a source link')
            baserev = linkinfo.get('baserev')
            opts.revision = baserev
            if pacs:
                print("diff working copy against last committed version\n")
            else:
                print("diff committed package against linked revision %s\n" % baserev)
                run_pager(server_diff(self.get_api_url(), linkinfo.get('project'), linkinfo.get('package'), baserev,
                  args[0], args[1], linkinfo.get('lsrcmd5'), not opts.plain, opts.missingok))
                return

        if opts.change:
            try:
                rev = int(opts.change)
                if rev > 0:
                    rev1 = rev - 1
                    rev2 = rev
                elif rev < 0:
                    rev1 = -rev
                    rev2 = -rev - 1
                else:
                    return
            except:
                print('Revision \'%s\' not an integer' % opts.change, file=sys.stderr)
                return
        else:
            rev1, rev2 = parseRevisionOption(opts.revision)
        diff = b''
        for pac in pacs:
            if not rev2:
                for i in pac.get_diff(rev1):
                    diff += b''.join(i)
            else:
                diff += server_diff_noex(pac.apiurl, pac.prjname, pac.name, rev1,
                                pac.prjname, pac.name, rev2,
                                not opts.plain, opts.missingok, opts.meta, not opts.unexpand)
        run_pager(diff)


    @cmdln.option('--oldprj', metavar='OLDPRJ',
                  help='project to compare against'
                  ' (deprecated, use 3 argument form)')
    @cmdln.option('--oldpkg', metavar='OLDPKG',
                  help='package to compare against'
                  ' (deprecated, use 3 argument form)')
    @cmdln.option('--issues-only', action='store_true',
                        help='show only issues in diff')
    @cmdln.option('-M', '--meta', action='store_true',
                        help='diff meta data')
    @cmdln.option('-r', '--revision', metavar='N[:M]',
                  help='revision id, where N = old revision and M = new revision')
    @cmdln.option('-p', '--plain', action='store_true',
                  help='output the diff in plain (not unified) diff format')
    @cmdln.option('-c', '--change', metavar='rev',
                        help='the change made by revision rev (like -r rev-1:rev). '
                             'If rev is negative this is like -r rev:rev-1.')
    @cmdln.option('--missingok', action='store_true',
                        help='do not fail if the source or target project/package does not exist on the server')
    @cmdln.option('-u', '--unexpand', action='store_true',
                        help='diff unexpanded version if sources are linked')
    def do_rdiff(self, subcmd, opts, *args):
        """${cmd_name}: Server-side "pretty" diff of two packages

        Compares two packages (three or four arguments) or shows the
        changes of a specified revision of a package (two arguments)

        If no revision is specified the latest revision is used.

        Note that this command doesn't return a normal diff (which could be
        applied as patch), but a "pretty" diff, which also compares the content
        of tarballs.


        usage:
            osc ${cmd_name} OLDPRJ OLDPAC NEWPRJ [NEWPAC]
            osc ${cmd_name} PROJECT PACKAGE
        ${cmd_option_list}
        """

        args = slash_split(args)
        apiurl = self.get_api_url()

        rev1 = None
        rev2 = None

        old_project = None
        old_package = None
        new_project = None
        new_package = None

        if len(args) == 2:
            new_project = args[0]
            new_package = args[1]
            if opts.oldprj:
                old_project = opts.oldprj
            if opts.oldpkg:
                old_package = opts.oldpkg
        elif len(args) == 3 or len(args) == 4:
            if opts.oldprj or opts.oldpkg:
                raise oscerr.WrongArgs('--oldpkg and --oldprj are only valid with two arguments')
            old_project = args[0]
            new_package = old_package = args[1]
            new_project = args[2]
            if len(args) == 4:
                new_package = args[3]
        elif len(args) == 1 and opts.meta:
            new_project = args[0]
            new_package = '_project'
        else:
            raise oscerr.WrongArgs('Wrong number of arguments')

        if opts.meta:
            opts.unexpand = True

        if opts.change:
            try:
                rev = int(opts.change)
                if rev > 0:
                    rev1 = rev - 1
                    rev2 = rev
                elif rev < 0:
                    rev1 = -rev
                    rev2 = -rev - 1
                else:
                    return
            except:
                print('Revision \'%s\' not an integer' % opts.change, file=sys.stderr)
                return
        else:
            if opts.revision:
                rev1, rev2 = parseRevisionOption(opts.revision)

        rdiff = server_diff_noex(apiurl,
                            old_project, old_package, rev1,
                            new_project, new_package, rev2, not opts.plain, opts.missingok,
                            meta=opts.meta,
                            expand=not opts.unexpand,
                            onlyissues=opts.issues_only)
        if opts.issues_only:
            print(rdiff)
        else:
            run_pager(rdiff)

    def _pdiff_raise_non_existing_package(self, project, package, msg = None):
        raise oscerr.PackageMissing(project, package, msg or '%s/%s does not exist.' % (project, package))

    def _pdiff_package_exists(self, apiurl, project, package):
        try:
            show_package_meta(apiurl, project, package)
            return True
        except HTTPError as e:
            if e.code != 404:
                print('Cannot check that %s/%s exists: %s' % (project, package, e), file=sys.stderr)
            return False

    def _pdiff_guess_parent(self, apiurl, project, package, check_exists_first = False):
        # Make sure the parent exists
        if check_exists_first and not self._pdiff_package_exists(apiurl, project, package):
            self._pdiff_raise_non_existing_package(project, package)

        if project.startswith('home:'):
            guess = project[len('home:'):]
            # remove user name
            pos = guess.find(':')
            if pos > 0:
                guess = guess[guess.find(':') + 1:]
                if guess.startswith('branches:'):
                    guess = guess[len('branches:'):]
                    return (guess, package)

        return (None, None)

    def _pdiff_get_parent_from_link(self, apiurl, project, package):
        link_url = makeurl(apiurl, ['source', project, package, '_link'])

        try:
            file = http_GET(link_url)
            root = ET.parse(file).getroot()
        except HTTPError as e:
            return (None, None)
        except SyntaxError as e:
            print('Cannot parse %s/%s/_link: %s' % (project, package, e), file=sys.stderr)
            return (None, None)

        parent_project = root.get('project')
        parent_package = root.get('package') or package

        if parent_project is None:
            return (None, None)

        return (parent_project, parent_package)

    def _pdiff_get_exists_and_parent(self, apiurl, project, package):
        link_url = makeurl(apiurl, ['public', 'source', project, package])
        try:
            file = http_GET(link_url)
            root = ET.parse(file).getroot()
        except HTTPError as e:
            if e.code != 404:
                print('Cannot get list of files for %s/%s: %s' % (project, package, e), file=sys.stderr)
            return (None, None, None)
        except SyntaxError as e:
            print('Cannot parse list of files for %s/%s: %s' % (project, package, e), file=sys.stderr)
            return (None, None, None)

        link_node = root.find('linkinfo')
        if link_node is None:
            return (True, None, None)

        parent_project = link_node.get('project')
        parent_package = link_node.get('package') or package

        if parent_project is None:
            raise oscerr.APIError('%s/%s is a link with no parent?' % (project, package))

        return (True, parent_project, parent_package)

    @cmdln.option('-p', '--plain', action='store_true',
                  dest='plain',
                  help='output the diff in plain (not unified) diff format')
    @cmdln.option('-n', '--nomissingok', action='store_true',
                  dest='nomissingok',
                  help='fail if the parent package does not exist on the server')
    def do_pdiff(self, subcmd, opts, *args):
        """${cmd_name}: Quick alias to diff the content of a package with its parent.

        Usage:
            osc pdiff [--plain|-p] [--nomissing-ok|-n]
            osc pdiff [--plain|-p] [--nomissing-ok|-n] PKG
            osc pdiff [--plain|-p] [--nomissing-ok|-n] PRJ PKG

        ${cmd_option_list}
        """

        apiurl = self.get_api_url()
        args = slash_split(args)

        unified = not opts.plain
        noparentok = not opts.nomissingok

        if len(args) > 2:
            raise oscerr.WrongArgs('Too many arguments.')

        if len(args) == 0:
            if not is_package_dir(os.getcwd()):
                raise oscerr.WrongArgs('Current directory is not a checked out package. Please specify a project and a package.')
            project = store_read_project(os.curdir)
            package = store_read_package(os.curdir)
        elif len(args) == 1:
            if not is_project_dir(os.getcwd()):
                raise oscerr.WrongArgs('Current directory is not a checked out project. Please specify a project and a package.')
            project = store_read_project(os.curdir)
            package = args[0]
        elif len(args) == 2:
            project = args[0]
            package = args[1]
        else:
            raise RuntimeError('Internal error: bad check for arguments.')

        ## Find parent package

        # Old way, that does one more request to api
        #(parent_project, parent_package) = self._pdiff_get_parent_from_link(apiurl, project, package)
        #if not parent_project:
        #    (parent_project, parent_package) = self._pdiff_guess_parent(apiurl, project, package, check_exists_first = True)
        #    if parent_project and parent_package:
        #        print 'Guessed that %s/%s is the parent package.' % (parent_project, parent_package)

        # New way
        (exists, parent_project, parent_package) = self._pdiff_get_exists_and_parent (apiurl, project, package)
        if not exists:
            self._pdiff_raise_non_existing_package(project, package)
        if not parent_project:
            (parent_project, parent_package) = self._pdiff_guess_parent(apiurl, project, package, check_exists_first = False)
            if parent_project and parent_package:
                print('Guessed that %s/%s is the parent package.' % (parent_project, parent_package))

        if not parent_project or not parent_package:
            print('Cannot find a parent for %s/%s to diff against.' % (project, package), file=sys.stderr)
            return 1

        if not noparentok and not self._pdiff_package_exists(apiurl, parent_project, parent_package):
            self._pdiff_raise_non_existing_package(parent_project, parent_package,
                                                   msg = 'Parent for %s/%s (%s/%s) does not exist.' % \
                                                   (project, package, parent_project, parent_package))

        rdiff = server_diff(apiurl, parent_project, parent_package, None, project,
                            package, None, unified = unified, missingok = noparentok)

        run_pager(rdiff)

    def _get_branch_parent(self, prj):
        m = re.match('^home:[^:]+:branches:(.+)', prj)
        # OBS_Maintained is a special case
        if m and prj.find(':branches:OBS_Maintained:') == -1:
            return m.group(1)
        return None

    def _prdiff_skip_package(self, opts, pkg):
        if opts.exclude and re.search(opts.exclude, pkg):
            return True

        if opts.include and not re.search(opts.include, pkg):
            return True

        return False

    def _prdiff_output_diff(self, opts, rdiff):
        if opts.diffstat:
            print()
            p = subprocess.Popen("diffstat",
                                 stdin=subprocess.PIPE,
                                 stdout=subprocess.PIPE,
                                 close_fds=True)
            p.stdin.write(rdiff)
            p.stdin.close()
            print("".join(decode_it(x) for x in p.stdout.readlines()))
        elif opts.unified:
            print()
            if isinstance(rdiff, str):
                print(rdiff)
            else:
                try:
                    sys.stdout.buffer.write(rdiff)
                except AttributeError as e:
                    print(decode_it(rdiff))
            #run_pager(rdiff)

    def _prdiff_output_matching_requests(self, opts, requests,
                                         srcprj, pkg):
        """
        Search through the given list of requests and output any
        submitrequests which target pkg and originate from srcprj.
        """
        for req in requests:
            for action in req.get_actions('submit'):
                if action.src_project != srcprj:
                    continue

                if action.tgt_package != pkg:
                    continue

                print()
                print(req.list_view())
                break

    @cmdln.alias('projectdiff')
    @cmdln.alias('projdiff')
    @cmdln.option('-r', '--requests', action='store_true',
                  help='show open requests for any packages with differences')
    @cmdln.option('-e', '--exclude',  metavar='REGEXP', dest='exclude',
                  help='skip packages matching REGEXP')
    @cmdln.option('-i', '--include',  metavar='REGEXP', dest='include',
                  help='only consider packages matching REGEXP')
    @cmdln.option('-n', '--show-not-in-old', action='store_true',
                  help='show packages only in the new project')
    @cmdln.option('-o', '--show-not-in-new', action='store_true',
                  help='show packages only in the old project')
    @cmdln.option('-u', '--unified',  action='store_true',
                  help='show full unified diffs of differences')
    @cmdln.option('-d', '--diffstat', action='store_true',
                  help='show diffstat of differences')

    def do_prdiff(self, subcmd, opts, *args):
        """${cmd_name}: Server-side diff of two projects

        Compares two projects and either summarizes or outputs the
        differences in full.  In the second form, a project is compared
        with one of its branches inside a home:$USER project (the branch
        is treated as NEWPRJ).  The home branch is optional if the current
        working directory is a checked out copy of it.

        Usage:
            osc prdiff [OPTIONS] OLDPRJ NEWPRJ
            osc prdiff [OPTIONS] [home:$USER:branch:$PRJ]

        ${cmd_option_list}
        """

        if len(args) > 2:
            raise oscerr.WrongArgs('Too many arguments.')

        if len(args) == 0:
            if is_project_dir(os.curdir):
                newprj = Project('.', getPackageList=False).name
                oldprj = self._get_branch_parent(newprj)
                if oldprj is None:
                    raise oscerr.WrongArgs('Current directory is not a valid home branch.')
            else:
                raise oscerr.WrongArgs('Current directory is not a project.')
        elif len(args) == 1:
            newprj = args[0]
            oldprj = self._get_branch_parent(newprj)
            if oldprj is None:
                raise oscerr.WrongArgs('Single-argument form must be for a home branch.')
        elif len(args) == 2:
            oldprj, newprj = args
        else:
            raise RuntimeError('BUG in argument parsing, please report.\n'
                               'args: ' + repr(args))

        if opts.diffstat and opts.unified:
            print('error - cannot specify both --diffstat and --unified', file=sys.stderr)
            sys.exit(1)

        apiurl = self.get_api_url()

        old_packages = meta_get_packagelist(apiurl, oldprj)
        new_packages = meta_get_packagelist(apiurl, newprj)

        if opts.requests:
            requests = get_request_list(apiurl, project=oldprj,
                                        req_state=('new', 'review'))

        for pkg in old_packages:
            if self._prdiff_skip_package(opts, pkg):
                continue

            if pkg not in new_packages:
                if opts.show_not_in_new:
                    print("old only:  %s" % pkg)
                continue

            rdiff = server_diff_noex(
                apiurl,
                oldprj, pkg, None,
                newprj, pkg, None,
                unified=True, missingok=False, meta=False, expand=True
                )

            if rdiff:
                print("differs:   %s" % pkg)
                self._prdiff_output_diff(opts, rdiff)

                if opts.requests:
                    self._prdiff_output_matching_requests(opts, requests,
                                                          newprj, pkg)
            else:
                print("identical: %s" % pkg)

        for pkg in new_packages:
            if self._prdiff_skip_package(opts, pkg):
                continue

            if pkg not in old_packages:
                if opts.show_not_in_old:
                    print("new only:  %s" % pkg)


    def do_repourls(self, subcmd, opts, *args):
        """${cmd_name}: Shows URLs of .repo files

        Shows URLs on which to access the project .repos files (yum-style
        metadata) on download.opensuse.org.

        usage:
           osc repourls [PROJECT]

        ${cmd_option_list}
        """

        apiurl = self.get_api_url()

        if len(args) == 1:
            project = args[0]
        elif len(args) == 0:
            project = store_read_project('.')
        else:
            raise oscerr.WrongArgs('Wrong number of arguments')

        root = ET.fromstring(b''.join(show_configuration(apiurl)))
        elm = root.find('download_url')
        if elm is None or not elm.text:
            raise oscerr.APIError('download_url configuration element expected')

        url_tmpl = elm.text + '/%s/%s/%s.repo'
        repos = get_repositories_of_project(apiurl, project)
        for repo in repos:
            print(url_tmpl % (project.replace(':', ':/'), repo, project))


    def do_browse(self, subcmd, opts, *args):
        """${cmd_name}: opens browser

        usage:
           osc browse [PROJECT [PACKAGE]]

        ${cmd_option_list}
        """

        apiurl = self.get_api_url()

        package = None
        if len(args) == 1:
            project = args[0]
        elif len(args) == 2:
            project = args[0]
            package = args[1]
        elif len(args) == 0:
            project = store_read_project('.')
            if is_package_dir('.'):
                package = store_read_package('.')
        else:
            raise oscerr.WrongArgs('Wrong number of arguments')

        root = ET.fromstring(b''.join(show_configuration(apiurl)))
        node = root.find('obs_url')
        if node is None or not node.text:
            raise oscerr.APIError('obs_url configuration element expected')
        obs_url = node.text

        if package is None:
            url = "{}/project/show/{}".format(obs_url, project)
        else:
            url = "{}/package/show/{}/{}".format(obs_url, project, package)

        run_external('xdg-open', url)


    @cmdln.option('-r', '--revision', metavar='rev',
                        help='checkout the specified revision. '
                             'NOTE: if you checkout the complete project '
                             'this option is ignored!')
    @cmdln.option('-e', '--expand-link', action='store_true',
                        help='if a package is a link, check out the expanded '
                             'sources (no-op, since this became the default)')
    @cmdln.option('-D', '--deleted', action='store_true',
                        help='checkout an already deleted package. No meta information ')
    @cmdln.option('-u', '--unexpand-link', action='store_true',
                        help='if a package is a link, check out the _link file ' \
                             'instead of the expanded sources')
    @cmdln.option('-M', '--meta', action='store_true',
                        help='checkout out meta data instead of sources' )
    @cmdln.option('-c', '--current-dir', action='store_true',
                        help='place PACKAGE folder in the current directory ' \
                             'instead of a PROJECT/PACKAGE directory')
    @cmdln.option('-o', '--output-dir', metavar='outdir',
                        help='place package in the specified directory ' \
                             'instead of a PROJECT/PACKAGE directory')
    @cmdln.option('-s', '--source-service-files', action='store_true',
                        help='Run source services.' )
    @cmdln.option('-S', '--server-side-source-service-files', action='store_true',
                        help='Use server side generated sources instead of local generation.' )
    @cmdln.option('-l', '--limit-size', metavar='limit_size',
                        help='Skip all files with a given size')
    @cmdln.alias('co')
    def do_checkout(self, subcmd, opts, *args):
        """${cmd_name}: Check out content from the repository

        Check out content from the repository server, creating a local working
        copy.

        When checking out a single package, the option --revision can be used
        to specify a revision of the package to be checked out.

        When a package is a source link, then it will be checked out in
        expanded form. If --unexpand-link option is used, the checkout will
        instead produce the raw _link file plus patches.

        usage:
            osc co PROJECT [PACKAGE] [FILE]
               osc co PROJECT                    # entire project
               osc co PROJECT PACKAGE            # a package
               osc co PROJECT PACKAGE FILE       # single file -> to current dir

            while inside a project directory:
               osc co PACKAGE                    # check out PACKAGE from project

            with the result of rpm -q --qf '%%{DISTURL}\\n' PACKAGE
               osc co obs://API/PROJECT/PLATFORM/REVISION-PACKAGE

        ${cmd_option_list}
        """

        if opts.unexpand_link:
            expand_link = False
        else:
            expand_link = True

        if not args:
            raise oscerr.WrongArgs('Incorrect number of arguments.\n\n' \
                  + self.get_cmd_help('checkout'))

        # A DISTURL can be found in build results to be able to relocate the source used to build
        # obs://$OBS_INSTANCE/$PROJECT/$REPOSITORY/$XSRCMD5-$PACKAGE(:$FLAVOR)
        # obs://build.opensuse.org/openSUSE:11.3/standard/fc6c25e795a89503e99d59da5dc94a79-screen
        m = re.match(r"obs://([^/]+)/(\S+)/([^/]+)/([A-Fa-f\d]+)\-([^:]*)(:\S+)?", args[0])
        if m and len(args) == 1:
            apiurl   = "https://" + m.group(1)
            project = project_dir = m.group(2)
            # platform            = m.group(3)
            opts.revision         = m.group(4)
            package               = m.group(5)
            apiurl = apiurl.replace('/build.', '/api.')
            filename = None
        else:
            args = slash_split(args)
            project = package = filename = None
            apiurl = self.get_api_url()
            try:
                project = project_dir = args[0]
                package = args[1]
                filename = args[2]
            except:
                pass

            if len(args) == 1 and is_project_dir(os.curdir):
                project = store_read_project(os.curdir)
                project_dir = os.curdir
                package = args[0]

        if opts.deleted and package:
            if not opts.output_dir:
                raise oscerr.WrongOptions('-o | --output-dir is needed to get deleted sources')
        elif opts.deleted and not package:
            raise oscerr.WrongOptions('-D | --deleted can only be used with a package')

        rev, dummy = parseRevisionOption(opts.revision)
        if rev == None:
            rev = "latest"

        if rev and rev != "latest" and not checkRevision(project, package, rev):
            print('Revision \'%s\' does not exist' % rev, file=sys.stderr)
            sys.exit(1)

        if filename:
            # Note: same logic as with 'osc cat' (not 'osc ls', which never merges!)
            if expand_link:
                rev = show_upstream_srcmd5(apiurl, project, package, expand=True, revision=rev)
            get_source_file(apiurl, project, package, filename, revision=rev, progress_obj=self.download_progress)

        elif package:
            if opts.deleted:
                checkout_deleted_package(apiurl, project, package, opts.output_dir)
            else:
                if opts.current_dir:
                    project_dir = None
                checkout_package(apiurl, project, package, rev, expand_link=expand_link, \
                                 prj_dir=project_dir, service_files = opts.source_service_files, \
                                 server_service_files=opts.server_side_source_service_files, \
                                 progress_obj=self.download_progress, size_limit=opts.limit_size, \
                                 meta=opts.meta, outdir=opts.output_dir)
                print_request_list(apiurl, project, package)

        elif project:
            prj_dir = opts.output_dir if opts.output_dir else project
            if not opts.output_dir and conf.config['checkout_no_colon']:
                prj_dir = prj_dir.replace(':', '/')
            if sys.platform[:3] == 'win':
                prj_dir = prj_dir.replace(':', ';')
            if os.path.exists(prj_dir):
                sys.exit('osc: project directory \'%s\' already exists' % prj_dir)

            # check if the project does exist (show_project_meta will throw an exception)
            show_project_meta(apiurl, project)

            Project.init_project(apiurl, prj_dir, project, conf.config['do_package_tracking'])
            print(statfrmt('A', prj_dir))

            # all packages
            for package in meta_get_packagelist(apiurl, project):
                if opts.output_dir is not None:
                    outputdir = os.path.join(opts.output_dir, package)
                    if not os.path.exists(opts.output_dir):
                        os.mkdir(os.path.join(opts.output_dir))
                else:
                    outputdir=None

                # don't check out local links by default
                try:
                    m = show_files_meta(apiurl, project, package)
                    li = Linkinfo()
                    li.read(ET.fromstring(''.join(m)).find('linkinfo'))
                    if not li.haserror():
                        if li.project == project:
                            print(statfrmt('S', package + " link to package " + li.package))
                            continue
                except:
                    pass

                try:
                    checkout_package(apiurl, project, package, expand_link = expand_link, \
                                     prj_dir = prj_dir, service_files = opts.source_service_files, \
                                     server_service_files = opts.server_side_source_service_files, \
                                     progress_obj=self.download_progress, size_limit=opts.limit_size, \
                                     meta=opts.meta)
                except oscerr.LinkExpandError as e:
                    print('Link cannot be expanded:\n', e, file=sys.stderr)
                    print('Use "osc repairlink" for fixing merge conflicts:\n', file=sys.stderr)
                    # check out in unexpanded form at least
                    checkout_package(apiurl, project, package, expand_link = False, \
                                     prj_dir = prj_dir, service_files = opts.source_service_files, \
                                     server_service_files = opts.server_side_source_service_files, \
                                     progress_obj=self.download_progress, size_limit=opts.limit_size, \
                                     meta=opts.meta)
            print_request_list(apiurl, project)

        else:
            raise oscerr.WrongArgs('Missing argument.\n\n' \
                  + self.get_cmd_help('checkout'))


    @cmdln.option('-q', '--quiet', action='store_true',
                        help='print as little as possible')
    @cmdln.option('-v', '--verbose', action='store_true',
                        help='print extra information')
    @cmdln.option('-e', '--show-excluded', action='store_true',
                        help='also show files which are excluded by the ' \
                             '"exclude_glob" config option')
    @cmdln.alias('st')
    def do_status(self, subcmd, opts, *args):
        """${cmd_name}: Show status of files in working copy

        Show the status of files in a local working copy, indicating whether
        files have been changed locally, deleted, added, ...

        The first column in the output specifies the status and is one of the
        following characters:
          ' ' no modifications
          'A' Added
          'C' Conflicted
          'D' Deleted
          'M' Modified
          'R' Replaced (file was deleted and added again afterwards)
          '?' item is not under version control
          '!' item is missing (removed by non-osc command) or incomplete
          'S' item is skipped (item exceeds a file size limit or is _service:* file)
          'F' Frozen (use "osc pull" to merge conflicts) (package-only state)

        examples:
          osc st
          osc st <directory>
          osc st file1 file2 ...

        usage:
            osc status [OPTS] [PATH...]
        ${cmd_option_list}
        """

        if opts.quiet and opts.verbose:
            raise oscerr.WrongOptions('\'--quiet\' and \'--verbose\' are mutually exclusive')

        args = parseargs(args)
        lines = []
        excl_states = (' ',)
        if opts.quiet:
            excl_states += ('?',)
        elif opts.verbose:
            excl_states = ()
        for arg in args:
            if is_project_dir(arg):
                prj = Project(arg, False)
                # don't exclude packages with state ' ' because the packages
                # might have modified etc. files
                prj_excl = [st for st in excl_states if st != ' ']
                for st, pac in sorted(prj.get_status(*prj_excl), key=cmp_to_key(compare)):
                    p = prj.get_pacobj(pac)
                    if p is None:
                        # state is != ' '
                        lines.append(statfrmt(st, os.path.normpath(os.path.join(prj.dir, pac))))
                        continue
                    if p.isfrozen():
                        lines.append(statfrmt('F', os.path.normpath(os.path.join(prj.dir, pac))))
                    elif st == ' ' and opts.verbose or st != ' ':
                        lines.append(statfrmt(st, os.path.normpath(os.path.join(prj.dir, pac))))
                    states = p.get_status(opts.show_excluded, *excl_states)
                    for st, filename in sorted(states, key=cmp_to_key(compare)):
                        lines.append(statfrmt(st, os.path.normpath(os.path.join(p.dir, filename))))
            else:
                p = findpacs([arg])[0]
                for st, filename in sorted(p.get_status(opts.show_excluded, *excl_states), key=cmp_to_key(compare)):
                    lines.append(statfrmt(st, os.path.normpath(os.path.join(p.dir, filename))))
        if lines:
            print('\n'.join(lines))


    def do_add(self, subcmd, opts, *args):
        """${cmd_name}: Mark files to be added upon the next commit

        In case a URL is given the file will get downloaded and registered to be downloaded
        by the server as well via the download_url source service.

        This is recommended for release tar balls to track their source and to help
        others to review your changes esp. on version upgrades.

        usage:
            osc add URL [URL...]
            osc add FILE [FILE...]
        ${cmd_option_list}
        """
        if not args:
            raise oscerr.WrongArgs('Missing argument.\n\n' \
                  + self.get_cmd_help('add'))

        # Do some magic here, when adding a url. We want that the server to download the tar ball and to verify it
        for arg in parseargs(args):
            if arg.startswith('http://') or arg.startswith('https://') or arg.startswith('ftp://') or arg.startswith('git://'):
                if arg.endswith('.git'):
                    addGitSource(arg)
                else:
                    addDownloadUrlService(arg)
            else:
                addFiles([arg])


    def do_mkpac(self, subcmd, opts, *args):
        """${cmd_name}: Create a new package under version control

        usage:
            osc mkpac new_package
        ${cmd_option_list}
        """
        if not conf.config['do_package_tracking']:
            print("to use this feature you have to enable \'do_package_tracking\' " \
                                "in the [general] section in the configuration file", file=sys.stderr)
            sys.exit(1)

        if len(args) != 1:
            raise oscerr.WrongArgs('Wrong number of arguments.')

        createPackageDir(args[0])

    @cmdln.option('-r', '--recursive', action='store_true',
                        help='If CWD is a project dir then scan all package dirs as well')
    @cmdln.alias('ar')
    def do_addremove(self, subcmd, opts, *args):
        """${cmd_name}: Adds new files, removes disappeared files

        Adds all files new in the local copy, and removes all disappeared files.

        ARG, if specified, is a package working copy.

        ${cmd_usage}
        ${cmd_option_list}
        """

        args = parseargs(args)
        arg_list = args[:]
        for arg in arg_list:
            if is_project_dir(arg) and conf.config['do_package_tracking']:
                prj = Project(arg, False)
                for pac in prj.pacs_unvers:
                    pac_dir = getTransActPath(os.path.join(prj.dir, pac))
                    if os.path.isdir(pac_dir):
                        addFiles([pac_dir], prj)
                for pac in prj.pacs_broken:
                    if prj.get_state(pac) != 'D':
                        prj.set_state(pac, 'D')
                        print(statfrmt('D', getTransActPath(os.path.join(prj.dir, pac))))
                if opts.recursive:
                    for pac in prj.pacs_have:
                        state = prj.get_state(pac)
                        if state != None and state != 'D':
                            pac_dir = getTransActPath(os.path.join(prj.dir, pac))
                            args.append(pac_dir)
                args.remove(arg)
                prj.write_packages()
            elif is_project_dir(arg):
                print('osc: addremove is not supported in a project dir unless ' \
                                    '\'do_package_tracking\' is enabled in the configuration file', file=sys.stderr)
                sys.exit(1)

        pacs = findpacs(args)
        for p in pacs:
            todo = list(set(p.filenamelist + p.filenamelist_unvers + p.to_be_added))
            for filename in todo:
                abs_filename = os.path.join(p.absdir, filename)
                if os.path.isdir(abs_filename):
                    continue
                # ignore foo.rXX, foo.mine for files which are in 'C' state
                if os.path.splitext(filename)[0] in p.in_conflict:
                    continue
                state = p.status(filename)
                if state == '?':
                    # TODO: should ignore typical backup files suffix ~ or .orig
                    p.addfile(filename)
                elif state == 'D' and os.path.isfile(abs_filename):
                    # if the "deleted" file exists in the wc, track it again
                    p.addfile(filename)
                elif state == '!':
                    p.delete_file(filename)
                    print(statfrmt('D', getTransActPath(os.path.join(p.dir, filename))))

    @cmdln.alias('ci')
    @cmdln.alias('checkin')
    @cmdln.option('-m', '--message', metavar='TEXT',
                  help='specify log message TEXT')
    @cmdln.option('-n', '--no-message', default=False, action='store_true',
                  help='do not specify a log message')
    @cmdln.option('-F', '--file', metavar='FILE',
                  help='read log message from FILE, \'-\' denotes standard input.')
    @cmdln.option('-f', '--force', default=False, action="store_true",
                  help='force commit, even if there were no changes')
    @cmdln.option('--skip-validation', default=False, action="store_true",
                  help='deprecated, don\'t use it')
    @cmdln.option('-v', '--verbose', default=False, action="store_true",
                  help='Run the source services with verbose information')
    @cmdln.option('--skip-local-service-run', '--noservice', default=False, action="store_true",
                  help='Skip service run of configured source services for local run')
    def do_commit(self, subcmd, opts, *args):
        """${cmd_name}: Upload content to the repository server

        Upload content which is changed in your working copy, to the repository
        server.

        examples:
           osc ci                   # current dir
           osc ci <dir>
           osc ci file1 file2 ...

        ${cmd_usage}
        ${cmd_option_list}
        """
        try:
            self._commit(subcmd, opts, args)
        except oscerr.ExtRuntimeError as e:
            pattern = re.compile("No such file")
            if "No such file" in e.msg:
                editor = os.getenv('EDITOR', default=get_default_editor())
                print("Editor %s not found" % editor)
                return 1
            print("ERROR: service run failed", e, file=sys.stderr)
            return 1
        except oscerr.PackageNotInstalled as e:
            print("ERROR: please install %s " % e.args, end='')
            print("or use the --noservice option")
            return 1


    def _commit(self, subcmd, opts, args):
        args = parseargs(args)
        if opts.skip_validation:
            print("WARNING: deprecated option --skip-validation ignored.", file=sys.stderr)

        msg = ''
        if opts.message:
            msg = opts.message
        elif opts.file:
            if opts.file == '-':
                msg = sys.stdin.read()
            else:
                try:
                    msg = open(opts.file).read()
                except:
                    sys.exit('could not open file \'%s\'.' % opts.file)
        skip_local_service_run = False
        if not conf.config['local_service_run'] or opts.skip_local_service_run:
            skip_local_service_run = True
        arg_list = args[:]
        for arg in arg_list:
            if conf.config['do_package_tracking'] and is_project_dir(arg):
                prj = Project(arg)
                if not msg and not opts.no_message:
                    msg = edit_message()

                # check any of the packages is a link, if so, as for branching
                pacs = (Package(os.path.join(prj.dir, pac))
                        for pac in prj.pacs_have if prj.get_state(pac) == ' ')
                can_branch = False
                if any(pac.is_link_to_different_project() for pac in pacs):
                    repl = raw_input('Some of the packages are links to a different project!\n' \
                                     'Create a local branch before commit? (y|N) ')
                    if repl in('y', 'Y'):
                        can_branch = True

                prj.commit(msg=msg, skip_local_service_run=skip_local_service_run, verbose=opts.verbose, can_branch=can_branch)
                args.remove(arg)

        pacs, no_pacs = findpacs(args, fatal=False)

        if conf.config['do_package_tracking'] and (pacs or no_pacs):
            prj_paths = {}
            single_paths = []
            files = {}
            # XXX: this is really ugly
            pac_objs = {}
            # it is possible to commit packages from different projects at the same
            # time: iterate over all pacs and put each pac to the right project in the dict
            for pac in pacs:
                path = os.path.normpath(os.path.join(pac.dir, os.pardir))
                if is_project_dir(path):
                    # use this path construction for computing "pac_name",
                    # because it is possible that pac.name != pac_name (e.g.
                    # for an external package wc)
                    pac_name = os.path.basename(os.path.normpath(pac.absdir))
                    prj_paths.setdefault(path, []).append(pac_name)
                    pac_objs.setdefault(path, []).append(pac)
                    files.setdefault(path, {})[pac_name] = pac.todo
                else:
                    single_paths.append(pac.dir)
                    if not pac.todo:
                        pac.todo = pac.filenamelist + pac.filenamelist_unvers
                    pac.todo.sort()
            for pac in no_pacs:
                if os.path.exists(pac):
                    # fail with an appropriate error message
                    store_read_apiurl(pac, defaulturl=False)
                path = os.path.normpath(os.path.join(pac, os.pardir))
                if is_project_dir(path):
                    pac_name = os.path.basename(os.path.normpath(os.path.abspath(pac)))
                    prj_paths.setdefault(path, []).append(pac_name)
                    pac_objs.setdefault(path, [])
                    # wrt. the current implementation of Project.commit, this
                    # actually not needed
                    files.setdefault(path, {})[pac_name] = []
                else:
                    # fail with an appropriate error message
                    store_read_apiurl(pac, defaulturl=False)
            for prj_path, packages in prj_paths.items():
                prj = Project(prj_path)
                if not msg and not opts.no_message:
                    msg = get_commit_msg(prj.absdir, pac_objs[prj_path])

                # check any of the packages is a link, if so, as for branching
                can_branch = False
                if any(pac.is_link_to_different_project() for pac in pacs):
                    repl = raw_input('Some of the packages are links to a different project!\n' \
                                     'Create a local branch before commit? (y|N) ')
                    if repl in('y', 'Y'):
                        can_branch = True

                prj_files = files[prj_path]
                prj.commit(packages, msg=msg, files=prj_files, skip_local_service_run=skip_local_service_run, verbose=opts.verbose, can_branch=can_branch, force=opts.force)
                store_unlink_file(prj.absdir, '_commit_msg')
            for pac in single_paths:
                p = Package(pac)
                if not msg and not opts.no_message:
                    msg = get_commit_msg(p.absdir, [p])
                p.commit(msg, skip_local_service_run=skip_local_service_run, verbose=opts.verbose, force=opts.force)
                store_unlink_file(p.absdir, '_commit_msg')
        elif no_pacs:
            # fail with an appropriate error message
            store_read_apiurl(no_pacs[0], defaulturl=False)
        else:
            for p in pacs:
                if not p.todo:
                    p.todo = p.filenamelist + p.filenamelist_unvers
                p.todo.sort()
                if not msg and not opts.no_message:
                    msg = get_commit_msg(p.absdir, [p])
                p.commit(msg, skip_local_service_run=skip_local_service_run, verbose=opts.verbose, force=opts.force)
                store_unlink_file(p.absdir, '_commit_msg')

    @cmdln.option('-r', '--revision', metavar='REV',
                        help='update to specified revision (this option will be ignored '
                             'if you are going to update the complete project or more than '
                             'one package)')
    @cmdln.option('', '--linkrev', metavar='REV',
                        help='revision of the link target that is used during link expansion')
    @cmdln.option('-u', '--unexpand-link', action='store_true',
                        help='if a package is an expanded link, update to the raw _link file')
    @cmdln.option('-e', '--expand-link', action='store_true',
                        help='if a package is a link, update to the expanded sources')
    @cmdln.option('-s', '--source-service-files', action='store_true',
                        help='Run local source services after update.' )
    @cmdln.option('-S', '--server-side-source-service-files', action='store_true',
                        help='Use server side generated sources instead of local generation.' )
    @cmdln.option('-l', '--limit-size', metavar='limit_size',
                        help='Skip all files with a given size')
    @cmdln.alias('up')
    def do_update(self, subcmd, opts, *args):
        """${cmd_name}: Update a working copy

        examples:

        1. osc up
                If the current working directory is a package, update it.
                If the directory is a project directory, update all contained
                packages, AND check out newly added packages.

                To update only checked out packages, without checking out new
                ones, you might want to use "osc up *" from within the project
                dir.

        2. osc up PAC
                Update the packages specified by the path argument(s)

        When --expand-link is used with source link packages, the expanded
        sources will be checked out. Without this option, the _link file and
        patches will be checked out. The option --unexpand-link can be used to
        switch back to the "raw" source with a _link file plus patch(es).

        ${cmd_usage}
        ${cmd_option_list}
        """

        if opts.expand_link and opts.unexpand_link:
            raise oscerr.WrongOptions('Sorry, the options --expand-link and '
                                      '--unexpand-link and are mutually '
                                      'exclusive.')

        args = parseargs(args)
        arg_list = args[:]

        for arg in arg_list:
            if is_project_dir(arg):
                prj = Project(arg, progress_obj=self.download_progress)

                if conf.config['do_package_tracking']:
                    prj.update(expand_link=opts.expand_link,
                               unexpand_link=opts.unexpand_link)
                    args.remove(arg)
                else:
                    # if not tracking package, and 'update' is run inside a project dir,
                    # it should do the following:
                    # (a) update all packages
                    args += prj.pacs_have
                    # (b) fetch new packages
                    prj.checkout_missing_pacs(opts.expand_link, opts.unexpand_link)
                    args.remove(arg)
                print_request_list(prj.apiurl, prj.name)

        args.sort()
        pacs = findpacs(args, progress_obj=self.download_progress)

        if opts.revision and len(args) == 1:
            rev, dummy = parseRevisionOption(opts.revision)
            if not checkRevision(pacs[0].prjname, pacs[0].name, rev, pacs[0].apiurl):
                print('Revision \'%s\' does not exist' % rev, file=sys.stderr)
                sys.exit(1)
            if opts.expand_link or opts.unexpand_link:
                meta = show_files_meta(pacs[0].apiurl, pacs[0].prjname,
                                       pacs[0].name, revision=rev,
                                       linkrev=opts.linkrev,
                                       expand=opts.server_side_source_service_files)
                directory = ET.fromstring(meta)
                li_node = directory.find('linkinfo')
                if li_node is None:
                    print('Revision \'%s\' is no link' % rev, file=sys.stderr)
                    sys.exit(1)
                li = Linkinfo()
                li.read(li_node)
                if li.haserror() and opts.expand_link:
                    raise oscerr.LinkExpandError(pacs[0].prjname, pacs[0].name,
                                                 li.error)
                rev = li.lsrcmd5
                if opts.expand_link:
                    rev = li.xsrcmd5
                if rev is None:
                    # 2 cases: a) unexpand and passed rev has linkerror
                    #          b) expand and passed rev is already expanded
                    rev = directory.get('srcmd5')
        else:
            rev = None

        for p in pacs:
            if len(pacs) > 1:
                print('Updating %s' % p.name)

            # this shouldn't be needed anymore with the new update mechanism
            # an expand/unexpand update is treated like a normal update (there's nothing special)
            # FIXME: ugly workaround for #399247
#            if opts.expand_link or opts.unexpand_link:
#                if [ i for i in p.filenamelist+p.filenamelist_unvers if p.status(i) != ' ' and p.status(i) != '?']:
#                    print >>sys.stderr, 'osc: cannot expand/unexpand because your working ' \
#                                        'copy has local modifications.\nPlease revert/commit them ' \
#                                        'and try again.'
#                    sys.exit(1)

            if not rev:
                if opts.expand_link:
                    rev = p.latest_rev(expand=True)
                    if p.islink() and not p.isexpanded():
                        print('Expanding to rev', rev)
                elif opts.unexpand_link and p.islink() and p.isexpanded():
                    rev = show_upstream_rev(p.apiurl, p.prjname, p.name, meta=p.meta)
                    print('Unexpanding to rev', rev)
                elif (p.islink() and p.isexpanded()) or opts.server_side_source_service_files:
                    rev = p.latest_rev(include_service_files=opts.server_side_source_service_files)

            p.update(rev, opts.server_side_source_service_files, opts.limit_size)
            if opts.source_service_files:
                print('Running local source services')
                p.run_source_services()
            if opts.unexpand_link:
                p.unmark_frozen()
            rev = None
            print_request_list(p.apiurl, p.prjname, p.name)


    @cmdln.option('-f', '--force', action='store_true',
                        help='forces removal of entire package and its files')
    @cmdln.alias('rm')
    @cmdln.alias('del')
    @cmdln.alias('remove')
    def do_delete(self, subcmd, opts, *args):
        """${cmd_name}: Mark files or package directories to be deleted upon the next 'checkin'

        usage:
            cd .../PROJECT/PACKAGE
            osc delete FILE [...]
            cd .../PROJECT
            osc delete PACKAGE [...]

        This command works on check out copies. Use "rdelete" for working on server
        side only. This is needed for removing the entire project.

        As a safety measure, projects must be empty (i.e., you need to delete all
        packages first).

        If you are sure that you want to remove a package and all
        its files use \'--force\' switch. Sometimes this also works without --force.

        ${cmd_option_list}
        """

        if not args:
            raise oscerr.WrongArgs('Missing argument.\n\n' \
                  + self.get_cmd_help('delete'))

        args = parseargs(args)
        # check if args contains a package which was removed by
        # a non-osc command and mark it with the 'D'-state
        arg_list = args[:]
        for i in arg_list:
            if not os.path.exists(i):
                prj_dir, pac_dir = getPrjPacPaths(i)
                if is_project_dir(prj_dir):
                    prj = Project(prj_dir, False)
                    if i in prj.pacs_broken:
                        if prj.get_state(i) != 'A':
                            prj.set_state(pac_dir, 'D')
                        else:
                            prj.del_package_node(i)
                        print(statfrmt('D', getTransActPath(i)))
                        args.remove(i)
                        prj.write_packages()
        pacs = findpacs(args)

        for p in pacs:
            if not p.todo:
                prj_dir, pac_dir = getPrjPacPaths(p.absdir)
                if is_project_dir(prj_dir):
                    if conf.config['do_package_tracking']:
                        prj = Project(prj_dir, False)
                        prj.delPackage(p, opts.force)
                    else:
                        print("WARNING: package tracking is disabled, operation skipped !", file=sys.stderr)
            else:
                pathn = getTransActPath(p.dir)
                for filename in p.todo:
                    p.clear_from_conflictlist(filename)
                    ret, state = p.delete_file(filename, opts.force)
                    if ret:
                        print(statfrmt('D', os.path.join(pathn, filename)))
                        continue
                    if state == '?':
                        sys.exit('\'%s\' is not under version control' % filename)
                    elif state in ['A', 'M'] and not opts.force:
                        sys.exit('\'%s\' has local modifications (use --force to remove this file)' % filename)
                    elif state == 'S':
                        sys.exit('\'%s\' is marked as skipped and no local file with this name exists' % filename)


    def do_resolved(self, subcmd, opts, *args):
        """${cmd_name}: Remove 'conflicted' state on working copy files

        If an upstream change can't be merged automatically, a file is put into
        in 'conflicted' ('C') state. Within the file, conflicts are marked with
        special <<<<<<< as well as ======== and >>>>>>> lines.

        After manually resolving all conflicting parts, use this command to
        remove the 'conflicted' state.

        Note:  this subcommand does not semantically resolve conflicts or
        remove conflict markers; it merely removes the conflict-related
        artifact files and allows PATH to be committed again.

        usage:
            osc resolved FILE [FILE...]
        ${cmd_option_list}
        """

        if not args:
            raise oscerr.WrongArgs('Missing argument.\n\n' \
                  + self.get_cmd_help('resolved'))

        args = parseargs(args)
        pacs = findpacs(args)

        for p in pacs:
            for filename in p.todo:
                print('Resolved conflicted state of "%s"' % filename)
                p.clear_from_conflictlist(filename)


    @cmdln.alias('dists')
# FIXME: using just ^DISCONTINUED as match is not a general approach and only valid for one instance
#        we need to discuss an api call for that, if we need this
#    @cmdln.option('-d', '--discontinued', action='store_true',
#                        help='show discontinued distributions')
    def do_distributions(self, subcmd, opts, *args):
        """${cmd_name}: Shows all available distributions

        This command shows the available distributions. For active distributions
        it shows the name, project and name of the repository and a suggested default repository name.

        usage:
            osc distributions

        ${cmd_option_list}
        """
        apiurl = self.get_api_url()

        print('\n'.join(get_distibutions(apiurl)))#FIXME:, opts.discontinued))

    @cmdln.hide(1)
    def do_results_meta(self, subcmd, opts, *args):
        """${cmd_name}:

        Obsolete command to show build results. Use 'results --xml' now.

        See the help output of 'results'.
        """

        print("This command is obsolete. Use 'osc results --xml'.",
              file=sys.stderr)
        print("See 'osc help results'.", file=sys.stderr)
        return 2

    @cmdln.hide(1)
    @cmdln.option('-l', '--last-build', action='store_true',
                        help='show last build results (succeeded/failed/unknown)')
    @cmdln.option('-r', '--repo', action='append', default = [],
                        help='Show results only for specified repo(s)')
    @cmdln.option('-a', '--arch', action='append', default = [],
                        help='Show results only for specified architecture(s)')
    @cmdln.option('', '--xml', action='store_true',
                        help='generate output in XML (former results_meta)')
    def do_rresults(self, subcmd, opts, *args):
        """${cmd_name}:

        Obsolete command to show build results. Use 'results' now.

        See the help output of 'results'.
        """

        print("Command rresults is obsolete. Running 'osc results' instead",
              file=sys.stderr)
        print("See 'osc help results'.", file=sys.stderr)
        return self.do_results('results', opts, *args)

    @cmdln.option('-f', '--force', action='store_true', default=False,
                        help="Don't ask and delete files")
    def do_rremove(self, subcmd, opts, project, package, *files):
        """${cmd_name}: Remove source files from selected package

        ${cmd_usage}
        ${cmd_option_list}
        """
        apiurl = self.get_api_url()

        if len(files) == 0:
            if not '/' in project:
                raise oscerr.WrongArgs("Missing operand, type osc help rremove for help")
            else:
                files = (package, )
                project, package = project.split('/')

        for filename in files:
            if not opts.force:
                resp = raw_input("rm: remove source file `%s' from `%s/%s'? (yY|nN) " % (filename, project, package))
                if resp not in ('y', 'Y'):
                    continue
            try:
                delete_files(apiurl, project, package, (filename, ))
            except HTTPError as e:
                if opts.force:
                    print(e, file=sys.stderr)
                    body = e.read()
                    if e.code in [ 400, 403, 404, 500 ]:
                        if '<summary>' in body:
                            msg = body.split('<summary>')[1]
                            msg = msg.split('</summary>')[0]
                            print(msg, file=sys.stderr)
                else:
                    raise e

    @cmdln.alias('r')
    @cmdln.option('-l', '--last-build', action='store_true',
                        help='show last build results (succeeded/failed/unknown)')
    @cmdln.option('-r', '--repo', action='append', default = [],
                        help='Show results only for specified repo(s)')
    @cmdln.option('-a', '--arch', action='append', default = [],
                        help='Show results only for specified architecture(s)')
    @cmdln.option('-v', '--verbose', action='store_true', default=False,
                        help='more verbose output')
    @cmdln.option('--no-multibuild', action='store_true', default=False,
                        help='Disable results for all direct affect packages inside of the project')
    @cmdln.option('-M', '--multibuild-package', action='append', default=[],
                        help='Only show results for the specified multibuild package')
    @cmdln.option('-V', '--vertical', action='store_true',
                        help='list packages vertically instead horizontally for entire project')
    @cmdln.option('-w', '--watch', action='store_true',
                        help='watch the results until all finished building')
    @cmdln.option('', '--xml', action='store_true', default=False,
                        help='generate output in XML (former results_meta)')
    @cmdln.option('', '--csv', action='store_true', default=False,
                        help='generate output in CSV format')
    @cmdln.option('', '--format', default='%(repository)s|%(arch)s|%(state)s|%(dirty)s|%(code)s|%(details)s',
                        help='format string for csv output')
    @cmdln.option('--show-excluded', action='store_true',
                        help='show repos that are excluded for this package')
    def do_results(self, subcmd, opts, *args):
        """${cmd_name}: Shows the build results of a package or project

        Usage:
            osc results                 # (inside working copy of PRJ or PKG)
            osc results PROJECT [PACKAGE]

        ${cmd_option_list}
        """

        args = slash_split(args)

        apiurl = self.get_api_url()
        if len(args) > 2:
            raise oscerr.WrongArgs('Too many arguments (required none, one, or two)')
        project = package = None
        wd = os.curdir
        if is_project_dir(wd):
            project = store_read_project(wd)
        elif is_package_dir(wd):
            project = store_read_project(wd)
            package = store_read_package(wd)
        if len(args) > 0:
            project = args[0]
        if len(args) > 1:
            package = args[1]

        if project == None:
            raise oscerr.WrongOptions("No project given")

        if package == None:
            opts.hide_legend = None
            opts.name_filter = None
            opts.status_filter = None
            opts.show_non_building = None
            opts.show_excluded = None
            return self.do_prjresults('prjresults', opts, *args)

        if opts.xml and opts.csv:
            raise oscerr.WrongOptions("--xml and --csv are mutual exclusive")

        kwargs = {'apiurl': apiurl, 'project': project, 'package': package,
                  'lastbuild': opts.last_build, 'repository': opts.repo,
                  'arch': opts.arch, 'wait': opts.watch, 'showexcl': opts.show_excluded}
        if opts.multibuild_package:
            opts.no_multibuild = False
            kwargs['multibuild_packages'] = opts.multibuild_package
        if not opts.no_multibuild:
            kwargs['multibuild'] = kwargs['locallink'] = True
        if opts.xml or opts.csv:
            # hmm should we filter excluded repos here as well?
            # for now, ignore --show-excluded
            del kwargs['showexcl']
            for xml in get_package_results(**kwargs):
                if opts.xml:
                    print(decode_it(xml), end='')
                else:
                    # csv formatting
                    results = [r for r, _ in result_xml_to_dicts(xml)]
                    print('\n'.join(format_results(results, opts.format)))
        else:
            kwargs['verbose'] = opts.verbose
            kwargs['wait'] = opts.watch
            kwargs['printJoin'] = '\n'
            get_results(**kwargs)


    # WARNING: this function is also called by do_results. You need to set a default there
    #          as well when adding a new option!
    @cmdln.option('-q', '--hide-legend', action='store_true',
                        help='hide the legend')
    @cmdln.option('-w', '--watch', action='store_true',
                        help='watch the results until all finished building, only supported with --xml')
    @cmdln.option('-c', '--csv', action='store_true',
                        help='csv output')
    @cmdln.option('', '--xml', action='store_true', default=False,
                        help='generate output in XML')
    @cmdln.option('-s', '--status-filter', metavar='STATUS',
                        help='show only packages with buildstatus STATUS (see legend)')
    @cmdln.option('-n', '--name-filter', metavar='EXPR',
                        help='show only packages whose names match EXPR')
    @cmdln.option('-a', '--arch', metavar='ARCH', action='append',
                        help='show results only for specified architecture(s)')
    @cmdln.option('-r', '--repo', metavar='REPO', action='append',
                        help='show results only for specified repo(s)')
    @cmdln.option('-V', '--vertical', action='store_true',
                        help='list packages vertically instead horizontally')
    @cmdln.option('--show-excluded', action='store_true',
                        help='show packages that are excluded in all repos, also hide repos that have only excluded packages')
    @cmdln.alias('pr')
    def do_prjresults(self, subcmd, opts, *args):
        """${cmd_name}: Shows project-wide build results

        Usage:
            osc prjresults (inside working copy)
            osc prjresults PROJECT

        ${cmd_option_list}
        """
        apiurl = self.get_api_url()

        if args:
            if len(args) == 1:
                project = args[0]
            else:
                raise oscerr.WrongArgs('Wrong number of arguments.')
        else:
            wd = os.curdir
            project = store_read_project(wd)

        if opts.xml:
            kwargs = {}
            if opts.repo:
                kwargs['repository'] = opts.repo
            if opts.arch:
                kwargs['arch'] = opts.arch
            kwargs['wait'] = opts.watch
            for results in get_package_results(apiurl, project, **kwargs):
                print(decode_it(results))
            return

        if opts.watch:
            print('Please implement support for osc prjresults --watch without --xml.')
            return 2

        print('\n'.join(get_prj_results(apiurl, project, hide_legend=opts.hide_legend, \
                                        csv=opts.csv, status_filter=opts.status_filter, \
                                        name_filter=opts.name_filter, repo=opts.repo, \
                                        arch=opts.arch, vertical=opts.vertical, \
                                        show_excluded=opts.show_excluded)))

    @cmdln.option('-q', '--hide-legend', action='store_true',
                        help='hide the legend')
    @cmdln.option('-c', '--csv', action='store_true',
                        help='csv output')
    @cmdln.option('-s', '--status-filter', metavar='STATUS',
                        help='show only packages with buildstatus STATUS (see legend)')
    @cmdln.option('-n', '--name-filter', metavar='EXPR',
                        help='show only packages whose names match EXPR')

    @cmdln.hide(1)
    def do_rprjresults(self, subcmd, opts, *args):
        """${cmd_name}:

        Obsolete command to show project-wide build results. Use 'prjresults' now.

        See the help output of 'prjresults'.
        """

        print("Command rprjresults is obsolete. Please use 'osc prjresults'",
              file=sys.stderr)
        print("See 'osc help prjresults'.", file=sys.stderr)
        return 2

    @cmdln.alias('rpmlint')
    @cmdln.alias('lint')
    def do_rpmlintlog(self, subcmd, opts, *args):
        """${cmd_name}: Shows the rpmlint logfile

        Shows the rpmlint logfile to analyse if there are any problems
        with the spec file and the built binaries.

        usage:
            osc rpmlintlog project package repository arch
        """
        apiurl = self.get_api_url()
        args = slash_split(args)

        if len(args) == 4:
            project, package, repository, arch = args
        else:
            raise oscerr.WrongArgs('please provide project package repository arch.')

        print(decode_it(get_rpmlint_log(apiurl, project, package, repository, arch)))

    @cmdln.alias('bl')
    @cmdln.alias('blt')
    @cmdln.alias('buildlogtail')
    @cmdln.option('-l', '--last', action='store_true',
                        help='Show the last finished log file')
    @cmdln.option('-M', '--multibuild-package', metavar='MPAC',
                    help='get log of the specified multibuild package')
    @cmdln.option('-o', '--offset', metavar='OFFSET',
                    help='get log start or end from the offset')
    @cmdln.option('-s', '--strip-time', action='store_true',
                        help='strip leading build time from the log')
    def do_buildlog(self, subcmd, opts, *args):
        """${cmd_name}: Shows the build log of a package

        Shows the log file of the build of a package. Can be used to follow the
        log while it is being written.
        Needs to be called from within a package directory.

        When called as buildlogtail (or blt) it just shows the end of the logfile.
        This is useful to see just a build failure reasons.

        The arguments REPOSITORY and ARCH are the first two columns in the 'osc
        results' output. If the buildlog url is used buildlog command has the
        same behavior as remotebuildlog.

        ${cmd_usage} [REPOSITORY ARCH | BUILDLOGURL]
        ${cmd_option_list}
        """
        import osc.build

        project = package = repository = arch = None

        apiurl = self.get_api_url()

        if len(args) == 1 and args[0].startswith('http'):
            apiurl, project, package, repository, arch = parse_buildlogurl(args[0])
        else:
            project = store_read_project(os.curdir)
            package = store_read_package(os.curdir)
            if len(args) == 1:
                repository, arch = self._find_last_repo_arch(args[0], fatal=False)
                if repository is None:
                    # no local build with this repo was done
                    print('failed to guess arch, using hostarch')
                    repository = args[0]
                    arch = osc.build.hostarch
            elif len(args) < 2:
                self.print_repos()
            elif len(args) > 2:
                raise oscerr.WrongArgs('Too many arguments.')
            else:
                repository = args[0]
                arch = args[1]

        if opts.multibuild_package:
            package = package + ":" + opts.multibuild_package

        offset = 0
        if subcmd == "blt" or subcmd == "buildlogtail":
            query = { 'view': 'entry' }
            if opts.last:
                query['last'] = 1
            u = makeurl(self.get_api_url(), ['build', project, repository, arch, package, '_log'], query=query)
            f = http_GET(u)
            root = ET.parse(f).getroot()
            offset = int(root.find('entry').get('size'))
            if opts.offset:
                offset = offset - int(opts.offset)
            else:
                offset = offset - ( 8 * 1024 )
            if offset < 0:
                offset = 0
        elif opts.offset:
            offset = int(opts.offset)
        strip_time = opts.strip_time or conf.config['buildlog_strip_time']
        print_buildlog(apiurl, project, package, repository, arch, offset, strip_time, opts.last)


    def print_repos(self, repos_only=False, exc_class=oscerr.WrongArgs, exc_msg='Missing arguments', project=None):
        wd = os.curdir
        doprint = False
        if is_package_dir(wd):
            msg = 'Valid arguments for this package are:'
            doprint = True
        elif is_project_dir(wd):
            msg = 'Valid arguments for this project are:'
            doprint = True

        args = []
        if project is not None:
            args.append(project)
            msg = 'Valid arguments are:'
            doprint=True

        if doprint:
            print(msg)
            print()
            if repos_only:
                self.do_repositories("repos_only", None, *args)
            else:
                self.do_repositories(None, None, *args)
        raise exc_class(exc_msg)

    @cmdln.alias('rbl')
    @cmdln.alias('rbuildlog')
    @cmdln.alias('rblt')
    @cmdln.alias('rbuildlogtail')
    @cmdln.alias('remotebuildlogtail')
    @cmdln.option('-l', '--last', action='store_true',
                        help='Show the last finished log file')
    @cmdln.option('--lastsucceeded', action='store_true',
                        help='Show the last succeeded log file')
    @cmdln.option('-M', '--multibuild-package', metavar='MPAC',
                        help='show log file for specified multibuild package')
    @cmdln.option('-o', '--offset', metavar='OFFSET',
                    help='get log starting or ending from the offset')
    @cmdln.option('-s', '--strip-time', action='store_true',
                        help='strip leading build time from the log')
    def do_remotebuildlog(self, subcmd, opts, *args):
        """${cmd_name}: Shows the build log of a package

        Shows the log file of the build of a package. Can be used to follow the
        log while it is being written.

        remotebuildlogtail shows just the tail of the log file.

        usage:
            osc remotebuildlog project package repository arch
            or
            osc remotebuildlog project/package/repository/arch
            or
            osc remotebuildlog buildlogurl
        ${cmd_option_list}
        """
        if len(args) == 1 and args[0].startswith('http'):
            apiurl, project, package, repository, arch = parse_buildlogurl(args[0])
        else:
            args = slash_split(args)
            apiurl = self.get_api_url()
            if len(args) < 4:
                raise oscerr.WrongArgs('Too few arguments.')
            elif len(args) > 4:
                raise oscerr.WrongArgs('Too many arguments.')
            else:
                project, package, repository, arch = args

        if opts.multibuild_package:
            package = package + ":" + opts.multibuild_package

        offset = 0
        if subcmd == "rblt" or subcmd == "rbuildlogtail" or subcmd == "remotebuildlogtail":
            query = { 'view': 'entry' }
            if opts.last:
                query['last'] = 1
            u = makeurl(self.get_api_url(), ['build', project, repository, arch, package, '_log'], query=query)
            f = http_GET(u)
            root = ET.parse(f).getroot()
            offset = int(root.find('entry').get('size'))
            if opts.offset:
                offset = offset - int(opts.offset)
            else:
                offset = offset - ( 8 * 1024 )
            if offset < 0:
                offset = 0
        elif opts.offset:
            offset = int(opts.offset)
        strip_time = opts.strip_time or conf.config['buildlog_strip_time']
        print_buildlog(apiurl, project, package, repository, arch, offset, strip_time, opts.last, opts.lastsucceeded)

    def _find_last_repo_arch(self, repo=None, fatal=True):
        import glob
        files = glob.glob(os.path.join(os.getcwd(), store, "_buildinfo-*"))
        if repo is not None:
            files = [f for f in files
                     if os.path.basename(f).replace('_buildinfo-', '').startswith(repo + '-')]
        if not files:
            if not fatal:
                return None, None
            self.print_repos()
        cfg = files[0]
        # find newest file
        for f in files[1:]:
            if os.stat(f).st_atime > os.stat(cfg).st_atime:
                cfg = f
        root = ET.parse(cfg).getroot()
        repo = root.get("repository")
        arch = root.find("arch").text
        return repo, arch

    @cmdln.alias('lbl')
    @cmdln.option('-o', '--offset', metavar='OFFSET',
                  help='get log starting from offset')
    @cmdln.option('-s', '--strip-time', action='store_true',
                        help='strip leading build time from the log')
    def do_localbuildlog(self, subcmd, opts, *args):
        """${cmd_name}: Shows the build log of a local buildchroot

        usage:
            osc lbl [REPOSITORY [ARCH]]
            osc lbl # show log of newest last local build

        ${cmd_option_list}
        """
        if conf.config['build-type']:
            # FIXME: raise Exception instead
            print('Not implemented for VMs', file=sys.stderr)
            sys.exit(1)

        if len(args) == 0 or len(args) == 1:
            project = store_read_project('.')
            package = store_read_package('.')
            repo = None
            if args:
                repo = args[0]
            repo, arch = self._find_last_repo_arch(repo)
        elif len(args) == 2:
            project = store_read_project('.')
            package = store_read_package('.')
            repo = args[0]
            arch = args[1]
        else:
            if is_package_dir(os.curdir):
                self.print_repos()
            raise oscerr.WrongArgs('Wrong number of arguments.')

        # TODO: refactor/unify buildroot calculation and move it to core.py
        buildroot = os.environ.get('OSC_BUILD_ROOT', conf.config['build-root'])
        apihost = urlsplit(self.get_api_url())[1]
        buildroot = buildroot % {'project': project, 'package': package,
                                 'repo': repo, 'arch': arch, 'apihost': apihost}
        offset = 0
        if opts.offset:
            offset = int(opts.offset)
        logfile = os.path.join(buildroot, '.build.log')
        if not os.path.isfile(logfile):
            raise oscerr.OscIOError(None, 'logfile \'%s\' does not exist' % logfile)
        f = open(logfile, 'rb')
        f.seek(offset)
        data = f.read(BUFSIZE)
        data = decode_it(data)
        while len(data):
            if opts.strip_time or conf.config['buildlog_strip_time']:
                data = buildlog_strip_time(data)
            sys.stdout.write(decode_it(data))
            data = f.read(BUFSIZE)
        f.close()

    @cmdln.option('-M', '--multibuild-package', metavar='MPAC',
                    help='get triggerreason of the specified multibuild package')
    @cmdln.alias('tr')
    def do_triggerreason(self, subcmd, opts, *args):
        """${cmd_name}: Show reason why a package got triggered to build

        The server decides when a package needs to get rebuild, this command
        shows the detailed reason for a package. A brief reason is also stored
        in the jobhistory, which can be accessed via "osc jobhistory".

        Trigger reasons might be:
          - new build (never build yet or rebuild manually forced)
          - source change (e.g. on updating sources)
          - meta change (packages which are used for building have changed)
          - rebuild count sync (In case that it is configured to sync release numbers)

        usage in package or project directory:
            osc triggerreason REPOSITORY ARCH
            osc triggerreason PROJECT PACKAGE REPOSITORY ARCH

        ${cmd_option_list}
        """
        wd = os.curdir
        args = slash_split(args)
        project = package = repository = arch = None

        if len(args) < 2:
            self.print_repos()

        apiurl = self.get_api_url()

        if len(args) == 2: # 2
            if is_package_dir('.'):
                package = store_read_package(wd)
            else:
                raise oscerr.WrongArgs('package is not specified.')
            project = store_read_project(wd)
            repository = args[0]
            arch = args[1]
        elif len(args) == 4:
            project = args[0]
            package = args[1]
            repository = args[2]
            arch = args[3]
        else:
            raise oscerr.WrongArgs('Too many arguments.')

        if opts.multibuild_package:
            package = package + ":" + opts.multibuild_package

        print(apiurl, project, package, repository, arch)
        xml = show_package_trigger_reason(apiurl, project, package, repository, arch)
        root = ET.fromstring(xml)
        if root.find('explain') is None:
            reason = "No triggerreason found"
            print(reason)
        else:
            reason = root.find('explain').text
            triggertime = time.strftime('%Y-%m-%d %H:%M:%S', time.gmtime(int(root.find('time').text)))
            print("%s (at %s)" % (reason, triggertime))
        if reason == "meta change":
            print("changed keys:")
            for package in root.findall('packagechange'):
                print("  ", package.get('change'), package.get('key'))


    # FIXME: the new osc syntax should allow to specify multiple packages
    # FIXME: the command should optionally use buildinfo data to show all dependencies
    @cmdln.alias('whatdependson')
    def do_dependson(self, subcmd, opts, *args):
        """${cmd_name}: Show the build dependencies

        The command dependson and whatdependson can be used to find out what
        will be triggered when a certain package changes.
        This is no guarantee, since the new build might have changed dependencies.

        dependson shows the build dependencies inside of a project, valid for a
        given repository and architecture.
        NOTE: to see all binary packages, which can trigger a build you need to
              refer the buildinfo, since this command shows only the dependencies
              inside of a project.

        The arguments REPOSITORY and ARCH can be taken from the first two columns
        of the 'osc repos' output.

        usage in package or project directory:
            osc dependson REPOSITORY ARCH
            osc whatdependson REPOSITORY ARCH

        usage:
            osc dependson PROJECT [PACKAGE] REPOSITORY ARCH
            osc whatdependson PROJECT [PACKAGE] REPOSITORY ARCH

        ${cmd_option_list}
        """
        wd = os.curdir
        args = slash_split(args)
        project = packages = repository = arch = reverse = None

        if len(args) < 2 and (is_package_dir('.') or is_project_dir('.')):
            self.print_repos()

        if len(args) > 4:
            raise oscerr.WrongArgs('Too many arguments.')

        apiurl = self.get_api_url()

        if len(args) < 3: # 2
            if is_package_dir('.'):
                packages = [store_read_package(wd)]
            elif not is_project_dir('.'):
                raise oscerr.WrongArgs('Project and package is not specified.')
            project = store_read_project(wd)
            repository = args[0]
            arch = args[1]

        if len(args) == 3:
            project = args[0]
            repository = args[1]
            arch = args[2]

        if len(args) == 4:
            project = args[0]
            packages = [args[1]]
            repository = args[2]
            arch = args[3]

        if subcmd == 'whatdependson':
            reverse = 1

        xml = get_dependson(apiurl, project, repository, arch, packages, reverse)

        root = ET.fromstring(xml)
        for package in root.findall('package'):
            print(package.get('name'), ":")
            for dep in package.findall('pkgdep'):
                print("  ", dep.text)


    @cmdln.option('-d', '--debug', action='store_true',
                  help='verbose output of build dependencies')
    @cmdln.option('--alternative-project', metavar='PROJECT',
                  help='specify the build target project')
    @cmdln.option('-M', '--multibuild-package', metavar='MPAC',
                  help='Show the buildinfo of the specified multibuild package')
    @cmdln.option('-x', '--extra-pkgs', metavar='PAC', action='append',
                  help='Add this package when computing the buildinfo')
    @cmdln.option('-p', '--prefer-pkgs', metavar='DIR', action='append',
                  help='Prefer packages from this directory when installing the build-root')
    def do_buildinfo(self, subcmd, opts, *args):
        """${cmd_name}: Shows the build info

        Shows the build "info" which is used in building a package.
        This command is mostly used internally by the 'build' subcommand.
        It needs to be called from within a package directory.

        The BUILD_DESCR argument is optional. BUILD_DESCR is a local RPM specfile
        or Debian "dsc" file. If specified, it is sent to the server, and the
        buildinfo will be based on it. If the argument is not supplied, the
        buildinfo is derived from the specfile which is currently on the source
        repository server.

        The returned data is XML and contains a list of the packages used in
        building, their source, and the expanded BuildRequires.

        The arguments REPOSITORY and ARCH are optional. They can be taken from
        the first two columns of the 'osc repos' output. If not specified,
        REPOSITORY defaults to the 'build_repository' config entry in your 'oscrc'
        and ARCH defaults to your host architecture.

        usage:
            in a package working copy:
                osc buildinfo [OPTS] REPOSITORY ARCH BUILD_DESCR
                osc buildinfo [OPTS] REPOSITORY (ARCH = hostarch, BUILD_DESCR is detected automatically)
                osc buildinfo [OPTS] ARCH (REPOSITORY = build_repository (config option), BUILD_DESCR is detected automatically)
                osc buildinfo [OPTS] BUILD_DESCR (REPOSITORY = build_repository (config option), ARCH = hostarch)
                osc buildinfo [OPTS] (REPOSITORY = build_repository (config option), ARCH = hostarch, BUILD_DESCR is detected automatically)
                Note: if BUILD_DESCR does not exist locally the remote BUILD_DESCR is used

            osc buildinfo [OPTS] PROJECT PACKAGE REPOSITORY ARCH [BUILD_DESCR]

        ${cmd_option_list}
        """
        wd = os.curdir
        args = slash_split(args)

        project = package = repository = arch = build_descr = None
        if len(args) <= 3:
            if not is_package_dir('.'):
                raise oscerr.WrongArgs('Incorrect number of arguments (Note: \'.\' is no package wc)')
            if opts.alternative_project:
                project = opts.alternative_project
                package = '_repository'
            else:
                project = store_read_project('.')
                package = store_read_package('.')
            repository, arch, build_descr = self.parse_repoarchdescr(args, alternative_project=opts.alternative_project, ignore_descr=True, multibuild_package=opts.multibuild_package)
        elif len(args) == 4 or len(args) == 5:
            project = args[0]
            package = args[1]
            repository = args[2]
            arch = args[3]
            if len(args) == 5:
                build_descr = args[4]
        else:
            raise oscerr.WrongArgs('Too many arguments.')

        apiurl = self.get_api_url()

        build_descr_data = None
        if not build_descr is None:
            build_descr_data = open(build_descr, 'rb').read()
        if opts.prefer_pkgs and build_descr_data is None:
            raise oscerr.WrongArgs('error: a build description is needed if \'--prefer-pkgs\' is used')
        elif opts.prefer_pkgs:
            from .build import get_prefer_pkgs
            from .util import cpio
            print('Scanning the following dirs for local packages: %s' % ', '.join(opts.prefer_pkgs))
            cpiodata = cpio.CpioWrite()
            prefer_pkgs = get_prefer_pkgs(opts.prefer_pkgs, arch,
                                          os.path.splitext(build_descr)[1],
                                          cpiodata)
            cpiodata.add(os.path.basename(build_descr.encode()), build_descr_data)
            build_descr_data = cpiodata.get()

        if opts.multibuild_package:
            package = package + ":" + opts.multibuild_package

        print(decode_it(get_buildinfo(apiurl,
                                    project, package, repository, arch,
                                    specfile=build_descr_data,
                                    debug=opts.debug,
                                    addlist=opts.extra_pkgs)))


    def do_buildconfig(self, subcmd, opts, *args):
        """${cmd_name}: Shows the build config

        Shows the build configuration which is used in building a package.
        This command is mostly used internally by the 'build' command.

        The returned data is the project-wide build configuration in a format
        which is directly readable by the build script. It contains RPM macros
        and BuildRequires expansions, for example.

        The argument REPOSITORY an be taken from the first column of the
        'osc repos' output.

        usage:
            osc buildconfig REPOSITORY                      (in pkg or prj dir)
            osc buildconfig PROJECT REPOSITORY
        ${cmd_option_list}
        """

        wd = os.curdir
        args = slash_split(args)

        if len(args) < 1 and (is_package_dir('.') or is_project_dir('.')):
            self.print_repos(True)

        if len(args) > 2:
            raise oscerr.WrongArgs('Too many arguments.')

        apiurl = self.get_api_url()

        if len(args) == 1:
            #FIXME: check if args[0] is really a repo and not a project, need a is_project() function for this
            project = store_read_project(wd)
            repository = args[0]
        elif len(args) == 2:
            project = args[0]
            repository = args[1]
        else:
            raise oscerr.WrongArgs('Wrong number of arguments.')

        print(decode_it(get_buildconfig(apiurl, project, repository)))


    def do_workerinfo(self, subcmd, opts, worker):
        """${cmd_name}: gets the information to a worker from the server

        Examples:
            osc workerinfo <workername>

        ${cmd_usage}
        ${cmd_option_list}
        """
        apiurl = self.get_api_url()
        print(''.join(get_worker_info(apiurl, worker)))


    @cmdln.option('', '--ignore-file', action='store_true',
                  help='ignore _constraints file and only check project constraints')
    def do_checkconstraints(self, subcmd, opts, *args):
        """${cmd_name}: check the constraints and view compliant workers

        Checks the constraints for compliant workers.

        usage:
            remote request:
                osc checkconstraints [OPTS] PROJECT PACKAGE REPOSITORY ARCH

            in a package working copy:
                osc checkconstraints [OPTS] REPOSITORY ARCH CONSTRAINTSFILE
                osc checkconstraints [OPTS] CONSTRAINTSFILE
                osc checkconstraints [OPTS]

        ${cmd_option_list}
        """
        repository = arch = constraintsfile = None
        args = slash_split(args)

        if len(args) == 4:
            project = args[0]
            package = args[1]
            repository = args[2]
            arch = args[3]
            opts.ignore_file = True
        else:
            project = store_read_project('.')
            package = store_read_package('.')

        if len(args) == 1:
            constraintsfile = args[0]
        elif len(args) == 2 or len(args) == 3:
            repository = args[0]
            arch = args[1]
            if len(args) == 3:
                constraintsfile = args[2]

        constraintsfile_data = None
        if constraintsfile is not None:
            constraintsfile_data = open(constraintsfile, 'r').read()
        elif not opts.ignore_file:
            if os.path.isfile("_constraints"):
                constraintsfile_data = open("_constraints", 'r').read()
            else:
                print("No local _constraints file. Using just the project constraints")

        apiurl = self.get_api_url()
        r = []
        if not arch and not repository:
            result_line_templ = '%(name)-25s %(arch)-25s %(comp_workers)s'
            for repo in get_repos_of_project(apiurl, project):
                rmap = {}
                rmap['name'] = repo.name
                rmap['arch'] = repo.arch
                workers = check_constraints(apiurl, project, repo.name, repo.arch, package, constraintsfile_data)
                rmap['comp_workers'] = len(workers)
                r.append(result_line_templ % rmap)
            r.insert(0, 'Repository                Arch                      Worker')
            r.insert(1, '----------                ----                      ------')
        else:
            r = check_constraints(apiurl, project, repository, arch, package, constraintsfile_data)
            r.insert(0, 'Worker')
            r.insert(1, '------')

        print('\n'.join(r))

    @cmdln.alias('repos')
    @cmdln.alias('platforms')
    def do_repositories(self, subcmd, opts, *args):
        """${cmd_name}: shows repositories configured for a project.
                        It skips repositories by default which are disabled for a given package.

        usage:
            osc repos
            osc repos [PROJECT] [PACKAGE]

        ${cmd_option_list}
        """

        apiurl = self.get_api_url()
        project = None
        package = None
        disabled = None

        if len(args) == 1:
            project = args[0]
        elif len(args) == 2:
            project = args[0]
            package = args[1]
        elif len(args) == 0:
            if is_package_dir('.'):
                package = store_read_package('.')
                project = store_read_project('.')
            elif is_project_dir('.'):
                project = store_read_project('.')
        else:
            raise oscerr.WrongArgs('Wrong number of arguments')

        if project is None:
            raise oscerr.WrongArgs('No project specified')

        if package is not None:
            disabled = show_package_disabled_repos(apiurl, project, package)

        if subcmd == 'repos_only':
            for repo in get_repositories_of_project(apiurl, project):
                if (disabled is None) or ((disabled is not None) and (repo not in [d['repo'] for d in disabled])):
                    print(repo)
        else:
            data = []
            for repo in get_repos_of_project(apiurl, project):
                if disabled is not None:
                    if ({'repo': repo.name, 'arch': repo.arch} in disabled
                        or repo.name in [d['repo'] for d in disabled if d['arch'] is None]
                        or repo.arch in [d['arch'] for d in disabled if d['repo'] is None]):
                            continue
                data += [repo.name, repo.arch]

            for row in build_table(2, data, width=2):
                print(row)


    def parse_repoarchdescr(self, args, noinit = False, alternative_project = None, ignore_descr = False, vm_type = None, multibuild_package = None):
        """helper to parse the repo, arch and build description from args"""
        import osc.build
        import glob
        import tempfile
        arg_arch = arg_repository = arg_descr = None
        if len(args) < 3:
            # some magic, works only sometimes, but people seem to like it :/
            all_archs = []
            for mainarch in osc.build.can_also_build:
                all_archs.append(mainarch)
                for subarch in osc.build.can_also_build.get(mainarch):
                    all_archs.append(subarch)
            for arg in args:
                if arg.endswith('.spec') or arg.endswith('.dsc') or arg.endswith('.kiwi') or arg.endswith('.livebuild') or arg == 'PKGBUILD' or arg == 'build.collax' or arg == 'Dockerfile' or arg == 'fissile.yml' or arg == 'appimage.yml':
                    arg_descr = arg
                else:
                    if (arg == osc.build.hostarch or arg in all_archs) and arg_arch is None:
                        # it seems to be an architecture in general
                        arg_arch = arg
                        if not (arg == osc.build.hostarch or arg in osc.build.can_also_build.get(osc.build.hostarch, [])):
                            if not (vm_type == 'qemu' or vm_type == 'emulator'):
                               print("WARNING: native compile is not possible, a emulator via binfmt misc handler must be configured!")
                    elif not arg_repository:
                        arg_repository = arg
                    else:
#                        raise oscerr.WrongArgs('\'%s\' is neither a build description nor a supported arch' % arg)
                        # take it as arch (even though this is no supported arch) - hopefully, this invalid
                        # arch will be detected below
                        arg_arch = arg
        else:
            arg_repository, arg_arch, arg_descr = args

        arg_arch = arg_arch or osc.build.hostarch

        repositories = []
        # store list of repos for potential offline use
        repolistfile = os.path.join(os.getcwd(), osc.core.store, "_build_repositories")
        if noinit:
            repositories = Repo.fromfile(repolistfile)
        else:
            project = alternative_project or store_read_project('.')
            apiurl = self.get_api_url()
            repositories = list(get_repos_of_project(apiurl, project))
            if not len(repositories):
                raise oscerr.WrongArgs('no repositories defined for project \'%s\'' % project)
            if alternative_project is None:
                # only persist our own repos
                Repo.tofile(repolistfile, repositories)

        no_repo = False
        repo_names = sorted(set([r.name for r in repositories]))
        if not arg_repository and repositories:
            # XXX: we should avoid hardcoding repository names
            # Use a default value from config, but just even if it's available
            # unless try standard, or openSUSE_Factory, or openSUSE_Tumbleweed
            no_repo = True
            arg_repository = repositories[-1].name
            for repository in (conf.config['build_repository'], 'standard', 'openSUSE_Factory', 'openSUSE_Tumbleweed'):
                if repository in repo_names:
                    arg_repository = repository
                    no_repo = False
                    break

        if not arg_repository:
            raise oscerr.WrongArgs('please specify a repository')
        if not noinit:
            if not arg_repository in repo_names:
                raise oscerr.WrongArgs('%s is not a valid repository, use one of: %s' % (arg_repository, ', '.join(repo_names)))
            arches = [r.arch for r in repositories if r.name == arg_repository and r.arch]
            if arches and not arg_arch in arches:
                raise oscerr.WrongArgs('%s is not a valid arch for the repository %s, use one of: %s' % (arg_arch, arg_repository, ', '.join(arches)))

        # can be implemented using
        # reduce(lambda x, y: x + y, (glob.glob(x) for x in ('*.spec', '*.dsc', '*.kiwi')))
        # but be a bit more readable :)
        descr = glob.glob('*.spec') + glob.glob('*.dsc') + glob.glob('*.kiwi') + glob.glob('*.livebuild') \
                + glob.glob('PKGBUILD') + glob.glob('build.collax') + glob.glob('Dockerfile') + glob.glob('fissile.yml') \
                + glob.glob('appimage.yml')

        # FIXME:
        # * request repos from server and select by build type.
        if not arg_descr and len(descr) == 1:
            arg_descr = descr[0]
        elif not arg_descr:
            msg = None
            if len(descr) > 1:
                if no_repo:
                    raise oscerr.WrongArgs("Repository is missing. Cannot guess build description without repository")
                apiurl = self.get_api_url()
                project = store_read_project('.')
                # some distros like Debian rename and move build to obs-build
                if not os.path.isfile('/usr/lib/build/queryconfig') and os.path.isfile('/usr/lib/obs-build/queryconfig'):
                    queryconfig = '/usr/lib/obs-build/queryconfig'
                else:
                    queryconfig = '/usr/lib/build/queryconfig'
                if noinit:
                    bc_filename = '_buildconfig-%s-%s' % (arg_repository, arg_arch)
                    if is_package_dir('.'):
                        bc_filename = os.path.join(os.getcwd(), osc.core.store, bc_filename)
                    else:
                        bc_filename = os.path.abspath(bc_filename)
                    if not os.path.isfile(bc_filename):
                        raise oscerr.WrongOptions('--offline is not possible, no local buildconfig file')
                    recipe = return_external(queryconfig, '--dist', bc_filename, 'type')
                else:
                    bc = get_buildconfig(apiurl, project, arg_repository)
                    with tempfile.NamedTemporaryFile() as f:
                        f.write(bc)
                        f.flush()
                        recipe = return_external(queryconfig, '--dist', f.name, 'type')
                recipe = recipe.strip()
                if recipe == 'arch':
                    recipe = 'PKGBUILD'
                recipe = decode_it(recipe)
                pac = os.path.basename(os.getcwd())
                if is_package_dir(os.getcwd()):
                    pac = store_read_package(os.getcwd())
                if multibuild_package:
                    pac = multibuild_package
                if recipe == 'PKGBUILD':
                    cands = [d for d in descr if d.startswith(recipe)]
                else:
                    cands = [d for d in descr if d.endswith('.' + recipe)]
                if len(cands) > 1:
                    repo_cands = [d for d in cands if d == '%s-%s.%s' % (pac, arg_repository, recipe)]
                    if repo_cands:
                        cands = repo_cands
                    else:
                        pac_cands = [d for d in cands if d == '%s.%s' % (pac, recipe)]
                        if pac_cands:
                            cands = pac_cands
                if len(cands) == 1:
                    arg_descr = cands[0]
                if not arg_descr:
                    msg = 'Multiple build description files found: %s' % ', '.join(cands)
            elif not ignore_descr:
                msg = 'Missing argument: build description (for example a spec, dsc or kiwi file)'
                try:
                    p = Package('.')
                    if p.islink() and not p.isexpanded():
                        msg += ' (this package is not expanded - you might want to try osc up --expand)'
                except:
                    pass
            if msg:
                raise oscerr.WrongArgs(msg)

        return arg_repository, arg_arch, arg_descr


    @cmdln.option('--clean', action='store_true',
                  help='Delete old build root before initializing it')
    @cmdln.option('-o', '--offline', action='store_true',
                  help='Start with cached prjconf and packages without contacting the api server')
    @cmdln.option('-l', '--preload', action='store_true',
                  help='Preload all files into the cache for offline operation')
    @cmdln.option('--no-changelog', action='store_true',
                  help='don\'t update the package changelog from a changes file')
    @cmdln.option('--rsync-src', metavar='RSYNCSRCPATH', dest='rsyncsrc',
                  help='Copy folder to buildroot after installing all RPMs. Use together with --rsync-dest. This is the path on the HOST filesystem e.g. /tmp/linux-kernel-tree. It defines RSYNCDONE 1 .')
    @cmdln.option('--rsync-dest', metavar='RSYNCDESTPATH', dest='rsyncdest',
                  help='Copy folder to buildroot after installing all RPMs. Use together with --rsync-src. This is the path on the TARGET filesystem e.g. /usr/src/packages/BUILD/linux-2.6 .')
    @cmdln.option('--overlay', metavar='OVERLAY',
                  help='Copy overlay filesystem to buildroot after installing all RPMs .')
    @cmdln.option('--noinit', '--no-init', action='store_true',
                  help='Skip initialization of build root and start with build immediately.')
    @cmdln.option('--nochecks', '--no-checks', action='store_true',
                  help='Do not run build checks on the resulting packages.')
    @cmdln.option('--no-verify', '--noverify', action='store_true',
                  help='Skip signature verification (via pgp keys) of packages used for build. (Global config in oscrc: no_verify)')
    @cmdln.option('--nodebugpackages', '--no-debug-packages', action='store_true',
                  help='Skip installation of additional debug packages for CLI builds')
    @cmdln.option('--noservice', '--no-service', action='store_true',
                  help='Skip run of local source services as specified in _service file.')
    @cmdln.option('-p', '--prefer-pkgs', metavar='DIR', action='append',
                  help='Prefer packages from this directory when installing the build-root')
    @cmdln.option('-k', '--keep-pkgs', metavar='DIR',
                  help='Save built packages into this directory')
    @cmdln.option('-M', '--multibuild-package', metavar='MPAC',
                  help='Build the specified multibuild package')
    @cmdln.option('-x', '--extra-pkgs', metavar='PAC', action='append',
                  help='Add this package when installing the build-root')
    @cmdln.option('--root', metavar='ROOT',
                  help='Build in specified directory')
    @cmdln.option('-j', '--jobs', metavar='N',
                  help='Compile with N jobs')
    @cmdln.option('-t', '--threads', metavar='N',
                  help='Compile with N threads')
    @cmdln.option('--icecream', metavar='N',
                  help='use N parallel build jobs with icecream')
    @cmdln.option('--ccache', action='store_true',
                  help='use ccache to speed up rebuilds')
    @cmdln.option('--with', metavar='X', dest='_with', action='append',
                  help='enable feature X for build')
    @cmdln.option('--without', metavar='X', action='append',
                  help='disable feature X for build')
    @cmdln.option('--define', metavar='\'X Y\'', action='append',
                  help='define macro X with value Y')
    @cmdln.option('--build-opt', metavar='OPT', action='append',
                  help='pass option OPT to the build command')
    @cmdln.option('--userootforbuild', '--login-as-root', action='store_true',
                  help='Run build or shell as root. The default is to build as '
                  'unprivileged user. Note that a line "# norootforbuild" '
                  'in the spec file will invalidate this option.')
    @cmdln.option('--build-uid', metavar='uid:gid|"caller"',
                  help='specify the numeric uid:gid pair to assign to the '
                  'unprivileged "abuild" user or use "caller" to use the current user uid:gid')
    @cmdln.option('--local-package', action='store_true',
                  help='build a package which does not exist on the server')
    @cmdln.option('--linksources', action='store_true',
                  help='use hard links instead of a deep copied source')
    @cmdln.option('--vm-memory', metavar='MEMORY',
                  help='amount of memory for VM defined in MB')
    @cmdln.option('--vm-disk-size', metavar='DISKSIZE',
                  help='size for newly created disk image in MB')
    @cmdln.option('--vm-type', metavar='TYPE',
                  help='use VM type TYPE (e.g. kvm)')
    @cmdln.option('--vm-telnet', metavar='TELNET',
                  help='Launch a telnet server inside of VM build')
    @cmdln.option('--target', metavar='TARGET',
                  help='define target platform')
    @cmdln.option('--alternative-project', metavar='PROJECT',
                  help='specify the build target project')
    @cmdln.option('-d', '--debuginfo', action='store_true',
                  help='also build debuginfo sub-packages')
    @cmdln.option('--disable-debuginfo', action='store_true',
                  help='disable build of debuginfo packages')
    @cmdln.option('-b', '--baselibs', action='store_true',
                  help='Create -32bit/-64bit/-x86 rpms for other architectures')
    @cmdln.option('--release', metavar='N',
                  help='set release number of the package to N')
    @cmdln.option('--disable-cpio-bulk-download', action='store_true',
                  help='disable downloading packages as cpio archive from api')
    @cmdln.option('--cpio-bulk-download', action='store_false',
                  dest='disable_cpio_bulk_download', help=SUPPRESS_HELP)
    @cmdln.option('--download-api-only', action='store_true',
                  help='only fetch packages from the api')
    @cmdln.option('--oldpackages', metavar='DIR',
            help='take previous build from DIR (special values: _self, _link)')
    @cmdln.option('--wipe', action='store_true',
                  help=SUPPRESS_HELP)
    @cmdln.option('--shell', action='store_true',
                  help=SUPPRESS_HELP)
    @cmdln.option('--shell-cmd', metavar='COMMAND',
                  help='run specified command instead of bash')
    @cmdln.option('-f', '--force', action='store_true',
                  help='Do not ask for confirmation to wipe')
    @cmdln.option('--host', metavar='HOST',
            help='perform the build on a remote server - user@server:~/remote/directory')
    @cmdln.option('--trust-all-projects', action='store_true',
                  help='trust packages from all projects')
    @cmdln.option('--nopreinstallimage', '--no-preinstallimage', action='store_true',
                  help='Do not use preinstall images for creating the build root.')
    @cmdln.alias('chroot')
    @cmdln.alias('shell')
    @cmdln.alias('wipe')
    def do_build(self, subcmd, opts, *args):
        """${cmd_name}: Build a package on your local machine

        You need to call the command inside a package directory, which should be a
        buildsystem checkout. (Local modifications are fine.)

        The arguments REPOSITORY and ARCH can be taken from the first two columns
        of the 'osc repos' output. BUILD_DESCR is either a RPM spec file, or a
        Debian dsc file.

        The command honors packagecachedir, build-root and build-uid
        settings in oscrc, if present. You may want to set su-wrapper = 'sudo'
        in oscrc, and configure sudo with option NOPASSWD for /usr/bin/build.

        If neither --clean nor --noinit is given, build will reuse an existing
        build-root again, removing unneeded packages and add missing ones. This
        is usually the fastest option.

        If the package doesn't exist on the server please use the --local-package
        option.
        If the project of the package doesn't exist on the server please use the
        --alternative-project <alternative-project> option:
        Example:
            osc build [OPTS] --alternative-project openSUSE:10.3 standard i586 BUILD_DESCR

        usage:
            osc build [OPTS]                      # will try to guess a build environement
            osc build [OPTS] REPOSITORY ARCH BUILD_DESCR
            osc build [OPTS] REPOSITORY ARCH
            osc build [OPTS] REPOSITORY (ARCH = hostarch, BUILD_DESCR is detected automatically)
            osc build [OPTS] ARCH (REPOSITORY = build_repository (config option), BUILD_DESCR is detected automatically)
            osc build [OPTS] BUILD_DESCR (REPOSITORY = build_repository (config option), ARCH = hostarch)
            osc build [OPTS] (REPOSITORY = build_repository (config option), ARCH = hostarch, BUILD_DESCR is detected automatically)

        For debugging purposes you can run after a build the following to jump inside of of
        the build environemnt:

            osc shell [OPTS] REPOSITORY ARCH

        OPTS may be

            --noinit             # for faster run
            --shell-cmd=COMMAND

        To clean up the build environment run

            osc wipe [OPTS]
            osc wipe [OPTS] REPOSITORY ARCH

        You may set the used VM type in oscrc already, but you can also overwrite it for example
        with

            --vm-type=chroot     # for faster, but uncleaner and unsecure build
            --vm-type=kvm        # for clean and secure build
            --vm-type=qemu       # for slow cross architecture build using system emulator

        # Note:
        # Configuration can be overridden by envvars, e.g.
        # OSC_SU_WRAPPER overrides the setting of su-wrapper.
        # OSC_BUILD_ROOT overrides the setting of build-root.
        # OSC_PACKAGECACHEDIR overrides the setting of packagecachedir.

        ${cmd_option_list}
        """

        import osc.build

        if which(conf.config['build-cmd']) is None:
            print('Error: build (\'%s\') command not found' % conf.config['build-cmd'], file=sys.stderr)
            print('Install the build package from http://download.opensuse.org/repositories/openSUSE:/Tools/', file=sys.stderr)
            return 1

        if opts.debuginfo and opts.disable_debuginfo:
            raise oscerr.WrongOptions('osc: --debuginfo and --disable-debuginfo are mutual exclusive')

        if subcmd == 'wipe':
            opts.wipe = True

        if len(args) > 3:
            raise oscerr.WrongArgs('Too many arguments')

        project = None
        try:
            project = store_read_project(os.curdir)
        except oscerr.NoWorkingCopy:
            pass
        if project == opts.alternative_project:
            opts.alternative_project = None

        if len(args) == 0 and is_package_dir(os.curdir):
            # build env not specified, just read from last build attempt
            lastbuildroot = store_read_last_buildroot(os.curdir)
            if lastbuildroot:
               args = [ lastbuildroot[0], lastbuildroot[1] ]
               if not opts.vm_type:
                  opts.vm_type = lastbuildroot[2]

        vm_chroot = opts.vm_type or conf.config['build-type']
        if (subcmd in ('shell', 'chroot') or opts.shell or opts.wipe) and not vm_chroot:
            if opts.root:
                build_root = opts.root
            else:
                args = self.parse_repoarchdescr(args, opts.noinit or opts.offline, opts.alternative_project, False, opts.vm_type, opts.multibuild_package)
                repo, arch, build_descr = args
                prj, pac = osc.build.calculate_prj_pac(opts, build_descr)
                apihost = urlsplit(self.get_api_url())[1]
                build_root = osc.build.calculate_build_root(apihost, prj, pac, repo,
                                                    arch)
            if opts.wipe and not opts.force:
                    # Confirm delete
                    print("Really wipe '%s'? [y/N]: " % build_root)
                    choice = raw_input().lower()
                    if choice != 'y':
                        print('Aborting')
                        sys.exit(0)
            build_args = ['--root=' + build_root, '--noinit', '--shell']
            if opts.wipe:
                build_args.append('--wipe')
            sys.exit(osc.build.run_build(opts, *build_args))
        elif subcmd in ('shell', 'chroot') or opts.shell:
            print('--shell in combination with build-type %s is experimental.' % vm_chroot)
            print('The semantics may change at any time!')
            opts.shell = True

        args = self.parse_repoarchdescr(args, opts.noinit or opts.offline, opts.alternative_project, False, opts.vm_type, opts.multibuild_package)

        if not opts.local_package:
            try:
                package = store_read_package(os.curdir)
                prj = Project(os.pardir, getPackageList=False, wc_check=False)
                if prj.status(package) == 'A':
                    # a package with state 'A' most likely does not exist on
                    # the server - hence, treat it as a local package
                    opts.local_package = True
            except oscerr.NoWorkingCopy:
                pass

        if conf.config['no_verify']:
            opts.no_verify = True

        if opts.keep_pkgs and not os.path.isdir(opts.keep_pkgs):
            if os.path.exists(opts.keep_pkgs):
                raise oscerr.WrongOptions('Preferred save location \'%s\' is not a directory' % opts.keep_pkgs)
            else:
                os.makedirs(opts.keep_pkgs)

        if opts.prefer_pkgs:
            for d in opts.prefer_pkgs:
                if not os.path.isdir(d):
                    raise oscerr.WrongOptions('Preferred package location \'%s\' is not a directory' % d)

        if opts.offline and opts.preload:
            raise oscerr.WrongOptions('--offline and --preload are mutually exclusive')

        if opts.shell or opts.wipe:
            opts.noservice = True

        if opts.preload:
            opts.nopreinstallimage = True

        print('Building %s for %s/%s' % (args[2], args[0], args[1]))
        if not opts.host:
            return osc.build.main(self.get_api_url(), opts, args)
        else:
            return self._do_rbuild(subcmd, opts, *args)

    def _do_rbuild(self, subcmd, opts, *args):

        # drop the --argument, value tuple from the list
        def drop_arg2(lst, name):
            if not name:
                return lst
            while name in lst:
                i = lst.index(name)
                lst.pop(i+1)
                lst.pop(i)
            return lst

        # change the local directory to more suitable remote one in hostargs
        # and perform the rsync to such location as well
        def rsync_dirs_2host(hostargs, short_name, long_name, dirs):

            drop_arg2(hostargs, short_name)
            drop_arg2(hostargs, long_name)

            for pdir in dirs:
                # drop the last '/' from pdir name - this is because
                # rsync foo  remote:/bar create /bar/foo on remote machine
                # rsync foo/ remote:/bar copy the content of foo in the /bar
                if pdir[-1:] == os.path.sep:
                    pdir = pdir[:-1]

                hostprefer = os.path.join(
                        hostpath,
                        basename,
                        "%s__" % (long_name.replace('-', '_')),
                        os.path.basename(os.path.abspath(pdir)))
                hostargs.append(long_name)
                hostargs.append(hostprefer)

                rsync_prefer_cmd = ['rsync', '-az', '--delete', '-e', 'ssh',
                        pdir,
                        "%s:%s" % (hostname, os.path.dirname(hostprefer))]
                print('Run: %s' % " ".join(rsync_prefer_cmd))
                ret = run_external(rsync_prefer_cmd[0], *rsync_prefer_cmd[1:])
                if ret != 0:
                    return ret

            return 0


        cwd = os.getcwd()
        basename = os.path.basename(cwd)
        if not ':' in opts.host:
            hostname = opts.host
            hostpath = "~/"
        else:
            hostname, hostpath = opts.host.split(':', 1)

        # arguments for build: use all arguments behind build and drop --host 'HOST'
        hostargs = sys.argv[sys.argv.index(subcmd)+1:]
        drop_arg2(hostargs, '--host')

        # global arguments: use first '-' up to subcmd
        gi = 0
        for i, a in enumerate(sys.argv):
            if a == subcmd:
                break
            if a[0] == '-':
                gi = i
                break

        if gi:
            hostglobalargs = sys.argv[gi : sys.argv.index(subcmd)+1]
        else:
            hostglobalargs = (subcmd, )

        # keep-pkgs
        hostkeep = None
        if opts.keep_pkgs:
            drop_arg2(hostargs, '-k')
            drop_arg2(hostargs, '--keep-pkgs')
            hostkeep = os.path.join(
                    hostpath,
                    basename,
                    "__keep_pkgs__",
                    "")   # <--- this adds last '/', thus triggers correct rsync behavior
            hostargs.append('--keep-pkgs')
            hostargs.append(hostkeep)

        ### run all commands ###
        # 1.) rsync sources
        rsync_source_cmd = ['rsync', '-az', '--delete', '-e', 'ssh', cwd, "%s:%s" % (hostname, hostpath)]
        print('Run: %s' % " ".join(rsync_source_cmd))
        ret = run_external(rsync_source_cmd[0], *rsync_source_cmd[1:])
        if ret != 0:
            return ret

        # 2.) rsync prefer-pkgs dirs, overlay and rsyns-src
        if opts.prefer_pkgs:
            ret = rsync_dirs_2host(hostargs, '-p', '--prefer-pkgs', opts.prefer_pkgs)
            if ret != 0:
                return ret

        for arg, long_name in ((opts.rsyncsrc, '--rsync-src'), (opts.overlay, '--overlay')):
            if not arg:
                continue
            ret = rsync_dirs_2host(hostargs, None, long_name, (arg, ))
            if ret != 0:
                return ret

        # 3.) call osc build
        osc_cmd = "osc"
        for var in ('OSC_SU_WRAPPER', 'OSC_BUILD_ROOT', 'OSC_PACKAGECACHEDIR'):
            if os.getenv(var):
                osc_cmd = "%s=%s %s" % (var, os.getenv(var), osc_cmd)

        ssh_cmd = \
            ['ssh', '-t', hostname,
            "cd %(remote_dir)s; %(osc_cmd)s %(global_args)s %(local_args)s" % dict(
            remote_dir = os.path.join(hostpath, basename),
            osc_cmd = osc_cmd,
            global_args = " ".join(hostglobalargs),
            local_args = " ".join(hostargs))
            ]
        print('Run: %s' % " ".join(ssh_cmd))
        build_ret = run_external(ssh_cmd[0], *ssh_cmd[1:])
        if build_ret != 0:
            return build_ret

        # 4.) get keep-pkgs back
        if opts.keep_pkgs:
            ret = rsync_keep_cmd = ['rsync', '-az', '-e', 'ssh', "%s:%s" % (hostname, hostkeep), opts.keep_pkgs]
            print('Run: %s' % " ".join(rsync_keep_cmd))
            ret = run_external(rsync_keep_cmd[0], *rsync_keep_cmd[1:])
            if ret != 0:
                return ret

        return build_ret


    @cmdln.option('', '--csv', action='store_true',
                        help='generate output in CSV (separated by |)')
    @cmdln.option('-l', '--limit', metavar='limit',
                        help='for setting the number of results')
    @cmdln.option('-M', '--multibuild-package', metavar= 'MPAC',
                        help='Show the buildhistory of the specified multibuild package')
    @cmdln.alias('buildhist')
    def do_buildhistory(self, subcmd, opts, *args):
        """${cmd_name}: Shows the build history of a package

        The arguments REPOSITORY and ARCH can be taken from the first two columns
        of the 'osc repos' output.

        usage:
           osc buildhist REPOSITORY ARCHITECTURE
           osc buildhist PROJECT PACKAGE REPOSITORY ARCHITECTURE
        ${cmd_option_list}
        """

        args = slash_split(args)

        if len(args) < 2 and is_package_dir('.'):
            self.print_repos()

        apiurl = self.get_api_url()

        if len(args) == 4:
            project = args[0]
            package = args[1]
            repository = args[2]
            arch = args[3]
        elif len(args) == 2:
            wd = os.curdir
            package = store_read_package(wd)
            project = store_read_project(wd)
            repository = args[0]
            arch = args[1]
        else:
            raise oscerr.WrongArgs('Wrong number of arguments')

        if opts.multibuild_package:
            package = package + ":" + opts.multibuild_package

        format = 'text'
        if opts.csv:
            format = 'csv'

        print('\n'.join(get_buildhistory(apiurl, project, package, repository, arch, format, opts.limit)))

    @cmdln.option('', '--csv', action='store_true',
                        help='generate output in CSV (separated by |)')
    @cmdln.option('-l', '--limit', metavar='limit',
                        help='for setting the number of results')
    @cmdln.option('-M', '--multibuild-package', metavar='MPAC',
                        help='get jobhistory for the specified multibuild package')
    @cmdln.alias('jobhist')
    def do_jobhistory(self, subcmd, opts, *args):
        """${cmd_name}: Shows the job history of a project

        The arguments REPOSITORY and ARCH can be taken from the first two columns
        of the 'osc repos' output.

        usage:
           osc jobhist REPOSITORY ARCHITECTURE  (in project dir)
           osc jobhist PROJECT [PACKAGE] REPOSITORY ARCHITECTURE
        ${cmd_option_list}
        """
        wd = os.curdir
        args = slash_split(args)

        if len(args) < 2 and (is_project_dir('.') or is_package_dir('.')):
            self.print_repos()

        apiurl = self.get_api_url()

        if len(args) == 4:
            project = args[0]
            package = args[1]
            repository = args[2]
            arch = args[3]
        elif len(args) == 3:
            project = args[0]
            package = None        # skipped = prj
            repository = args[1]
            arch = args[2]
        elif len(args) == 2:
            package = None
            try:
                package = store_read_package(wd)
            except:
                pass
            project = store_read_project(wd)
            repository = args[0]
            arch = args[1]
        else:
            raise oscerr.WrongArgs('Wrong number of arguments')

        if opts.multibuild_package and package is not None:
            package = package + ":" + opts.multibuild_package

        format = 'text'
        if opts.csv:
            format = 'csv'

        print_jobhistory(apiurl, project, package, repository, arch, format, opts.limit)

    @cmdln.hide(1)
    def do_rlog(self, subcmd, opts, *args):
        """${cmd_name}:

        Obsolete command to show commit logs. Use 'log' now.

        See the help output of 'log'.
        """

        print("This command is obsolete. Use 'osc log'.", file=sys.stderr)
        print("See 'osc help log'.", file=sys.stderr)
        return 2


    @cmdln.option('-r', '--revision', metavar='rev',
                        help='show log of the specified revision')
    @cmdln.option('', '--csv', action='store_true',
                        help='generate output in CSV (separated by |)')
    @cmdln.option('', '--xml', action='store_true',
                        help='generate output in XML')
    @cmdln.option('-D', '--deleted', action='store_true',
                        help='work on deleted package')
    @cmdln.option('-M', '--meta', action='store_true',
                        help='checkout out meta data instead of sources' )
    def do_log(self, subcmd, opts, *args):
        """${cmd_name}: Shows the commit log of a package

        Usage:
            osc log (inside working copy)
            osc log remote_project [remote_package]

        ${cmd_option_list}
        """

        args = slash_split(args)
        apiurl = self.get_api_url()

        if len(args) == 0:
            wd = os.curdir
            if is_project_dir(wd) or is_package_dir(wd):
                project = store_read_project(wd)
                if is_project_dir(wd):
                    package = "_project"
                else:
                    package = store_read_package(wd)
            else:
                raise oscerr.NoWorkingCopy("Error: \"%s\" is not an osc working copy." % os.path.abspath(wd))
        elif len(args) < 1:
            raise oscerr.WrongArgs('Too few arguments (required none or two)')
        elif len(args) > 2:
            raise oscerr.WrongArgs('Too many arguments (required none or two)')
        elif len(args) == 1:
            project = args[0]
            package = "_project"
        else:
            project = args[0]
            package = args[1]

        rev, rev_upper = parseRevisionOption(opts.revision)
        if rev and not checkRevision(project, package, rev, apiurl, opts.meta):
            print('Revision \'%s\' does not exist' % rev, file=sys.stderr)
            sys.exit(1)

        format = 'text'
        if opts.csv:
            format = 'csv'
        if opts.xml:
            format = 'xml'

        log = '\n'.join(get_commitlog(apiurl, project, package, rev, format, opts.meta, opts.deleted, rev_upper))
        run_pager(log)

    def do_service(self, subcmd, opts, *args):
        """${cmd_name}: Handle source services

        Source services can be used to modify sources like downloading files,
        verify files, generating files or modify existing files.

        usage:
            osc service COMMAND (inside working copy)
            osc service run [SOURCE_SERVICE]
            osc service runall
            osc service localrun
            osc service disabledrun
            osc service remoterun [PROJECT PACKAGE]
            osc service merge [PROJECT PACKAGE]
            osc service wait [PROJECT PACKAGE]

            COMMAND can be:
            run         r  run defined services locally, it takes an optional parameter to run only a
                           specified source service. In case parameters exist for this one in _service file
                           they are used.
            runall      ra run all services independent of the used mode
            localrun    lr run all services except the ones with mode "buildtime", "disabled", or
                           "serveronly" (deprecated)
            disabledrun dr run all services with mode "disabled" or "serveronly" (deprecated)
            remoterun   rr trigger a re-run on the server side
            merge          commits all server side generated files and drops the _service definition
            wait           waits until the service finishes and returns with an error if it failed

        ${cmd_option_list}
        """
        # disabledrun and localrun exists as well, but are considered to be obsolete

        args = slash_split(args)
        project = package = singleservice = mode = None
        apiurl = self.get_api_url()

        if len(args) < 1:
            raise oscerr.WrongArgs('No command given.')
        elif len(args) < 3:
            if is_package_dir(os.curdir):
                project = store_read_project(os.curdir)
                package = store_read_package(os.curdir)
            else:
                raise oscerr.WrongArgs('Too few arguments.')
            if len(args) == 2:
                singleservice = args[1]
        elif len(args) == 3 and args[0] in ('remoterun', 'rr', 'merge', 'wait'):
            project = args[1]
            package = args[2]
        else:
            raise oscerr.WrongArgs('Too many arguments.')

        command = args[0]

        if not (command in ( 'runall', 'ra', 'run', 'localrun', 'disabledrun', 'remoterun', 'lr', 'dr', 'r', 'rr', 'merge', 'wait' )):
            raise oscerr.WrongArgs('Wrong command given.')

        if command == "remoterun" or command == "rr":
            print(runservice(apiurl, project, package))
            return

        if command == "wait":
            print(waitservice(apiurl, project, package))
            return

        if command == "merge":
            print(mergeservice(apiurl, project, package))
            return

        if command in ('runall', 'ra', 'run', 'localrun', 'disabledrun', 'lr', 'dr', 'r'):
            if not is_package_dir(os.curdir):
                raise oscerr.WrongArgs('Local directory is no package')
            p = Package(".")
            if command == "localrun" or command == "lr":
                mode = "local"
            elif command == "disabledrun" or command == "dr":
                mode = "disabled"
            elif command == "runall" or command == "ra":
                mode = "all"

        return p.run_source_services(mode, singleservice)

    @cmdln.option('-a', '--arch', metavar='ARCH',
                        help='trigger rebuilds for a specific architecture')
    @cmdln.option('-r', '--repo', metavar='REPO',
                        help='trigger rebuilds for a specific repository')
    @cmdln.option('-f', '--failed', action='store_true',
                  help='rebuild all failed packages')
    @cmdln.option('-M', '--multibuild-package', action='append',
                  help='rebuild specified multibuild package')
    @cmdln.option('--all', action='store_true',
                        help='Rebuild all packages of entire project')
    @cmdln.alias('rebuildpac')
    def do_rebuild(self, subcmd, opts, *args):
        """${cmd_name}: Trigger package rebuilds

        Note that it is normally NOT needed to kick off rebuilds like this, because
        they principally happen in a fully automatic way, triggered by source
        check-ins. In particular, the order in which packages are built is handled
        by the build service.

        The arguments REPOSITORY and ARCH can be taken from the first two columns
        of the 'osc repos' output.

        usage:
            osc rebuild [PROJECT [PACKAGE [REPOSITORY [ARCH]]]]
        ${cmd_option_list}
        """

        args = slash_split(args)

        package = repo = arch = code = None
        apiurl = self.get_api_url()

        if opts.repo:
            repo = opts.repo

        if opts.arch:
            arch = opts.arch

        if len(args) < 1:
            if is_package_dir(os.curdir):
                project = store_read_project(os.curdir)
                package = store_read_package(os.curdir)
                apiurl = store_read_apiurl(os.curdir)
            elif is_project_dir(os.curdir):
                project = store_read_project(os.curdir)
                apiurl = store_read_apiurl(os.curdir)
            else:
                raise oscerr.WrongArgs('Too few arguments.')
        else:
            project = args[0]
            if len(args) > 1:
                package = args[1]

        if len(args) > 2:
            repo = args[2]
        if len(args) > 3:
            arch = args[3]

        if opts.failed:
            code = 'failed'

        if not (opts.all or package or repo or arch or code):
            raise oscerr.WrongOptions('No option has been provided. If you want to rebuild all packages of the entire project, use --all option.')

        packages = []
        if opts.multibuild_package:
            for subpackage in opts.multibuild_package:
                packages.append(package + ":" + subpackage)
        else:
            packages.append(package)

        for package in packages:
            print(rebuild(apiurl, project, package, repo, arch, code))


    def do_info(self, subcmd, opts, *args):
        """${cmd_name}: Print information about a working copy

        Print information about each ARG (default: '.')
        ARG is a working-copy path.

        ${cmd_usage}
        ${cmd_option_list}
        """

        args = parseargs(args)
        pacs = findpacs(args)

        for p in pacs:
            print(p.info())


    @cmdln.option('-M', '--multibuild-package', action='append',
                        help='specify a specific multibuild flavor')
    def do_sendsysrq(self, subcmd, opts, *args):
        """${cmd_name}: trigger a sysrq in a running build

        This is only going to work when the build is running in a supported VM.
        Also only a subset of sysrq are supported. Typical use case for debugging
        are 9, t and w in this sequence.

        usage:
            osc sendsysrq REPOSITORY ARCH SYSRQ
            osc sendsysrq PROJECT PACKAGE REPOSITORY ARCH SYSRQ
        ${cmd_option_list}
        """
        args = slash_split(args)

        project = package = repo = arch = sysrq = None
        apiurl = self.get_api_url()

        if len(args) < 4:
            if is_package_dir(os.curdir):
                project = store_read_project(os.curdir)
                package = store_read_package(os.curdir)
                apiurl = store_read_apiurl(os.curdir)
                repo = args[0]
                arch = args[1]
                sysrq = args[2]
            else:
                raise oscerr.WrongArgs('Too few arguments.')
        elif len(args) != 5:
            raise oscerr.WrongArgs('Wrong number of arguments.')
        else:
            project = args[0]
            package = args[1]
            repo = args[2]
            arch = args[3]
            sysrq = args[4]

        packages = [package]
        if opts.multibuild_package:
            packages = ['%s:%s' % (package, flavor) for flavor in opts.multibuild_package]
        for package in packages:
            print(cmdbuild(apiurl, 'sendsysrq', project, package, arch, repo, None, sysrq))

    @cmdln.option('-a', '--arch', metavar='ARCH',
                        help='Restart builds for a specific architecture')
    @cmdln.option('-M', '--multibuild-package', action='append',
                        help='Restart builds for specified multibuild package')
    @cmdln.option('-r', '--repo', metavar='REPO',
                        help='Restart builds for a specific repository')
    @cmdln.option('--all', action='store_true',
                        help='Restart all running builds of entire project')
    @cmdln.alias('abortbuild')
    def do_restartbuild(self, subcmd, opts, *args):
        """${cmd_name}: Restart the build of a certain project or package

        usage:
            osc restartbuild [PROJECT [PACKAGE [REPOSITORY [ARCH]]]]
        ${cmd_option_list}
        """
        args = slash_split(args)

        package = repo = arch = code = None
        apiurl = self.get_api_url()

        if opts.repo:
            repo = opts.repo

        if opts.arch:
            arch = opts.arch

        if len(args) < 1:
            if is_package_dir(os.curdir):
                project = store_read_project(os.curdir)
                package = store_read_package(os.curdir)
                apiurl = store_read_apiurl(os.curdir)
            elif is_project_dir(os.curdir):
                project = store_read_project(os.curdir)
                apiurl = store_read_apiurl(os.curdir)
            else:
                raise oscerr.WrongArgs('Too few arguments.')
        else:
            project = args[0]
            if len(args) > 1:
                package = args[1]

        if len(args) > 2:
            repo = args[2]
        if len(args) > 3:
            arch = args[3]

        if not (opts.all or package or repo or arch):
            raise oscerr.WrongOptions('No option has been provided. If you want to restart all packages of the entire project, use --all option.')

        packages = []
        if opts.multibuild_package:
            for subpackage in opts.multibuild_package:
                packages.append(package + ":" + subpackage)
        else:
            packages.append(package)

        for package in packages:
            print(cmdbuild(apiurl, subcmd, project, package, arch, repo))


    @cmdln.option('-a', '--arch', metavar='ARCH',
                        help='Delete all binary packages for a specific architecture')
    @cmdln.option('-M', '--multibuild-package', action='append',
                        help='Delete all binary packages for specified multibuild package')
    @cmdln.option('-r', '--repo', metavar='REPO',
                        help='Delete all binary packages for a specific repository')
    @cmdln.option('--build-disabled', action='store_true',
                        help='Delete all binaries of packages for which the build is disabled')
    @cmdln.option('--build-failed', action='store_true',
                        help='Delete all binaries of packages for which the build failed')
    @cmdln.option('--broken', action='store_true',
                        help='Delete all binaries of packages for which the package source is bad')
    @cmdln.option('--unresolvable', action='store_true',
                        help='Delete all binaries of packages which have dependency errors')
    @cmdln.option('--all', action='store_true',
                        help='Delete all binaries regardless of the package status (previously default)')
    @cmdln.alias("unpublish")
    def do_wipebinaries(self, subcmd, opts, *args):
        """${cmd_name}: Delete all binary packages of a certain project/package

        With the optional argument <package> you can specify a certain package
        otherwise all binary packages in the project will be deleted.

        usage:
            osc wipebinaries OPTS                       # works in checked out project dir
            osc wipebinaries OPTS PROJECT [PACKAGE]
            osc unpublish OPTS                       # works in checked out project dir
            osc unpublish OPTS PROJECT [PACKAGE]
        ${cmd_option_list}
        """

        args = slash_split(args)

        package = project = None
        apiurl = self.get_api_url()

        # try to get project and package from checked out dirs
        if len(args) < 1:
            if is_project_dir(os.getcwd()):
                project = store_read_project(os.curdir)
            if is_package_dir(os.getcwd()):
                project = store_read_project(os.curdir)
                package = store_read_package(os.curdir)
            if project is  None:
                raise oscerr.WrongArgs('Missing <project> argument.')
        if len(args) > 2:
            raise oscerr.WrongArgs('Wrong number of arguments.')

        # respect given project and package
        if len(args) >= 1:
            project = args[0]

        if len(args) == 2:
            package = args[1]

        codes = []
        if opts.build_disabled:
            codes.append('disabled')
        if opts.build_failed:
            codes.append('failed')
        if opts.broken:
            codes.append('broken')
        if opts.unresolvable:
            codes.append('unresolvable')
        if len(codes) == 0:
            # don't do a second wipe if a filter got specified
            if opts.all or opts.repo or opts.arch:
                codes.append(None)

        if len(codes) == 0:
            raise oscerr.WrongOptions('No option has been provided. If you want to delete all binaries, use --all option.')

        packages = []
        if opts.multibuild_package:
            for subpackage in opts.multibuild_package:
                packages.append(package + ":" + subpackage)
        else:
            packages.append(package)

        # make a new request for each code= parameter and for each package in packages
        for package in packages:
            for code in codes:
                if subcmd == 'unpublish':
                    print(unpublish(apiurl, project, package, opts.arch, opts.repo, code))
                else:
                    print(wipebinaries(apiurl, project, package, opts.arch, opts.repo, code))


    @cmdln.option('-q', '--quiet', action='store_true',
                  help='do not show downloading progress')
    @cmdln.option('-d', '--destdir', default='./binaries', metavar='DIR',
                  help='destination directory')
    @cmdln.option('-M', '--multibuild-package', action='append',
                  help='get binaries from specified multibuild package')
    @cmdln.option('--sources', action="store_true",
                  help='also fetch source packages')
    @cmdln.option('--debug', action="store_true",
                  help='also fetch debug packages')
    def do_getbinaries(self, subcmd, opts, *args):
        """${cmd_name}: Download binaries to a local directory

        This command downloads packages directly from the api server.
        Thus, it directly accesses the packages that are used for building
        others even when they are not "published" yet.

        usage:
           osc getbinaries REPOSITORY                                 # works in checked out project/package (check out all archs in subdirs)
           osc getbinaries REPOSITORY ARCHITECTURE                    # works in checked out project/package
           osc getbinaries PROJECT REPOSITORY ARCHITECTURE
           osc getbinaries PROJECT PACKAGE REPOSITORY ARCHITECTURE
           osc getbinaries PROJECT PACKAGE REPOSITORY ARCHITECTURE FILE
        ${cmd_option_list}
        """

        args = slash_split(args)

        apiurl = self.get_api_url()
        project = None
        package = None
        binary = None

        if len(args) < 1 and is_package_dir('.'):
            self.print_repos()

        architecture = None
        if len(args) == 4 or len(args) == 5:
            project = args[0]
            package = args[1]
            repository   = args[2]
            architecture = args[3]
            if len(args) == 5:
                binary = args[4]
        elif len(args) == 3:
            project, repository, architecture = args
        elif len(args) >= 1 and len(args) <= 2:
            if is_package_dir(os.getcwd()):
                project = store_read_project(os.curdir)
                package = store_read_package(os.curdir)
            elif is_project_dir(os.getcwd()):
                project = store_read_project(os.curdir)
            else:
                raise oscerr.WrongArgs('Missing arguments: either specify <project> and ' \
                                       '<package> or move to a project or package working copy')
            repository   = args[0]
            if len(args) == 2:
                architecture = args[1]
        else:
            raise oscerr.WrongArgs('Need either 1, 2, 3 or 4 arguments')

        repos = list(get_repos_of_project(apiurl, project))
        if not [i for i in repos if repository == i.name]:
            self.print_repos(exc_msg='Invalid repository \'%s\'' % repository, project=project)

        arches = [architecture]
        if architecture is None:
            arches = [i.arch for i in repos if repository == i.name]


        if package is None:
            package = meta_get_packagelist(apiurl, project)
        else:
            if opts.multibuild_package:
                packages = []
                for subpackage in opts.multibuild_package:
                    packages.append(package + ":" + subpackage)
                package = packages
            else:
                package = [package]

        # Set binary target directory and create if not existing
        target_dir = os.path.normpath(opts.destdir)
        if not os.path.isdir(target_dir):
            print('Creating directory "%s"' % target_dir)
            os.makedirs(target_dir, 0o755)

        for arch in arches:
            for pac in package:
                binaries = get_binarylist(apiurl, project, repository, arch,
                                          package=pac, verbose=True)
                if not binaries:
                    print('no binaries found: Either the package %s ' \
                                        'does not exist or no binaries have been built.' % pac, file=sys.stderr)
                    continue

                for i in binaries:
                    if binary != None and binary != i.name:
                        continue
                    # skip source rpms
                    if not opts.sources and (i.name.endswith('src.rpm') or i.name.endswith('sdeb')):
                        continue
                    if not opts.debug:
                        if i.name.find('-debuginfo-') >= 0:
                            continue
                        if i.name.find('-debugsource-') >= 0:
                            continue
                    fname = '%s/%s' % (target_dir, i.name)
                    if os.path.exists(fname):
                        st = os.stat(fname)
                        if st.st_mtime == i.mtime and st.st_size == i.size:
                            continue
                    get_binary_file(apiurl,
                                    project,
                                    repository, arch,
                                    i.name,
                                    package = pac,
                                    target_filename = fname,
                                    target_mtime = i.mtime,
                                    progress_meter = not opts.quiet)


    @cmdln.option('-b', '--bugowner', action='store_true',
                        help='restrict listing to items where the user is bugowner')
    @cmdln.option('-m', '--maintainer', action='store_true',
                        help='restrict listing to items where the user is maintainer')
    @cmdln.option('-a', '--all', action='store_true',
                        help='all involvements')
    @cmdln.option('-U', '--user', metavar='USER',
                        help='search for USER instead of yourself')
    @cmdln.option('--exclude-project', action='append',
                        help='exclude requests for specified project')
    @cmdln.option('-v', '--verbose', action='store_true',
                        help='verbose listing')
    @cmdln.option('--maintained', action='store_true',
                        help='limit search results to packages with maintained attribute set.')
    def do_my(self, subcmd, opts, *args):
        """${cmd_name}: show waiting work, packages, projects or requests involving yourself

            Examples:
                # list all open tasks for me
                osc ${cmd_name} [work]
                # list packages where I am bugowner
                osc ${cmd_name} pkg -b
                # list projects where I am maintainer
                osc ${cmd_name} prj -m
                # list request for all my projects and packages
                osc ${cmd_name} rq
                # list requests, excluding project 'foo' and 'bar'
                osc ${cmd_name} rq --exclude-project foo,bar
                # list requests I made
                osc ${cmd_name} sr

            ${cmd_usage}
                where TYPE is one of requests, submitrequests,
                projects or packages (rq, sr, prj or pkg)

            ${cmd_option_list}
        """

        # TODO: please clarify the difference between sr and rq.
        # My first implementeation was to make no difference between requests FROM one
        # of my projects and TO one of my projects. The current implementation appears to make this difference.
        # The usage above indicates, that sr would be a subset of rq, which is no the case with my tests.
        # jw.

        args_rq = ('requests', 'request', 'req', 'rq', 'work')
        args_sr = ('submitrequests', 'submitrequest', 'submitreq', 'submit', 'sr')
        args_prj = ('projects', 'project', 'projs', 'proj', 'prj')
        args_pkg = ('packages', 'package', 'pack', 'pkgs', 'pkg')
        args_patchinfos = ('patchinfos', 'work')

        if opts.bugowner and opts.maintainer:
            raise oscerr.WrongOptions('Sorry, \'--bugowner\' and \'maintainer\' are mutually exclusive')
        elif opts.all and (opts.bugowner or opts.maintainer):
            raise oscerr.WrongOptions('Sorry, \'--all\' and \'--bugowner\' or \'--maintainer\' are mutually exclusive')

        apiurl = self.get_api_url()

        exclude_projects = []
        for i in opts.exclude_project or []:
            prj = i.split(',')
            if len(prj) == 1:
                exclude_projects.append(i)
            else:
                exclude_projects.extend(prj)
        if not opts.user:
            user = conf.get_apiurl_usr(apiurl)
        else:
            user = opts.user

        what = {'project': '', 'package': ''}
        type = "work"
        if len(args) > 0:
            type = args[0]

        list_patchinfos = list_requests = False
        if type in args_patchinfos:
            list_patchinfos = True
        if type in args_rq:
            list_requests = True
        elif type in args_prj:
            what = {'project': ''}
        elif type in args_sr:
            requests = get_request_collection(apiurl, 'creator', req_who=user)
            for r in sorted(requests, key=lambda x: x.reqid):
                print(r.list_view(), '\n')
            return
        elif not type in args_pkg:
            raise oscerr.WrongArgs("invalid type %s" % type)

        role_filter = ''
        if opts.maintainer:
            role_filter = 'maintainer'
        elif opts.bugowner:
            role_filter = 'bugowner'
        elif list_requests:
            role_filter = 'maintainer'
        if opts.all:
            role_filter = ''

        if list_patchinfos:
            u = makeurl(apiurl, ['/search/package'], {
                'match' : "([kind='patchinfo' and issue/[@state='OPEN' and owner/@login='%s']])" % user
                 })
            f = http_GET(u)
            root = ET.parse(f).getroot()
            if root.findall('package'):
                print("Patchinfos with open bugs assigned to you:\n")
                for node in root.findall('package'):
                    project = node.get('project')
                    package = node.get('name')
                    print(project, "/", package, '\n')
                    p = makeurl(apiurl, ['source', project, package], { 'view': 'issues' })
                    fp = http_GET(p)
                    issues = ET.parse(fp).findall('issue')
                    for issue in issues:
                        if issue.find('state') == None or issue.find('state').text != "OPEN":
                            continue
                        if issue.find('owner') == None or issue.find('owner').find('login').text != user:
                            continue
                        print("  #", issue.find('label').text, ': ', end=' ')
                        desc = issue.find('summary')
                        if desc != None:
                            print(desc.text)
                        else:
                            print("\n")
                print("")

        if list_requests:
            # try api side search as supported since OBS 2.2
            try:
                requests = []
                # open reviews
                u = makeurl(apiurl, ['request'], {
                    'view': 'collection',
                    'states': 'review',
                    'reviewstates': 'new',
                    'roles': 'reviewer',
                    'user': user,
                    })
                f = http_GET(u)
                root = ET.parse(f).getroot()
                if root.findall('request'):
                    print("Requests which request a review by you:\n")
                    for node in root.findall('request'):
                        r = Request()
                        r.read(node)
                        print(r.list_view(), '\n')
                    print("")
                # open requests
                u = makeurl(apiurl, ['request'], {
                    'view': 'collection',
                    'states': 'new',
                    'roles': 'maintainer',
                    'user': user,
                    })
                f = http_GET(u)
                root = ET.parse(f).getroot()
                if root.findall('request'):
                    print("Requests for your packages:\n")
                    for node in root.findall('request'):
                        r = Request()
                        r.read(node)
                        print(r.list_view(), '\n')
                    print("")
                # declined requests submitted by me
                u = makeurl(apiurl, ['request'], {
                    'view': 'collection',
                    'states': 'declined',
                    'roles': 'creator',
                    'user': user,
                    })
                f = http_GET(u)
                root = ET.parse(f).getroot()
                if root.findall('request'):
                    print("Declined requests created by you (revoke, reopen or supersede):\n")
                    for node in root.findall('request'):
                        r = Request()
                        r.read(node)
                        print(r.list_view(), '\n')
                    print("")
                return
            except HTTPError as e:
                if e.code != 400:
                    raise e
                # skip it ... try again with old style below

        res = get_user_projpkgs(apiurl, user, role_filter, exclude_projects,
                                'project' in what, 'package' in what,
                                opts.maintained, opts.verbose)

        # map of project =>[list of packages]
        # if list of packages is empty user is maintainer of the whole project
        request_todo = {}

        dummy_elm = ET.Element('dummy')
        roles = {}
        if len(what.keys()) == 2:
            for i in res.get('project_id', res.get('project', dummy_elm)).findall('project'):
                request_todo[i.get('name')] = []
                roles[i.get('name')] = [p.get('role') for p in i.findall('person') if p.get('userid') == user]
            for i in res.get('package_id', res.get('package', dummy_elm)).findall('package'):
                prj = i.get('project')
                roles['/'.join([prj, i.get('name')])] = [p.get('role') for p in i.findall('person') if p.get('userid') == user]
                if not prj in request_todo or request_todo[prj] != []:
                    request_todo.setdefault(prj, []).append(i.get('name'))
        else:
            for i in res.get('project_id', res.get('project', dummy_elm)).findall('project'):
                roles[i.get('name')] = [p.get('role') for p in i.findall('person') if p.get('userid') == user]

        if list_requests:
            # old style, only for OBS 2.1 and before. Should not be used, since it is slow and incomplete
            requests = get_user_projpkgs_request_list(apiurl, user, projpkgs=request_todo)
            for r in sorted(requests, key=lambda x: x.reqid):
                print(r.list_view(), '\n')
            if not len(requests):
                print(" -> try also 'osc my sr' to see more.")
        else:
            for i in sorted(roles.keys()):
                out = '%s' % i
                prjpac = i.split('/')
                if type in args_pkg and len(prjpac) == 1 and not opts.verbose:
                    continue
                if opts.verbose:
                    out = '%s (%s)' % (i, ', '.join(sorted(roles[i])))
                    if len(prjpac) == 2:
                        out = '   %s (%s)' % (prjpac[1], ', '.join(sorted(roles[i])))
                print(out)


    @cmdln.option('--repos-baseurl', action='store_true',
                        help='show base URLs of download repositories')
    @cmdln.option('-e', '--exact', action='store_true',
                        help='show only exact matches, this is default now')
    @cmdln.option('-s', '--substring', action='store_true',
                        help='Show also results where the search term is a sub string, slower search')
    @cmdln.option('--package', action='store_true',
                        help='search for a package')
    @cmdln.option('--project', action='store_true',
                        help='search for a project')
    @cmdln.option('--title', action='store_true',
                        help='search for matches in the \'title\' element')
    @cmdln.option('--description', action='store_true',
                        help='search for matches in the \'description\' element')
    @cmdln.option('-a', '--limit-to-attribute', metavar='ATTRIBUTE',
                        help='match only when given attribute exists in meta data')
    @cmdln.option('-v', '--verbose', action='store_true',
                        help='show more information')
    @cmdln.option('-V', '--version', action='store_true',
                        help='show package version, revision, and srcmd5. CAUTION: This is slow and unreliable')
    @cmdln.option('-i', '--involved', action='store_true',
                        help='show projects/packages where given person (or myself) is involved as bugowner or maintainer [[{group|person}/]<name>] default: person')
    @cmdln.option('-b', '--bugowner', action='store_true',
                        help='as -i, but only bugowner')
    @cmdln.option('-m', '--maintainer', action='store_true',
                        help='as -i, but only maintainer')
    @cmdln.option('--maintained', action='store_true',
                        help='OBSOLETE: please use maintained command instead.')
    @cmdln.option('-M', '--mine', action='store_true',
                        help='shorthand for --bugowner --package')
    @cmdln.option('--csv', action='store_true',
                        help='generate output in CSV (separated by |)')
    @cmdln.option('--binary', action='store_true',
                        help='search binary packages')
    @cmdln.option('-B', '--baseproject', metavar='PROJECT',
                        help='search packages built for PROJECT (implies --binary)')
    @cmdln.option('--binaryversion', metavar='VERSION',
                        help='search for binary with specified version (implies --binary)')
    @cmdln.alias('se')
    @cmdln.alias('bse')
    def do_search(self, subcmd, opts, *args):
        """${cmd_name}: Search for a project and/or package.

        If no option is specified osc will search for projects and
        packages which contains the \'search term\' in their name,
        title or description.

        usage:
            osc search \'search term\' <options>
            osc bse ...                         ('osc search --binary')
            osc se 'perl(Foo::Bar)'             ('osc search --package perl-Foo-Bar')
        ${cmd_option_list}
        """
        def build_xpath(attr, what, substr = False):
            if substr:
                return 'contains(%s, \'%s\')' % (attr, what)
            else:
                return '%s = \'%s\'' % (attr, what)

        search_term = ''
        if len(args) > 1:
            raise oscerr.WrongArgs('Too many arguments')
        elif len(args) == 0:
            if opts.involved or opts.bugowner or opts.maintainer or opts.mine:
                search_term = conf.get_apiurl_usr(conf.config['apiurl'])
            else:
                raise oscerr.WrongArgs('Too few arguments')
        else:
            search_term = args[0]

        if opts.maintained:
            raise oscerr.WrongOptions('The --maintained option is not anymore supported. Please use the maintained command instead.')

        # XXX: is it a good idea to make this the default?
        # support perl symbols:
        if re.match('^perl\(\w+(::\w+)*\)$', search_term):
            search_term = re.sub('\)', '', re.sub('(::|\()', '-', search_term))
            opts.package = True

        if opts.mine:
            opts.bugowner = True
            opts.package = True

        if (opts.title or opts.description) and (opts.involved or opts.bugowner or opts.maintainer):
            raise oscerr.WrongOptions('Sorry, the options \'--title\' and/or \'--description\' ' \
                                      'are mutually exclusive with \'-i\'/\'-b\'/\'-m\'/\'-M\'')
        if opts.substring and opts.exact:
            raise oscerr.WrongOptions('Sorry, the options \'--substring\' and \'--exact\' are mutually exclusive')

        if not opts.substring:
            opts.exact = True
        if subcmd == 'bse' or opts.baseproject or opts.binaryversion:
            opts.binary = True

        if opts.binary and (opts.title or opts.description or opts.involved or opts.bugowner or opts.maintainer
                            or opts.project or opts.package):
            raise oscerr.WrongOptions('Sorry, \'--binary\' and \'--title\' or \'--description\' or \'--involved ' \
                                      'or \'--bugowner\' or \'--maintainer\' or \'--limit-to-attribute <attr>\ ' \
                                      'or \'--project\' or \'--package\' are mutually exclusive')

        apiurl = self.get_api_url()

        xpath = ''
        if opts.title:
            xpath = xpath_join(xpath, build_xpath('title', search_term, opts.substring), inner=True)
        if opts.description:
            xpath = xpath_join(xpath, build_xpath('description', search_term, opts.substring), inner=True)
        if opts.project or opts.package or opts.binary:
            xpath = xpath_join(xpath, build_xpath('@name', search_term, opts.substring), inner=True)
        # role filter
        role_filter = ''
        if opts.bugowner or opts.maintainer or opts.involved:
            tmp = search_term.split(':')
            if len(tmp) > 1:
                search_type, search_term = [tmp[0], tmp[1]]
            else:
                search_type = 'person'
            search_dict = { 'person' : 'userid',
                            'group'  : 'groupid' }
            try:
                search_id = search_dict[ search_type ]
            except KeyError:
                search_type, search_id = [ 'person', 'userid' ]
            xpath = xpath_join(xpath, '%s/@%s = \'%s\'' % (search_type, search_id, search_term), inner=True)
            role_filter = '%s (%s)' % (search_term, search_type)
        role_filter_xpath = xpath
        if opts.bugowner and not opts.maintainer:
            xpath = xpath_join(xpath, '%s/@role=\'bugowner\'' % search_type, op='and')
            role_filter = 'bugowner'
        elif not opts.bugowner and opts.maintainer:
            xpath = xpath_join(xpath, '%s/@role=\'maintainer\'' % search_type, op='and')
            role_filter = 'maintainer'
        if opts.limit_to_attribute:
            xpath = xpath_join(xpath, 'attribute/@name=\'%s\'' % opts.limit_to_attribute, op='and')
        if opts.baseproject:
            xpath = xpath_join(xpath, 'path/@project=\'%s\'' % opts.baseproject, op='and')
        if opts.binaryversion:
            m = re.match(r'(.+)-(.*?)$', opts.binaryversion)
            if m:
                if m.group(2) != '':
                    xpath = xpath_join(xpath, '@versrel=\'%s\'' % opts.binaryversion, op='and')
                else:
                    xpath = xpath_join(xpath, '@version=\'%s\'' % m.group(1), op='and')
            else:
                xpath = xpath_join(xpath, '@version=\'%s\'' % opts.binaryversion, op='and')

        if not xpath:
            xpath = xpath_join(xpath, build_xpath('@name', search_term, opts.substring), inner=True)
            xpath = xpath_join(xpath, build_xpath('title', search_term, opts.substring), inner=True)
            xpath = xpath_join(xpath, build_xpath('description', search_term, opts.substring), inner=True)
        what = {'project': xpath, 'package': xpath}
        if opts.project and not opts.package:
            what = {'project': xpath}
        elif not opts.project and opts.package:
            what = {'package': xpath}
        elif opts.binary:
            what = {'published/binary/id': xpath}
        try:
            res = search(apiurl, **what)
        except HTTPError as e:
            if e.code != 400 or not role_filter:
                raise e
            # backward compatibility: local role filtering
            if opts.limit_to_attribute:
                role_filter_xpath = xpath_join(role_filter_xpath, 'attribute/@name=\'%s\'' % opts.limit_to_attribute, op='and')
            what = dict([[kind, role_filter_xpath] for kind in what.keys()])
            res = search(apiurl, **what)
            filter_role(res, search_term, role_filter)
        if role_filter:
            role_filter = '%s (%s)' % (search_term, role_filter)
        kind_map = {'published/binary/id': 'binary'}
        for kind, root in res.items():
            results = []
            for node in root.findall(kind_map.get(kind, kind)):
                result = []
                project = node.get('project')
                package = None
                if project is None:
                    project = node.get('name')
                else:
                    if kind == 'published/binary/id':
                        package = node.get('package')
                    else:
                        package = node.get('name')

                result.append(project)
                if not package is None:
                    result.append(package)

                if opts.version and package != None:
                    sr = get_source_rev(apiurl, project, package)
                    v = sr.get('version')
                    r = sr.get('rev')
                    s = sr.get('srcmd5')
                    if not v or v == 'unknown':
                        v = '-'
                    if not r:
                        r = '-'
                    if not s:
                        s = '-'
                    result.append(v)
                    result.append(r)
                    result.append(s)

                if opts.verbose:
                    title = node.findtext('title').strip()
                    if len(title) > 60:
                        title = title[:61] + '...'
                    result.append(title)

                if opts.repos_baseurl:
                    # FIXME: no hardcoded URL of instance
                    result.append('http://download.opensuse.org/repositories/%s/' % project.replace(':', ':/'))
                if kind == 'published/binary/id':
                    result.append(node.get('filepath'))
                results.append(result)

            if not len(results):
                print('No matches found for \'%s\' in %ss' % (role_filter or search_term, kind))
                continue
            # construct a sorted, flat list
            # Sort by first column, follwed by second column if we have two columns, else sort by first.
            if len(results[0]) > 1:
                sorted_results = sorted(results, key=itemgetter(0,1))
            else:
                sorted_results = sorted(results, key=itemgetter(0))
            new = []
            for i in sorted_results:
                new.extend(i)
            results = new
            headline = []
            if kind == 'package' or kind == 'published/binary/id':
                headline = [ '# Project', '# Package' ]
            else:
                headline = [ '# Project' ]
            if opts.version and kind == 'package':
                headline.append('# Ver')
                headline.append('Rev')
                headline.append('Srcmd5')
            if opts.verbose:
                headline.append('# Title')
            if opts.repos_baseurl:
                headline.append('# URL')
            if opts.binary:
                headline.append('# filepath')
            if not opts.csv:
                if len(what.keys()) > 1:
                    print('#' * 68)
                print('matches for \'%s\' in %ss:\n' % (role_filter or search_term, kind))
            for row in build_table(len(headline), results, headline, 2, csv = opts.csv):
                print(row)


    @cmdln.option('-p', '--project', metavar='project',
                        help='specify the path to a project')
    @cmdln.option('-n', '--name', metavar='name',
                        help='specify a package name')
    @cmdln.option('-t', '--title', metavar='title',
                        help='set a title')
    @cmdln.option('-d', '--description', metavar='description',
                        help='set the description of the package')
    @cmdln.option('',   '--delete-old-files', action='store_true',
                        help='delete existing files from the server')
    @cmdln.option('-c',   '--commit', action='store_true',
                        help='commit the new files')
    def do_importsrcpkg(self, subcmd, opts, srpm):
        """${cmd_name}: Import a new package from a src.rpm

        A new package dir will be created inside the project dir
        (if no project is specified and the current working dir is a
        project dir the package will be created in this project). If
        the package does not exist on the server it will be created
        too otherwise the meta data of the existing package will be
        updated (<title /> and <description />).
        The src.rpm will be extracted into the package dir. The files
        won't be committed unless you explicitly pass the --commit switch.

        SRPM is the path of the src.rpm in the local filesystem,
        or an URL.

        ${cmd_usage}
        ${cmd_option_list}
        """
        import glob
        from .util import rpmquery

        if opts.delete_old_files and conf.config['do_package_tracking']:
            # IMHO the --delete-old-files option doesn't really fit into our
            # package tracking strategy
            print('--delete-old-files is not supported anymore', file=sys.stderr)
            print('when do_package_tracking is enabled', file=sys.stderr)
            sys.exit(1)

        if '://' in srpm:
            if srpm.endswith('/'):
                print('%s is not a valid link. It must not end with /' % srpm)
                sys.exit(1)
            print('trying to fetch', srpm)
            from .grabber import OscFileGrabber
            OscFileGrabber().urlgrab(srpm)
            srpm = os.path.basename(srpm)

        srpm = os.path.abspath(srpm)
        if not os.path.isfile(srpm):
            print('file \'%s\' does not exist' % srpm, file=sys.stderr)
            sys.exit(1)

        if opts.project:
            project_dir = opts.project
        else:
            project_dir = os.curdir

        if not is_project_dir(project_dir):
            raise oscerr.WrongArgs("'%s' is no project working copy" % project_dir)

        if conf.config['do_package_tracking']:
            project = Project(project_dir)
        else:
            project = store_read_project(project_dir)

        rpmq = rpmquery.RpmQuery.query(srpm)
        title, pac, descr, url = rpmq.summary(), rpmq.name(), rpmq.description(), rpmq.url()
        if url is None:
            url = ''

        if opts.title:
            title = opts.title
        if opts.name:
            pac = opts.name
        if opts.description:
            descr = opts.description

        # title and description can be empty
        if not pac:
            print('please specify a package name with the \'--name\' option. ' \
                                'The automatic detection failed', file=sys.stderr)
            sys.exit(1)
        pac = pac.decode()
        if conf.config['do_package_tracking']:
            createPackageDir(os.path.join(project.dir, pac), project)
        else:
            if not os.path.exists(os.path.join(project_dir, pac)):
                apiurl = store_read_apiurl(project_dir)
                user = conf.get_apiurl_usr(apiurl)
                data = meta_exists(metatype='pkg',
                                   path_args=(quote_plus(project), quote_plus(pac)),
                                   template_args=({
                                       'name': pac,
                                       'user': user}), apiurl=apiurl)
                if data:
                    data = ET.fromstring(parse_meta_to_string(data))
                    data.find('title').text = ''.join(title)
                    data.find('description').text = ''.join(descr)
                    data.find('url').text = url
                    data = ET.tostring(data, encoding=ET_ENCODING)
                else:
                    print('error - cannot get meta data', file=sys.stderr)
                    sys.exit(1)
                edit_meta(metatype='pkg',
                          path_args=(quote_plus(project), quote_plus(pac)),
                          data = data, apiurl=apiurl)
                Package.init_package(apiurl, project, pac, os.path.join(project_dir, pac))
            else:
                print('error - local package already exists', file=sys.stderr)
                sys.exit(1)

        unpack_srcrpm(srpm, os.path.join(project_dir, pac))
        p = Package(os.path.join(project_dir, pac))
        if len(p.filenamelist) == 0 and opts.commit:
            print('Adding files to working copy...')
            addFiles(glob.glob('%s/*' % os.path.join(project_dir, pac)))
            if conf.config['do_package_tracking']:
                project.commit((pac, ))
            else:
                p.update_datastructs()
                p.commit()
        elif opts.commit and opts.delete_old_files:
            for filename in p.filenamelist:
                p.delete_remote_source_file(filename)
            p.update_local_filesmeta()
            print('Adding files to working copy...')
            addFiles(glob.glob('*'))
            p.update_datastructs()
            p.commit()
        else:
            print('No files were committed to the server. Please ' \
                  'commit them manually.')
            print('Package \'%s\' only imported locally' % pac)
            sys.exit(1)

        print('Package \'%s\' imported successfully' % pac)


    @cmdln.option('-X', '-m', '--method', default='GET', metavar='HTTP_METHOD',
                        help='specify HTTP method to use (GET|PUT|DELETE|POST)')
    @cmdln.option('-e', '--edit', default=None, action='store_true',
                        help='GET, edit and PUT the location')
    @cmdln.option('-d', '--data', default=None, metavar='STRING',
                        help='specify string data for e.g. POST')
    @cmdln.option('-T', '-f', '--file', default=None, metavar='FILE',
                        help='specify filename to upload, uses PUT mode by default')
    @cmdln.option('-a', '--add-header', default=None, metavar='NAME STRING',
                        nargs=2, action='append', dest='headers',
                        help='add the specified header to the request')
    def do_api(self, subcmd, opts, url):
        """${cmd_name}: Issue an arbitrary request to the API

        Useful for testing.

        URL can be specified either partially (only the path component), or fully
        with URL scheme and hostname ('http://...').

        Note the global -A and -H options (see osc help).

        Examples:
          osc api /source/home:user
          osc api -X PUT -T /etc/fstab source/home:user/test5/myfstab
          osc api -e /configuration

        ${cmd_usage}
        ${cmd_option_list}
        """

        apiurl = self.get_api_url()

        if not opts.method in ['GET', 'PUT', 'POST', 'DELETE']:
            sys.exit('unknown method %s' % opts.method)

        # default is PUT when uploading files
        if opts.file and opts.method == 'GET':
            opts.method = 'PUT'

        if not url.startswith('http'):
            if not url.startswith('/'):
                url = '/' + url
            url = apiurl + url

        if opts.headers:
            opts.headers = dict(opts.headers)

        r = http_request(opts.method,
                         url,
                         data=opts.data,
                         file=opts.file,
                         headers=opts.headers)
        out = r.read()

        if opts.edit:
            text = edit_text(out)
            r = http_request("PUT",
                         url,
                         data=text,
                         headers=opts.headers)
            out = r.read()

        if isinstance(out, str):
            sys.stdout.write(out)
        else:
            sys.stdout.buffer.write(out)


    @cmdln.option('-b', '--bugowner-only', action='store_true',
                  help='Show only the bugowner')
    @cmdln.option('-B', '--bugowner', action='store_true',
                  help='Show only the bugowner if defined, or maintainer otherwise')
    @cmdln.option('-e', '--email', action='store_true',
                  help='show email addresses instead of user names')
    @cmdln.option('--nodevelproject', action='store_true',
                  help='do not follow a defined devel project ' \
                       '(primary project where a package is developed)')
    @cmdln.option('-v', '--verbose', action='store_true',
                  help='show more information')
    @cmdln.option('-D', '--devel-project', metavar='devel_project',
                  help='define the project where this package is primarily developed')
    @cmdln.option('-a', '--add', metavar='user',
                  help='add a new person for given role ("maintainer" by default)')
    @cmdln.option('-A', '--all', action='store_true',
                  help='list all found entries not just the first one')
    @cmdln.option('-s', '--set-bugowner', metavar='user',
                  help='Set the bugowner to specified person (or group via group: prefix)')
    @cmdln.option('-S', '--set-bugowner-request', metavar='user',
                  help='Set the bugowner to specified person via a request (or group via group: prefix)')
    @cmdln.option('-U', '--user', metavar='USER',
                        help='All official maintained instances for the specified USER')
    @cmdln.option('-G', '--group', metavar='GROUP',
                        help='All official maintained instances for the specified GROUP')
    @cmdln.option('-d', '--delete', metavar='user',
                  help='delete a maintainer/bugowner (can be specified via --role)')
    @cmdln.option('-r', '--role', metavar='role', action='append', default=[],
                  help='Specify user role')
    @cmdln.option('-m', '--message',
                  help='Define message as commit entry or request description')
    @cmdln.alias('bugowner')
    def do_maintainer(self, subcmd, opts, *args):
        """${cmd_name}: Show maintainers according to server side configuration

            # Search for official maintained sources in OBS instance
            osc maintainer BINARY <options>
            osc maintainer -U <user> <options>
            osc maintainer -G <group> <options>

            # Lookup via containers
            osc maintainer <options>
            osc maintainer PRJ <options>
            osc maintainer PRJ PKG <options>

        The tool looks up the default responsible person for a certain project or package.
        When using with an OBS 2.4 (or later) server it is doing the lookup for
        a given binary according to the server side configuration of default owners.

        The tool is also looking into devel packages and supports to fallback to the project
        in case a package has no defined maintainer.

        Please use "osc meta pkg" in case you need to know the definition in a specific container.

        PRJ and PKG default to current working-copy path.

        ${cmd_usage}
        ${cmd_option_list}
        """
        def get_maintainer_data(apiurl, maintainer, verbose=False):
            tags = ('email',)
            if maintainer.startswith('group:'):
                group = maintainer.replace('group:', '')
                if verbose:
                    return [maintainer] + get_group_data(apiurl, group, 'title', *tags)
                return get_group_data(apiurl, group, 'email')
            if verbose:
                tags = ('login', 'realname', 'email')
            return get_user_data(apiurl, maintainer, *tags)
        def setBugownerHelper(apiurl, project, package, bugowner):
            try:
                setBugowner(apiurl, project, package, bugowner)
            except HTTPError as e:
                if e.code != 403:
                    raise
                print("No write permission in", project, end=' ')
                if package:
                    print("/", package, end=' ')
                print()
                repl = raw_input('\nCreating a request instead? (y/n) ')
                if repl.lower() == 'y':
                    opts.set_bugowner_request = bugowner
                    opts.set_bugowner = None

        binary = None
        prj = None
        pac = None
        metaroot = None
        searchresult = None
        roles = [ 'bugowner', 'maintainer' ]
        if len(opts.role):
            roles = opts.role
        elif opts.bugowner_only or opts.bugowner or subcmd == 'bugowner':
            roles = [ 'bugowner' ]

        args = slash_split(args)
        if opts.user or opts.group:
            if len(args) != 0:
                raise oscerr.WrongArgs('Either search for user or for packages.')
        elif len(args) == 0:
            try:
                pac = store_read_package('.')
            except oscerr.NoWorkingCopy:
                pass
            prj = store_read_project('.')
        elif len(args) == 1:
            # it is unclear if one argument is a binary or a project, try binary first for new OBS 2.4
            binary = prj = args[0]
        elif len(args) == 2:
            prj = args[0]
            pac = args[1]
        else:
            raise oscerr.WrongArgs('Wrong number of arguments.')

        apiurl = self.get_api_url()

        # Try the OBS 2.4 way first.
        if binary or opts.user or opts.group:
            limit = None
            if opts.all:
                limit = 0
            filterroles = roles
            if filterroles == [ 'bugowner', 'maintainer' ]:
                # use server side configured default
                filterroles = None
            if binary:
                searchresult = owner(apiurl, binary, "binary", usefilter=filterroles, devel=None, limit=limit)
                if searchresult != None and len(searchresult) == 0:
                    # We talk to an OBS 2.4 or later understanding the call
                    if opts.set_bugowner or opts.set_bugowner_request:
                        # filtered search did not succeed, but maybe we want to set an owner initially?
                        searchresult = owner(apiurl, binary, "binary", usefilter="", devel=None, limit=-1)
                        if searchresult:
                            print("WARNING: the binary exists, but has no matching maintainership roles defined.")
                            print("Do you want to set it in the container where the binary appeared first?")
                            result = searchresult.find('owner')
                            print("This is: " + result.get('project'), end=' ')
                            if result.get('package'):
                                print (" / " + result.get('package'))
                            repl = raw_input('\nUse this container? (y/n) ')
                            if repl.lower() != 'y':
                                searchresult = None
            elif opts.user:
                searchresult = owner(apiurl, opts.user, "user", usefilter=filterroles, devel=None)
            elif opts.group:
                searchresult = owner(apiurl, opts.group, "group", usefilter=filterroles, devel=None)
            else:
                raise oscerr.WrongArgs('osc bug, no valid search criteria')

        if opts.add:
            if searchresult:
                for result in searchresult.findall('owner'):
                    for role in roles:
                        addPerson(apiurl, result.get('project'), result.get('package'), opts.add, role)
            else:
                for role in roles:
                    addPerson(apiurl, prj, pac, opts.add, role)
        elif opts.set_bugowner or opts.set_bugowner_request:
            bugowner = opts.set_bugowner or opts.set_bugowner_request
            requestactionsxml = ""
            if searchresult:
                for result in searchresult.findall('owner'):
                    if opts.set_bugowner:
                        setBugownerHelper(apiurl, result.get('project'), result.get('package'), opts.set_bugowner)
                    if opts.set_bugowner_request:
                        args = [bugowner, result.get('project')]
                        if result.get('package'):
                            args = args + [result.get('package')]
                        requestactionsxml += self._set_bugowner(args, opts)

            else:
                if opts.set_bugowner:
                    setBugownerHelper(apiurl, prj, pac, opts.set_bugowner)

                if opts.set_bugowner_request:
                    args = [bugowner, prj]
                    if pac:
                        args = args + [pac]
                    requestactionsxml += self._set_bugowner(args, opts)

            if requestactionsxml != "":
                if opts.message:
                    message = opts.message
                else:
                    message = edit_message()

                import cgi
                xml = """<request> %s <state name="new"/> <description>%s</description> </request> """ % \
                      (requestactionsxml, cgi.escape(message or ""))
                u = makeurl(apiurl, ['request'], query='cmd=create')
                f = http_POST(u, data=xml)

                root = ET.parse(f).getroot()
                print("Request ID:", root.get('id'))

        elif opts.delete:
            if searchresult:
                for result in searchresult.findall('owner'):
                    for role in roles:
                        delPerson(apiurl, result.get('project'), result.get('package'), opts.delete, role)
            else:
                for role in roles:
                    delPerson(apiurl, prj, pac, opts.delete, role)
        elif opts.devel_project:
            # XXX: does it really belong to this command?
            setDevelProject(apiurl, prj, pac, opts.devel_project)
        else:
            if pac:
                m = show_package_meta(apiurl, prj, pac)
                metaroot = ET.fromstring(b''.join(m))
                if not opts.nodevelproject:
                    while metaroot.findall('devel'):
                        d = metaroot.find('devel')
                        prj = d.get('project', prj)
                        pac = d.get('package', pac)
                        if opts.verbose:
                            print("Following to the development space: %s/%s" % (prj, pac))
                        m = show_package_meta(apiurl, prj, pac)
                        metaroot = ET.fromstring(b''.join(m))
                    if not metaroot.findall('person') and not metaroot.findall('group'):
                        if opts.verbose:
                            print("No dedicated persons in package defined, showing the project persons.")
                        pac = None
                        m = show_project_meta(apiurl, prj)
                        metaroot = ET.fromstring(b''.join(m))
            else:
                # fallback to project lookup for old servers
                if prj and not searchresult:
                    m = show_project_meta(apiurl, prj)
                    metaroot = ET.fromstring(b''.join(m))

            # extract the maintainers
            projects = []
            # from owner search
            if searchresult:
                for result in searchresult.findall('owner'):
                    maintainers = {}
                    maintainers.setdefault("project", result.get('project'))
                    maintainers.setdefault("package", result.get('package'))
                    for person in result.findall('person'):
                        maintainers.setdefault(person.get('role'), []).append(person.get('name'))
                    for group in result.findall('group'):
                        maintainers.setdefault(group.get('role'), []).append("group:"+group.get('name'))
                    projects = projects + [maintainers]
            # from meta data
            if metaroot:
                # we have just one result
                maintainers = {}
                for person in metaroot.findall('person'):
                    maintainers.setdefault(person.get('role'), []).append(person.get('userid'))
                for group in metaroot.findall('group'):
                    maintainers.setdefault(group.get('role'), []).append("group:"+group.get('groupid'))
                projects = [maintainers]

            # showing the maintainers
            for maintainers in projects:
                indent = ""
                definingproject = maintainers.get("project")
                if definingproject:
                    definingpackage = maintainers.get("package")
                    indent = "  "
                    if definingpackage:
                        print("Defined in package: %s/%s " % (definingproject, definingpackage))
                    else:
                        print("Defined in project: ", definingproject)

                if prj:
                    # not for user/group search
                    for role in roles:
                        if opts.bugowner and not len(maintainers.get(role, [])):
                            role = 'maintainer'
                        if pac:
                            print("%s%s of %s/%s : " %(indent, role, prj, pac))
                        else:
                            print("%s%s of %s : " %(indent, role, prj))
                        if opts.email:
                            emails = []
                            for maintainer in maintainers.get(role, []):
                                user = get_maintainer_data(apiurl, maintainer, verbose=False)
                                if len(user):
                                    emails.append(''.join(user))
                            print(indent, end=' ')
                            print(', '.join(emails) or '-')
                        elif opts.verbose:
                            userdata = []
                            for maintainer in maintainers.get(role, []):
                                user = get_maintainer_data(apiurl, maintainer, verbose=True)
                                userdata.append(user[0])
                                if user[1] !=  '-':
                                    userdata.append("%s <%s>"%(user[1], user[2]))
                                else:
                                    userdata.append(user[2])
                            for row in build_table(2, userdata, None, 3):
                                print(indent, end=' ')
                                print(row)
                        else:
                            print(indent, end=' ')
                            print(', '.join(maintainers.get(role, [])) or '-')
                        print()

    @cmdln.alias('who')
    @cmdln.alias('user')
    def do_whois(self, subcmd, opts, *usernames):
        """${cmd_name}: Show fullname and email of a buildservice user

        ${cmd_usage}
        ${cmd_option_list}
        """
        apiurl = self.get_api_url()
        if len(usernames) < 1:
            if 'user' not in conf.config['api_host_options'][apiurl]:
                raise oscerr.WrongArgs('your oscrc does not have your user name.')
            usernames = (conf.config['api_host_options'][apiurl]['user'],)
        for name in usernames:
            user = get_user_data(apiurl, name, 'login', 'realname', 'email')
            if len(user) == 3:
                print("%s: \"%s\" <%s>"%(user[0], user[1], user[2]))


    @cmdln.option('-r', '--revision', metavar='rev',
                  help='print out the specified revision')
    @cmdln.option('-e', '--expand', action='store_true',
                  help='(default) force expansion of linked packages.')
    @cmdln.option('-u', '--unexpand', action='store_true',
                  help='always work with unexpanded packages.')
    @cmdln.option('-D', '--deleted', action='store_true',
                        help='access file in a deleted package')
    @cmdln.option('-M', '--meta', action='store_true',
                        help='list meta data files')
    @cmdln.alias('blame')
    @cmdln.alias('less')
    def do_cat(self, subcmd, opts, *args):
        """${cmd_name}: Output the content of a file to standard output

        Examples:
            osc cat file
            osc cat project package file
            osc cat project/package/file
            osc cat http://api.opensuse.org/build/.../_log
            osc cat http://api.opensuse.org/source/../_link

            osc less file
            osc less project package file

            osc blame file
            osc blame project package file

        ${cmd_usage}
        ${cmd_option_list}
        """

        if len(args) == 1 and (args[0].startswith('http://') or
                               args[0].startswith('https://')):
            opts.method = 'GET'
            opts.headers = None
            opts.data = None
            opts.file = None
            return self.do_api('list', opts, *args)

        args = slash_split(args)
        project = package = filename = None
        if len(args) == 3:
            project = args[0]
            package = args[1]
            filename = args[2]
        elif len(args) == 1 and is_package_dir(os.getcwd()):
            project = store_read_project(os.curdir)
            package = store_read_package(os.curdir)
            filename = args[0]
        else:
            raise oscerr.WrongArgs('Wrong number of arguments.')

        rev, dummy = parseRevisionOption(opts.revision)
        apiurl = self.get_api_url()

        query = { }
        if subcmd == 'blame':
            query['view'] = "blame"
        if opts.meta:
            query['meta'] = 1
        if opts.deleted:
            query['deleted'] = 1
        if opts.revision:
            query['rev'] = opts.revision
        if not opts.unexpand:
            query['rev'] = show_upstream_srcmd5(apiurl, project, package, expand=True, revision=opts.revision, meta=opts.meta, deleted=opts.deleted)
            query['expand'] = 1 # important for blame case to follow links in old revisions
        u = makeurl(apiurl, ['source', project, package, filename], query=query)
        if subcmd == 'less':
            f = http_GET(u)
            run_pager(b''.join(f.readlines()))
        else:
            for data in streamfile(u):
                if isinstance(data, str):
                    sys.stdout.write(data)
                else:
                    sys.stdout.buffer.write(data)


    # helper function to download a file from a specific revision
    def download(self, name, md5, dir, destfile):
        o = open(destfile, 'wb')
        if md5 != '':
            query = {'rev': dir['srcmd5']}
            u = makeurl(dir['apiurl'], ['source', dir['project'], dir['package'], pathname2url(name)], query=query)
            for buf in streamfile(u, http_GET, BUFSIZE):
                o.write(buf)
        o.close()


    @cmdln.option('-d', '--destdir', default='repairlink', metavar='DIR',
            help='destination directory')
    def do_repairlink(self, subcmd, opts, *args):
        """${cmd_name}: Repair a broken source link

        This command checks out a package with merged source changes. It uses
        a 3-way merge to resolve file conflicts. After reviewing/repairing
        the merge, use 'osc resolved ...' and 'osc ci' to re-create a
        working source link.

        usage:
        * For merging conflicting changes of a checkout package:
            osc repairlink

        * Check out a package and merge changes:
            osc repairlink PROJECT PACKAGE

        * Pull conflicting changes from one project into another one:
            osc repairlink PROJECT PACKAGE INTO_PROJECT [INTO_PACKAGE]

        ${cmd_option_list}
        """

        apiurl = self.get_api_url()
        args = slash_split(args)
        if len(args) >= 3 and len(args) <= 4:
            prj = args[0]
            package = target_package = args[1]
            target_prj = args[2]
            if len(args) == 4:
                target_package = args[3]
        elif len(args) == 2:
            target_prj = prj = args[0]
            target_package = package = args[1]
        elif is_package_dir(os.getcwd()):
            target_prj = prj = store_read_project(os.getcwd())
            target_package = package = store_read_package(os.getcwd())
        else:
            raise oscerr.WrongArgs('Please specify project and package')

        # first try stored reference, then lastworking
        query = { 'rev': 'latest' }
        u = makeurl(apiurl, ['source', prj, package], query=query)
        f = http_GET(u)
        root = ET.parse(f).getroot()
        linkinfo = root.find('linkinfo')
        if linkinfo == None:
            raise oscerr.APIError('package is not a source link')
        if linkinfo.get('error') == None:
            raise oscerr.APIError('source link is not broken')
        workingrev = None

        if linkinfo.get('baserev'):
            query = { 'rev': 'latest', 'linkrev': 'base' }
            u = makeurl(apiurl, ['source', prj, package], query=query)
            f = http_GET(u)
            root = ET.parse(f).getroot()
            linkinfo = root.find('linkinfo')
            if linkinfo.get('error') == None:
                workingrev = linkinfo.get('xsrcmd5')

        if workingrev == None:
            query = { 'lastworking': 1 }
            u = makeurl(apiurl, ['source', prj, package], query=query)
            f = http_GET(u)
            root = ET.parse(f).getroot()
            linkinfo = root.find('linkinfo')
            if linkinfo == None:
                raise oscerr.APIError('package is not a source link')
            if linkinfo.get('error') == None:
                raise oscerr.APIError('source link is not broken')
            workingrev = linkinfo.get('lastworking')
            if workingrev == None:
                raise oscerr.APIError('source link never worked')
            print("using last working link target")
        else:
            print("using link target of last commit")

        query = { 'expand': 1, 'emptylink': 1 }
        u = makeurl(apiurl, ['source', prj, package], query=query)
        f = http_GET(u)
        meta = f.readlines()
        root_new = ET.fromstring(b''.join(meta))
        dir_new = { 'apiurl': apiurl, 'project': prj, 'package': package }
        dir_new['srcmd5'] = root_new.get('srcmd5')
        dir_new['entries'] = [[n.get('name'), n.get('md5')] for n in root_new.findall('entry')]

        query = { 'rev': workingrev }
        u = makeurl(apiurl, ['source', prj, package], query=query)
        f = http_GET(u)
        root_oldpatched = ET.parse(f).getroot()
        linkinfo_oldpatched = root_oldpatched.find('linkinfo')
        if linkinfo_oldpatched == None:
            raise oscerr.APIError('working rev is not a source link?')
        if linkinfo_oldpatched.get('error') != None:
            raise oscerr.APIError('working rev is not working?')
        dir_oldpatched = { 'apiurl': apiurl, 'project': prj, 'package': package }
        dir_oldpatched['srcmd5'] = root_oldpatched.get('srcmd5')
        dir_oldpatched['entries'] = [[n.get('name'), n.get('md5')] for n in root_oldpatched.findall('entry')]

        query = {}
        query['rev'] = linkinfo_oldpatched.get('srcmd5')
        u = makeurl(apiurl, ['source', linkinfo_oldpatched.get('project'), linkinfo_oldpatched.get('package')], query=query)
        f = http_GET(u)
        root_old = ET.parse(f).getroot()
        dir_old = { 'apiurl': apiurl }
        dir_old['project'] = linkinfo_oldpatched.get('project')
        dir_old['package'] = linkinfo_oldpatched.get('package')
        dir_old['srcmd5'] = root_old.get('srcmd5')
        dir_old['entries'] = [[n.get('name'), n.get('md5')] for n in root_old.findall('entry')]

        entries_old = dict(dir_old['entries'])
        entries_oldpatched = dict(dir_oldpatched['entries'])
        entries_new = dict(dir_new['entries'])

        entries = {}
        entries.update(entries_old)
        entries.update(entries_oldpatched)
        entries.update(entries_new)

        destdir = opts.destdir
        if os.path.isdir(destdir):
            shutil.rmtree(destdir)
        os.mkdir(destdir)

        Package.init_package(apiurl, target_prj, target_package, destdir)
        store_write_string(destdir, '_files', b''.join(meta) + b'\n')
        store_write_string(destdir, '_linkrepair', '')
        pac = Package(destdir)

        storedir = os.path.join(destdir, store)

        for name in sorted(entries.keys()):
            md5_old = entries_old.get(name, '')
            md5_new = entries_new.get(name, '')
            md5_oldpatched = entries_oldpatched.get(name, '')
            if md5_new != '':
                self.download(name, md5_new, dir_new, os.path.join(storedir, name))
            if md5_old == md5_new:
                if md5_oldpatched == '':
                    pac.put_on_deletelist(name)
                    continue
                print(statfrmt(' ', name))
                self.download(name, md5_oldpatched, dir_oldpatched, os.path.join(destdir, name))
                continue
            if md5_old == md5_oldpatched:
                if md5_new == '':
                    continue
                print(statfrmt('U', name))
                shutil.copy2(os.path.join(storedir, name), os.path.join(destdir, name))
                continue
            if md5_new == md5_oldpatched:
                if md5_new == '':
                    continue
                print(statfrmt('G', name))
                shutil.copy2(os.path.join(storedir, name), os.path.join(destdir, name))
                continue
            self.download(name, md5_oldpatched, dir_oldpatched, os.path.join(destdir, name + '.mine'))
            if md5_new != '':
                shutil.copy2(os.path.join(storedir, name), os.path.join(destdir, name + '.new'))
            else:
                self.download(name, md5_new, dir_new, os.path.join(destdir, name + '.new'))
            self.download(name, md5_old, dir_old, os.path.join(destdir, name + '.old'))

            if binary_file(os.path.join(destdir, name + '.mine')) or \
               binary_file(os.path.join(destdir, name + '.old')) or \
               binary_file(os.path.join(destdir, name + '.new')):
                shutil.copy2(os.path.join(destdir, name + '.new'), os.path.join(destdir, name))
                print(statfrmt('C', name))
                pac.put_on_conflictlist(name)
                continue

            o = open(os.path.join(destdir,  name), 'wb')
            code = run_external('diff3', '-m', '-E',
              '-L', '.mine',
              os.path.join(destdir, name + '.mine'),
              '-L', '.old',
              os.path.join(destdir, name + '.old'),
              '-L', '.new',
              os.path.join(destdir, name + '.new'),
            stdout=o)
            if code == 0:
                print(statfrmt('G', name))
                os.unlink(os.path.join(destdir, name + '.mine'))
                os.unlink(os.path.join(destdir, name + '.old'))
                os.unlink(os.path.join(destdir, name + '.new'))
            elif code == 1:
                print(statfrmt('C', name))
                pac.put_on_conflictlist(name)
            else:
                print(statfrmt('?', name))
                pac.put_on_conflictlist(name)

        pac.write_deletelist()
        pac.write_conflictlist()
        print()
        print('Please change into the \'%s\' directory,' % destdir)
        print('fix the conflicts (files marked with \'C\' above),')
        print('run \'osc resolved ...\', and commit the changes.')


    def do_pull(self, subcmd, opts, *args):
        """${cmd_name}: merge the changes of the link target into your working copy.

        ${cmd_option_list}
        """

        if not is_package_dir('.'):
            raise oscerr.NoWorkingCopy('Error: \'%s\' is not an osc working copy.' % os.path.abspath('.'))
        p = Package('.')
        # check if everything is committed
        for filename in p.filenamelist:
            state = p.status(filename)
            if state != ' ' and state != 'S':
                raise oscerr.WrongArgs('Please commit your local changes first!')
        # check if we need to update
        upstream_rev = p.latest_rev()
        if not (p.isfrozen() or p.ispulled()):
            raise oscerr.WrongArgs('osc pull makes only sense with a detached head, did you mean osc up?')
        if p.rev != upstream_rev:
            raise oscerr.WorkingCopyOutdated((p.absdir, p.rev, upstream_rev))
        elif not p.islink():
            raise oscerr.WrongArgs('osc pull only works on linked packages.')
        elif not p.isexpanded():
            raise oscerr.WrongArgs('osc pull only works on expanded links.')
        linkinfo = p.linkinfo
        baserev = linkinfo.baserev
        if baserev == None:
            raise oscerr.WrongArgs('osc pull only works on links containing a base revision.')

        # get revisions we need
        query = { 'expand': 1, 'emptylink': 1 }
        u = makeurl(p.apiurl, ['source', p.prjname, p.name], query=query)
        f = http_GET(u)
        meta = f.readlines()
        root_new = ET.fromstring(b''.join(meta))
        linkinfo_new = root_new.find('linkinfo')
        if linkinfo_new == None:
            raise oscerr.APIError('link is not a really a link?')
        if linkinfo_new.get('error') != None:
            raise oscerr.APIError('link target is broken')
        if linkinfo_new.get('srcmd5') == baserev:
            print("Already up-to-date.")
            p.unmark_frozen()
            return
        dir_new = { 'apiurl': p.apiurl, 'project': p.prjname, 'package': p.name }
        dir_new['srcmd5'] = root_new.get('srcmd5')
        dir_new['entries'] = [[n.get('name'), n.get('md5')] for n in root_new.findall('entry')]

        dir_oldpatched = { 'apiurl': p.apiurl, 'project': p.prjname, 'package': p.name, 'srcmd5': p.srcmd5 }
        dir_oldpatched['entries'] = [[f.name, f.md5] for f in p.filelist]

        query = { 'rev': linkinfo.srcmd5 }
        u = makeurl(p.apiurl, ['source', linkinfo.project, linkinfo.package], query=query)
        f = http_GET(u)
        root_old = ET.parse(f).getroot()
        dir_old = { 'apiurl': p.apiurl, 'project': linkinfo.project, 'package': linkinfo.package, 'srcmd5': linkinfo.srcmd5 }
        dir_old['entries'] = [[n.get('name'), n.get('md5')] for n in root_old.findall('entry')]

        # now do 3-way merge
        entries_old = dict(dir_old['entries'])
        entries_oldpatched = dict(dir_oldpatched['entries'])
        entries_new = dict(dir_new['entries'])
        entries = {}
        entries.update(entries_old)
        entries.update(entries_oldpatched)
        entries.update(entries_new)
        for name in sorted(entries.keys()):
            if name.startswith('_service:') or name.startswith('_service_'):
                continue
            md5_old = entries_old.get(name, '')
            md5_new = entries_new.get(name, '')
            md5_oldpatched = entries_oldpatched.get(name, '')
            if md5_old == md5_new or md5_oldpatched == md5_new:
                continue
            if md5_old == md5_oldpatched:
                if md5_new == '':
                    print(statfrmt('D', name))
                    p.put_on_deletelist(name)
                    os.unlink(name)
                elif md5_old == '':
                    print(statfrmt('A', name))
                    self.download(name, md5_new, dir_new, name)
                    p.put_on_addlist(name)
                else:
                    print(statfrmt('U', name))
                    self.download(name, md5_new, dir_new, name)
                continue
            # need diff3 to resolve issue
            if md5_oldpatched == '':
                open(name, 'w').write('')
            os.rename(name, name + '.mine')
            self.download(name, md5_new, dir_new, name + '.new')
            self.download(name, md5_old, dir_old, name + '.old')
            if binary_file(name + '.mine') or binary_file(name + '.old') or binary_file(name + '.new'):
                shutil.copy2(name + '.new', name)
                print(statfrmt('C', name))
                p.put_on_conflictlist(name)
                continue

            o = open(name, 'wb')
            code = run_external('diff3', '-m', '-E',
              '-L', '.mine', name + '.mine',
              '-L', '.old', name + '.old',
              '-L', '.new', name + '.new',
            stdout=o)
            if code == 0:
                print(statfrmt('G', name))
                os.unlink(name + '.mine')
                os.unlink(name + '.old')
                os.unlink(name + '.new')
            elif code == 1:
                print(statfrmt('C', name))
                p.put_on_conflictlist(name)
            else:
                print(statfrmt('?', name))
                p.put_on_conflictlist(name)
        p.write_deletelist()
        p.write_addlist()
        p.write_conflictlist()
        # store new linkrev
        store_write_string(p.absdir, '_pulled', linkinfo_new.get('srcmd5') + '\n')
        p.unmark_frozen()
        print()
        if len(p.in_conflict):
            print('Please fix the conflicts (files marked with \'C\' above),')
            print('run \'osc resolved ...\', and commit the changes')
            print('to update the link information.')
        else:
            print('Please commit the changes to update the link information.')

    @cmdln.option('--create', action='store_true', default=False,
                  help='create new gpg signing key for this project')
    @cmdln.option('--extend', action='store_true', default=False,
                  help='extend expiration date of the gpg public key for this project')
    @cmdln.option('--delete', action='store_true', default=False,
                  help='delete the gpg signing key in this project')
    @cmdln.option('--notraverse', action='store_true', default=False,
                  help='don\'t traverse projects upwards to find key')
    @cmdln.option('--sslcert', action='store_true', default=False,
                  help='fetch SSL certificate instead of GPG key')
    def do_signkey(self, subcmd, opts, *args):
        """${cmd_name}: Manage Project Signing Key

        osc signkey [--create|--delete|--extend] <PROJECT>
        osc signkey [--notraverse] <PROJECT>

        This command is for managing gpg keys. It shows the public key
        by default. There is no way to download or upload the private
        part of a key by design.

        However you can create a new own key. You may want to consider
        to sign the public key with your own existing key.

        If a project has no key, the key from upper level project will
        be used (e.g. when dropping "KDE:KDE4:Community" key, the one from
        "KDE:KDE4" will be used).

        WARNING: THE OLD KEY CANNOT BE RESTORED AFTER USING DELETE OR CREATE

        ${cmd_usage}
        ${cmd_option_list}
        """

        apiurl = self.get_api_url()
        f = None

        prj = None
        if len(args) == 0:
            cwd = os.getcwd()
            if is_project_dir(cwd) or is_package_dir(cwd):
                prj = store_read_project(cwd)
        if len(args) == 1:
            prj = args[0]

        if not prj:
            raise oscerr.WrongArgs('Please specify just the project')

        if opts.create:
            url = makeurl(apiurl, ['source', prj], query='cmd=createkey')
            f = http_POST(url)
        elif opts.extend:
            url = makeurl(apiurl, ['source', prj], query='cmd=extendkey')
            f = http_POST(url)
        elif opts.delete:
            url = makeurl(apiurl, ['source', prj, "_pubkey"])
            f = http_DELETE(url)
        else:
            while True:
                try:
                    url = makeurl(apiurl, ['source', prj, '_pubkey'])
                    if opts.sslcert:
                        url = makeurl(apiurl, ['source', prj, '_project', '_sslcert'], 'meta=1')
                    f = http_GET(url)
                    break
                except HTTPError as e:
                    l = prj.rsplit(':', 1)
                    # try key from parent project
                    if not opts.notraverse and len(l) > 1 and l[0] and l[1] and e.code == 404:
                        print('%s has no key, trying %s' % (prj, l[0]))
                        prj = l[0]
                    else:
                        raise

        while True:
            buf = f.read(16384)
            if not buf:
                break
            sys.stdout.write(decode_it(buf))

    @cmdln.option('-m', '--message',
                  help='add MESSAGE to changes (do not open an editor)')
    @cmdln.option('-F', '--file', metavar='FILE',
                  help='read changes message from FILE (do not open an editor)')
    @cmdln.option('-e', '--just-edit', action='store_true', default=False,
                  help='just open changes (cannot be used with -m)')
    def do_vc(self, subcmd, opts, *args):
        """${cmd_name}: Edit the changes file

        osc vc [-m MESSAGE|-e] [filename[.changes]|path [file_with_comment]]
        If no <filename> is given, exactly one *.changes or *.spec file has to
        be in the cwd or in path.

        The email address used in .changes file is read from BuildService
        instance, or should be defined in oscrc
        [https://api.opensuse.org/]
        user = login
        pass = password
        email = user@defined.email

        or can be specified via mailaddr environment variable.

        ${cmd_usage}
        ${cmd_option_list}
        """

        from subprocess import Popen
        if opts.message and opts.file:
            raise oscerr.WrongOptions('\'--message\' and \'--file\' are mutually exclusive')
        elif opts.message and opts.just_edit:
            raise oscerr.WrongOptions('\'--message\' and \'--just-edit\' are mutually exclusive')
        elif opts.file and opts.just_edit:
            raise oscerr.WrongOptions('\'--file\' and \'--just-edit\' are mutually exclusive')
        meego_style = False
        if not args:
            import glob, re
            try:
                fn_changelog = glob.glob('*.changes')[0]
                fp = open(fn_changelog)
                titleline = fp.readline()
                fp.close()
                if re.match('^\*\W+(.+\W+\d{1,2}\W+20\d{2})\W+(.+)\W+<(.+)>\W+(.+)$', titleline):
                    meego_style = True
            except IndexError:
                pass

        cmd_list = [conf.config['vc-cmd']]
        if meego_style:
            if not os.path.exists('/usr/bin/vc'):
                print('Error: you need meego-packaging-tools for /usr/bin/vc command', file=sys.stderr)
                return 1
            cmd_list = ['/usr/bin/vc']
        elif which(cmd_list[0]) is None:
            print('Error: vc (\'%s\') command not found' % cmd_list[0], file=sys.stderr)
            print('Install the build package from http://download.opensuse.org/repositories/openSUSE:/Tools/', file=sys.stderr)
            return 1

        if args and is_package_dir(args[0]):
            apiurl = store_read_apiurl(args[0])
        else:
            apiurl = self.get_api_url()

        if meego_style:
            if opts.message or opts.just_edit:
                print('Warning: to edit MeeGo style changelog, opts will be ignored.', file=sys.stderr)
        else:
            if opts.message:
                cmd_list.append("-m")
                cmd_list.append(opts.message)
            if opts.file:
                if len(args) > 1:
                    raise oscerr.WrongOptions('--file and file_with_comment are mutually exclusive')
                elif not os.path.isfile(opts.file):
                    raise oscerr.WrongOptions('\'%s\': is no file' % opts.file)
                args = list(args)
                if not args:
                    args.append('')
                args.append(opts.file)

            if opts.just_edit:
                cmd_list.append("-e")

            cmd_list.extend(args)

        vc_export_env(apiurl)
        vc = Popen(cmd_list)
        vc.wait()
        sys.exit(vc.returncode)

    @cmdln.option('-f', '--force', action='store_true',
                        help='forces removal of entire package and its files')
    def do_mv(self, subcmd, opts, source, dest):
        """${cmd_name}: Move SOURCE file to DEST and keep it under version control

        ${cmd_usage}
        ${cmd_option_list}
        """

        if not os.path.isfile(source):
            raise oscerr.WrongArgs("Source file '%s' does not exist or is not a file" % source)
        if not opts.force and os.path.isfile(dest):
            raise oscerr.WrongArgs("Dest file '%s' already exists" % dest)
        if os.path.isdir(dest):
            dest = os.path.join(dest, os.path.basename(source))
        src_pkg = findpacs([source])
        tgt_pkg = findpacs([dest])
        if not src_pkg:
            raise oscerr.NoWorkingCopy("Error: \"%s\" is not located in an osc working copy." % os.path.abspath(source))
        if not tgt_pkg:
            raise oscerr.NoWorkingCopy("Error: \"%s\" does not point to an osc working copy." % os.path.abspath(dest))

        os.rename(source, dest)
        try:
            tgt_pkg[0].addfile(os.path.basename(dest))
        except oscerr.PackageFileConflict:
            # file is already tracked
            pass
        src_pkg[0].delete_file(os.path.basename(source), force=opts.force)

    @cmdln.option('-d', '--delete', action='store_true',
                        help='delete option from config or reset option to the default)')
    @cmdln.option('-s', '--stdin', action='store_true',
                        help='indicates that the config value should be read from stdin')
    @cmdln.option('-p', '--prompt', action='store_true',
                        help='prompt for a value')
    @cmdln.option('--change-password', action='store_true',
                        help='Change password')
    @cmdln.option('--select-password-store', action='store_true',
                        help='Change the password store')
    @cmdln.option('--no-echo', action='store_true',
                        help='prompt for a value but do not echo entered characters')
    @cmdln.option('--dump', action='store_true',
                        help='dump the complete configuration (without \'pass\' and \'passx\' options)')
    @cmdln.option('--dump-full', action='store_true',
                        help='dump the complete configuration (including \'pass\' and \'passx\' options)')
    def do_config(self, subcmd, opts, *args):
        """${cmd_name}: get/set a config option

        Examples:
            osc config section option (get current value)
            osc config section option value (set to value)
            osc config section option --delete (delete option/reset to the default)
            osc config section --change-password (changes the password in section "section")
            (section is either an apiurl or an alias or 'general')
            osc config --dump (dump the complete configuration)

        ${cmd_usage}
        ${cmd_option_list}
        """
        prompt_value = 'Value: '
        if opts.change_password:
            opts.no_echo = True
            opts.prompt = True
            opts.select_password_store = True
            prompt_value = 'Password: '
            if len(args) != 1:
                raise oscerr.WrongArgs('--change-password only needs the apiurl')
            args = [args[0], 'pass']
        if len(args) < 2 and not (opts.dump or opts.dump_full):
            raise oscerr.WrongArgs('Too few arguments')
        elif opts.dump or opts.dump_full:
            cp = conf.get_configParser(conf.config['conffile'])
            for sect in cp.sections():
                print('[%s]' % sect)
                for opt in sorted(cp.options(sect)):
                    if sect == 'general' and opt in conf.api_host_options or \
                        sect != 'general' and not opt in conf.api_host_options:
                        continue
                    if opt in ('pass', 'passx') and not opts.dump_full:
                        continue
                    val = str(cp.get(sect, opt, raw=True))
                    # special handling for continuation lines
                    val = '\n '.join(val.split('\n'))
                    print('%s = %s' % (opt, val))
                print()
            return

        section, opt, val = args[0], args[1], args[2:]
        if len(val) and (opts.delete or opts.stdin or opts.prompt or opts.no_echo):
            raise oscerr.WrongOptions('Sorry, \'--delete\' or \'--stdin\' or \'--prompt\' or \'--no-echo\' ' \
                'and the specification of a value argument are mutually exclusive')
        elif (opts.prompt or opts.no_echo) and opts.stdin:
            raise oscerr.WrongOptions('Sorry, \'--prompt\' or \'--no-echo\' and  \'--stdin\' are mutually exclusive')
        elif opts.stdin:
            # strip lines
            val = [i.strip() for i in sys.stdin.readlines() if i.strip()]
            if not len(val):
                raise oscerr.WrongArgs('error: read empty value from stdin')
        elif opts.no_echo or opts.prompt:
            if opts.no_echo:
                import getpass
                inp = getpass.getpass(prompt_value).strip()
            else:
                inp = raw_input(prompt_value).strip()
            if not inp:
                raise oscerr.WrongArgs('error: no value was entered')
            val = [inp]
        creds_mgr_descr = None
        if opt == 'pass' and opts.select_password_store:
            creds_mgr_descr = conf.select_credentials_manager_descr()
        orig_opt = opt
        opt, newval = conf.config_set_option(section, opt, ' '.join(val), delete=opts.delete, update=True, creds_mgr_descr=creds_mgr_descr)
        if newval is None and opts.delete:
            print('\'%s\': \'%s\' got removed' % (section, opt))
        elif newval is None:
            print('\'%s\': \'%s\' is not set' % (section, opt))
        else:
            if orig_opt == 'pass':
                print('Password has been changed.')
            elif opts.no_echo:
                # supress value
                print('\'%s\': set \'%s\'' % (section, opt))
            else:
                print('\'%s\': \'%s\' is set to \'%s\'' % (section, opt, newval))

    def do_revert(self, subcmd, opts, *files):
        """${cmd_name}: Restore changed files or the entire working copy.

        Examples:
            osc revert <modified file(s)>
            osc revert .
        Note: this only works for package working copies

        ${cmd_usage}
        ${cmd_option_list}
        """
        pacs = findpacs(files)
        for p in pacs:
            if not len(p.todo):
                p.todo = p.filenamelist + p.to_be_added
            for f in p.todo:
                p.revert(f)

    @cmdln.option('--force-apiurl', action='store_true',
                  help='ask once for an apiurl and force this apiurl for all inconsistent projects/packages')
    def do_repairwc(self, subcmd, opts, *args):
        """${cmd_name}: try to repair an inconsistent working copy

        Examples:
            osc repairwc <path>

        Note: if <path> is omitted it defaults to '.' (<path> can be
              a project or package working copy)

        Warning: This command might delete some files in the storedir
        (.osc). Please check the state of the wc afterwards (via 'osc status').

        ${cmd_usage}
        ${cmd_option_list}
        """
        def get_apiurl(apiurls):
            print('No apiurl is defined for this working copy.\n' \
                'Please choose one from the following list (enter the number):')
            for i in range(len(apiurls)):
                print(' %d) %s' % (i, apiurls[i]))
            num = raw_input('> ')
            try:
                num = int(num)
            except ValueError:
                raise oscerr.WrongArgs('\'%s\' is not a number. Aborting' % num)
            if num < 0 or num >= len(apiurls):
                raise oscerr.WrongArgs('number \'%s\' out of range. Aborting' % num)
            return apiurls[num]

        args = parseargs(args)
        pacs = []
        apiurls = list(conf.config['api_host_options'].keys())
        apiurl = ''
        for i in args:
            if is_project_dir(i):
                try:
                    prj = Project(i, getPackageList=False)
                except oscerr.WorkingCopyInconsistent as e:
                    if '_apiurl' in e.dirty_files and (not apiurl or not opts.force_apiurl):
                        apiurl = get_apiurl(apiurls)
                    prj = Project(i, getPackageList=False, wc_check=False)
                    prj.wc_repair(apiurl)
                for p in prj.pacs_have:
                    if p in prj.pacs_broken:
                        continue
                    try:
                        Package(os.path.join(i, p))
                    except oscerr.WorkingCopyInconsistent:
                        pacs.append(os.path.join(i, p))
            elif is_package_dir(i):
                pacs.append(i)
            else:
                print('\'%s\' is neither a project working copy ' \
                    'nor a package working copy' % i, file=sys.stderr)
        for pdir in pacs:
            try:
                p = Package(pdir)
            except oscerr.WorkingCopyInconsistent as e:
                if '_apiurl' in e.dirty_files and (not apiurl or not opts.force_apiurl):
                    apiurl = get_apiurl(apiurls)
                p = Package(pdir, wc_check=False)
                p.wc_repair(apiurl)
                print('done. Please check the state of the wc (via \'osc status %s\').' % i)
            else:
                print('osc: working copy \'%s\' is not inconsistent' % i, file=sys.stderr)

    @cmdln.option('-n', '--dry-run', action='store_true',
                  help='print the results without actually removing a file')
    def do_clean(self, subcmd, opts, *args):
        """${cmd_name}: removes all untracked files from the package working copy

        Examples:
            osc clean <path>

        Note: if <path> is omitted it defaults to '.' (<path> has to
              be a package working copy)

        Warning: This command removes all files with status '?'.

        ${cmd_usage}
        ${cmd_option_list}
        """
        pacs = parseargs(args)
        # do a sanity check first
        for pac in pacs:
            if not is_package_dir(pac):
                raise oscerr.WrongArgs('\'%s\' is no package working copy' % pac)
        for pdir in pacs:
            p = Package(pdir)
            pdir = getTransActPath(pdir)
            todo = [fname for st, fname in p.get_status() if st == '?']
            for fname in p.excluded:
                # there might be some rare cases, where an excluded file has
                # not state '?'
                if os.path.isfile(fname) and p.status(fname) == '?':
                    todo.append(fname)
            for filename in todo:
                print('Removing: %s' % os.path.join(pdir, filename))
                if not opts.dry_run:
                    os.unlink(os.path.join(p.absdir, filename))

    @cmdln.option('-c', '--comment',
            help='comment text', metavar='COMMENT')
    @cmdln.option('-p', '--parent',
            help='reply to comment with parent id', metavar='PARENT')
    def do_comment(self, subcmd, opts, *args):
        """${cmd_name}: List / create / delete comments

        On create:
            If -p is given a reply to the ID is created. Otherwise
            a toplevel comment is created.
            If -c is not given the default editor will be opened and
            you can type your comment

        usage:
            osc comment list package PROJECT PACKAGE
            osc comment list project PROJECT
            osc comment list request REQUEST_ID

            osc comment create [-p PARENT_ID] [-c COMMENT] package PROJECT PACKAGE
            osc comment create [-p PARENT_ID] [-c COMMENT] project PROJECT
            osc comment create [-p PARENT_ID] [-c COMMENT] request REQUEST_ID

            osc comment delete ID

        """

        comment = None
        args = slash_split(args)
        apiurl = self.get_api_url()

        if len(args) < 2:
            raise oscerr.WrongArgs('Incorrect number of arguments.\n\n' \
                  + self.get_cmd_help('comment'))

        cmds = ['list', 'create', 'delete']
        if args[0] not in cmds:
            raise oscerr.WrongArgs('Unknown comment action %s. Choose one of %s.' \
                                                % (args[0], ', '.join(cmds)))

        comment_targets = ['package', 'project', 'request']
        if args[0] != 'delete' and args[1] not in comment_targets:
            raise oscerr.WrongArgs('Unknown comment target %s. Choose one of %s.' \
                                                % (args[1], ', '.join(comment_targets)))

        if args[1] == 'package' and len(args) != 4:
            raise oscerr.WrongArgs('Please use PROJECT PACKAGE')
        elif args[1] == 'project' and len(args) != 3:
            raise oscerr.WrongArgs('Please use PROJECT')
        elif args[1] == 'request' and len(args) != 3:
            raise oscerr.WrongArgs('Please use REQUEST')
        elif args[0] == 'delete' and len(args) != 2:
            raise oscerr.WrongArgs('Please use COMMENT_ID')
        if not opts.comment and args[0] == 'create':
            comment = edit_text()
        else:
            comment = opts.comment

        if args[0] == 'list':
            print_comments(apiurl, args[1], *args[2:])
        elif args[0] == 'create':
            result = create_comment(apiurl, args[1], comment,
                                    *args[2:], parent=opts.parent)
            print(result)
        elif args[0] == 'delete':
            result = delete_comment(apiurl, args[1])
            print(result)

    def _load_plugins(self):
        plugin_dirs = [
            '/usr/lib/osc-plugins',
            '/usr/local/lib/osc-plugins',
            '/var/lib/osc-plugins',  # Kept for backward compatibility
            os.path.expanduser('~/.osc-plugins')]
        for plugin_dir in plugin_dirs:
            if not os.path.isdir(plugin_dir):
                continue
            sys.path.append(plugin_dir)
            for extfile in os.listdir(plugin_dir):
                if not extfile.endswith('.py'):
                    continue
                try:
                    modname = os.path.splitext(extfile)[0]
                    mod = imp.load_source(modname, os.path.join(plugin_dir, extfile))
                    # restore the old exec semantic
                    mod.__dict__.update(globals())
                    for name in dir(mod):
                        data = getattr(mod, name)
                        # Add all functions (which are defined in the imported module)
                        # to the class (filtering only methods which start with "do_"
                        # breaks the old behavior).
                        # Also add imported modules (needed for backward compatibility).
                        # New plugins should not use "self.<imported modname>.<something>"
                        # to refer to the imported module. Instead use
                        # "<imported modname>.<something>".
                        if (inspect.isfunction(data) and inspect.getmodule(data) == mod
                            or inspect.ismodule(data)):
                            setattr(self.__class__, name, data)
                except (SyntaxError, NameError, ImportError) as e:
                    if (os.environ.get('OSC_PLUGIN_FAIL_IGNORE')):
                        print("%s: %s\n" % (os.path.join(plugin_dir, extfile), e), file=sys.stderr)
                    else:
                        import traceback
                        traceback.print_exc(file=sys.stderr)
                        print('\n%s: %s' % (os.path.join(plugin_dir, extfile), e), file=sys.stderr)
                        print("\n Try 'env OSC_PLUGIN_FAIL_IGNORE=1 osc ...'", file=sys.stderr)
                        sys.exit(1)

# fini!
###############################################################################

# vim: sw=4 et
