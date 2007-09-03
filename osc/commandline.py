#!/usr/bin/python

# Copyright (C) 2006 Peter Poeml / Novell Inc.  All rights reserved.
# This program is free software; it may be used, copied, modified
# and distributed under the terms of the GNU General Public Licence,
# either version 2, or (at your option) any later version.


from core import *
import cmdln
import conf


class Osc(cmdln.Cmdln):
    """usage:
        osc [GLOBALOPTS] SUBCOMMAND [OPTS] [ARGS...]
        osc help SUBCOMMAND
    OpenSUSE build service command-line tool.
    Type 'osc help <subcommand>' for help on a specific subcommand.

    ${command_list}
    ${help_list}
    global ${option_list}
    For additional information, see 
    * http://www.opensuse.org/Build_Service_Tutorial
    * http://www.opensuse.org/Build_Service/CLI
    """
    name = 'osc'


    def __init__(self, *args, **kwargs):
        cmdln.Cmdln.__init__(self, *args, **kwargs)
        cmdln.Cmdln.do_help.aliases.append('h')


    def get_optparser(self):
        """this is the parser for "global" options (not specific to subcommand)"""

        optparser = cmdln.CmdlnOptionParser(self, version=get_osc_version())
        optparser.add_option('-H', '--http-debug', action='store_true',
                      help='debug HTTP traffic')
        optparser.add_option('-A', '--apisrv', dest='apisrv',
                      metavar='URL',
                      help='specify URL to access API server at')
        optparser.add_option('-c', '--config', dest='conffile',
                      metavar='FILE',
                      help='specify alternate configuration file')
        return optparser


    def postoptparse(self):
        """merge commandline options into the config"""

        conf.get_config(override_conffile = self.options.conffile,
                        override_http_debug = self.options.http_debug,
                        override_apisrv = self.options.apisrv)


    def do_init(self, subcmd, opts, project, package):
        """${cmd_name}: Initialize a directory as working copy 

        Initialize a directory to be a working copy of an
        existing buildservice package. 
        
        (This is the same as checking out a
        package and then copying sources into the directory. It does NOT create
        a new package. To create a package, use createpac.)

        usage: 
            osc init PRJ PAC
        ${cmd_option_list}
        """

        init_package_dir(conf.config['apiurl'], project, package, os.path.curdir)
        print 'Initializing %s (Project: %s, Package: %s)' % (os.curdir, project, package)


    @cmdln.alias('ls')
    @cmdln.option('-a', '--arch', metavar='ARCH',
                        help='specify architecture')
    @cmdln.option('-r', '--repo', metavar='REPO',
                        help='specify repository')
    @cmdln.option('-b', '--binaries', action='store_true',
                        help='list built binaries, instead of sources')
    @cmdln.option('-v', '--verbose', action='store_true',
                        help='print extra information')
    def do_list(self, subcmd, opts, *args):
        """${cmd_name}: List existing content on the server

        This command is used to list sources, or binaries (when used with the
        --binaries option). To use the --binary option, --repo and --arch are
        also required.

        Examples:
           ls                         # list all projects
           ls Apache                  # list packages in a project
           ls -b Apache               # list all binaries of a project
           ls Apache apache2          # list source files of package of a project
           ls -v Apache apache2       # verbosely list source files of package 

        With --verbose, the following fields will be shown for each item:
           MD5 hash of file
           Revision number of the last commit
           Size (in bytes)
           Date and time of the last commit

        ${cmd_usage}
        ${cmd_option_list}
        """

        args = slash_split(args)

        if len(args) == 1:
            project = args[0]
        elif len(args) == 2:
            project = args[0]
            package = args[1]

        if opts.binaries and (not opts.repo or not opts.arch):
            sys.exit('missing options:\n'
                     '-r <repo> -a <arch>\n'
                     'list repositories with:\n'
                     '\'osc platforms %s\'' %project)

        # list binaries
        if opts.binaries:
            if not args:
                sys.exit('there are no binaries to list above project level.')

            elif len(args) == 1:
                #if opts.verbose:
                #    sys.exit('The verbose option is not implemented for projects.')
                r = get_binarylist(conf.config['apiurl'], project, opts.repo, opts.arch)
                print '\n'.join(r)

            elif len(args) == 2:
                r = get_binarylist(conf.config['apiurl'], project, opts.repo, opts.arch, package=package)
                print '\n'.join(r)

        # list sources
        elif not opts.binaries:
            if not args:
                print '\n'.join(meta_get_project_list(conf.config['apiurl']))

            elif len(args) == 1:
                if opts.verbose:
                    sys.exit('The verbose option is not implemented for projects.')

                print '\n'.join(meta_get_packagelist(conf.config['apiurl'], project))

            elif len(args) == 2:
                l = meta_get_filelist(conf.config['apiurl'], 
                                      project, 
                                      package,
                                      verbose=opts.verbose)
                if opts.verbose:
                    for i in l:
                        print '%s %7d %9d %s %s' \
                            % (i.md5, i.rev, i.size, shorttime(i.mtime), i.name)
                else:
                    print '\n'.join(l)


    @cmdln.option('-F', '--file', metavar='FILE',
                        help='read metadata from FILE, instead of opening an editor. '
                        '\'-\' denotes standard input. ')
    @cmdln.option('-e', '--edit', action='store_true',
                        help='edit metadata')
    @cmdln.option('--delete', action='store_true',
                        help='delete a pattern file')
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
        osc meta prjconf home:poeml | sed ... | osc meta prjconf home:poeml -F -

        When trying to edit a non-existing resource, it is created implicitely.


        Examples:
            osc meta prj PRJ
            osc meta pkg PRJ PKG
            osc meta pkg PRJ PKG -e

        Usage:
            osc meta <prj|pkg|prjconf|user|pattern> ARGS...
            osc meta <prj|pkg|prjconf|user|pattern> -e|--edit ARGS...
            osc meta <prj|pkg|prjconf|user|pattern> -F|--file ARGS...
            osc meta pattern --delete PRJ PATTERN
        ${cmd_option_list}
        """

        args = slash_split(args)

        if not args or args[0] not in metatypes.keys():
            print >>sys.stderr, 'Unknown meta type. Choose one of %s.' % ', '.join(metatypes)
            return 2

        cmd = args[0]
        del args[0]

        if cmd in ['pkg']:
            min_args, max_args = 2, 2
        elif cmd in ['pattern']:
            min_args, max_args = 1, 2
        else:
            min_args, max_args = 1, 1
        if len(args) < min_args:
            print >>sys.stderr, 'Too few arguments.'
            return 2
        if len(args) > max_args:
            print >>sys.stderr, 'Too many arguments.'
            return 2

        # specific arguments
        if cmd == 'prj':
            project = args[0]
        elif cmd == 'pkg':
            project, package = args[0:2]
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
                    sys.exit('a pattern file argument is required.')

        # show 
        if not opts.edit and not opts.file and not opts.delete:
            if cmd == 'prj':
                sys.stdout.write(''.join(show_project_meta(conf.config['apiurl'], project)))
            elif cmd == 'pkg':
                sys.stdout.write(''.join(show_package_meta(conf.config['apiurl'], project, package)))
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
                          template_args=(project, conf.config['user']))
            elif cmd == 'pkg':
                edit_meta(metatype='pkg', 
                          edit=True,
                          path_args=(quote_plus(project), quote_plus(package)),
                          template_args=(package, conf.config['user']))
            elif cmd == 'prjconf':
                edit_meta(metatype='prjconf', 
                          edit=True,
                          path_args=quote_plus(project),
                          template_args=None)
            elif cmd == 'user':
                edit_meta(metatype='user', 
                          edit=True,
                          path_args=(quote_plus(user)),
                          template_args=(user, user))
            elif cmd == 'pattern':
                edit_meta(metatype='pattern', 
                          edit=True,
                          path_args=(project, pattern),
                          template_args=None)

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
            else:
                sys.exit('The --delete switch is only for pattern metadata.')



    # editmeta and its aliases are all depracated
    @cmdln.alias("editprj")
    @cmdln.alias("createprj")
    @cmdln.alias("editpac")
    @cmdln.alias("createpac")
    @cmdln.alias("edituser")
    @cmdln.alias("usermeta")
    def do_editmeta(self, subcmd, opts, *args):
        """${cmd_name}: 
        
        Obsolete command to edit metadata. Use 'meta' now.

        See the help output of 'meta'.

        """

        print >>sys.stderr, 'This command is obsolete. Use \'osc meta <metatype> ...\'.'
        print >>sys.stderr, 'See \'osc help meta\'.'
        #self.do_help([None, 'meta'])
        return 2

#    @cmdln.alias("createpac")
#    def do_editpac(self, subcmd, opts, project, package):
#        """${cmd_name}: Create package or edit package metadata
#
#        If the named package does not exist, it will be created.
#
#        ${cmd_usage}
#        ${cmd_option_list}
#        """
#
#        edit_meta(project, package)


