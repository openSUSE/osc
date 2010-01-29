# vim: sw=4 et

# Copyright (C) 2006 Novell Inc.  All rights reserved.
# This program is free software; it may be used, copied, modified
# and distributed under the terms of the GNU General Public Licence,
# either version 2, or version 3 (at your option).


from core import *
import cmdln
import conf
import oscerr

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
 * http://www.opensuse.org/Build_Service_Tutorial
 * http://www.opensuse.org/Build_Service/CLI
.PP
You can modify osc commands, or roll you own, via the plugin API:
 * http://www.opensuse.org/Build_Service/osc_plugins
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
    * http://www.opensuse.org/Build_Service_Tutorial
    * http://www.opensuse.org/Build_Service/CLI

    You can modify osc commands, or roll you own, via the plugin API:
    * http://www.opensuse.org/Build_Service/osc_plugins
    """
    name = 'osc'
    conf = None

    man_header = MAN_HEADER
    man_footer = MAN_FOOTER

    def __init__(self, *args, **kwargs):
        cmdln.Cmdln.__init__(self, *args, **kwargs)
        cmdln.Cmdln.do_help.aliases.append('h')

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
                      help='debug HTTP traffic')
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
                            override_traceback = self.options.traceback,
                            override_post_mortem = self.options.post_mortem,
                            override_no_keyring = self.options.no_keyring,
                            override_no_gnome_keyring = self.options.no_gnome_keyring,
                            override_verbose = self.options.verbose)
        except oscerr.NoConfigfile, e:
            print >>sys.stderr, e.msg
            print >>sys.stderr, 'Creating osc configuration file %s ...' % e.file
            import getpass
            config = {}
            config['user'] = raw_input('Username: ')
            config['pass'] = getpass.getpass()
            if self.options.apiurl:
                config['apiurl'] = self.options.apiurl

            conf.write_initial_config(e.file, config)
            print >>sys.stderr, 'done'
            if try_again: self.postoptparse(try_again = False)
        except oscerr.ConfigMissingApiurl, e:
            print >>sys.stderr, e.msg
            import getpass
            user = raw_input('Username: ')
            passwd = getpass.getpass()
            conf.add_section(e.file, e.url, user, passwd)
            if try_again: self.postoptparse(try_again = False)

        self.options.verbose = conf.config['verbose']


    def get_cmd_help(self, cmdname):
        doc = self._get_cmd_handler(cmdname).__doc__
        doc = self._help_reindent(doc)
        doc = self._help_preprocess(doc, cmdname)
        doc = doc.rstrip() + '\n' # trim down trailing space
        return self._str(doc)


    # overridden from class Cmdln() to use config variables in help texts
    def _help_preprocess(self, help, cmdname):
        help = cmdln.Cmdln._help_preprocess(self, help, cmdname)
        return help % conf.config


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

        if not package:
            init_project_dir(conf.config['apiurl'], os.curdir, project)
            print 'Initializing %s (Project: %s)' % (os.curdir, project)
        else:
            init_package_dir(conf.config['apiurl'], project, package, os.path.curdir)
            print 'Initializing %s (Project: %s, Package: %s)' % (os.curdir, project, package)

    @cmdln.alias('ls')
    @cmdln.alias('ll')
    @cmdln.alias('lL')
    @cmdln.alias('LL')
    @cmdln.option('-a', '--arch', metavar='ARCH',
                        help='specify architecture')
    @cmdln.option('-R', '--revision', metavar='REVISION',
                        help='specify revision')
    @cmdln.option('-r', '--repo', metavar='REPO',
                        help='specify repository')
    @cmdln.option('-b', '--binaries', action='store_true',
                        help='list built binaries, instead of sources')
    @cmdln.option('-v', '--verbose', action='store_true',
                        help='print extra information')
    @cmdln.option('-l', '--long', action='store_true', dest='verbose',
                        help='print extra information')
    @cmdln.option('-e', '--expand', action='store_true',
                        help='expand linked package')
    def do_list(self, subcmd, opts, *args):
        """${cmd_name}: List existing content on the server

        This command is used to list sources, or binaries (when used with the
        --binaries option). When using the --binaries option, --repo
        and --arch can be used to limit output to specific repos
        and/or architectures.

        Examples:
           ls                         # list all projects
           ls Apache                  # list packages in a project
           ls -b Apache               # list all binaries of a project
           ls Apache apache2          # list source files of package of a project
           ls Apache apache2 <file>   # list <file> if this file exists
           ls -v Apache apache2       # verbosely list source files of package
           ls -l Apache apache2       # verbosely list source files of package
           ll Apache apache2          # verbosely list source files of package
           LL Apache apache2          # verbosely list source files of expanded link

        With --verbose, the following fields will be shown for each item:
           MD5 hash of file
           Revision number of the last commit
           Size (in bytes)
           Date and time of the last commit

        ${cmd_usage}
        ${cmd_option_list}
        """

        apiurl = conf.config['apiurl']
        args = slash_split(args)
        if subcmd == 'll':
            opts.verbose = True
        if subcmd == 'lL' or subcmd == 'LL':
            opts.verbose = True
            opts.expand = True

        project = None
        package = None
        if len(args) == 1:
            project = args[0]
            package = None
        elif len(args) == 2 or len(args) == 3:
            project = args[0]
            package = args[1]
            fname = None
            if len(args) == 3:
                fname = args[2]
        elif len(args) > 3:
            raise oscerr.WrongArgs('Too many arguments')

        if opts.binaries and opts.expand:
            raise oscerr.WrongOptions('Sorry, --binaries and --expand are mutual exclusive.')

        # list binaries
        if opts.binaries:
            # ls -b toplevel doesn't make sense, so use info from
            # current dir if available
            if len(args) == 0:
                dir = os.getcwd()
                if is_project_dir(dir):
                    project = store_read_project(dir)
                    apiurl = store_read_apiurl(dir)
                elif is_package_dir(dir):
                    project = store_read_project(dir)
                    package = store_read_package(dir)
                    apiurl = store_read_apiurl(dir)

            if not project:
                raise oscerr.WrongArgs('There are no binaries to list above project level.')
            if opts.revision:
                raise oscerr.WrongOptions('Sorry, the --revision option is not supported for binaries.')

            repos = []

            if opts.repo and opts.arch:
                repos.append(Repo(opts.repo, opts.arch))
            elif opts.repo and not opts.arch:
                for repo in get_repos_of_project(apiurl, project):
                    if repo.name == opts.repo:
                        repos.append(repo)
            elif opts.arch and not opts.repo:
                for repo in get_repos_of_project(apiurl, project):
                    if repo.arch == opts.arch:
                        repos.append(repo)
            else:
                repos = get_repos_of_project(apiurl, project)

            results = []
            for repo in repos:
                results.append((repo, get_binarylist(apiurl, project, repo.name, repo.arch, package=package, verbose=opts.verbose)))

            for result in results:
                indent = ''
                if len(results) > 1:
                    print '%s/%s' % (result[0].name, result[0].arch)
                    indent = ' '

                if opts.verbose:
                    for f in result[1]:
                        print "%9d %s %-40s" % (f.size, shorttime(f.mtime), f.name)
                else:
                    for f in result[1]:
                        print indent+f

        # list sources
        elif not opts.binaries:
            if not args:
                print '\n'.join(meta_get_project_list(conf.config['apiurl']))

            elif len(args) == 1:
                if opts.verbose:
                    if self.options.verbose:
                        print >>sys.stderr, 'Sorry, the --verbose option is not implemented for projects.'
                if opts.expand:
                    raise oscerr.WrongOptions('Sorry, the --expand option is not implemented for projects.')

                print '\n'.join(meta_get_packagelist(conf.config['apiurl'], project))

            elif len(args) == 2 or len(args) == 3:
                l = meta_get_filelist(conf.config['apiurl'],
                                      project,
                                      package,
                                      verbose=opts.verbose,
                                      expand=opts.expand,
                                      revision=opts.revision)
                if opts.verbose:
                    out = [ '%s %7s %9d %s %s' % (i.md5, i.rev, i.size, shorttime(i.mtime), i.name) \
                            for i in l if not fname or fname == i.name ]
                    if len(out) == 0:
                        if fname:
                            print 'file \'%s\' does not exist' % fname
                    else:
                        print '\n'.join(out)
                else:
                    if fname:
                        if fname in l:
                            print fname
                        else:
                            print 'file \'%s\' does not exist' % fname
                    else:
                        print '\n'.join(l)


    @cmdln.option('-f', '--force', action='store_true',
                        help='force generation of new patchinfo file')
    @cmdln.option('--force-update', action='store_true',
                        help='drops away collected packages from an already built patch and let it collect again')
    def do_patchinfo(self, subcmd, opts, *args):
        """${cmd_name}: Generate and edit a patchinfo file.

        A patchinfo file describes the packages for an update and the kind of
        problem it solves.

        Examples:
            osc patchinfo
            osc patchinfo PATCH_NAME
        ${cmd_option_list}
        """

        project_dir = localdir = os.getcwd()
        if is_project_dir(localdir):
            project = store_read_project(localdir)
            apiurl = store_read_apiurl(localdir)
        else:
            sys.exit('This command must be called in a checked out project.')
        patchinfo = None
        for p in meta_get_packagelist(apiurl, project):
            if p.startswith("_patchinfo:"):
                patchinfo = p
        
        if opts.force or not patchinfo:
            print "Creating initial patchinfo..."
            query='cmd=createpatchinfo'
            if args and args[0]:
               query += "&name=" + args[0]
            url = makeurl(apiurl, ['source', project], query=query)
            f = http_POST(url)
       	    for p in meta_get_packagelist(apiurl, project):
       	        if p.startswith("_patchinfo:"):
       	            patchinfo = p

        if not os.path.exists(project_dir + "/" + patchinfo):
            checkout_package(apiurl, project, patchinfo, prj_dir=project_dir)

        if sys.platform[:3] != 'win':
            editor = os.getenv('EDITOR', default='vim')
        else:
            editor = os.getenv('EDITOR', default='notepad')
        subprocess.call('%s %s' % (editor, project_dir + "/" + patchinfo + "/_patchinfo"), shell=True)


    @cmdln.option('-a', '--attribute', metavar='ATTRIBUTE',
                        help='affect only a given attribute')
    @cmdln.option('--attribute-defaults', action='store_true',
                        help='include defined attribute defaults')
    @cmdln.option('--attribute-project', action='store_true',
                        help='include project values, if missing in packages ')
    @cmdln.option('-F', '--file', metavar='FILE',
                        help='read metadata from FILE, instead of opening an editor. '
                        '\'-\' denotes standard input. ')
    @cmdln.option('-e', '--edit', action='store_true',
                        help='edit metadata')
    @cmdln.option('-c', '--create', action='store_true',
                        help='create attribute without values')
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
        pattern denotes installation patterns defined for a project.

        To list patterns, use 'osc meta pattern PRJ'. An additional argument
        will be the pattern file to view or edit.

        With the --edit switch, the metadata can be edited. Per default, osc
        opens the program specified by the environmental variable EDITOR with a
        temporary file. Alternatively, content to be saved can be supplied via
        the --file switch. If the argument is '-', input is taken from stdin:
        osc meta prjconf home:user | sed ... | osc meta prjconf home:user -F -

        When trying to edit a non-existing resource, it is created implicitly.


        Examples:
            osc meta prj PRJ
            osc meta pkg PRJ PKG
            osc meta pkg PRJ PKG -e
            osc meta attribute PRJ [PKG [SUBPACKAGE]] [--attribute ATTRIBUTE] [--create|--delete|--set [value_list]]

        Usage:
            osc meta <prj|pkg|prjconf|user|pattern|attribute> ARGS...
            osc meta <prj|pkg|prjconf|user|pattern|attribute> -e|--edit ARGS...
            osc meta <prj|pkg|prjconf|user|pattern|attribute> -F|--file ARGS...
            osc meta pattern --delete PRJ PATTERN
        ${cmd_option_list}
        """

        args = slash_split(args)

        if not args or args[0] not in metatypes.keys():
            raise oscerr.WrongArgs('Unknown meta type. Choose one of %s.' \
                                               % ', '.join(metatypes))

        cmd = args[0]
        del args[0]

        if cmd in ['pkg']:
            min_args, max_args = 2, 2
        elif cmd in ['pattern']:
            min_args, max_args = 1, 2
        elif cmd in ['attribute']:
            min_args, max_args = 1, 3
        else:
            min_args, max_args = 1, 1
        if len(args) < min_args:
            raise oscerr.WrongArgs('Too few arguments.')
        if len(args) > max_args:
            raise oscerr.WrongArgs('Too many arguments.')

        # specific arguments
        attributepath = []
        if cmd == 'prj':
            project = args[0]
        elif cmd == 'pkg':
            project, package = args[0:2]
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
        elif cmd == 'prjconf':
            project = args[0]
        elif cmd == 'user':
            user = args[0]
        elif cmd == 'pattern':
            project = args[0]
            if len(args) > 1:
                pattern = args[1]
            else:
                pattern = None
                # enforce pattern argument if needed
                if opts.edit or opts.file:
                    raise oscerr.WrongArgs('A pattern file argument is required.')

        # show
        if not opts.edit and not opts.file and not opts.delete and not opts.create and not opts.set:
            if cmd == 'prj':
                sys.stdout.write(''.join(show_project_meta(conf.config['apiurl'], project)))
            elif cmd == 'pkg':
                sys.stdout.write(''.join(show_package_meta(conf.config['apiurl'], project, package)))
            elif cmd == 'attribute':
                sys.stdout.write(''.join(show_attribute_meta(conf.config['apiurl'], project, package, subpackage, opts.attribute, opts.attribute_defaults, opts.attribute_project)))
            elif cmd == 'prjconf':
                sys.stdout.write(''.join(show_project_conf(conf.config['apiurl'], project)))
            elif cmd == 'user':
                r = get_user_meta(conf.config['apiurl'], user)
                if r:
                    sys.stdout.write(''.join(r))
            elif cmd == 'pattern':
                if pattern:
                    r = show_pattern_meta(conf.config['apiurl'], project, pattern)
                    if r:
                        sys.stdout.write(''.join(r))
                else:
                    r = show_pattern_metalist(conf.config['apiurl'], project)
                    if r:
                        sys.stdout.write('\n'.join(r) + '\n')

        # edit
        if opts.edit and not opts.file:
            if cmd == 'prj':
                edit_meta(metatype='prj',
                          edit=True,
                          path_args=quote_plus(project),
                          template_args=({
                                  'name': project,
                                  'user': conf.config['user']}))
            elif cmd == 'pkg':
                edit_meta(metatype='pkg',
                          edit=True,
                          path_args=(quote_plus(project), quote_plus(package)),
                          template_args=({
                                  'name': package,
                                  'user': conf.config['user']}))
            elif cmd == 'prjconf':
                edit_meta(metatype='prjconf',
                          edit=True,
                          path_args=quote_plus(project),
                          template_args=None)
            elif cmd == 'user':
                edit_meta(metatype='user',
                          edit=True,
                          path_args=(quote_plus(user)),
                          template_args=({'user': user}))
            elif cmd == 'pattern':
                edit_meta(metatype='pattern',
                          edit=True,
                          path_args=(project, pattern),
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
            d = '<attributes><attribute namespace=\'%s\' name=\'%s\' >%s</attribute></attributes>' % (aname[0], aname[1], values)
            url = makeurl(conf.config['apiurl'], attributepath)
            for data in streamfile(url, http_POST, data=d):
                sys.stdout.write(data)

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
                          path_args=quote_plus(project))
            elif cmd == 'pkg':
                edit_meta(metatype='pkg',
                          data=f,
                          edit=opts.edit,
                          path_args=(quote_plus(project), quote_plus(package)))
            elif cmd == 'prjconf':
                edit_meta(metatype='prjconf',
                          data=f,
                          edit=opts.edit,
                          path_args=quote_plus(project))
            elif cmd == 'user':
                edit_meta(metatype='user',
                          data=f,
                          edit=opts.edit,
                          path_args=(quote_plus(user)))
            elif cmd == 'pattern':
                edit_meta(metatype='pattern',
                          data=f,
                          edit=opts.edit,
                          path_args=(project, pattern))


        # delete
        if opts.delete:
            path = metatypes[cmd]['path']
            if cmd == 'pattern':
                path = path % (project, pattern)
                u = makeurl(conf.config['apiurl'], [path])
                http_DELETE(u)
            elif cmd == 'attribute':
                if not opts.attribute:
                    raise oscerr.WrongOptions('no attribute given to create')
                attributepath.append(opts.attribute)
                u = makeurl(conf.config['apiurl'], attributepath)
                for data in streamfile(u, http_DELETE):
                    sys.stdout.write(data)
            else:
                raise oscerr.WrongOptions('The --delete switch is only for pattern metadata or attributes.')


    @cmdln.option('-m', '--message', metavar='TEXT',
                  help='specify message TEXT')
    @cmdln.option('-r', '--revision', metavar='REV',
                  help='for "create", specify a certain source revision ID (the md5 sum)')
    @cmdln.option('-s', '--supersede', metavar='SUPERSEDE',
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
    @cmdln.option('-d', '--diff', action='store_true',
                  help='show diff only instead of creating the actual request')
    @cmdln.option('--yes', action='store_true',
                  help='proceed without asking.')
    @cmdln.alias("sr")
    @cmdln.alias("submitreq")
    @cmdln.alias("submitpac")
    def do_submitrequest(self, subcmd, opts, *args):
        """${cmd_name}: Create request to submit source into another Project

        [See http://en.opensuse.org/Build_Service/Collaboration for information
        on this topic.]

        See the "request" command for showing and modifing existing requests.

        usage:
            osc submitreq [OPTIONS]
            osc submitreq [OPTIONS] DESTPRJ [DESTPKG]
            osc submitreq [OPTIONS] SOURCEPRJ SOURCEPKG DESTPRJ [DESTPKG]
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

        args = slash_split(args)

        # remove this block later again
        oldcmds = ['create', 'list', 'log', 'show', 'decline', 'accept', 'delete', 'revoke']
        if args and args[0] in oldcmds:
            print "************************************************************************"
            print "* WARNING: It looks that you are using this command with a             *"
            print "*          deprecated syntax.                                          *"
            print "*          Please run \"osc sr --help\" and \"osc rq --help\"              *"
            print "*          to see the new syntax.                                      *"
            print "************************************************************************"
            if args[0] == 'create':
                args.pop(0)
            else:
                sys.exit(1)

        if len(args) > 4:
            raise oscerr.WrongArgs('Too many arguments.')

        if len(args) > 0 and len(args) <= 2 and is_project_dir(os.getcwd()):
            sys.exit('osc submitrequest from project directory is only working without target specs and for source linked files\n')

        apiurl = conf.config['apiurl']

        if len(args) == 0 and is_project_dir(os.getcwd()):
            import cgi
            # submit requests for multiple packages are currently handled via multiple requests
            # They could be also one request with multiple actions, but that avoids to accepts parts of it.
            project = store_read_project(os.curdir)
            apiurl = store_read_apiurl(os.curdir)

            sr_ids = []
            pi = []
            pac = []
            targetprojects = []
            # loop via all packages for checking their state
            for p in meta_get_packagelist(apiurl, project):
                if p.startswith("_patchinfo:"):
                   pi.append(p)
                else:
                   # get _link info from server, who knows about the local state ...
                   u = makeurl(apiurl, ['source', project, p])
                   f = http_GET(u)
                   root = ET.parse(f).getroot()
                   linkinfo = root.find('linkinfo')
                   if linkinfo == None:
                       print "Package ", p, " is not a source link."
                       sys.exit("This is currently not supported.")
                   if linkinfo.get('error'):
                       print "Package ", p, " is a broken source link."
                       sys.exit("Please fix this first")
                   t = linkinfo.get('project')
                   if t:
                       if len(root.findall('entry')) > 1: # This is not really correct, but should work mostly
                                                          # Real fix is to ask the api if sources are modificated
                                                          # but there is no such call yet.
                          targetprojects.append(t)
                          pac.append(p)
                          print "Submitting package ", p
                       else:
                          print "  Skipping package ", p
                   else:
                       print "Skipping package ", p,  " since it is a source link pointing inside to the project."

            if not opts.yes:
                if pi:
                   print "Submitting patchinfo ", ', '.join(pi), " to ", ', '.join(targetprojects)
                print "\nEverything fine? Can we create the requests ? [y/n]"
                if sys.stdin.read(1) != "y":
                   sys.exit("Aborted...")

            # loop via all packages to do the action
            for p in pac:
                result = create_submit_request(apiurl, project, p)
                if not result:
#                   sys.exit(result)
                   sys.exit("submit request creation failed")
                sr_ids.append(result)

            # create submit requests for all found patchinfos
            actionxml=""
            options_block=""
            if src_update:
                options_block="""<options><sourceupdate>%s</sourceupdate></options> """ % (src_update)

            for p in pi:
                for t in targetprojects:
                    s = """<action type="submit"> <source project="%s" package="%s" /> <target project="%s" package="%s" /> %s </action>"""  % \
                           (project, p, t, p, options_block)
                    actionxml += s

            if actionxml != "":
                xml = """<request> %s <state name="new"/> <description>%s</description> </request> """ % \
                      (actionxml, cgi.escape(opts.message or ""))
                u = makeurl(apiurl, ['request'], query='cmd=create')
                f = http_POST(u, data=xml)
         
                root = ET.parse(f).getroot()
                sr_ids.append(root.get('id'))

            print "Requests created: ",
            for i in sr_ids:
               print i,
            sys.exit('Successfull finished')

        elif len(args) <= 2:
            # try using the working copy at hand
            p = findpacs(os.curdir)[0]
            src_project = p.prjname
            src_package = p.name
            apiurl = p.apiurl
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
                print 'Your working copy has local modifications.'
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
                devloc = show_develproject(apiurl, dst_project, dst_package)
            except urllib2.HTTPError:
                print >>sys.stderr, """\
Warning: failed to fetch meta data for '%s' package '%s' (new package?) """ \
                    % (dst_project, dst_package)
                pass

            if devloc and \
               dst_project != devloc and \
               src_project != devloc:
                print """\
Sorry, but a different project, %s, is defined as the place where development
of the package %s primarily takes place.
Please submit there instead, or use --nodevelproject to force direct submission.""" \
                % (devloc, dst_package)
                sys.exit(1)
        if opts.diff:
            print 'old: %s/%s\nnew: %s/%s' %(dst_project, dst_package, src_project, src_package)
            rdiff = server_diff(apiurl,
                                dst_project, dst_package, None,
                                src_project, src_package, None, True)
            print rdiff
        else:
            reqs = get_request_list(apiurl, dst_project, dst_package, req_type='submit')
            user = conf.get_apiurl_usr(apiurl)
            myreqs = [ i for i in reqs if i.state.who == user ]
            repl = ''
            if len(myreqs) > 0:
                print 'You already created the following submit request: %s.' % \
                      ', '.join([str(i.reqid) for i in myreqs ])
                repl = raw_input('Revoke the old requests? (y/N) ')

            if not opts.message:
                opts.message = edit_message()

            result = create_submit_request(apiurl,
                                           src_project, src_package,
                                           dst_project, dst_package,
                                           opts.message, orev=opts.revision, src_update=src_update)
            if repl == 'y':
                for req in myreqs:
                    change_request_state(apiurl, str(req.reqid), 'superseded',
                                         'superseded by %s' % result, result)

            if opts.supersede:
                r = change_request_state(conf.config['apiurl'],
                        opts.supersede, 'superseded', opts.message or '', result)

            print 'created request id', result


    @cmdln.option('-m', '--message', metavar='TEXT',
                  help='specify message TEXT')
    @cmdln.alias("dr")
    @cmdln.alias("deletereq")
    def do_deleterequest(self, subcmd, opts, *args):
        """${cmd_name}: Create request to delete a package or project


        usage:
            osc deletereq [-m TEXT] PROJECT [PACKAGE]
        ${cmd_option_list}
        """

        args = slash_split(args)

        if len(args) < 1:
            raise oscerr.WrongArgs('Please specify at least a project.')
        if len(args) > 2:
            raise oscerr.WrongArgs('Too many arguments.')

        apiurl = conf.config['apiurl']

        project = args[0]
        package = None
        if len(args) > 1:
            package = args[1]

        if not opts.message:
            opts.message = edit_message()

        result = create_delete_request(apiurl, project, package, opts.message)
        print result


    @cmdln.option('-m', '--message', metavar='TEXT',
                  help='specify message TEXT')
    @cmdln.alias("cr")
    @cmdln.alias("changedevelreq")
    def do_changedevelrequest(self, subcmd, opts, *args):
        """${cmd_name}: Create request to change the devel package definition.

        [See http://en.opensuse.org/Build_Service/Collaboration for information
        on this topic.]

        See the "request" command for showing and modifing existing requests.

        osc changedevelrequest PROJECT PACKAGE DEVEL_PROJECT [DEVEL_PACKAGE]
        """

        if len(args) > 4:
            raise oscerr.WrongArgs('Too many arguments.')
        if len(args) < 3:
            raise oscerr.WrongArgs('Too few arguments.')

        apiurl = conf.config['apiurl']

        devel_project = args[2]
        project = args[0]
        package = args[1]
        devel_package = package
        if len(args) > 3:
            devel_package = args[3]

        if not opts.message:
            opts.message = edit_message()

        result = create_change_devel_request(apiurl,
                                       devel_project, devel_package,
                                       project, package,
                                       opts.message)
        print result


    @cmdln.option('-d', '--diff', action='store_true',
                  help='generate a diff')
    @cmdln.option('-u', '--unified', action='store_true',
                  help='output the diff in the unified diff format')
    @cmdln.option('-m', '--message', metavar='TEXT',
                  help='specify message TEXT')
    @cmdln.option('-t', '--type', metavar='TYPE',
                  help='limit to requests which contain a given action type (submit/delete/change_devel)')
    @cmdln.option('-a', '--all', action='store_true',
                        help='all states. Same as\'-s all\'')
    @cmdln.option('-s', '--state', default='',  # default is 'all' if no args given, 'new' otherwise
                        help='only list requests in one of the comma separated given states (new/accepted/revoked/declined) or "all" [default=new, or all, if no args given]')
    @cmdln.option('-D', '--days', metavar='DAYS',
                        help='only list requests in state "new" or changed in the last DAYS. [default=%(request_list_days)s]')
    @cmdln.option('-U', '--user', metavar='USER',
                        help='same as -M, but for the specified USER')
    @cmdln.option('-b', '--brief', action='store_true', default=False,
                        help='print output in list view as list subcommand')
    @cmdln.option('-M', '--mine', action='store_true',
                        help='only show requests created by yourself')
    @cmdln.option('-B', '--bugowner', action='store_true',
                        help='also show requests about packages where I am bugowner')
    @cmdln.alias("rq")
    @cmdln.alias("review")
    def do_request(self, subcmd, opts, *args):
        """${cmd_name}: Show and modify requests

        [See http://en.opensuse.org/Build_Service/Collaboration for information
        on this topic.]

        This command shows and modifies existing requests. To create new requests
        you need to call one of the following:
          osc submitrequest
          osc deleterequest
          osc changedevelrequest
        To send low level requests to the buildservice API, use:
          osc api

        This command has the following sub commands:

        "list" lists open requests attached to a project or package or person.
        Uses the project/package of the current directory if none of
        -M, -U USER, project/package are given.

        "log" will show the history of the given ID

        "show" will show the request itself, and generate a diff for review, if
        used with the --diff option. The keyword show can be omitted if the ID is numeric.

        "decline" will change the request state to "declined" and append a
        message that you specify with the --message option.

        "wipe" will permanently delete a request.

        "revoke" will set the request state to "revoked" and append a
        message that you specify with the --message option.

        "accept" will change the request state to "accepted" and will trigger
        the actual submit process. That would normally be a server-side copy of
        the source package to the target package.

        "checkout" will checkout the request's source package. This only works for "submit" requests.

        usage:
            osc request list [-M] [-U USER] [-s state] [-D DAYS] [-t type] [-B] [PRJ [PKG]]
            osc request log ID
            osc request [show] [-d] [-b] ID
            osc request accept [-m TEXT] ID
            osc request decline [-m TEXT] ID
            osc request revoke [-m TEXT] ID
            osc request wipe ID
            osc request checkout/co ID
            osc review accept [-m TEXT] ID
            osc review decline [-m TEXT] ID
        ${cmd_option_list}
        """

        args = slash_split(args)

        if opts.all and opts.state:
            raise oscerr.WrongOptions('Sorry, the options --all and --state ' \
                     'are mutually exclusive.')
        if opts.mine and opts.user:
            raise oscerr.WrongOptions('Sorry, the options --user and --mine ' \
                     'are mutually exclusive.')

        if not args:
            args = [ 'list' ]
            opts.mine = 1
            if opts.state == '':
                opts.state = 'all'

        if opts.state == '':
            opts.state = 'new'

        cmds = ['list', 'log', 'show', 'decline', 'accept', 'wipe', 'revoke', 'checkout', 'co', 'help']
        if not args or args[0] not in cmds:
            raise oscerr.WrongArgs('Unknown request action %s. Choose one of %s.' \
                                               % (args[0],', '.join(cmds)))

        cmd = args[0]
        del args[0]

        if cmd == 'help':
            return self.do_help(['help', 'request'])

        if cmd in ['wipe']:
            min_args, max_args = 1, 1
        elif cmd in ['list']:
            min_args, max_args = 0, 2
        else:
            min_args, max_args = 1, 1
        if len(args) < min_args:
            raise oscerr.WrongArgs('Too few arguments.')
        if len(args) > max_args:
            raise oscerr.WrongArgs('Too many arguments.')

        apiurl = conf.config['apiurl']

        if cmd == 'list':
            package = None
            project = None
            if len(args) > 0:
                project = args[0]
            elif not opts.mine and not opts.user:
                try:
                    project = store_read_project(os.curdir)
                    apiurl = store_read_apiurl(os.curdir)
                    package = store_read_package(os.curdir)
                except oscerr.NoWorkingCopy:
                    pass

            if len(args) > 1:
                package = args[1]
        elif cmd in ['log', 'show', 'decline', 'accept', 'wipe', 'revoke', 'checkout', 'co']:
            reqid = args[0]

        # list
        if cmd == 'list':
            states = ('new', 'accepted', 'revoked', 'declined')
            state_list = opts.state.split(',')
            if opts.state == 'all':
                state_list = ['all']
            else:
                for s in state_list:
                    if not s in states:
                        raise oscerr.WrongArgs('Unknown state \'%s\', try one of %s' % (s, ','.join(states)))
            who = ''
            if opts.mine:
                who = conf.get_apiurl_usr(apiurl)
            if opts.user:
                who = opts.user
            if opts.all:
                state_list = ['all']

            ## FIXME -B not implemented!
            if opts.bugowner:
                if (self.options.debug):
                    print 'list: option --bugowner ignored: not impl.'

            results = get_request_list(apiurl,
                                       project, package, who, state_list, opts.type)
            results.sort(reverse=True)
            import time
            days = opts.days or conf.config['request_list_days']
            since = ''
            try:
                days = int(days)
            except ValueError:
                days = 0
            if days > 0:
                since = time.strftime('%Y-%m-%dT%H:%M:%S',time.localtime(time.time()-days*24*3600))

            skipped = 0
            ## bs has received 2009-09-20 a new xquery compare() function
            ## which allows us to limit the list inside of get_request_list
            ## That would be much faster for coolo. But counting the remainder
            ## would not be possible with current xquery implementation.
            ## Workaround: fetch all, and filter on client side.

            ## FIXME: date filtering should become implemented on server side
            for result in results:
                if days == 0 or result.state.when > since or result.state.name == 'new':
                    print result.list_view()
                else:
                    skipped += 1
            if skipped:
                print "There are %d requests older than %s days.\n" % (skipped, days)

        elif cmd == 'log':
            for l in get_request_log(conf.config['apiurl'], reqid):
                print l

        # show
        elif cmd == 'show':
            r = get_request(conf.config['apiurl'], reqid)
            if opts.brief:
                print r.list_view()
            else:
                print r
            # fixme: will inevitably fail if the given target doesn't exist
            if opts.diff:
                try:
                    print server_diff(conf.config['apiurl'],
                                      r.actions[0].dst_project, r.actions[0].dst_package, None,
                                      r.actions[0].src_project, r.actions[0].src_package, r.actions[0].src_rev, opts.unified)
                except urllib2.HTTPError, e:
                    e.osc_msg = 'Diff not possible'
                    raise

        # checkout
        elif cmd == 'checkout' or cmd == 'co':
            r = get_request(conf.config['apiurl'], reqid)
            submits = [ i for i in r.actions if i.type == 'submit' ]
            if not len(submits):
                raise oscerr.WrongArgs('\'checkout\' only works for \'submit\' requests')
            checkout_package(conf.config['apiurl'], submits[0].src_project, submits[0].src_package, \
                submits[0].src_rev, expand_link=True, prj_dir=submits[0].src_project)

        else:
            if not opts.message:
                opts.message = edit_message()
            state_map = {'accept' : 'accepted', 'decline' : 'declined', 'wipe' : 'deleted', 'revoke' : 'revoked'}
            # Change review state only
            if subcmd == 'review':
                if cmd in ['accept', 'decline']:
                    r = change_review_state(conf.config['apiurl'],
                            reqid, state_map[cmd], conf.config['user'], '', opts.message or '')
                    print r
            # Change state of entire request
            elif cmd in ['accept', 'decline', 'wipe', 'revoke']:
                r = change_request_state(conf.config['apiurl'],
                        reqid, state_map[cmd], opts.message or '')
                print r

    # editmeta and its aliases are all depracated
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

        print >>sys.stderr, 'This command is obsolete. Use \'osc meta <metatype> ...\'.'
        print >>sys.stderr, 'See \'osc help meta\'.'
        #self.do_help([None, 'meta'])
        return 2


    @cmdln.option('-r', '--revision', metavar='rev',
                  help='use the specified revision.')
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
        apiurl = conf.config['apiurl']
        package = None
        if not args or len(args) == 0:
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
            packages = [ package ]
        else:
            packages = meta_get_packagelist(apiurl, project)

        for p in packages:
            print "setting revision for package", p
            if opts.unset:
                rev=-1
            else:
                rev, dummy = parseRevisionOption(opts.revision)
            set_link_rev(apiurl, project, p, rev)


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
        if len(args) == 0:
            wd = os.curdir
            project = store_read_project(wd)
            package = store_read_package(wd)
            apiurl = store_read_apiurl(wd)
            update_local_dir = True
        elif len(args) < 2:
            raise oscerr.WrongArgs('Too few arguments (required none or two)')
        elif len(args) > 2:
            raise oscerr.WrongArgs('Too many arguments (required none or two)')
        else:
            apiurl = conf.config['apiurl']
            project = args[0]
            package = args[1]
            update_local_dir = False

        # execute
        link_to_branch(apiurl, project, package)
        if update_local_dir:
            pac = findpacs(wd)[0]
            pac.update()


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

        usage:
            osc linkpac SOURCEPRJ SOURCEPAC DESTPRJ [DESTPAC]
        ${cmd_option_list}
        """

        args = slash_split(args)

        if not args or len(args) < 3:
            raise oscerr.WrongArgs('Incorrect number of arguments.\n\n' \
                  + self.get_cmd_help('linkpac'))

        rev, dummy = parseRevisionOption(opts.revision)

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

        if opts.current:
            rev = show_upstream_rev(conf.config['apiurl'], src_project, src_package)

        if rev and not checkRevision(src_project, src_package, rev):
            print >>sys.stderr, 'Revision \'%s\' does not exist' % rev
            sys.exit(1)

        link_pac(src_project, src_package, dst_project, dst_package, opts.force, rev, opts.cicount, opts.disable_publish)

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
        http://en.opensuse.org/Build_Service/Tips_and_Tricks#_link_and__aggregate
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

        aggregate_pac(src_project, src_package, dst_project, dst_package, repo_map, opts.disable_publish)


    @cmdln.option('-c', '--client-side-copy', action='store_true',
                        help='do a (slower) client-side copy')
    @cmdln.option('-k', '--keep-maintainers', action='store_true',
                        help='keep original maintainers. Default is remove all and replace with the one calling the script.')
    @cmdln.option('-d', '--keep-develproject', action='store_true',
                        help='keep develproject tag in the package metadata')
    @cmdln.option('-r', '--revision', metavar='rev',
                        help='link the specified revision.')
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
        In that case, a client-side copy is implied.

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

        if src_project == dst_project and \
           src_package == dst_package and \
           src_apiurl == dst_apiurl:
            raise oscerr.WrongArgs('Source and destination are the same.')

        if src_apiurl != dst_apiurl:
            opts.client_side_copy = True

        rev, dummy = parseRevisionOption(opts.revision)

        if opts.message:
            comment = opts.message
        else:
            if not rev:
                rev = show_upstream_rev(src_apiurl, src_project, src_package)
            comment = 'osc copypac from project:%s package:%s revision:%s' % ( src_project, src_package, rev )

        r = copy_pac(src_apiurl, src_project, src_package,
                     dst_apiurl, dst_project, dst_package,
                     client_side_copy=opts.client_side_copy,
                     keep_maintainers=opts.keep_maintainers,
                     keep_develproject=opts.keep_develproject,
                     expand=opts.expand,
                     revision=rev,
                     comment=comment)
        print r


    @cmdln.option('-c', '--checkout', action='store_true',
                        help='Checkout branched package afterwards ' \
                                '(\'osc bco\' is a shorthand for this option)' )
    @cmdln.option('-a', '--attribute', metavar='ATTRIBUTE',
                        help='Use this attribute to find affected packages (default is OBS:Maintained)')
    @cmdln.option('-u', '--update-project-attribute', metavar='UPDATE_ATTRIBUTE',
                        help='Use this attribute to find update projects (default is OBS:UpdateProject) ')
    def do_mbranch(self, subcmd, opts, *args):
        """${cmd_name}: Multiple branch of a package

        [See http://en.opensuse.org/Build_Service/Concepts/Maintenance for information
        on this topic.]

        This command is used for creating multiple links of defined version of a package
        in one project. This is esp. used for maintenance updates.

        The branched package will live in
            home:USERNAME:branches:ATTRIBUTE:PACKAGE
        if nothing else specified.

        usage:
            osc mbranch [ SOURCEPACKAGE [ TARGETPROJECT ] ]
        ${cmd_option_list}
        """
        args = slash_split(args)
        tproject = None

        maintained_attribute = conf.config['maintained_attribute']
        maintained_update_project_attribute = conf.config['maintained_update_project_attribute']

        if not (len(args) >= 1 and len(args) <= 2):
            raise oscerr.WrongArgs('Wrong number of arguments.')
        if len(args) >= 1:
            package = args[0]
        if len(args) >= 2:
            tproject = args[1]

        r = attribute_branch_pkg(conf.config['apiurl'], maintained_attribute, maintained_update_project_attribute, \
                                 package, tproject)

        if r is None:
            print >>sys.stderr, 'ERROR: Attribute branch call came not back with a project.' 
            sys.exit(1)

        print "Project " + r + " created."

        if opts.checkout:
            init_project_dir(conf.config['apiurl'], r, r)
            print statfrmt('A', r)

            # all packages
            for package in meta_get_packagelist(conf.config['apiurl'], r):
                try:
                    checkout_package(conf.config['apiurl'], r, package, expand_link = True, prj_dir = r)
                except:
                    print >>sys.stderr, 'Error while checkout package:\n', package

            if conf.config['verbose']:
                print 'Note: You can use "osc delete" or "osc submitpac" when done.\n'


    @cmdln.alias('branchco')
    @cmdln.alias('bco')
    @cmdln.alias('getpac')
    @cmdln.option('--nodevelproject', action='store_true',
                        help='do not follow a defined devel project ' \
                             '(primary project where a package is developed)')
    @cmdln.option('-c', '--checkout', action='store_true',
                        help='Checkout branched package afterwards ' \
                                '(\'osc bco\' is a shorthand for this option)' )
    @cmdln.option('-r', '--revision', metavar='rev',
                        help='branch against a specific revision')
    def do_branch(self, subcmd, opts, *args):
        """${cmd_name}: Branch a package

        [See http://en.opensuse.org/Build_Service/Collaboration for information
        on this topic.]

        Create a source link from a package of an existing project to a new
        subproject of the requesters home project (home:branches:)

        The branched package will live in
            home:USERNAME:branches:PROJECT/PACKAGE
        if nothing else specified.

        With getpac or bco, the branched package will come from
            %(getpac_default_project)s
        if nothing else specified.

        usage:
            osc branch SOURCEPROJECT SOURCEPACKAGE
            osc branch SOURCEPROJECT SOURCEPACKAGE TARGETPROJECT
            osc branch SOURCEPROJECT SOURCEPACKAGE TARGETPROJECT TARGETPACKAGE
            osc getpac  SOURCEPACKAGE
            osc bco ...
        ${cmd_option_list}
        """

        if subcmd == 'getpac' or subcmd == 'branchco' or subcmd == 'bco': opts.checkout = True
        args = slash_split(args)
        tproject = tpackage = None

        if (subcmd == 'getpac' or subcmd == 'bco') and len(args) == 1:
            print >>sys.stderr, 'defaulting to %s/%s' % (conf.config['getpac_default_project'], args[0])
            # python has no args.unshift ???
            args = [ conf.config['getpac_default_project'] , args[0] ]

        expected = 'home:%s:branches:%s' % (conf.config['user'], args[0])
        if not (len(args) >= 2 and len(args) <= 4):
            raise oscerr.WrongArgs('Wrong number of arguments.')
        if len(args) >= 3:
            expected = tproject = args[2]
        if len(args) >= 4:
            tpackage = args[3]

        r = branch_pkg(conf.config['apiurl'], args[0], args[1],
                           nodevelproject=opts.nodevelproject, rev=opts.revision,
                           target_project=tproject, target_package=tpackage,
                           return_existing=opts.checkout)

        if r[0] is None:
            r = expected = r[1]
            print >>sys.stderr, 'Using existing branch project:', r, '\n'

        devloc = None
        if r != expected:
            devloc = r
            if 'branches:' in r:
                devloc = r.split('branches:')[1]
            print '\nNote: The branch has been created of a different project,\n' \
                  '              %s,\n' \
                  '      which is the primary location of where development for\n' \
                  '      that package takes place.\n' \
                  '      That\'s also where you would normally make changes against.\n' \
                  '      A direct branch of the specified package can be forced\n' \
                  '      with the --nodevelproject option.\n' % devloc

        package = args[1]
        if tpackage:
            package = tpackage
        if opts.checkout:
            checkout_package(conf.config['apiurl'], r, package,
                             expand_link=True, prj_dir=r)
            if conf.config['verbose']:
                print 'Note: You can use "osc delete" or "osc submitpac" when done.\n'
        else:
            apiopt = ''
            if conf.get_configParser().get('general', 'apiurl') != conf.config['apiurl']:
                apiopt = '-A %s ' % conf.config['apiurl']
            print 'A working copy of the branched package can be checked out with:\n\n' \
                  'osc %sco %s/%s' \
                      % (apiopt, r, package)
        print_request_list(conf.config['apiurl'], args[0], args[1])
        if devloc:
            print_request_list(conf.config['apiurl'], devloc, args[1])



    @cmdln.option('-f', '--force', action='store_true',
                        help='deletes a package or an empty project')
    def do_rdelete(self, subcmd, opts, *args):
        """${cmd_name}: Delete a project or packages on the server.

        As a safety measure, project must be empty (i.e., you need to delete all
        packages first). If you are sure that you want to remove this project and all
        its packages use \'--force\' switch.

        usage:
           osc rdelete -f PROJECT
           osc rdelete PROJECT PACKAGE [PACKAGE ...]

        ${cmd_option_list}
        """

        args = slash_split(args)
        if len(args) < 1:
            raise oscerr.WrongArgs('Missing argument.')
        prj = args[0]
        pkgs = args[1:]

        if pkgs:
            for pkg in pkgs:
               # careful: if pkg is an empty string, the package delete request results
               # into a project delete request - which works recursively...
                if pkg:
                    delete_package(conf.config['apiurl'], prj, pkg)
        elif len(meta_get_packagelist(conf.config['apiurl'], prj)) >= 1 and not opts.force:
            print >>sys.stderr, 'Project contains packages. It must be empty before deleting it. ' \
                                'If you are sure that you want to remove this project and all its ' \
                                'packages use the \'--force\' switch'
            sys.exit(1)
        else:
            delete_project(conf.config['apiurl'], prj)

    @cmdln.hide(1)
    def do_deletepac(self, subcmd, opts, *args):
        print """${cmd_name} is obsolete !

                 Please use either
                   osc delete       for checked out packages or projects
                 or
                   osc rdelete      for server side operations."""

        sys.exit(1)

    @cmdln.hide(1)
    @cmdln.option('-f', '--force', action='store_true',
                        help='deletes a project and its packages')
    def do_deleteprj(self, subcmd, opts, project):
        """${cmd_name} is obsolete !

                 Please use
                   osc rdelete PROJECT
        """
        sys.exit(1)

    @cmdln.alias('metafromspec')
    @cmdln.option('', '--specfile', metavar='FILE',
                      help='Path to specfile. (if you pass more than working copy this option is ignored)')
    def do_updatepacmetafromspec(self, subcmd, opts, *args):
        """${cmd_name}: Update package meta information from a specfile

        ARG, if specified, is a package working copy.

        ${cmd_usage}
        ${cmd_option_list}
        """

        args = parseargs(args)
        if opts.specfile and (len(args) == 1):
            specfile = opts.specfile
        else:
            specfile = None
        pacs = findpacs(args)
        for p in pacs:
            p.read_meta_from_spec(specfile)
            p.update_package_meta()


    @cmdln.alias('di')
    @cmdln.option('-c', '--change', metavar='rev',
                        help='the change made by revision rev (like -r rev-1:rev).'
                             'If rev is negative this is like -r rev:rev-1.')
    @cmdln.option('-r', '--revision', metavar='rev1[:rev2]',
                        help='If rev1 is specified it will compare your working copy against '
                             'the revision (rev1) on the server. '
                             'If rev1 and rev2 are specified it will compare rev1 against rev2 '
                             '(NOTE: changes in your working copy are ignored in this case)')
    @cmdln.option('-p', '--plain', action='store_true',
                        help='output the diff in plain (not unified) diff format')
    def do_diff(self, subcmd, opts, *args):
        """${cmd_name}: Generates a diff

        Generates a diff, comparing local changes against the repository
        server.

        ARG, specified, is a filename to include in the diff.

        ${cmd_usage}
        ${cmd_option_list}
        """

        args = parseargs(args)
        pacs = findpacs(args)

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
                print >>sys.stderr, 'Revision \'%s\' not an integer' % opts.change
                return
        else:
            rev1, rev2 = parseRevisionOption(opts.revision)
        diff = ''
        for pac in pacs:
            if not rev2:
                diff += ''.join(make_diff(pac, rev1))
            else:
                diff += server_diff(pac.apiurl, pac.prjname, pac.name, rev1,
                                    pac.prjname, pac.name, rev2, not opts.plain)
        if len(diff) > 0:
            print diff


    @cmdln.option('--oldprj', metavar='OLDPRJ',
                  help='project to compare against'
                  ' (deprecated, use 3 argument form)')
    @cmdln.option('--oldpkg', metavar='OLDPKG',
                  help='package to compare against'
                  ' (deprecated, use 3 argument form)')
    @cmdln.option('-r', '--revision', metavar='N[:M]',
                  help='revision id, where N = old revision and M = new revision')
    @cmdln.option('-p', '--plain', action='store_true',
                  help='output the diff in plain (not unified) diff format')
    @cmdln.option('-c', '--change', metavar='rev',
                        help='the change made by revision rev (like -r rev-1:rev). '
                             'If rev is negative this is like -r rev:rev-1.')
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
            old_package = args[1]
            new_project = args[2]
            if len(args) == 4:
                new_package = args[3]
        else:
            raise oscerr.WrongArgs('Wrong number of arguments')


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
                print >>sys.stderr, 'Revision \'%s\' not an integer' % opts.change
                return
        else:
            if opts.revision:
                rev1, rev2 = parseRevisionOption(opts.revision)

        rdiff = server_diff(conf.config['apiurl'],
                            old_project, old_package, rev1,
                            new_project, new_package, rev2, not opts.plain)

        print rdiff

    @cmdln.hide(1)
    @cmdln.alias('in')
    def do_install(self, subcmd, opts, *args):
        """${cmd_name}: install a package after build via zypper in -r

        Not implemented yet. Use osc repourls,
        select the url you best like (standard),
        chop off after the last /, this should work with zypper.


        ${cmd_usage}
        ${cmd_option_list}
        """

        args = slash_split(args)
        args = expand_proj_pack(args)

        ## FIXME: 
        ## if there is only one argument, and it ends in .ymp
        ## then fetch it, Parse XML to get the first 
        ##  metapackage.group.repositories.repository.url
        ## and construct zypper cmd's for all
        ##  metapackage.group.software.item.name
        ##
        ## if args[0] is already an url, the use it as is.

        cmd = "sudo zypper -p http://download.opensuse.org/repositories/%s/%s --no-refresh -v in %s" % (re.sub(':',':/',args[0]), 'openSUSE_11.1', args[1])
        print self.do_install.__doc__
        print "Example: \n" + cmd


    def do_repourls(self, subcmd, opts, *args):
        """${cmd_name}: Shows URLs of .repo files

        Shows URLs on which to access the project .repos files (yum-style
        metadata) on download.opensuse.org.

        usage:
           osc repourls [PROJECT]

        ${cmd_option_list}
        """

        apiurl = conf.config['apiurl']

        if len(args) == 1:
            project = args[0]
        elif len(args) == 0:
            project = store_read_project('.')
            apiurl = store_read_apiurl('.')
        else:
            raise oscerr.WrongArgs('Wrong number of arguments')

        # XXX: API should somehow tell that
        url_tmpl = 'http://download.opensuse.org/repositories/%s/%s/%s.repo'
        repos = get_repositories_of_project(apiurl, project)
        for repo in repos:
            print url_tmpl % (project.replace(':', ':/'), repo, project)


    @cmdln.option('-r', '--revision', metavar='rev',
                        help='checkout the specified revision. '
                             'NOTE: if you checkout the complete project '
                             'this option is ignored!')
    @cmdln.option('-e', '--expand-link', action='store_true',
                        help='if a package is a link, check out the expanded '
                             'sources (no-op, since this became the default)')
    @cmdln.option('-u', '--unexpand-link', action='store_true',
                        help='if a package is a link, check out the _link file ' \
                             'instead of the expanded sources')
    @cmdln.option('-c', '--current-dir', action='store_true',
                        help='place PACKAGE folder in the current directory' \
                             'instead of a PROJECT/PACKAGE directory')
    @cmdln.option('-s', '--source-service-files', action='store_true',
                        help='server side generated files of source services' \
                             'gets downloaded as well' )
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

        ${cmd_option_list}
        """

        if opts.unexpand_link:
            expand_link = False
        else:
            expand_link = True
        if opts.source_service_files:
            service_files = True
        else:
            service_files = False

        args = slash_split(args)
        project = package = filename = None
        apiurl = conf.config['apiurl']
        try:
            project = project_dir = args[0]
            package = args[1]
            filename = args[2]
        except:
            pass

        if args and len(args) == 1:
            localdir = os.getcwd()
            if is_project_dir(localdir):
                project = store_read_project(localdir)
                project_dir = localdir
                package = args[0]
                apiurl = store_read_apiurl(localdir)

        rev, dummy = parseRevisionOption(opts.revision)
        if rev==None:
            rev="latest"

        if rev and rev != "latest" and not checkRevision(project, package, rev):
            print >>sys.stderr, 'Revision \'%s\' does not exist' % rev
            sys.exit(1)

        if filename:
            get_source_file(apiurl, project, package, filename, revision=rev)

        elif package:
            if opts.current_dir:
                project_dir = None
            checkout_package(apiurl, project, package,
                             rev, expand_link=expand_link, prj_dir=project_dir, service_files=service_files)
            print_request_list(apiurl, project, package)

        elif project:
            prj_dir = project
            if sys.platform[:3] == 'win':
                prj_dir = prj_dir.replace(':', ';')
            if os.path.exists(prj_dir):
                sys.exit('osc: project \'%s\' already exists' % project)

            # check if the project does exist (show_project_meta will throw an exception)
            show_project_meta(apiurl, project)

            init_project_dir(apiurl, prj_dir, project)
            print statfrmt('A', prj_dir)

            # all packages
            for package in meta_get_packagelist(apiurl, project):
                try:
                    checkout_package(apiurl, project, package,
                                     expand_link = expand_link, prj_dir = prj_dir, service_files = service_files)
                except oscerr.LinkExpandError, e:
                    print >>sys.stderr, 'Link cannot be expanded:\n', e
                    print >>sys.stderr, 'Use "osc repairlink" for fixing merge conflicts:\n'
                    # check out in unexpanded form at least
                    checkout_package(apiurl, project, package,
                                     expand_link = False, prj_dir = prj_dir, service_files = service_files)
            print_request_list(apiurl, project)

        else:
            raise oscerr.WrongArgs('Missing argument.\n\n' \
                  + self.get_cmd_help('checkout'))


    @cmdln.option('-q', '--quiet', action='store_true',
                        help='print as little as possible')
    @cmdln.option('-v', '--verbose', action='store_true',
                        help='print extra information')
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
          '?' item is not under version control
          '!' item is missing (removed by non-osc command) or incomplete

        examples:
          osc st
          osc st <directory>
          osc st file1 file2 ...

        usage:
            osc status [OPTS] [PATH...]
        ${cmd_option_list}
        """

        args = parseargs(args)

        # storage for single Package() objects
        pacpaths = []
        # storage for a project dir ( { prj_instance : [ package objects ] } )
        prjpacs = {}
        for arg in args:
            # when 'status' is run inside a project dir, it should
            # stat all packages existing in the wc
            if is_project_dir(arg):
                prj = Project(arg, False)

                if conf.config['do_package_tracking']:
                    prjpacs[prj] = []
                    for pac in prj.pacs_have:
                        # we cannot create package objects if the dir does not exist
                        if not pac in prj.pacs_broken:
                            prjpacs[prj].append(os.path.join(arg, pac))
                else:
                    pacpaths += [arg + '/' + n for n in prj.pacs_have]
            elif is_package_dir(arg):
                pacpaths.append(arg)
            elif os.path.isfile(arg):
                pacpaths.append(arg)
            else:
                msg = '\'%s\' is neither a project or a package directory' % arg
                raise oscerr.NoWorkingCopy, msg
        lines = []
        # process single packages
        lines = getStatus(findpacs(pacpaths), None, opts.verbose, opts.quiet)
        # process project dirs
        for prj, pacs in prjpacs.iteritems():
            lines += getStatus(findpacs(pacs), prj, opts.verbose, opts.quiet)
        if lines:
            print '\n'.join(lines)


    def do_add(self, subcmd, opts, *args):
        """${cmd_name}: Mark files to be added upon the next commit

        usage:
            osc add FILE [FILE...]
        ${cmd_option_list}
        """
        if not args:
            raise oscerr.WrongArgs('Missing argument.\n\n' \
                  + self.get_cmd_help('add'))

        filenames = parseargs(args)
        addFiles(filenames)


    def do_mkpac(self, subcmd, opts, *args):
        """${cmd_name}: Create a new package under version control

        usage:
            osc mkpac new_package
        ${cmd_option_list}
        """
        if not conf.config['do_package_tracking']:
            print >>sys.stderr, "to use this feature you have to enable \'do_package_tracking\' " \
                                "in the [general] section in the configuration file"
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
                        print statfrmt('D', getTransActPath(os.path.join(prj.dir, pac)))
                if opts.recursive:
                    for pac in prj.pacs_have:
                        state = prj.get_state(pac)
                        if state != None and state != 'D':
                            pac_dir = getTransActPath(os.path.join(prj.dir, pac))
                            args.append(pac_dir)
                args.remove(arg)
                prj.write_packages()
            elif is_project_dir(arg):
                print >>sys.stderr, 'osc: addremove is not supported in a project dir unless ' \
                                    '\'do_package_tracking\' is enabled in the configuration file'
                sys.exit(1)

        pacs = findpacs(args)
        for p in pacs:
            p.todo = p.filenamelist + p.filenamelist_unvers

            for filename in p.todo:
                if os.path.isdir(filename):
                    continue
                # ignore foo.rXX, foo.mine for files which are in 'C' state
                if os.path.splitext(filename)[0] in p.in_conflict:
                    continue
                state = p.status(filename)

                if state == '?':
                    # TODO: should ignore typical backup files suffix ~ or .orig
                    p.addfile(filename)
                    print statfrmt('A', getTransActPath(os.path.join(p.dir, filename)))
                elif state == '!':
                    p.put_on_deletelist(filename)
                    p.write_deletelist()
                    os.unlink(os.path.join(p.storedir, filename))
                    print statfrmt('D', getTransActPath(os.path.join(p.dir, filename)))



    @cmdln.alias('ci')
    @cmdln.alias('checkin')
    @cmdln.option('-m', '--message', metavar='TEXT',
                  help='specify log message TEXT')
    @cmdln.option('-F', '--file', metavar='FILE',
                  help='read log message from FILE')
    @cmdln.option('-f', '--force', default=False, action="store_true",
                  help='force commit - do not tests a file list')
    def do_commit(self, subcmd, opts, *args):
        """${cmd_name}: Upload content to the repository server

        Upload content which is changed in your working copy, to the repository
        server.

        Optionally checks the state of a working copy, if found a file with
        unknown state, it requests an user input:
         * skip - don't change anything, just move to another file
         * remove - remove a file from dir
         * edit file list - edit filelist using EDITOR
         * commit - don't check anything and commit package
         * abort - abort commit - this is default value
        This can be supressed by check_filelist config item, or -f/--force
        command line option.

        examples:
           osc ci                   # current dir
           osc ci <dir>
           osc ci file1 file2 ...

        ${cmd_usage}
        ${cmd_option_list}
        """

        args = parseargs(args)

        msg = ''
        if opts.message:
            msg = opts.message
        elif opts.file:
            try:
                msg = open(opts.file).read()
            except:
                sys.exit('could not open file \'%s\'.' % opts.file)

        arg_list = args[:]
        for arg in arg_list:
            if conf.config['do_package_tracking'] and is_project_dir(arg):
                Project(arg).commit(msg=msg)
                if not msg:
                    msg = edit_message()
                args.remove(arg)

        pacs = findpacs(args)

        if conf.config['check_filelist'] and not opts.force:
            check_filelist_before_commit(pacs)

        if not msg:
            # open editor for commit message
            # but first, produce status and diff to append to the template
            footer = diffs = []
            template = []
            for pac in pacs:
                changed = getStatus([pac], quiet=True)
                if changed:
                    footer += changed
                    diffs += ['\nDiff for working copy: %s' % pac.dir]
                    diffs += make_diff(pac, 0)
                    template.extend(get_commit_message_template(pac))
            # if footer is empty, there is nothing to commit, and no edit needed.
            if footer:
                msg = edit_message(footer='\n'.join(footer), template='\n'.join(template))

        if conf.config['do_package_tracking'] and len(pacs) > 0:
            prj_paths = {}
            single_paths = []
            files = {}
            # it is possible to commit packages from different projects at the same
            # time: iterate over all pacs and put each pac to the right project in the dict
            for pac in pacs:
                path = os.path.normpath(os.path.join(pac.dir, os.pardir))
                if is_project_dir(path):
                    pac_path = os.path.basename(os.path.normpath(pac.absdir))
                    prj_paths.setdefault(path, []).append(pac_path)
                    files[pac_path] = pac.todo
                else:
                    single_paths.append(pac.dir)
            for prj, packages in prj_paths.iteritems():
                Project(prj).commit(tuple(packages), msg, files)
            for pac in single_paths:
                Package(pac).commit(msg)
        else:
            for p in pacs:
                p.commit(msg)


    @cmdln.option('-r', '--revision', metavar='REV',
                        help='update to specified revision (this option will be ignored '
                             'if you are going to update the complete project or more than '
                             'one package)')
    @cmdln.option('-u', '--unexpand-link', action='store_true',
                        help='if a package is an expanded link, update to the raw _link file')
    @cmdln.option('-e', '--expand-link', action='store_true',
                        help='if a package is a link, update to the expanded sources')
    @cmdln.option('-s', '--source-service-files', action='store_true',
                        help='Use server side generated sources instead of local generation.' )
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

        if (opts.expand_link and opts.unexpand_link) \
            or (opts.expand_link and opts.revision) \
            or (opts.unexpand_link and opts.revision):
            raise oscerr.WrongOptions('Sorry, the options --expand-link, --unexpand-link and '
                     '--revision are mutually exclusive.')

        if opts.source_service_files: service_files = True
        else: service_files = False

        args = parseargs(args)
        arg_list = args[:]

        for arg in arg_list:
            if is_project_dir(arg):
                prj = Project(arg)

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
                    prj.checkout_missing_pacs(opts.expand_link)
                    args.remove(arg)
                print_request_list(prj.apiurl, prj.name)

        args.sort()
        pacs = findpacs(args)

        if opts.revision and ( len(args) == 1):
            rev, dummy = parseRevisionOption(opts.revision)
            if not checkRevision(pacs[0].prjname, pacs[0].name, rev, pacs[0].apiurl):
                print >>sys.stderr, 'Revision \'%s\' does not exist' % rev
                sys.exit(1)
        else:
            rev = None

        for p in pacs:
            if len(pacs) > 1:
                print 'Updating %s' % p.name

            if opts.expand_link and p.haslinkerror() and not p.islinkrepair():
                raise oscerr.LinkExpandError(p.prjname, p.name, p.linkerror())

            if not rev:
                if opts.expand_link and p.islink() and not p.isexpanded():
                    print 'Expanding to rev', p.linkinfo.xsrcmd5
                    rev = p.linkinfo.xsrcmd5
                elif opts.unexpand_link and p.islink() and p.isexpanded():
                    print 'Unexpanding to rev', p.linkinfo.lsrcmd5
                    rev = p.linkinfo.lsrcmd5
                elif p.islink() and p.isexpanded():
                    rev = p.latest_rev()

            # FIXME: ugly workaround for #399247
            if opts.expand_link or opts.unexpand_link:
                if [ i for i in p.filenamelist+p.filenamelist_unvers if p.status(i) != ' ' and p.status(i) != '?']:
                    print >>sys.stderr, 'osc: cannot expand/unexpand because your working ' \
                                        'copy has local modifications. Please remove them ' \
                                        'and try again'
                    sys.exit(1)
            p.update(rev, service_files)
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
                        print statfrmt('D', getTransActPath(i))
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
                        print "WARNING: package tracking is disabled, operation skipped !"
            else:
                pathn = getTransActPath(p.dir)
                for filename in p.todo:
                    ret, state = p.delete_file(filename, opts.force)
                    if ret:
                        print statfrmt('D', os.path.join(pathn, filename))
                        continue
                    if state == '?':
                        sys.exit('\'%s\' is not under version control' % filename)
                    elif state in ['A', 'M'] and not opts.force:
                        sys.exit('\'%s\' has local modifications (use --force to remove this file)' % filename)


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
                print 'Resolved conflicted state of "%s"' % filename
                p.clear_from_conflictlist(filename)


    @cmdln.alias('platforms')
    def do_repositories(self, subcmd, opts, *args):
        """${cmd_name}: Shows available repositories

        Examples:
        1. osc repositories
                Shows all available repositories/build targets

        2. osc repositories <project>
                Shows the configured repositories/build targets of a project

        ${cmd_usage}
        ${cmd_option_list}
        """

        if args:
            project = args[0]
            print '\n'.join(get_repositories_of_project(conf.config['apiurl'], project))
        else:
            print '\n'.join(get_repositories(conf.config['apiurl']))


    @cmdln.hide(1)
    def do_results_meta(self, subcmd, opts, *args):
        print "Command results_meta is obsolete. Please use: osc results --xml"
        sys.exit(1)

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
        print "Command rresults is obsolete. Running 'osc results' instead"
        self.do_results('results', opts, *args)
        sys.exit(1)


    @cmdln.option('-f', '--force', action='store_true', default=False,
                        help="Don't ask and delete files")
    def do_rremove(self, subcmd, opts, project, package, *files):
        """${cmd_name}: Remove source files from selected package

        ${cmd_usage}
        ${cmd_option_list}
        """

        if len(files) == 0:
            if not '/' in project:
                raise oscerr.WrongArgs("Missing operand, type osc help rremove for help")
            else:
                files = (package, )
                project, package = project.split('/')

        for file in files:
            if not opts.force:
                resp = raw_input("rm: remove source file `%s' from `%s/%s'? (yY|nN) " % (file, project, package))
                if resp not in ('y', 'Y'):
                    continue
            try:
                delete_files(conf.config['apiurl'], project, package, (file, ))
            except urllib2.HTTPError, e:
                if opts.force:
                    print >>sys.stderr, e
                    body = e.read()
                    if e.code in [ 400, 403, 404, 500 ]:
                        if '<summary>' in body:
                            msg = body.split('<summary>')[1]
                            msg = msg.split('</summary>')[0]
                            print >>sys.stderr, msg
                else:
                    raise e

    @cmdln.alias('r')
    @cmdln.option('-l', '--last-build', action='store_true',
                        help='show last build results (succeeded/failed/unknown)')
    @cmdln.option('-r', '--repo', action='append', default = [],
                        help='Show results only for specified repo(s)')
    @cmdln.option('-a', '--arch', action='append', default = [],
                        help='Show results only for specified architecture(s)')
    @cmdln.option('', '--xml', action='store_true',
                        help='generate output in XML (former results_meta)')
    def do_results(self, subcmd, opts, *args):
        """${cmd_name}: Shows the build results of a package

        Usage:
            osc results (inside working copy)
            osc results remote_project remote_package

        ${cmd_option_list}
        """

        args = slash_split(args)

        apiurl = conf.config['apiurl']
        if len(args) == 0:
            wd = os.curdir
            if is_project_dir(wd):
                opts.csv = None
                opts.arch = None
                opts.repo = None
                opts.hide_legend = None
                opts.name_filter = None
                opts.status_filter = None
                self.do_prjresults('prjresults', opts, *args);
                sys.exit(0)
            else:
                project = store_read_project(wd)
                package = store_read_package(wd)
                apiurl = store_read_apiurl(wd)
        elif len(args) < 2:
            raise oscerr.WrongArgs('Too few arguments (required none or two)')
        elif len(args) > 2:
            raise oscerr.WrongArgs('Too many arguments (required none or two)')
        else:
            project = args[0]
            package = args[1]

        if not opts.xml:
            func = get_results
            delim = '\n'
        else:
            func = show_results_meta
            delim = ''

        print delim.join(func(apiurl, project, package, opts.last_build, opts.repo, opts.arch))

    # WARNING: this function is also called by do_results. You need to set a default there
    #          as well when adding a new option!
    @cmdln.option('-q', '--hide-legend', action='store_true',
                        help='hide the legend')
    @cmdln.option('-c', '--csv', action='store_true',
                        help='csv output')
    @cmdln.option('-s', '--status-filter', metavar='STATUS',
                        help='show only packages with buildstatus STATUS (see legend)')
    @cmdln.option('-n', '--name-filter', metavar='EXPR',
                        help='show only packages whose names match EXPR')
    @cmdln.option('-a', '--arch', metavar='ARCH',
                        help='show results only for specified architecture(s)')
    @cmdln.option('-r', '--repo', metavar='REPO',
                        help='show results only for specified repo(s)')
    @cmdln.option('-p', '--project', metavar='PROJECT',
                        help='show packages in project PROJECT')
    @cmdln.alias('pr')
    def do_prjresults(self, subcmd, opts, *args):
        """${cmd_name}: Shows project-wide build results

        Usage:
            osc prjresults (inside working copy)
            osc prjresults project

        ${cmd_option_list}
        """

        if args:
            apiurl = conf.config['apiurl']
            if len(args) == 1:
                project = args[0]
            else:
                print >>sys.stderr, 'getting results for more than one project is not supported'
                return 2
        else:
            wd = os.curdir
            project = store_read_project(wd)
            apiurl = store_read_apiurl(wd)

        print '\n'.join(get_prj_results(apiurl, project, hide_legend=opts.hide_legend, csv=opts.csv, status_filter=opts.status_filter, name_filter=opts.name_filter, repo=opts.repo, arch=opts.arch))


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
        print "Command rprjresults is obsolete. Please use 'osc prjresults'"
        sys.exit(1)

    @cmdln.alias('bl')
    @cmdln.option('-s', '--start', metavar='START',
                    help='get log starting from the offset')
    def do_buildlog(self, subcmd, opts, *args):
        """${cmd_name}: Shows the build log of a package

        Shows the log file of the build of a package. Can be used to follow the
        log while it is being written.
        Needs to be called from within a package directory.

        The arguments REPOSITORY and ARCH are the first two columns in the 'osc
        results' output.

        ${cmd_usage} REPOSITORY ARCH
        ${cmd_option_list}
        """

        wd = os.curdir
        package = store_read_package(wd)
        project = store_read_project(wd)
        apiurl = store_read_apiurl(wd)

        offset=0
        if opts.start:
            offset = int(opts.start)

        if args is None or len(args) < 2:
            self.print_repos()

        repository = args[0]
        arch = args[1]

        print_buildlog(apiurl, project, package, repository, arch, offset)


    def print_repos(self):
            wd = os.curdir
            doprint = False
            if is_package_dir(wd):
                str = "package"
                doprint = True
            elif is_project_dir(wd):
                str = "project"
                doprint = True
            
            if doprint:
                print 'Valid arguments for this %s are:' % str
                print
                self.do_repos(None, None)
                print
            raise oscerr.WrongArgs('Missing arguments')

    @cmdln.alias('rbl')
    @cmdln.alias('rbuildlog')
    def do_remotebuildlog(self, subcmd, opts, *args):
        """${cmd_name}: Shows the build log of a package

        Shows the log file of the build of a package. Can be used to follow the
        log while it is being written.

        usage:
            osc remotebuildlog project package repository arch
            or
            osc remotebuildlog project/package/repository/arch
        ${cmd_option_list}
        """
        args = slash_split(args)
        if len(args) < 4:
            raise oscerr.WrongArgs('Too few arguments.')
        elif len(args) > 4:
            raise oscerr.WrongArgs('Too many arguments.')

        print_buildlog(conf.config['apiurl'], *args)


    @cmdln.alias('tr')
    def do_triggerreason(self, subcmd, opts, *args):
        """${cmd_name}: Show reason why a package got triggered to build

        The server decides when a package needs to get rebuild, this command
        shows the detailed reason for a package. A brief reason is also stored
        in the jobhistory, which can be accessed via "osc jobhistory".

        Trigger reasons might be:
          - new build (never build yet or rebuild manually forced)
          - source change (eg. on updating sources)
          - meta change (packages which are used for building have changed)
          - rebuild count sync (In case that it is configured to sync release numbers)

        usage in package or project directory:
            osc reason REPOSITORY ARCH
            osc reason PROJECT PACKAGE REPOSITORY ARCH

        ${cmd_option_list}
        """
        wd = os.curdir
        args = slash_split(args)
        project = package = repository = arch = None
        
        if ( args is None or len(args) < 2):
            self.print_repos()

        if len(args) == 2: # 2
            if is_package_dir('.'):
                 package = store_read_package(wd)
            else:
                 raise oscerr.WrongArgs('package is not specified.')
            project = store_read_project(wd)
            apiurl = store_read_apiurl(wd)
            repository = args[0]
            arch = args[1]
        elif len(args) == 4:
            apiurl = conf.config['apiurl']
            project = args[0]
            package = args[1]
            repository = args[2]
            arch = args[3]
        else:
            raise oscerr.WrongArgs('Too many arguments.')

        print apiurl, project, package, repository, arch
        xml = show_package_trigger_reason(apiurl, project, package, repository, arch)
        root = ET.fromstring(xml)
        reason = root.find('explain').text
        print reason
        if reason == "meta change":
           print "changed keys:"
           for package in root.findall('packagechange'):
               print "  ", package.get('change'), package.get('key')


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
        
        if ( args is None or len(args) < 2) and (is_package_dir('.') or is_project_dir('.')):
            self.print_repos()

        if len(args) > 5:
            raise oscerr.WrongArgs('Too many arguments.')

        if len(args) < 3: # 2
            if is_package_dir('.'):
                 packages = [store_read_package(wd)]
            elif not is_project_dir('.'):
                 raise oscerr.WrongArgs('Project and package is not specified.')
            project = store_read_project(wd)
            apiurl = store_read_apiurl(wd)
            repository = args[0]
            arch = args[1]

        if len(args) == 3:
            apiurl = conf.config['apiurl']
            project = args[0]
            repository = args[1]
            arch = args[2]

        if len(args) == 4:
            apiurl = conf.config['apiurl']
            project = args[0]
            packages = [args[1]]
            repository = args[2]
            arch = args[3]

        if subcmd == 'whatdependson':
            reverse = 1

        xml = get_dependson(apiurl, project, repository, arch, packages, reverse)

        root = ET.fromstring(xml)
        for package in root.findall('package'):
            print package.get('name'), ":"
            for dep in package.findall('pkgdep'):
               print "  ", dep.text


    @cmdln.option('-x', '--extra-pkgs', metavar='PAC', action='append',
                  help='Add this package when computing the buildinfo')
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

        The arguments REPOSITORY and ARCH can be taken from the first two columns
        of the 'osc repos' output.

        usage:
            osc buildinfo REPOSITORY ARCH [BUILD_DESCR]    (in pkg dir)
            osc buildinfo PROJECT PACKAGE REPOSITORY ARCH [BUILD_DESCR]

        ${cmd_option_list}
        """
        wd = os.curdir
        args = slash_split(args)
        
        if ( args is None or len(args) < 2) and is_package_dir('.'):
            self.print_repos()

        if len(args) > 5:
            raise oscerr.WrongArgs('Too many arguments.')

        if len(args) < 4: # 2 or 3
            package = store_read_package(wd)
            project = store_read_project(wd)
            apiurl = store_read_apiurl(wd)
            repository = args[0]
            arch = args[1]

        if len(args) > 3 and len(args) < 6: # 4 or 5
            apiurl = conf.config['apiurl']
            project = args[0]
            package = args[1]
            repository = args[2]
            arch = args[3]
            # for following specfile detection ...
            del args[0]
            del args[0]

        # were we given a specfile (third argument)?
        try:
            spec = open(args[2]).read()
        except IndexError:
            spec = None
        except IOError, e:
            print >>sys.stderr, e
            return 1

        print ''.join(get_buildinfo(apiurl,
                                    project, package, repository, arch,
                                    specfile=spec,
                                    addlist=opts.extra_pkgs))


    def do_buildconfig(self, subcmd, opts, *args):
        """${cmd_name}: Shows the build config

        Shows the build configuration which is used in building a package.
        This command is mostly used internally by the 'build' command.
        It needs to be called from inside a package directory.

        The returned data is the project-wide build configuration in a format
        which is directly readable by the build script. It contains RPM macros
        and BuildRequires expansions, for example.

        The arguments REPOSITORY and ARCH can be taken from the first two columns
        of the 'osc repos' output.

        usage:
            osc buildconfig REPOSITORY ARCH    (in pkg dir)
            osc buildconfig PROJECT PACKAGE REPOSITORY ARCH
        ${cmd_option_list}
        """

        wd = os.curdir
        args = slash_split(args)
        
        if ( args is None or len(args) < 2) and is_package_dir('.'):
            self.print_repos()

        if len(args) > 4:
            raise oscerr.WrongArgs('Too many arguments.')

        if len(args) == 2:
            package = store_read_package(wd)
            project = store_read_project(wd)
            apiurl = store_read_apiurl(wd)
            repository = args[0]
            arch = args[1]
        elif len(args) == 4:
            apiurl = conf.config['apiurl']
            project = args[0]
            package = args[1]
            repository = args[2]
            arch = args[3]
        else:
            raise oscerr.WrongArgs('Wrong number of arguments.')

        print ''.join(get_buildconfig(apiurl, project, package, repository, arch))


    def do_repos(self, subcmd, opts, *args):
        """${cmd_name}: shows repositories configured for a project

        usage:
            osc repos
            osc repos [PROJECT]

        ${cmd_option_list}
        """

        apiurl = conf.config['apiurl']

        if len(args) == 1:
            project = args[0]
        elif len(args) == 0:
            project = store_read_project('.')
            apiurl = store_read_apiurl('.')
        else:
            raise oscerr.WrongArgs('Wrong number of arguments')

        data = []
        for repo in get_repos_of_project(apiurl, project):
            data += [repo.name, repo.arch]
        for row in build_table(2, data, width=2):
            print row

    @cmdln.option('--clean', action='store_true',
                  help='Delete old build root before initializing it')
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
                  help='Do not run post build checks on the resulting packages.')
    @cmdln.option('--no-verify', action='store_true',
                  help='Skip signature verification of packages used for build.')
    @cmdln.option('--noservice', '--no-service', action='store_true',
                  help='Skip run of local source services as specified in _service file.')
    @cmdln.option('-p', '--prefer-pkgs', metavar='DIR', action='append',
                  help='Prefer packages from this directory when installing the build-root')
    @cmdln.option('-k', '--keep-pkgs', metavar='DIR',
                  help='Save built packages into this directory')
    @cmdln.option('-x', '--extra-pkgs', metavar='PAC', action='append',
                  help='Add this package when installing the build-root')
    @cmdln.option('--root', metavar='ROOT',
                  help='Build in specified directory')
    @cmdln.option('-j', '--jobs', metavar='N',
                  help='Compile with N jobs')
    @cmdln.option('--icecream', metavar='N',
                  help='use N parallel build jobs with icecream')
    @cmdln.option('--ccache', action='store_true',
                  help='use ccache to speed up rebuilds')
    @cmdln.option('--with', metavar='X', dest='_with', action='append',
                  help='enable feature X for build')
    @cmdln.option('--without', metavar='X', action='append',
                  help='disable feature X for build')
# will not work as build.py does not support proper quoting
#    @cmdln.option('--define', metavar='\'X Y\'', action='append',
#                  help='define macro X with value Y')
    @cmdln.option('--userootforbuild', action='store_true',
                  help='Run build as root. The default is to build as '
                  'unprivileged user. Note that a line "# norootforbuild" '
                  'in the spec file will invalidate this option.')
    @cmdln.option('--local-package', action='store_true',
                  help='build a package which does not exist on the server')
    @cmdln.option('--linksources', action='store_true',
                  help='use hard links instead of a deep copied source')
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
    def do_build(self, subcmd, opts, *args):
        """${cmd_name}: Build a package on your local machine

        You need to call the command inside a package directory, which should be a
        buildsystem checkout. (Local modifications are fine.)

        The arguments REPOSITORY and ARCH can be taken from the first two columns
        of the 'osc repos' output. BUILD_DESCR is either a RPM spec file, or a
        Debian dsc file.

        The command honours packagecachedir and build-root settings in .oscrc,
        if present. You may want to set su-wrapper = 'sudo' in .oscrc, and
        configure sudo with option NOPASSWD for /usr/bin/build.

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
            osc build [OPTS] REPOSITORY ARCH BUILD_DESCR
            osc build [OPTS] REPOSITORY (ARCH = hostarch, BUILD_DESCR is detected automatically)
            osc build [OPTS] ARCH (REPOSITORY = build_repository (config option), BUILD_DESCR is detected automatically)
            osc build [OPTS] BUILD_DESCR (REPOSITORY = build_repository (config option), ARCH = hostarch)
            osc build [OPTS] (REPOSITORY = build_repository (config option), ARCH = hostarch, BUILD_DESCR is detected automatically)

        # Note:
        # Configuration can be overridden by envvars, e.g.
        # OSC_SU_WRAPPER overrides the setting of su-wrapper.
        # OSC_BUILD_ROOT overrides the setting of build-root.
        # OSC_PACKAGECACHEDIR overrides the setting of packagecachedir.

        ${cmd_option_list}
        """

        import osc.build

        if not os.path.exists('/usr/lib/build/debtransform') \
                and not os.path.exists('/usr/lib/lbuild/debtransform'):
            sys.stderr.write('Error: you need build.rpm with version 2007.3.12 or newer.\n')
            sys.stderr.write('See http://download.opensuse.org/repositories/openSUSE:/Tools/\n')
            return 1

        if opts.debuginfo and opts.disable_debuginfo:
            raise oscerr.WrongOptions('osc: --debuginfo and --disable-debuginfo are mutual exclusive')

        if len(args) > 3:
            raise oscerr.WrongArgs('Too many arguments')

        arg_arch = arg_repository = arg_descr = None
        if len(args) < 3:
            for arg in args:
                if arg.endswith('.spec') or arg.endswith('.dsc') or arg.endswith('.kiwi'):
                    arg_descr = arg
                else:
                    if arg in osc.build.can_also_build.get(osc.build.hostarch, []) or \
                       arg in osc.build.hostarch:
                        arg_arch = arg
                    elif not arg_repository:
                        arg_repository = arg
                    else:
                        raise oscerr.WrongArgs('unexpected argument: \'%s\'' % arg)
        else:
            arg_repository, arg_arch, arg_descr = args

        arg_arch = arg_arch or osc.build.hostarch

        if not opts.noinit:
            repositories = get_repositories_of_project( \
                    store_read_apiurl('.'), \
                    opts.alternative_project or store_read_project('.'))
            if not arg_repository:

                if len(repositories) == 0:
                    arg_repository = conf.config['build_repository']

                else:

                    # Use a default value from config, but just even if it's available
                    # unless try standard, or openSUSE_Factory
                    for repository in (conf.config['build_repository'], 'standard', 'openSUSE_Factory'):
                        if repository in repositories:
                            arg_repository = repository
                            break

                    arg_repository = arg_repository or repositories[len(repositories)-1]

            if not arg_repository in repositories:
                raise oscerr.WrongArgs('%s is not a valid repository, use one of: %s' % (arg_repository, ", ".join(repositories)))

        if not arg_repository:
                raise oscerr.WrongArgs('please specify a repository')

        # check for source services
        if not opts.noservice and not opts.noinit and os.listdir('.').count("_service"):
            p = Package('.')
            p.run_source_services()

        descr = [ i for i in os.listdir('.') if i.endswith('.spec') or i.endswith('.dsc') or i.endswith('.kiwi') ]
        # FIXME:
        # * request repos from server and select by build type.
        if not arg_descr and len(descr) == 1:
            arg_descr = descr[0]
        elif not arg_descr:
            msg = 'Missing argument: build description (spec, dsc or kiwi file)'
            try:
                p = Package('.')
                if p.islink() and not p.isexpanded():
                    msg += ' (this package is not expanded - you might want to try osc up --expand)'
            except:
                pass
            raise oscerr.WrongArgs(msg)

        args = (arg_repository, arg_arch, arg_descr)

        if opts.prefer_pkgs:
            for d in opts.prefer_pkgs:
                if not os.path.isdir(d):
                    raise oscerr.WrongOptions('Preferred package location \'%s\' is not a directory' % d)

        if opts.keep_pkgs and not os.path.isdir(opts.keep_pkgs):
            raise oscerr.WrongOptions('Preferred save location \'%s\' is not a directory' % opts.keep_pkgs)

        print 'Building %s for %s/%s' % (arg_descr, arg_repository, arg_arch)
        return osc.build.main(opts, args)



    @cmdln.option('', '--csv', action='store_true',
                        help='generate output in CSV (separated by |)')
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

        if ( args is None or len(args) < 2) and is_package_dir('.'):
            self.print_repos()

        if len(args) == 4:
            apiurl = conf.config['apiurl']
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
            apiurl = store_read_apiurl(wd)
        else:
            raise oscerr.WrongArgs('Wrong number of arguments')

        format = 'text'
        if opts.csv:
            format = 'csv'

        print '\n'.join(get_buildhistory(apiurl, project, package, repository, arch, format))

    @cmdln.option('', '--csv', action='store_true',
                        help='generate output in CSV (separated by |)')
    @cmdln.option('-l', '--limit', metavar='limit',
                        help='for setting the number of results')
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

        if (args is None or len(args) < 2) \
            and (is_project_dir('.') or is_package_dir('.')):
            self.print_repos()

        if len(args) == 4:
            apiurl = conf.config['apiurl']
            project = args[0]
            package = args[1]
            repository = args[2]
            arch = args[3]
        elif len(args) == 3:
            apiurl = conf.config['apiurl']
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
            apiurl = store_read_apiurl(wd)
        else:
            raise oscerr.WrongArgs('Wrong number of arguments')

        format = 'text'
        if opts.csv:
            format = 'csv'

        print_jobhistory(apiurl, project, package, repository, arch, format, opts.limit)

    @cmdln.hide(1)
    def do_rlog(self, subcmd, opts, *args):
        print "Command rlog is obsolete. Please use 'osc log'"
        sys.exit(1)


    @cmdln.option('-r', '--revision', metavar='rev',
                        help='show log of the specified revision')
    @cmdln.option('', '--csv', action='store_true',
                        help='generate output in CSV (separated by |)')
    @cmdln.option('', '--xml', action='store_true',
                        help='generate output in XML')
    def do_log(self, subcmd, opts, *args):
        """${cmd_name}: Shows the commit log of a package

        Usage:
            osc log (inside working copy)
            osc log remote_project remote_package

        ${cmd_option_list}
        """

        args = slash_split(args)
        if len(args) == 0:
            wd = os.curdir
            project = store_read_project(wd)
            package = store_read_package(wd)
            apiurl = store_read_apiurl(wd)
        elif len(args) < 2:
            raise oscerr.WrongArgs('Too few arguments (required none or two)')
        elif len(args) > 2:
            raise oscerr.WrongArgs('Too many arguments (required none or two)')
        else:
            apiurl = conf.config['apiurl']
            project = args[0]
            package = args[1]

        rev, dummy = parseRevisionOption(opts.revision)
        if rev and not checkRevision(project, package, rev, apiurl):
            print >>sys.stderr, 'Revision \'%s\' does not exist' % rev
            sys.exit(1)

        format = 'text'
        if opts.csv:
            format = 'csv'
        if opts.xml:
            format = 'xml'

        print '\n'.join(get_commitlog(apiurl, project, package, rev, format))

    @cmdln.option('-f', '--failed', action='store_true',
                  help='rebuild all failed packages')
    @cmdln.alias('rebuildpac')
    def do_rebuild(self, subcmd, opts, *args):
        """${cmd_name}: Triggers package rebuilds

        With the optional <repo> and <arch> arguments, the rebuild can be limited
        to a certain repository or architecture.

        Note that it is normally NOT needed to kick off rebuilds like this, because
        they principally happen in a fully automatic way, triggered by source
        check-ins. In particular, the order in which packages are built is handled
        by the build service.

        Note the --failed option, which can be used to rebuild all failed
        packages.

        The arguments REPOSITORY and ARCH can be taken from the first two columns
        of the 'osc repos' output.

        usage:
            osc rebuild PROJECT [PACKAGE [REPOSITORY [ARCH]]]
        ${cmd_option_list}
        """

        args = slash_split(args)

        if len(args) < 1:
            raise oscerr.WrongArgs('Missing argument.')

        package = repo = arch = code = None
        project = args[0]
        if len(args) > 1:
            package = args[1]
        if len(args) > 2:
            repo = args[2]
        if len(args) > 3:
            arch = args[3]

        if opts.failed:
            code = 'failed'

        print rebuild(conf.config['apiurl'], project, package, repo, arch, code)


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
            print p.info()


    @cmdln.option('-a', '--arch', metavar='ARCH',
                        help='Abort builds for a specific architecture')
    @cmdln.option('-r', '--repo', metavar='REPO',
                        help='Abort builds for a specific repository')
    def do_abortbuild(self, subcmd, opts, *args):
        """${cmd_name}: Aborts the build of a certain project/package

        With the optional argument <package> you can specify a certain package
        otherwise all builds in the project will be cancelled.

        usage:
            osc abortbuild [OPTS] PROJECT [PACKAGE]
        ${cmd_option_list}
        """

        if len(args) < 1:
            raise oscerr.WrongArgs('Missing <project> argument.')

        if len(args) == 2:
            package = args[1]
        else:
            package = None

        print abortbuild(conf.config['apiurl'], args[0], package, opts.arch, opts.repo)


    @cmdln.option('-a', '--arch', metavar='ARCH',
                        help='Delete all binary packages for a specific architecture')
    @cmdln.option('-r', '--repo', metavar='REPO',
                        help='Delete all binary packages for a specific repository')
    @cmdln.option('--build-disabled', action='store_true',
                        help='Delete all binaries of packages for which the build is disabled')
    @cmdln.option('--build-failed', action='store_true',
                        help='Delete all binaries of packages for which the build failed')
    @cmdln.option('--broken', action='store_true',
                        help='Delete all binaries of packages for which the package source is bad')
    @cmdln.option('--expansion', action='store_true',
                        help='Delete all binaries of packages which have expansion errors')
    @cmdln.option('--all', action='store_true',
                        help='Delete all binaries regardless of the package status (previously default)')
    def do_wipebinaries(self, subcmd, opts, *args):
        """${cmd_name}: Delete all binary packages of a certain project/package

        With the optional argument <package> you can specify a certain package
        otherwise all binary packages in the project will be deleted.

        usage:
            osc wipebinaries OPTS PROJECT [PACKAGE]
        ${cmd_option_list}
        """

        args = slash_split(args)

        if len(args) < 1:
            raise oscerr.WrongArgs('Missing <project> argument.')
        if len(args) > 2:
            raise oscerr.WrongArgs('Wrong number of arguments.')

        if len(args) == 2:
            package = args[1]
        else:
            package = None

        codes = []
        if opts.build_disabled:
            codes.append('disabled')
        if opts.build_failed:
            codes.append('failed')
        if opts.broken:
            codes.append('broken')
        if opts.expansion:
            codes.append('expansion error')
        if opts.all or opts.repo or opts.arch:
            codes.append(None)

        if len(codes) == 0:
            raise oscerr.WrongOptions('No option has been provided. If you want to delete all binaries, use --all option.')

        # make a new request for each code= parameter
        for code in codes:
            print wipebinaries(conf.config['apiurl'], args[0], package, opts.arch, opts.repo, code)


    @cmdln.option('-q', '--quiet', action='store_true',
                  help='do not show downloading progress')
    @cmdln.option('-d', '--destdir', default='.', metavar='DIR',
                  help='destination directory')
    @cmdln.option('--sources', action="store_true",
                  help='also fetch source packages')
    def do_getbinaries(self, subcmd, opts, *args):
        """${cmd_name}: Download binaries to a local directory

        This command downloads packages directly from the api server.
        Thus, it directly accesses the packages that are used for building
        others even when they are not "published" yet.

        usage:
           osc getbinaries REPOSITORY ARCHITECTURE                    # works in checked out package
           osc getbinaries PROJECT PACKAGE REPOSITORY ARCHITECTURE
        ${cmd_option_list}
        """

        args = slash_split(args)
        apiurl = conf.config['apiurl']

        if ( args is None or len(args) < 2) and is_package_dir('.'):
            self.print_repos()

        if len(args) == 4:
            project = args[0]
            package = args[1]
            repository   = args[2]
            architecture = args[3]
        elif len(args) == 2:
            if is_package_dir(os.getcwd()):
                project = store_read_project(os.curdir)
                package = store_read_package(os.curdir)
                apiurl  = store_read_apiurl(os.curdir)
                repository   = args[0]
                architecture = args[1]
            else:
                sys.exit('Local directory is no checkout package, neither it is specified. ' )
        else:
            raise oscerr.WrongArgs('Need either 2 or 4 arguments')

        # Get package list
        binaries = get_binarylist(apiurl,
                                   project, repository, architecture,
                                   package = package, verbose=True)

        if not os.path.isdir(opts.destdir):
            print "Creating %s" % opts.destdir
            os.makedirs(opts.destdir, 0755)

        if binaries == [ ]:
            sys.exit('no binaries found. Either the package does not '
                     'exist or no binaries have been built.')

        for binary in binaries:

            # skip source rpms
            if not opts.sources and binary.name.endswith('.src.rpm'):
                continue

            target_filename = '%s/%s' % (opts.destdir, binary.name)

            if os.path.exists(target_filename):
                st = os.stat(target_filename)
                if st.st_mtime == binary.mtime and st.st_size == binary.size:
                    continue

            get_binary_file(apiurl,
                            project,
                            repository, architecture,
                            binary.name,
                            package = package,
                            target_filename = target_filename,
                            target_mtime = binary.mtime,
                            progress_meter = not opts.quiet)


    @cmdln.option('-b', '--bugowner', action='store_true',
                        help='restrict listing to items where the user is bugowner')

    @cmdln.option('-m', '--maintainer', action='store_true',
                        help='restrict listing to items where the user is maintainer')

    @cmdln.option('-a', '--all', action='store_true',
                        help='all involvements')

    @cmdln.option('-U', '--user', metavar='USER',
                        help='search for USER instead of yourself')

    @cmdln.option('--exclude-project', metavar='exclude_project',
                        help='exclude requests for specified project')

    @cmdln.option('-v', '--verbose', action='store_true',
                        help='verbose listing')

    def do_my(self, subcmd, opts, type):
        """${cmd_name}: show packages, projects or requests involving yourself

            Examples:
                # list packages where I am bugowner
                osc ${cmd_name} pkg -b
                # list projects where I am maintainer
                osc ${cmd_name} prj -m
                # list request for all my projects and packages
                osc ${cmd_name} rq
                # list requests, excluding project 'foo' and 'bar'
                osc ${cmd_name} rq --exclude-project foo,bar
                # list submitrequests I made
                osc ${cmd_name} sr

            ${cmd_usage}
                where TYPE is one of requests, submitrequests,
                projects or packages (rq, sr, prj or pkg)

            ${cmd_option_list}
        """

        args_rq = ('requests', 'request', 'req', 'rq')
        args_sr = ('submitrequests', 'submitrequest', 'submitreq', 'submit', 'sr')
        args_prj = ('projects', 'project', 'projs', 'proj', 'prj')
        args_pkg = ('packages', 'package', 'pack', 'pkgs', 'pkg')

        apiurl = conf.config['apiurl']

        project_exclude = {}
        if opts.exclude_project:
            for p in opts.exclude_project.split(','):
                project_exclude[p] = True

        if not opts.user:
            user = conf.get_apiurl_usr(apiurl)
        else:
            user = opts.user

        list_requests = False
        my_requests_only = False
        if type in args_rq:
            list_requests = True
            query_types = [ 'project', 'package' ]
        elif type in args_sr:
            list_requests = True
            my_requests_only = True
            query_types = []
        elif type in args_prj:
            query_types = [ 'project' ]
        elif type in args_pkg:
            query_types = [ 'project', 'package' ]
        else:
            raise oscerr.WrongArgs("invalid type %s" % type)

        if opts.all:
            roles = ['bugowner', 'maintainer']
            role_filter = None
        elif opts.maintainer:
            roles = [ 'maintainer' ]
            role_filter = 'maintainer'
        elif opts.bugowner:
            role_filter = 'bugowner'
            roles = [ 'bugowner' ]
        else:
            if list_requests:
                roles = [ 'maintainer' ]
                role_filter = 'maintainer'
            else:
                roles = ['bugowner', 'maintainer']
                role_filter = None

        # prjname => {
        #   'maintainer' : True,
        #   'bugowner' : True,
        #   'packages' : {
        #     'pkgname' : {
        #        'maintainer' : True,
        #        'bugowner' : True
        #       }
        #    }
        # }
        p = {}
        # find projects and packages we're involved in
        for kind in query_types:
            u = makeurl(apiurl, ['search', kind], ['match=%s' % quote_plus("person/@userid='%s'"%user)])
            f = http_GET(u)

            root = ET.parse(f).getroot()
            for node in root.findall(kind):
                if kind == 'package':
                    project = node.get('project')
                    package = node.get('name')
                    if not project in p:
                        p[project] = {}
                    if not 'packages' in p[project]:
                        p[project]['packages'] = {}
                    if not package in p[project]['packages']:
                        p[project]['packages'][package] = {}
                    for person in node.findall('person'):
                        if person.get('userid') == user:
                            role = person.get('role')
                            if role in roles:
                                p[project]['packages'][package][role] = True
                    if role_filter and not role_filter in p[project]['packages'][package]:
                        del p[project]['packages'][package]

                else:
                    project = node.get('name')
                    if not project in project_exclude:
                        if not project in p:
                            p[project] = {}
                        for person in node.findall('person'):
                            if person.get('userid') == user:
                                role = person.get('role')
                                if role in roles:
                                    p[project][role] = True

        if role_filter:
            for prj in p.keys():
                if ( not 'packages' in p[prj] or \
                        len(p[prj]['packages']) == 0
                    ) and \
                    not role_filter in p[prj]:
                        del p[prj]

        if list_requests:
            req_state = ('new',)
            req_type = None
            req_user = None
            results = []
            query = ''
            if my_requests_only:
                query = "state/@name='new' and (state/@who='%(user)s' or history/@who='%(user)s')" % { 'user':user }
            else:
                predicate = []
                for prj in p.keys():
                    involved = False
                    for role in roles:
                        if role in p[prj]:
                            involved = True
                            break
                    if involved:
                        pkg = None
                        predicate.append("action/target/@project='%s'" % prj)
                    elif 'packages' in p[prj] and len(p[prj]['packages']) != 0:
                        q = "(action/target/@project='%s'" % prj
                        for pkg in p[prj]['packages'].keys():
                            q += " and action/target/@package='%s'" % pkg
                        q += ')'
                        predicate.append(q)
                    else: # not supposed to happen
                        True
                query = '(' + ' or '.join(predicate) + ')' + " and state/@name='new'"

            u = makeurl(apiurl, ['search', 'request'], ['match=%s' % quote_plus(query)])
            f = http_GET(u)
            collection = ET.parse(f).getroot()

            for root in collection.findall('request'):
                r = Request()
                r.read(root)
                results.append(r)

            for result in results:
                print result.list_view()
        else:
            def _get_role_string(p):
                roles = []
                for role in ['bugowner', 'maintainer']:
                    if role in p:
                        roles.append(role)
                if roles:
                    return '(' + ','.join(roles)+ ')'
                return None

            for prj in sorted(p.keys()):
                if opts.verbose:
                    s = prj
                    rs = _get_role_string(p[prj])
                    if rs:
                        s += '  ' + rs
                    print s
                elif 'project' in query_types and not 'package' in query_types:
                    print prj
                if 'package' in query_types and 'packages' in p[prj]:
                    for pkg in sorted(p[prj]['packages'].keys()):
                        if opts.verbose:
                            s = pkg
                            rs = _get_role_string(p[prj]['packages'][pkg])
                            if rs:
                                s += '  ' + rs
                            print '  ', s
                        else:
                            print "%s/%s" % (prj, pkg)



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
    @cmdln.option('-i', '--involved', action='store_true',
                        help='show projects/packages where given person (or myself) is involved as bugowner or maintainer')
    @cmdln.option('-b', '--bugowner', action='store_true',
                        help='as -i, but only bugowner')
    @cmdln.option('-m', '--maintainer', action='store_true',
                        help='as -i, but only maintainer')
    @cmdln.option('--maintained', action='store_true',
                        help='limit search results to packages with maintained attribute set.')
    @cmdln.option('-M', '--mine', action='store_true',
                        help='shorthand for --bugowner --package')
    @cmdln.option('--csv', action='store_true',
                        help='generate output in CSV (separated by |)')
    @cmdln.alias('sm')
    @cmdln.alias('se')
    def do_search(self, subcmd, opts, *args):
        """${cmd_name}: Search for a project and/or package.

        If no option is specified osc will search for projects and
        packages which contains the \'search term\' in their name,
        title or description.

        usage:
            osc search \'search term\' <options>
            osc maintained \'source package name\'
            osc se ...
        ${cmd_option_list}

        osc search does not find binary rpm names. Use
        http://software.opensuse.org/search?q=binaryname
        """

        if opts.mine:
            opts.bugowner = True
            opts.package = True

        for_user = False
        if opts.involved or opts.bugowner or opts.maintainer:
            for_user = True

        search_term = None
        if len(args) > 1:
            raise oscerr.WrongArgs('Too many arguments.')
        elif len(args) < 1 and not for_user:
            raise oscerr.WrongArgs('Too few arguments.')
        elif len(args) == 1:
            search_term = args[0]

        if (opts.title or opts.description) and for_user:
            raise oscerr.WrongArgs('Sorry, the options \'--title\' and/or \'--description\' ' \
                                   'are mutually exclusive with \'-i\'/\'-b\'/\'-m\'/\'-M\'')
        search_list = []
        search_for = []
        extra_limiter = ""
        if subcmd == 'sm' or opts.maintained:
            opts.bugowner = True
            opts.package = True
            opts.limit_to_attribute = conf.config['maintained_attribute']
        if opts.title:
            search_list.append('title')
        if opts.description:
            search_list.append('description')
        if opts.package:
            search_list.append('@name')
            search_for.append('package')
        if opts.project:
            search_list.append('@name')
            search_for.append('project')
        if opts.limit_to_attribute:
            extra_limiter='attribute/@name="%s"' % (opts.limit_to_attribute)
        if not opts.substring:
            opts.exact = True
            

        role_filter=None
        if for_user:
            search_list = [ 'person/@userid' ]
            search_term = search_term or conf.get_apiurl_usr(conf.config['apiurl'])
            if opts.bugowner and not opts.maintainer:
                role_filter = search_term+':bugowner'
            if not opts.bugowner and opts.maintainer:
                role_filter = search_term+':maintainer'

        if not search_list:
            search_list = ['title', 'description', '@name']
        if not search_for:
            search_for = [ 'project', 'package' ]
        for kind in search_for:
            result = search(conf.config['apiurl'], set(search_list), kind, search_term, opts.verbose, opts.exact, opts.repos_baseurl, role_filter, extra_limiter)

            if not result:
                print 'No matches found for \'%s\' in %ss' % (role_filter or search_term, kind)
                continue

            # unfortunately, there is no sort support in the api.
            # we can do it here. Maybe it would be better done in osc.core.search() already.
            if kind in ['project']:
                result.sort()
            if kind in ['package']:
                # hm... results is a flat list
                ## FIXME: this messes up with se -v .
                l = [ (j, i) for i, j in zip(*[iter(result)]*2) ]
                l.sort()
                result = []
                ##
                ## search used to report the table as
                ## 'package project', I see no reason for having package before project.
                ## But it definitly hinders copy-paste.
                ## Changed to more normal 'project package' ordering. 2009-10-05, jw
                ##
                for j, i in l:
                    result.extend([j, i])

            if kind == 'package':
                headline = [ '# Project', '# Package' ]
            else:
                headline = [ '# Project' ]
            if opts.verbose:
                headline.append('# Title')
            if opts.repos_baseurl:
                headline.append('# URL')
            if not opts.csv:
                if len(search_for) > 1:
                    print '#' * 68
                print 'matches for \'%s\' in %ss:\n' % (role_filter or search_term, kind)
            for row in build_table(len(headline), result, headline, 2, csv = opts.csv):
                print row


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
        from util import rpmquery

        if opts.delete_old_files and conf.config['do_package_tracking']:
            # IMHO the --delete-old-files option doesn't really fit into our
            # package tracking strategy
            print >>sys.stderr, '--delete-old-files is not supported anymore'
            print >>sys.stderr, 'when do_package_tracking is enabled'
            sys.exit(1)

        if '://' in srpm:
            print 'trying to fetch', srpm
            import urlgrabber
            urlgrabber.urlgrab(srpm)
            srpm = os.path.basename(srpm)

        srpm = os.path.abspath(srpm)
        if not os.path.isfile(srpm):
            print >>sys.stderr, 'file \'%s\' does not exist' % srpm
            sys.exit(1)

        if opts.project:
            project_dir = opts.project
        else:
            project_dir = os.curdir

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
            print >>sys.stderr, 'please specify a package name with the \'--name\' option. ' \
                                'The automatic detection failed'
            sys.exit(1)

        olddir = os.getcwd()
        if conf.config['do_package_tracking']:
            createPackageDir(os.path.join(project.dir, pac), project)
            os.chdir(os.path.join(project.dir, pac))
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
                    data = ET.fromstring(''.join(data))
                    data.find('title').text = title
                    data.find('description').text = ''.join(descr)
                    data.find('url').text = url
                    data = ET.tostring(data)
                else:
                    print >>sys.stderr, 'error - cannot get meta data'
                    sys.exit(1)
                edit_meta(metatype='pkg',
                          path_args=(quote_plus(project), quote_plus(pac)),
                          data = data, apiurl=apiurl)
                os.mkdir(os.path.join(project_dir, pac))
                os.chdir(os.path.join(project_dir, pac))
                init_package_dir(apiurl, project, pac, os.path.join(project, pac))
            else:
                print >>sys.stderr, 'error - local package already exists'
                sys.exit(1)

        unpack_srcrpm(srpm, os.getcwd())
        p = Package(os.getcwd())
        if len(p.filenamelist) == 0 and opts.commit:
            print 'Adding files to working copy...'
            addFiles(glob.glob('*'))
            if conf.config['do_package_tracking']:
                os.chdir(olddir)
                project.commit((pac, ))
            else:
                p.update_datastructs()
                p.commit()
        elif opts.commit and opts.delete_old_files:
            for file in p.filenamelist:
                p.delete_remote_source_file(file)
            p.update_local_filesmeta()
            print 'Adding files to working copy...'
            addFiles(glob.glob('*'))
            p.update_datastructs()
            p.commit()
        else:
            print 'No files were committed to the server. Please ' \
                  'commit them manually.'
            print 'Package \'%s\' only imported locally' % pac
            sys.exit(1)

        print 'Package \'%s\' imported successfully' % pac


    @cmdln.option('-m', '--method', default='GET', metavar='HTTP_METHOD',
                        help='specify HTTP method to use (GET|PUT|DELETE|POST)')
    @cmdln.option('-d', '--data', default=None, metavar='STRING',
                        help='specify string data for e.g. POST')
    @cmdln.option('-f', '--file', default=None, metavar='FILE',
                        help='specify filename for e.g. PUT or DELETE')
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
          osc api -m PUT -f /etc/fstab source/home:user/test5/myfstab

        ${cmd_usage}
        ${cmd_option_list}
        """

        if not opts.method in ['GET', 'PUT', 'POST', 'DELETE']:
            sys.exit('unknown method %s' % opts.method)

        if not url.startswith('http'):
            if not url.startswith('/'):
                url = '/' + url
            url = conf.config['apiurl'] + url

        if opts.headers:
            opts.headers = dict(opts.headers)

        r = http_request(opts.method,
                         url,
                         data=opts.data,
                         file=opts.file,
                         headers=opts.headers)

        out = r.read()
        sys.stdout.write(out)

    @cmdln.option('-v', '--verbose', action='store_true',
                  help='show more information')
    @cmdln.option('--nodevelproject', action='store_true',
                  help='do not follow a defined devel project ' \
                       '(primary project where a package is developed)')
    @cmdln.option('-e', '--email', action='store_true',
                  help='show email addresses instead of user names')
    def do_bugowner(self, subcmd, opts, *args):
        """${cmd_name}: Show bugowners of a project/package

            osc bugowner PRJ 
            osc bugowner PRJ PKG

        Shortcut for osc maintainer -B [PRJ] PKG

        PRJ defaults to '%(getpac_default_project)s'.
        Prints bugowner if defined, or maintainer otherwise.

        ${cmd_option_list}
        """
        opts.role = ()
        opts.bugowner = True
        opts.bugowner_only = None
        opts.add = None
        opts.delete = None
        opts.devel_project = None

        if len(args) == 1:
            print >>sys.stderr, 'defaulting to %s/%s' % (conf.config['getpac_default_project'], args[0])
            # python has no args.unshift ???
            args = [ conf.config['getpac_default_project'] , args[0] ]
        return self.do_maintainer(subcmd, opts, *args)


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
                  help='add a new maintainer/bugowner (can be specified via --role)')
    @cmdln.option('-d', '--delete', metavar='user',
                  help='delete a maintainer/bugowner (can be specified via --role)')
    @cmdln.option('-r', '--role', metavar='role', action='append', default=[],
                  help='Specify user role')
    def do_maintainer(self, subcmd, opts, *args):
        """${cmd_name}: Show maintainers of a project/package

        To be used like this:

            osc maintainer PRJ <options>
        or
            osc maintainer PRJ PKG <options>

        ${cmd_usage}
        ${cmd_option_list}
        """

        pac = None
        root = None
        roles = [ 'bugowner', 'maintainer' ]
        if len(opts.role):
            roles = opts.role
        if opts.bugowner_only or opts.bugowner:
            roles = [ 'bugowner' ]

        if len(args) == 1:
            prj = args[0]
            m = show_project_meta(conf.config['apiurl'], prj)
            root = ET.fromstring(''.join(m))
        elif len(args) == 2:
            prj = args[0]
            pac = args[1]
            m = show_package_meta(conf.config['apiurl'], prj, pac)
            root = ET.fromstring(''.join(m))
            if not opts.nodevelproject and not opts.delete and not opts.add:
                while root.findall('devel'):
                    d = root.find('devel')
                    prj = d.get('project', prj)
                    pac = d.get('package', pac)
                    if opts.verbose:
                        print "Following to the development space:", prj, "/", pac
                    m = show_package_meta(conf.config['apiurl'], prj, pac)
                    root = ET.fromstring(''.join(m))
                if not root.findall('person'):
                    print "No dedicated persons in package defined, showing the project persons !"
                    m = show_project_meta(conf.config['apiurl'], prj)
                    root = ET.fromstring(''.join(m))
        else:
            raise oscerr.WrongArgs('I need at least one argument.')

        if opts.add:
            for role in roles:
                addPerson(conf.config['apiurl'], prj, pac, opts.add, role)
        elif opts.delete:
            for role in roles:
                delPerson(conf.config['apiurl'], prj, pac, opts.delete, role)
        elif opts.devel_project:
            # XXX: does it really belong to this command?
            setDevelProject(conf.config['apiurl'], prj, pac, opts.devel_project)
        else:
            # showing the maintainers
            maintainers = {}
            for person in root.findall('person'):
                maintainers.setdefault(person.get('role'), []).append(person.get('userid'))
            for role in roles:
                if opts.bugowner and not len(maintainers.get(role, [])):
                    role = 'maintainer'
                print role + ':'
                if opts.email:
                    emails = []
                    for maintainer in maintainers.get(role, []):
                        user = get_user_data(conf.config['apiurl'], maintainer, 'email')
                        if len(user):
                            emails.append(''.join(user))
                    print ', '.join(emails) or '-'
                elif opts.verbose:
                    userdata = []
                    for maintainer in maintainers.get(role, []):
                        user = get_user_data(conf.config['apiurl'], maintainer, 'realname', 'login', 'email')
                        userdata.extend(user)
                    for row in build_table(3, userdata, ['realname', 'userid', 'email\n']):
                        print row
                else:
                    print ', '.join(maintainers.get(role, [])) or '-'
                print


    @cmdln.option('-r', '--revision', metavar='rev',
                  help='print out the specified revision')
    @cmdln.option('-e', '--expand', action='store_true',
                  help='expand linked package')
    def do_cat(self, subcmd, opts, *args):
        """${cmd_name}: Output the content of a file to standard output

        Examples:
            osc cat project package file
            osc cat project/package/file
            osc cat http://api.opensuse.org/build/.../_log
            osc cat http://api.opensuse.org/source/../_link

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
        if len(args) != 3:
            raise oscerr.WrongArgs('Wrong number of arguments.')
        rev, dummy = parseRevisionOption(opts.revision)

        query = { }
        if opts.revision:
            query['rev'] = opts.revision
        if opts.expand:
            query['rev'] = show_upstream_srcmd5(conf.config['apiurl'], args[0], args[1], expand=True, revision=opts.revision)
        u = makeurl(conf.config['apiurl'], ['source', args[0], args[1], args[2]], query=query)
        for data in streamfile(u):
            sys.stdout.write(data)


    # helper function to download a file from a specific revision
    def download(self, name, md5, dir, destfile):
        o = open(destfile, 'wb')
        if md5 != '':
            query = {'rev': dir['srcmd5']}
            u = makeurl(dir['apiurl'], ['source', dir['project'], dir['package'], pathname2url(name)], query=query)
            for buf in streamfile(u, http_GET, BUFSIZE):
                o.write(buf)
        o.close


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

        apiurl = conf.config['apiurl']
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
            apiurl = store_read_apiurl(os.getcwd())
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

        baserev = linkinfo.get('baserev')
        if baserev != None:
            query = { 'rev': 'latest', 'linkrev': baserev }
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
            print "using last working link target"
        else:
            print "using link target of last commit"

        query = { 'expand': 1, 'emptylink': 1 }
        u = makeurl(apiurl, ['source', prj, package], query=query)
        f = http_GET(u)
        meta = f.readlines()
        root_new = ET.fromstring(''.join(meta))
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

        olddir=os.getcwd()
        os.chdir(destdir)
        init_package_dir(apiurl, target_prj, target_package, destdir, files=False)
        os.chdir(olddir)
        store_write_string(destdir, '_files', ''.join(meta))
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
                print statfrmt(' ', name)
                self.download(name, md5_oldpatched, dir_oldpatched, os.path.join(destdir, name))
                continue
            if md5_old == md5_oldpatched:
                if md5_new == '':
                    continue
                print statfrmt('U', name)
                shutil.copy2(os.path.join(storedir, name), os.path.join(destdir, name))
                continue
            if md5_new == md5_oldpatched:
                if md5_new == '':
                    continue
                print statfrmt('G', name)
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
                print statfrmt('C', name)
                pac.put_on_conflictlist(name)
                continue

            o = open(os.path.join(destdir,  name), 'wb')
            code = subprocess.call(['diff3', '-m',
              '-L', '.mine',
              os.path.join(destdir, name + '.mine'),
              '-L', '.old',
              os.path.join(destdir, name + '.old'),
              '-L', '.new',
              os.path.join(destdir, name + '.new'),
            ], stdout=o)
            if code == 0:
                print statfrmt('G', name)
                os.unlink(os.path.join(destdir, name + '.mine'))
                os.unlink(os.path.join(destdir, name + '.old'))
                os.unlink(os.path.join(destdir, name + '.new'))
            elif code == 1:
                print statfrmt('C', name)
                pac.put_on_conflictlist(name)
            else:
                print statfrmt('?', name)
                pac.put_on_conflictlist(name)

        pac.write_deletelist()
        pac.write_conflictlist()
        print
        print 'Please change into the \'%s\' directory,' % destdir
        print 'fix the conflicts (files marked with \'C\' above),'
        print 'run \'osc resolved ...\', and commit the changes.'


    def do_pull(self, subcmd, opts, *args):
        """${cmd_name}: merge the changes of the link target into your working copy.

        ${cmd_option_list}
        """

        if not is_package_dir('.'):
            raise oscerr.NoWorkingCopy('Error: \'%s\' is not an osc working copy.' % os.path.abspath('.'))
        p = Package('.')
        # check if everything is committed
        for filename in p.filenamelist:
            if p.status(filename) != ' ':
                raise oscerr.WrongArgs('Please commit your local changes first!')
        # check if we need to update
        upstream_rev = p.latest_rev()
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
        root_new = ET.fromstring(''.join(meta))
        linkinfo_new = root_new.find('linkinfo')
        if linkinfo_new == None:
            raise oscerr.APIError('link is not a really a link?')
        if linkinfo_new.get('error') != None:
            raise oscerr.APIError('link target is broken')
        if linkinfo_new.get('srcmd5') == baserev:
            print "Already up-to-date."
            if os.path.exists(os.path.join(p.storedir, '_frozenlink')):
                os.unlink(os.path.join(p.storedir, '_frozenlink'))
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
            md5_old = entries_old.get(name, '')
            md5_new = entries_new.get(name, '')
            md5_oldpatched = entries_oldpatched.get(name, '')
            if md5_old == md5_new or md5_oldpatched == md5_new:
                continue
            if md5_old == md5_oldpatched:
                if md5_new == '':
                    print statfrmt('D', name)
                    p.put_on_deletelist(name)
                    os.unlink(name)
                else:
                    print statfrmt('U', name)
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
                print statfrmt('C', name)
                p.put_on_conflictlist(name)
                continue

            o = open(name, 'wb')
            code = subprocess.call(['diff3', '-m',
              '-L', '.mine', name + '.mine',
              '-L', '.old', name + '.old',
              '-L', '.new', name + '.new',
            ], stdout=o)
            if code == 0:
                print statfrmt('G', name)
                os.unlink(name + '.mine')
                os.unlink(name + '.old')
                os.unlink(name + '.new')
            elif code == 1:
                print statfrmt('C', name)
                p.put_on_conflictlist(name)
            else:
                print statfrmt('?', name)
                p.put_on_conflictlist(name)
        p.write_deletelist()
        p.write_conflictlist()
        # store new linkrev
        store_write_string(p.absdir, '_pulled', linkinfo_new.get('srcmd5'))
        if os.path.exists(os.path.join(p.storedir, '_frozenlink')):
            os.unlink(os.path.join(p.storedir, '_frozenlink'))
        print
        if len(p.in_conflict):
            print 'Please fix the conflicts (files marked with \'C\' above),'
            print 'run \'osc resolved ...\', and commit the changes'
            print 'to update the link information.'
        else:
            print 'Please commit the changes to update the link information.'

    @cmdln.option('--create', action='store_true', default=False,
                  help='create new gpg signing key for this project')
    @cmdln.option('--delete', action='store_true', default=False,
                  help='delete the gpg signing key in this project')
    @cmdln.option('--notraverse', action='store_true', default=False,
                  help='don\' traverse projects upwards to find key')
    def do_signkey(self, subcmd, opts, *args):
        """${cmd_name}: Manage Project Signing Key

        osc signkey [--create|--delete] <PROJECT>
        osc signkey [--notraverse] <PROJECT>

        This command is for managing gpg keys. It shows the public key
        by default. There is no way to download or upload the private
        part of a key by design.

        However you can create a new own key. You may want to consider
        to sign the public key with your own existing key.

        If a project has no key, the key from upper level project will
        be used (eg. when dropping "KDE:KDE4:Community" key, the one from
        "KDE:KDE4" will be used).

        WARNING: THE OLD KEY WILL NOT BE RESTORABLE WHEN USING DELETE OR CREATE

        ${cmd_usage}
        ${cmd_option_list}
        """

        apiurl = conf.config['apiurl']
        f = None

        prj = None
        if len(args) == 0:
            dir = os.getcwd()
            if is_project_dir(dir) or is_package_dir(dir):
                prj = store_read_project(dir)
                apiurl = store_read_apiurl(dir)
        if len(args) == 1:
            prj = args[0]

        if not prj:
            raise oscerr.WrongArgs('Please specify just the project')

        if opts.create:
            url = makeurl(apiurl, ['source', prj], query='cmd=createkey')
            f = http_POST(url)
        elif opts.delete:
            url = makeurl(apiurl, ['source', prj, "_pubkey"])
            f = http_DELETE(url)
        else:
            prjs = [ prj ]
            for prj in prjs:
                try:
                    url = makeurl(apiurl, ['source', prj, "_pubkey"])
                    f = http_GET(url)
                    break
                except:
                    l = prj.rsplit(':', 1)
                    # try key from parent project
                    if not opts.notraverse and len(l) > 1 and l[1]:
                        print "%s has no key, trying %s" % (prj, l[0])
                        prjs.append(l[0])
                    else:
                        raise

        while 1:
            buf = f.read(16384)
            if not buf: break
            print buf



    @cmdln.option('-m', '--message',
                  help='add MESSAGE to changes (not open an editor)')
    @cmdln.option('-e', '--just-edit', action='store_true', default=False,
                  help='just open changes (cannot be used with -m)')
    def do_vc(self, subcmd, opts, *args):
        """${cmd_name}: Edit the changes file

        osc vc [-m MESSAGE|-e] [filename[.changes]|path [file_with_comment]]
        If no <filename> is given, exactly one *.changes or *.spec file has to
        be in the cwd or in path.

        The email address used in .changes file is read from BuildService
        instance, or should be defined in ~/.oscrc
        [https://api.opensuse.org/]
        user = login
        pass = password
        email = user@defined.email

        or can be specified via mailaddr environment variable.

        ${cmd_usage}
        ${cmd_option_list}
        """

        from subprocess import Popen, PIPE

        if not os.path.exists('/usr/lib/build/vc'):
            print >>sys.stderr, 'Error: you need build.rpm with version 2009.04.17 or newer'
            print >>sys.stderr, 'See http://download.opensuse.org/repositories/openSUSE:/Tools/'
            return 1

        cmd_list = ["/usr/lib/build/vc", ]

        if len(args) > 0:
            arg = args[0]
        else:
            arg = ""

        # set user's email if no mailaddr exists
        if not os.environ.has_key('mailaddr'):

            if arg and is_package_dir(arg):
                apiurl = store_read_apiurl(arg)
            elif is_package_dir(os.getcwd()):
                apiurl = store_read_apiurl(os.getcwd())
            else:
                apiurl = conf.config['apiurl']

            user = conf.get_apiurl_usr(apiurl)

            # work with all combinations of URL with or withouth the ending slash
            if conf.config['api_host_options'][apiurl].has_key('email'):
                os.environ['mailaddr'] = conf.config['api_host_options'][apiurl]['email']
            else:
                try:
                    os.environ['mailaddr'] = get_user_data(apiurl, user, 'email')[0]
                except Exception, e:
                    sys.exit('%s\nget_user_data(email) failed. Try env mailaddr=....\n' % e)

        if opts.message:
            cmd_list.append("-m")
            cmd_list.append(opts.message)

        if opts.just_edit:
            cmd_list.append("-e")

        if args:
            cmd_list.extend(args)

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
            raise oscerr.WrongArgs("Source file ``%s'' does not exists" % source)
        if not opts.force and os.path.isfile(dest):
            raise oscerr.WrongArgs("Dest file ``%s'' already exists" % dest)
        if not is_package_dir('.'):
            raise oscerr.NoWorkingCopy("Error: \"%s\" is not an osc working copy." % os.path.abspath(dir))

        p = findpacs('.')[0]
        os.rename(source, dest)
        self.do_add(subcmd, opts, dest)
        self.do_delete(subcmd, opts, source)


# fini!
###############################################################################

    # load subcommands plugged-in locally
    plugin_dirs = [
        '/usr/lib/osc-plugins',
        '/usr/local/lib/osc-plugins',
        '/var/lib/osc-plugins',  # Kept for backward compatibility
        os.path.expanduser('~/.osc-plugins')]
    for plugin_dir in plugin_dirs:
        if os.path.isdir(plugin_dir):
            for extfile in os.listdir(plugin_dir):
                if not extfile.endswith('.py'):
                    continue
                exec open(os.path.join(plugin_dir, extfile))