#    @cmdln.alias('createprj')
#    def do_editprj(self, subcmd, opts, project):
#        """${cmd_name}: Create project or edit project metadata
#
#        If the named project does not exist, it will be created.
#
#        ${cmd_usage}
#        ${cmd_option_list}
#        """
#
#        edit_meta(project, None)


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
            print >>sys.stderr, 'Incorrect number of argument.'
            self.do_help([None, 'linkpac'])
            return 2

        src_project = args[0]
        src_package = args[1]
        dst_project = args[2]
        if len(args) > 3:
            dst_package = args[3]
        else:
            dst_package = src_package

        if src_project == dst_project and src_package == dst_package:
            print >>sys.stderr, 'Error: source and destination are the same.'
            return 1
        link_pac(src_project, src_package, dst_project, dst_package)


    @cmdln.option('-t', '--to-apiurl', metavar='URL',
                        help='URL of destination api server. Default is the source api server.')
    def do_copypac(self, subcmd, opts, *args):
        """${cmd_name}: Copy a package

        A client-side copy implementation. It can be done cross-project, or even 
        across buildservice instances, if the -t option is used.

        The DESTPAC name is optional; the source packages' name will be used if
        DESTPAC is omitted.

        usage: 
            osc copypac SOURCEPRJ SOURCEPAC DESTPRJ [DESTPAC]
        ${cmd_option_list}
        """

        args = slash_split(args)

        if not args or len(args) < 3:
            print >>sys.stderr, 'Incorrect number of argument.'
            self.do_help([None, 'copypac'])
            return 2

        src_project = args[0]
        src_package = args[1]
        dst_project = args[2]
        if len(args) > 3:
            dst_package = args[3]
        else:
            dst_package = src_package

        src_apiurl = conf.config['apiurl']
        if opts.to_apiurl:
            dst_apiurl = opts.to_apiurl
        else:
            dst_apiurl = src_apiurl

        if src_project == dst_project and \
           src_package == dst_package and \
           src_apiurl == dst_apiurl:
            print >>sys.stderr, 'Error: source and destination are the same.'
            return 1
        copy_pac(src_apiurl, src_project, src_package, 
                 dst_apiurl, dst_project, dst_package)


    def do_deletepac(self, subcmd, opts, project, package):
        """${cmd_name}: Delete a package on the repository server

        ${cmd_usage}
        ${cmd_option_list}
        """

        delete_package(conf.config['apiurl'], project, package)


    def do_deleteprj(self, subcmd, opts, project):
        """${cmd_name}: Delete a project on the repository server

        As a safety measure, project must be empty (i.e., you first need to delete all
        packages first).

        NOTE: This command is not implemented yet. Please mail
        admin@opensuse.org in order to get projects deleted.

        ${cmd_usage}
        ${cmd_option_list}
        """

        if meta_get_packagelist(conf.config['apiurl'], project) != []:
            print >>sys.stderr, 'Project contains packages. It must be empty before deleting it.'
            return 1

        #delete_project(conf.config['apiurl'], project)
        print >>sys.stderr, 'Deleting projects is not yet implemented.'
        print >>sys.stderr, 'Please send a request to opensuse-buildservice@opensuse.org'
        print >>sys.stderr, 'or admin@opensuse.org.'


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
    @cmdln.option('-r', '--revision', metavar='rev1[:rev2]',
                        help='If rev1 is specified it will compare your working copy against '
                             'the revision (rev1) on the server. '
                             'If rev1 and rev2 are specified it will compare rev1 against rev2'
                             '(changes in your working copy are ignored in this case).\n'
                             'NOTE: if more than 1 package is specified --revision will be ignored!')
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
        
        difference_found = False
        d = []
        
        rev1, rev2 = parseRevisionOption(opts.revision)
        pac = pacs[0]
        
        if rev1 and rev2 and (len(pacs) == 1):
            # this is currently not implemented
            print >>sys.stderr, 'this feature isn\'t implemented yet'
            sys.exit(1)
        elif rev1 and (pac.rev != rev1) and (len(pacs) == 1):
            if not checkRevision(pac.prjname, pac.name, rev1):
                print >>sys.stderr, 'Revision \'%s\' does not exist' % rev1
                sys.exit(1)
            # make a temp dir for checking out the project
            import tempfile
            tmpdir = tempfile.mkdtemp(rev1, pac.name, '/tmp')
            curdir = os.getcwd()
            os.chdir(tmpdir)
            init_package_dir(conf.config['apiurl'], pac.prjname, pac.name, tmpdir, rev1)
            os.chdir(curdir)
            tmppac = Package(tmpdir)

            changed_files = []
            added_files = []
            removed_files = []
            if pac.todo:
                for file in pac.todo:
                    if file in tmppac.filenamelist:
                        if dgst(os.path.join(pac.dir, file)) != tmppac.findfilebyname(file).md5:
                            changed_files.append(file)
                    else:
                        added_files.append(file)
            else:           
                changed_files, added_files, removed_files = pac.comparePac(tmppac)
           
            for file in changed_files:
                tmppac.updatefile(file, rev1)
                d.append('Index: %s\n' % file)
                d.append('===================================================================\n')
                d.append(get_source_file_diff(pac.dir, file, rev1, file, tmppac.dir))
                tmppac.delete_localfile(file)
                tmppac.delete_storefile(file)

            # this tempfile is used as a dummy file for difflib
            (fd, filename) = tempfile.mkstemp(dir=tmppac.storedir)

            for file in added_files:
                d.append('Index: %s\n' % file)
                d.append('===================================================================\n')
                d.append(get_source_file_diff(pac.dir, file, rev1, \
                                              os.path.basename(filename), \
                                              tmppac.storedir, file))
        
            for file in removed_files:
                tmppac.updatefile(file, rev1)
                d.append('Index: %s\n' % file)
                d.append('===================================================================\n')
                d.append(get_source_file_diff(tmppac.storedir, \
                                              os.path.basename(filename), \
                                              rev1, file, tmppac.dir, file))
                tmppac.delete_localfile(file)
                tmppac.delete_storefile(file)

            # clean up 
            os.unlink(filename)
            for dir, dirnames, files in os.walk(tmppac.storedir):
                for file in files:
                    os.unlink(os.path.join(dir, file))
            os.rmdir(tmppac.storedir)
            os.rmdir(tmppac.dir)
        else:
            for p in pacs:
                if p.todo == []:
                    for i in p.filenamelist:
                        s = p.status(i)
                        if s == 'M' or s == 'C':
                            p.todo.append(i)

                for filename in p.todo:
                    d.append('Index: %s\n' % filename)
                    d.append('===================================================================\n')
                    d.append(get_source_file_diff(p.dir, filename, p.rev))

        
        if d:
            print ''.join(d)
            difference_found = True

        if difference_found:
            return 1
                
    def do_repourls(self, subcmd, opts, *args):
        """${cmd_name}: shows URLs of .repo files 

        Shows URLs on which to access the project .repos files (yum-style
        metadata) on download.opensuse.org.

        ARG, if specified, is a package working copy.

        ${cmd_usage}
        ${cmd_option_list}
        """

        args = parseargs(args)
        pacs = findpacs(args)

        url_tmpl = 'http://download.opensuse.org/repositories/%s/%s/%s.repo'
        for p in pacs:
            platforms = get_platforms_of_project(p.apiurl, p.prjname)
            for platform in platforms:
                print url_tmpl % (p.prjname.replace(':', ':/'), platform, p.prjname)



    @cmdln.option('-r', '--revision', metavar='rev',
                        help='checkout the specified revision. '
                             'NOTE: if you checkout the complete project '
                             'this option is ignored!')
    @cmdln.alias('co')
    def do_checkout(self, subcmd, opts, *args):
        """${cmd_name}: check out content from the repository
        
        Check out content from the repository server, creating a local working
        copy.

        examples:
            osc co Apache                    # entire project
            osc co Apache apache2            # a package
            osc co Apache apache2 foo        # single file -> to current dir

        usage: 
            osc co PROJECT [PACKAGE] [FILE]
        ${cmd_option_list}
        """

        args = slash_split(args)
        project = package = filename = None
        try: 
            project = args[0]
            package = args[1]
            filename = args[2]
        except: 
            pass

        rev, dummy = parseRevisionOption(opts.revision)

        if rev and not checkRevision(project, package, rev):
            print >>sys.stderr, 'Revision \'%s\' does not exist' % rev
            sys.exit(1)

        if filename:
            get_source_file(conf.config['apiurl'], project, package, filename, revision=rev)

        elif package:
            checkout_package(conf.config['apiurl'], project, package, rev)

        elif project:
            # all packages
            for package in meta_get_packagelist(conf.config['apiurl'], project):
                checkout_package(conf.config['apiurl'], project, package)
        else:
            print >>sys.stderr, 'Missing argument.'
            self.do_help([None, 'checkout'])
            return 2


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
          '!' item is missing (removed by non-svn command) or incomplete

        examples:
          osc st
          osc st <directory>
          osc st file1 file2 ...

        usage: 
            osc status [OPTS] [PATH...]
        ${cmd_option_list}
        """

        args = parseargs(args)

        pacpaths = []
        for arg in args:
            # when 'status' is run inside a project dir, it should
            # stat all packages existing in the wc
            if is_project_dir(arg):
                prj = Project(arg)
                pacpaths += [arg + '/' + n for n in prj.pacs_have]
            elif is_package_dir(arg):
                pacpaths.append(arg)
            elif os.path.isfile(arg):
                pacpaths.append(arg)
            else:
                print >>sys.stderr, 'osc: error: %s is neither a project or a package directory' % arg
                return 1
            

        pacs = findpacs(pacpaths)

        for p in pacs:

            # no files given as argument? Take all files in current dir
            if not p.todo:
                p.todo = p.filenamelist + p.filenamelist_unvers
            p.todo.sort()

            lines = []
            for filename in p.todo:
                if filename in p.excluded:
                    continue
                s = p.status(filename)
                if s == 'F':
                    lines.append(statfrmt('!', pathjoin(p.dir, filename)))
                elif s != ' ' or (s == ' ' and opts.verbose):
                    lines.append(statfrmt(s, pathjoin(p.dir, filename)))

            # arrange the lines in order: unknown files first
            # filenames are already sorted
            lines = [line for line in lines if line[0] == '?'] \
                  + [line for line in lines if line[0] != '?']
            if lines:
                print '\n'.join(lines)


    def do_add(self, subcmd, opts, *args):
        """${cmd_name}: Mark files to be added upon the next commit

        usage: 
            osc add FILE [FILE...]
        ${cmd_option_list}
        """
        if not args:
            print >>sys.stderr, 'Missing argument.'
            self.do_help([None, 'add'])
            return 2

        filenames = parseargs(args)

        for filename in filenames:
            if not os.path.exists(filename):
                print >>sys.stderr, "file '%s' does not exist" % filename
                return 1

        pacs = findpacs(filenames)

        for pac in pacs:
            for filename in pac.todo:
                if filename in pac.excluded:
                    continue
                if filename in pac.filenamelist:
                    print >>sys.stderr, 'osc: warning: \'%s\' is already under version control' % filename
                    continue

                pac.addfile(filename)
                print statfrmt('A', filename)


    def do_addremove(self, subcmd, opts, *args):
        """${cmd_name}: Adds new files, removes disappeared files

        Adds all files new in the local copy, and removes all disappeared files.

        ARG, if specified, is a package working copy.

        ${cmd_usage}
        ${cmd_option_list}
        """

        args = parseargs(args)
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
                    p.addfile(filename)
                    print statfrmt('A', filename)
                elif state == '!':
                    p.put_on_deletelist(filename)
                    p.write_deletelist()
                    os.unlink(os.path.join(p.storedir, filename))
                    print statfrmt('D', filename)



    @cmdln.alias('ci')
    @cmdln.alias('checkin')
    @cmdln.option('-m', '--message', metavar='TEXT',
                  help='specify log message TEXT')
    @cmdln.option('-F', '--file', metavar='FILE',
                  help='read log message from FILE')
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

        args = parseargs(args)
        pacs = findpacs(args)

        for p in pacs:
            msg = ''
            if opts.message:
                msg = opts.message
            elif opts.file:
                try:
                    msg = open(opts.file).read()
                except:
                    sys.exit('could not open file \'%s\'.' % opts.file)
            p.commit(msg)


    @cmdln.option('-r', '--revision', metavar='rev',
                        help='update to specified revision (this option will be ignored '
                             'if you are going to update the complete project or more than '
                             'one package)')
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

        ${cmd_usage}
        ${cmd_option_list}
        """

        args = parseargs(args)

        for arg in args:

            # when 'update' is run inside a project dir, it should...
            if is_project_dir(arg):

                prj = Project(arg)

                # (a) update all packages
                args += prj.pacs_have

                # (b) fetch new packages
                prj.checkout_missing_pacs()
                args.remove(arg)


        pacs = findpacs(args)

        if opts.revision and ( len(args) == 1):
            rev, dummy = parseRevisionOption(opts.revision)
            if not checkRevision(pacs[0].prjname, pacs[0].name, rev):
                print >>sys.stderr, 'Revision \'%s\' does not exist' % rev
                sys.exit(1)
        else:
            rev = None

        for p in pacs:

            if len(pacs) > 1:
                print 'Updating %s' % p.name
            # save filelist and (modified) status before replacing the meta file
            saved_filenames = p.filenamelist
            saved_modifiedfiles = [ f for f in p.filenamelist if p.status(f) == 'M' ]

            oldp = p
            p.update_local_filesmeta(rev)
            p = Package(p.dir)

            # which files do no longer exist upstream?
            disappeared = [ f for f in saved_filenames if f not in p.filenamelist ]
                

            for filename in saved_filenames:
                if filename in disappeared:
                    print statfrmt('D', filename)
                    # keep file if it has local modifications
                    if oldp.status(filename) == ' ':
                        p.delete_localfile(filename)
                    p.delete_storefile(filename)
                    continue

            for filename in p.filenamelist:

                state = p.status(filename)
                if state == 'M' and p.findfilebyname(filename).md5 == oldp.findfilebyname(filename).md5:
                    # no merge necessary... local file is changed, but upstream isn't
                    pass
                elif state == 'M' and filename in saved_modifiedfiles:
                    status_after_merge = p.mergefile(filename)
                    print statfrmt(status_after_merge, filename)
                elif state == 'M':
                    p.updatefile(filename, rev)
                    print statfrmt('U', filename)
                elif state == '!':
                    p.updatefile(filename, rev)
                    print 'Restored \'%s\'' % filename
                elif state == 'F':
                    p.updatefile(filename, rev)
                    print statfrmt('A', filename)
                elif state == ' ':
                    pass


            p.update_local_pacmeta()

            #print ljust(p.name, 45), 'At revision %s.' % p.rev
            print 'At revision %s.' % p.rev
                    


            
    @cmdln.alias('rm')
    @cmdln.alias('del')
    @cmdln.alias('remove')
    def do_delete(self, subcmd, opts, *args):
        """${cmd_name}: Mark files to be deleted upon the next 'checkin'

        usage: 
            osc rm FILE [FILE...]
        ${cmd_option_list}
        """

        if not args:
            print >>sys.stderr, 'Missing argument.'
            self.do_help([None, 'delete'])
            return 2

        args = parseargs(args)
        pacs = findpacs(args)

        for p in pacs:

            for filename in p.todo:
                if filename not in p.filenamelist:
                    sys.exit('\'%s\' is not under version control' % filename)
                p.put_on_deletelist(filename)
                p.write_deletelist()
                try:
                    os.unlink(os.path.join(p.dir, filename))
                    os.unlink(os.path.join(p.storedir, filename))
                except:
                    pass
                print statfrmt('D', filename)


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
            print >>sys.stderr, 'Missing argument.'
            self.do_help([None, 'resolved'])
            return 2

        args = parseargs(args)
        pacs = findpacs(args)

        for p in pacs:

            for filename in p.todo:
                print 'Resolved conflicted state of "%s"' % filename
                p.clear_from_conflictlist(filename)


    def do_platforms(self, subcmd, opts, *args):
        """${cmd_name}: Shows available platforms
        
        Examples:
        1. osc platforms
                Shows all available platforms/build targets

        2. osc platforms <project>
                Shows the configured platforms/build targets of a project

        ${cmd_usage}
        ${cmd_option_list}
        """

        if args:
            project = args[0]
            print '\n'.join(get_platforms_of_project(conf.config['apiurl'], project))
        else:
            print '\n'.join(get_platforms(conf.config['apiurl']))


    def do_results_meta(self, subcmd, opts, *args):
        """${cmd_name}: Shows raw build results of a package

        Shows the build results of the package in raw XML.

        ARG, if specified, is the working copy of a package.

        ${cmd_usage}
        ${cmd_option_list}
        """

        args = parseargs(args)
        pacs = findpacs(args)

        for pac in pacs:
            print ''.join(show_results_meta(pac.apiurl, pac.prjname, package=pac.name))

                
    def do_results(self, subcmd, opts, *args):
        """${cmd_name}: Shows the build results of a package

        ARG, if specified, is the working copy of a package.

        ${cmd_usage}
        ${cmd_option_list}
        """

        args = parseargs(args)
        pacs = findpacs(args)

        for pac in pacs:
            print '\n'.join(get_results(pac.apiurl, pac.prjname, pac.name))

                
    @cmdln.option('-l', '--legend', action='store_true',
                        help='show the legend')
    def do_prjresults(self, subcmd, opts, *args):
        """${cmd_name}: Shows project-wide build results
        
        Examples:

        1. osc prjresults <dir>
                dir is a project or package directory

        2. osc prjresults
                the project is guessed from the current dir

        ${cmd_usage}
        ${cmd_option_list}
        """

        if args and len(args) > 1:
            print >>sys.stderr, 'getting results for more than one project is not supported'
            return 2
            
        if args:
            wd = args[0]
        else:
            wd = os.curdir

        try:
            project = store_read_project(wd)
            apiurl = store_read_apiurl(wd)
        except:
            print >>sys.stderr, '\'%s\' is neither an osc project or package directory' % wd
            return 1

        print '\n'.join(get_prj_results(apiurl, project, show_legend=opts.legend))

                
    @cmdln.alias('bl')
    def do_buildlog(self, subcmd, opts, platform, arch):
        """${cmd_name}: Shows the build log of a package

        Shows the log file of the build of a package. Can be used to follow the
        log while it is being written.
        Needs to be called from within a package directory.

        The arguments PLATFORM and ARCH are the first two columns in the 'osc
        results' output.

        ${cmd_usage}
        ${cmd_option_list}
        """

        wd = os.curdir
        package = store_read_package(wd)
        project = store_read_project(wd)
        apiurl = store_read_apiurl(wd)

        offset = 0
        try:
            while True:
                log_chunk = get_log(apiurl, project, package, platform, arch, offset)
                if len(log_chunk) == 0:
                    break
                offset += len(log_chunk)
                print log_chunk.strip()

        except urllib2.HTTPError, e:
            print >>sys.stderr, 'Can\'t get logfile'
            print >>sys.stderr, e

        except KeyboardInterrupt:
            pass


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

        The arguments PLATFORM and ARCH can be taken from first two columns
        of the 'osc repos' output.

        usage: 
            osc buildinfo PLATFORM ARCH [BUILD_DESCR]
        ${cmd_option_list}
        """

        wd = os.curdir
        package = store_read_package(wd)
        project = store_read_project(wd)
        apiurl = store_read_apiurl(wd)

        if args is None or len(args) < 2:
            print >>sys.stderr, 'Missing argument.'
            print 'Valid arguments for this package are:'
            print 
            self.do_repos(None, None)
            print
            return 2
            
        platform = args[0]
        arch = args[1]

        # were we given a specfile (third argument)?
        try:
            spec = open(args[2]).read()
        except IndexError:
            spec = None
        except IOError, e:
            print >>sys.stderr, e
            return 1

        print ''.join(get_buildinfo(apiurl, 
                                    project, package, platform, arch, 
                                    specfile=spec, 
                                    addlist=opts.extra_pkgs))


    def do_buildconfig(self, subcmd, opts, platform, arch):
        """${cmd_name}: Shows the build config

        Shows the build configuration which is used in building a package.
        This command is mostly used internally by the 'build' command.
        It needs to be called from inside a package directory.

        The returned data is the project-wide build configuration in a format
        which is directly readable by the build script. It contains RPM macros
        and BuildRequires expansions, for example.

        The arguments PLATFORM and ARCH can be taken first two columns in the
        'osc repos' output.

        ${cmd_usage}
        ${cmd_option_list}
        """

        wd = os.curdir
        package = store_read_package(wd)
        project = store_read_project(wd)
        apiurl = store_read_apiurl(wd)

        print ''.join(get_buildconfig(apiurl, project, package, platform, arch))


    def do_repos(self, subcmd, opts, *args):
        """${cmd_name}: Shows the repositories which are defined for a package

        ARG, if specified, is a package working copy.

        examples: 1. osc repos                   # package = current dir
                  2. osc repos <packagedir>

        ${cmd_usage}
        ${cmd_option_list}
        """

        args = parseargs(args)
        pacs = findpacs(args)

        for p in pacs:

            for platform in get_repos_of_project(p.apiurl, p.prjname):
                print platform


    @cmdln.option('--clean', action='store_true',
                  help='Delete old build root before initializing it')
    @cmdln.option('--changelog', action='store_true',
                  help='Force update of package changelog from a changes file')
    @cmdln.option('--noinit', '--no-init', action='store_true',
                  help='Skip initialization of build root and start with build immediately.')
    @cmdln.option('-p', '--prefer-pkgs', metavar='DIR', action='append',
                  help='Prefer packages from this directory when installing the build-root')
    @cmdln.option('-k', '--keep-pkgs', metavar='DIR', 
                  help='Save built packages into this directory')
    @cmdln.option('-x', '--extra-pkgs', metavar='PAC', action='append',
                  help='Add this package when installing the build-root')
    @cmdln.option('--userootforbuild', action='store_true',
                  help='Run build as root. The default is to build as '
                  'unprivileged user. Note that a line "# norootforbuild" '
                  'in the spec file will invalidate this option.')
    def do_build(self, subcmd, opts, *args):
        """${cmd_name}: Build a package on your local machine

        You need to call the command inside a package directory, which should be a
        buildsystem checkout. (Local modifications are fine.)

        The arguments PLATFORM and ARCH can be taken from first two columns
        of the 'osc repos' output. BUILD_DESCR is either a RPM spec file, or a
        Debian dsc file.

        The command honours packagecachedir and build-root settings in .oscrc,
        if present. You may want to set su-wrapper = 'sudo' in .oscrc, and
        configure sudo with option NOPASSWD for /usr/bin/build.

        If neither --clean nor --noinit is given, build will reuse an existing
        build-root again, removing unneeded packages and add missing ones. This
        is usually the fastest option.

        usage: 
            osc build [OPTS] PLATFORM ARCH BUILD_DESCR
        ${cmd_option_list}
        """
        # Note: 
        # Configuration can be overridden by envvars, e.g.  
        # OSC_SU_WRAPPER overrides the setting of su-wrapper. 
        # BUILD_DIST or OSC_BUILD_DIST overrides the build target.
        # BUILD_ROOT or OSC_BUILD_ROOT overrides the build-root.
        # 
        #       2. BUILD_DIST=... osc build <specfile> [--clean|--noinit]
        #          where BUILD_DIST equals <platform>-<arch>

        import osc.build

        if not os.path.exists('/usr/lib/build/debtransform'):
            sys.stderr.write('Error: you need build.rpm with version 2007.3.12 or newer.\n')
            sys.stderr.write('See http://download.opensuse.org/repositories/openSUSE:/Tools/\n')
            return 1

        builddist = os.getenv('BUILD_DIST')
        if builddist:
            hyphen = builddist.rfind('-')
            if len(args) == 1:
                args = (builddist[:hyphen], builddist[hyphen+1:], args[0])
            elif len(args) == 0:
                print >>sys.stderr, 'Missing argument: build description (spec of dsc file)'
                return 2
            else:
                print >>sys.stderr, 'Too many arguments'
                return 2
            # print sys.argv

        elif len(args) >= 2 and len(args) < 3:
            print >>sys.stderr, 'Missing argument: build description (spec of dsc file)'
            return 2
        elif len(args) < 2:
            print
            print >>sys.stderr, 'Missing argument.'
            print 'Valid arguments are:'
            print 'you have to choose a repo to build on'
            print 'possible repositories on this machine are:'
            print 
            # here, we can't simply use self.do_repos(None, None), because it doesn't
            # _return_ the stuff, but prints right to stdout... in the future,
            # it would be good to make all commands return their output, but
            # better make them generators then
            (i, o) = os.popen4(['osc', 'repos'])
            i.close()

            for line in o.readlines():
                a = line.split()[1] # arch
                if a == osc.build.hostarch or \
                   a in osc.build.can_also_build.get(osc.build.hostarch, []):
                    print line.strip()
            return 1

        if opts.prefer_pkgs:
            for d in opts.prefer_pkgs:
                if not os.path.isdir(d):
                    print >> sys.stderr, 'Preferred package location \'%s\' is not a directory' % d
                    return 1

        if opts.keep_pkgs:
            if not os.path.isdir(opts.keep_pkgs):
                print >> sys.stderr, 'Preferred save location \'%s\' is not a directory' % opts.keep_pkgs
                return 1

        return osc.build.main(opts, args)

            

    @cmdln.alias('buildhist')
    def do_buildhistory(self, subcmd, opts, platform, arch):
        """${cmd_name}: Shows the build history of a package

        The arguments PLATFORM and ARCH can be taken from first two columns
        of the 'osc repos' output.

        ${cmd_usage}
        ${cmd_option_list}
        """

        wd = os.curdir
        package = store_read_package(wd)
        project = store_read_project(wd)
        apiurl = store_read_apiurl(wd)

        print '\n'.join(get_buildhistory(apiurl, project, package, platform, arch))


    @cmdln.option('-r', '--revision', metavar='rev',
                        help='show log of the specified revision')
    def do_log(self, subcmd, opts):
        """${cmd_name}: Shows the commit log of a package

        ${cmd_usage}
        ${cmd_option_list}
        """

        wd = os.curdir
        package = store_read_package(wd)
        project = store_read_project(wd)
        apiurl = store_read_apiurl(wd)
        rev, dummy = parseRevisionOption(opts.revision)
        if rev and not checkRevision(project, package, rev):
            print >>sys.stderr, 'Revision \'%s\' does not exist' % rev
            sys.exit(1)

        print '\n'.join(get_commitlog(apiurl, project, package, rev))


    @cmdln.option('-f', '--failed', action='store_true',
                  help='rebuild all failed packages')
    def do_rebuildpac(self, subcmd, opts, *args):
        """${cmd_name}: Triggers package rebuilds

        With the optional <repo> and <arch> arguments, the rebuild can be limited
        to a certain repository or architecture.

        Note that it is normally NOT needed to kick off rebuilds like this, because
        they principally happen in a fully automatic way, triggered by source
        check-ins. In particular, the order in which packages are built is handled
        by the build service.

        Note the --failed option, which can be used to rebuild all failed
        packages.

        The arguments PLATFORM and ARCH are as in the first two columns of the
        'osc repos' output.

        usage: 
            osc rebuildpac PROJECT [PACKAGE [PLATFORM [ARCH]]]
        ${cmd_option_list}
        """

        args = slash_split(args)

        if len(args) < 1:
            print >>sys.stderr, 'Missing argument.'
            #self.do_help([None, 'rebuildpac'])
            return 2

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
            print >>sys.stderr, 'Missing <project> argument'
            return 2

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
    def do_wipebinaries(self, subcmd, opts, *args):
        """${cmd_name}: Delete all binary packages of a certain project/package

        With the optional argument <package> you can specify a certain package
        otherwise all binary packages in the project will be deleted.

        usage: 
            osc wipebinaries [OPTS] PROJECT [PACKAGE]
        ${cmd_option_list}
        """
        
        args = slash_split(args)

        if len(args) < 1:
            print >>sys.stderr, 'Missing <project> argument'
            return 2
        
        if len(args) == 2:
            package = args[1]
        else:
            package = None
        
        print wipebinaries(conf.config['apiurl'], args[0], package, opts.arch, opts.repo, opts.build_disabled)


    @cmdln.option('--repos-baseurl', action='store_true',
                        help='show base URLs of download repositories')
    @cmdln.option('-e', '--enable-exact', action='store_true',
                        help='show only exact matches')
    @cmdln.option('--package', action='store_true',
                        help='search for a package')
    @cmdln.option('--project', action='store_true',
                        help='search for a project')
    @cmdln.option('--title', action='store_true',
                        help='search for matches in the \'title\' element')
    @cmdln.option('--description', action='store_true',
                        help='search for matches in the \'description\' element')
    @cmdln.option('-v', '--verbose', action='store_true',
                        help='show more information')
    def do_search(self, subcmd, opts, *args):
        """${cmd_name}: search for a project and/or package.

        If no option is specified osc will search for projects and
        packages which contains the \'search term\' in their name,
        title or description.

        usage:
            osc search \'search term\' <options>
        ${cmd_option_list}
        """

        if len(args) > 1:
            print >>sys.stderr, 'too many arguments'
            sys.exit(1)
        elif len(args) < 1:
            print >>sys.stderr, 'too few arguments'
            sys.exit(1)

        search_list = []
        search_for = []
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

        if not search_list:
            search_list = ['title', 'description', '@name']
        if not search_for:
            search_for = [ 'project', 'package' ]
        for kind in search_for:
            result = search(conf.config['apiurl'], set(search_list), kind, args[0], opts.verbose, opts.enable_exact, opts.repos_baseurl)
            if result:
                if kind == 'package':
                    headline = [ '# Package', '# Project' ]
                else:
                    headline = [ '# Project' ]
                if opts.verbose:
                    headline.append('# Title')
                if opts.repos_baseurl:
                    headline.append('# URL')
                if len(search_for) > 1:
                    print '#' * 68
                print 'matches for \'%s\' in %ss:\n' % (args[0], kind)
                for row in build_table(len(headline), result, headline, 2):
                    print row
            else:
               print 'No matches found for \'%s\' in %ss' % (args[0], kind)


    @cmdln.option('-p', '--project', metavar='project',
                        help='specify a project name')
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
        """${cmd_name}: import a new package from a src.rpm

        A new package dir will be created inside the project dir
        (if no project is specified and the current working dir is a
        project dir the package will be created in this project). If
        the package does not exist on the server it will be created
        too otherwise the meta data of the existing package will be
        updated (<title /> and <description />).
        The src.rpm will be extracted into the package dir. If the
        --disable-commit switch is not used all changes will be
        committed.

        SRPM is the path of the src.rpm in the local filesystem,
        or an URL.

        ${cmd_usage}
        ${cmd_option_list}
        """
        import glob

        if '://' in srpm:
            print 'trying to fetch', srpm
            import urlgrabber
            urlgrabber.urlgrab(srpm)
            srpm = os.path.basename(srpm)

        srpm = os.path.abspath(srpm)

        if opts.project:
            project_dir = opts.project
        else:
            project_dir = os.getcwd()

        if not is_project_dir(project_dir):
            print >>sys.stderr, 'project dir \'%s\' does not exist' % opts.project
            sys.exit(1)
        else:
            project = store_read_project(project_dir)

        rpm_data = data_from_rpm(srpm, 'Name:', 'Summary:', '%description')
        if rpm_data:
            title, pac, descr = ( v for k, v in rpm_data.iteritems() )
        else:
            title = pac = descr = ''

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

        if not os.path.exists(os.path.join(project_dir, pac)):
            os.mkdir(os.path.join(project_dir, pac))
            os.chdir(os.path.join(project_dir, pac))
            data = meta_exists(metatype='pkg',
                               path_args=(quote_plus(project), quote_plus(pac)),
                               template_args=(pac, conf.config['user']))
            if data:
                data = ET.fromstring(''.join(data))
                data.find('title').text = title
                data.find('description').text = ''.join(descr)
                data = ET.tostring(data)
            else:
                print >>sys.stderr, 'error - cannot get meta data'
                sys.exit(1)
            edit_meta(metatype='pkg',
                      path_args=(quote_plus(project), quote_plus(pac)),
                      data = data)
            init_package_dir(conf.config['apiurl'], project, pac, os.path.join(project, pac))
            unpack_srcrpm(srpm, os.getcwd())
            p = Package(os.getcwd())
            if len(p.filenamelist) == 0 and opts.commit:
                # TODO: moving this into the Package class
                print 'Adding files to working copy...'
                self.do_add(None, None, *glob.glob('*'))
                p.commit()
            elif opts.commit and opts.delete_old_files:
                delete_server_files(conf.config['apiurl'], project, pac, p.filenamelist)
                p.update_local_filesmeta()
                # TODO: moving this into the Package class
                print 'Adding files to working copy...'
                self.do_add(None, None, *glob.glob('*'))
                p.update_datastructs()
                p.commit()
            else:
                print 'No files were committed to the server. Please ' \
                      'commit them manually.'
                print 'Package \'%s\' only imported locally' % pac
                sys.exit(1)
        else:
            print >>sys.stderr, 'error - local package already exists'
            sys.exit(1)

        print 'Package \'%s\' imported successfully' % pac


    @cmdln.option('-m', '--method', default='GET', metavar='HTTP_METHOD',
                        help='specify HTTP method to use (GET|PUT|DELETE|POST)')
    @cmdln.option('-d', '--data', default=None, metavar='STRING',
                        help='specify string data for e.g. POST')
    @cmdln.option('-f', '--file', default=None, metavar='FILE',
                        help='specify filename for e.g. PUT or DELETE')
    def do_req(self, subcmd, opts, url):
        """${cmd_name}: Issue an arbitrary request to the API

        Useful for testing.

        URL can be specified either partially (only the path component), or fully
        with URL scheme and hostname ('http://...').

        Note the global -A and -H options (see osc help).

        Examples:
          osc req /source/home:poeml
          osc req -m PUT -f /etc/fstab source/home:poeml/test5/myfstab

        ${cmd_usage}
        ${cmd_option_list}
        """

        if not opts.method in ['GET', 'PUT', 'POST', 'DELETE']:
            sys.exit('unknown method %s' % opts.method)

        if not url.startswith('http'):
            if not url.startswith('/'):
                url = '/' + url
            url = conf.config['apiurl'] + url

        try:
            r = http_request(opts.method, 
                             url, 
                             data=opts.data, 
                             file=opts.file) 

        except urllib2.HTTPError, e:
            if e.code in [400, 404]:
                print >>sys.stderr, e
                print >>sys.stderr, e.read()
                sys.exit(1)
            elif e.code == 500:
                print >>sys.stderr, e
                # this may be unhelpful... because it may just print a big blob of uninteresting
                # ichain html and javascript... however it could potentially be useful if the orign
                # server returns an information body
                if conf.config['http_debug']:
                    print >>sys.stderr, e.read()
                sys.exit(1)
            else:
                sys.exit('unexpected error')

        try:
            out = r.read()
        except:
            sys.exit('failed to read from file object')

        sys.stdout.write(out)


    @cmdln.option('-e', '--email', action='store_true',
                  help='show email addresses instead of user names')
    def do_maintainer(self, subcmd, opts, *args):
        """${cmd_name}: Show maintainers of a project/package
    
        To be used like this:
    
            osc maintainer PRJ
        or 
            osc maintainer PRJ PKG
    
        ${cmd_usage}
        ${cmd_option_list}
        """
    
        if len(args) == 1:
            m = show_project_meta(conf.config['apiurl'], args[0])
        elif len(args) == 2:
            m = show_package_meta(conf.config['apiurl'], args[0], args[1])
        else:
            sys.exit('wrong argument count')
    
        maintainers = []
    
        tree = ET.parse(StringIO(''.join(m)))
        for person in tree.findall('person'):
            maintainers.append(person.get('userid'))
    
        if not opts.email:
            print ', '.join(maintainers)
        else:
            emails = []
            for maintainer in maintainers:
                emails.append(get_user_email(conf.config['apiurl'], maintainer))
            print ', '.join(emails)



# fini!
###############################################################################
        
    # load subcommands plugged-in locally
    plugin_dirs = ['/var/lib/osc-plugins', os.path.expanduser('~/.osc-plugins')]
    for plugin_dir in plugin_dirs:
        if os.path.isdir(plugin_dir):
            for extfile in os.listdir(plugin_dir):
                if not extfile.endswith('.py'):
                    continue
                exec open(os.path.join(plugin_dir, extfile))


