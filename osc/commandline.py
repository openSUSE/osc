#!/usr/bin/python

# Copyright (C) 2006 Peter Poeml.  All rights reserved.
# This program is free software; it may be used, copied, modified
# and distributed under the terms of the GNU General Public Licence,
# either version 2, or (at your option) any later version.


from core import *


usage_general = """\
usage: osc <subcommand> [options] [args]
OpenSUSE build service command-line tool, version %s.
Type 'osc help <subcommand>' for help on a specific subcommand.

Most subcommands take file and/or directory arguments, recursing
on the directories.  If no arguments are supplied to such a
command, it recurses on the current directory (inclusive) by default.

Available subcommands:

    add
    addremove
    commit (checkin, ci)
    checkout (co)
    diff
    editmeta
    help
    history (hist)
    id
    log
    ls
    meta
    platforms
    rebuildpac
    remove (del, delete, rm)
    resolved
    results
    results_meta
    status (st)
    update (up)
    updatepacmetafromspec

""" % get_osc_version()


def init(args):
    """Initialize a directory to be a working copy of an existing buildservice
package. (This is the same as checking out a package and then copying sources
into the directory. It does NOT create a new package.)

usage: osc init <prj> <pac>
    """

    project = args[0]
    package = args[1]
    init_package_dir(project, package, os.path.curdir)
    print 'Initializing %s (Project: %s, Package: %s)' % (os.curdir, project, package)


def ls(args):
    """ls (list): List existing content on the server

usage: osc ls                         # list projects
       ls Apache                  # list packages in a project
       ls Apache subversion       # list files of package of a project
    """

    if not args:
        print '\n'.join(get_slash_source())
    elif len(args) == 1:
        project = args[0]
        print '\n'.join(meta_get_packagelist(project))
    elif len(args) == 2:
        project = args[0]
        package = args[1]
        print '\n'.join(meta_get_filelist(project, package))


def meta(args):
    """Shows meta information

usage: osc meta Apache              # show meta of project 'Apache'
       osc meta Apache subversion   # show meta of package 'subversion'
    """

    if not args:
        print 'missing argument'
        print meta.func_doc
        sys.exit(1)

    if len(args) == 2:
        project = args[0]
        package = args[1]
        print ''.join(show_package_meta(project, package))
        print ''.join(show_files_meta(project, package))

    elif len(args) == 1:
        project = args[0]
        print ''.join(show_project_meta(project))


def editmeta(args):
    """Edit project/package meta information
If the named project or package does not exist, it will be created.

usage: osc editmeta FooPrj              # edit meta of project 'FooPrj'
       osc editmeta FooPrj barpackage   # edit meta of package 'barpackage'
    """

    if not args:
        print 'missing argument'
        print meta.func_doc
        sys.exit(1)

    if len(args) == 2:
        project = args[0]
        package = args[1]
        edit_meta(project, package)

    elif len(args) == 1:
        project = args[0]
        edit_meta(project, None)


def updatepacmetafromspec(args):
    """Update package meta information from a specfile

usage: 1. osc updatepacmetafromspec                       # current dir
       2. osc updatepacmetafromspec dir1 dir2 ...
    """
    args = parseargs(args)
    pacs = findpacs(args)

    for p in pacs:

        p.read_meta_from_spec()
        p.update_pac_meta()


def diff(args):
    """diff: Generates a diff, to view the local changes

    usage: 1. osc diff                       # current dir
           2. osc diff file1 file2 ...

    """

    args = parseargs(args)
    pacs = findpacs(args)

    for p in pacs:
        if p.todo == []:
            for i in p.filenamelist:
                s = p.status(i)
                if s == 'M' or s == 'C':
                    p.todo.append(i)

        d = []
        for filename in p.todo:
            d.append('Index: %s\n' % filename)
            d.append('===================================================================\n')
            d.append(get_source_file_diff(p.dir, filename, p.rev))
        if d:
            print ''.join(d)


            
def repourls(args):
    """repourls: shows URLs on which to access the .repos files

usage: 1. osc repourls
       2. osc repourls [dir1] [dir2] ...

    """

    args = parseargs(args)
    pacs = findpacs(args)

    url_tmpl = 'http://software.opensuse.org/download/%s/%s/%s.repo'
    for p in pacs:
        platforms = get_platforms_of_project(p.prjname)
        for platform in platforms:
            print url_tmpl % (p.prjname.replace(':', ':/'), platform, p.prjname)


            
def checkout(args):
    """checkout (co): Check out content from the server.

usage: osc co Apache                    # entire project
       osc co Apache subversion         # a package
       osc co Apache subversion foo     # single file -> to current dir
    """

    project = package = filename = None
    try: 
        project = args[0]
        package = args[1]
        filename = args[2]
    except: 
        pass

    if filename:
        get_source_file(project, package, filename)

    elif package:
        checkout_package(project, package)

    else:
        # all packages
        for package in meta_get_packagelist(project):
            checkout_package(project, package)


def status(args):
    """Show the status (which files have been changed locally)
usage: osc st
       osc st <directory>
       osc st file1 file2 ...
    """

    args = parseargs(args)
    pacs = findpacs(args)

    for p in pacs:

        # no files given as argument? Take all files in current dir
        if not p.todo:
            p.todo = p.filenamelist + p.filenamelist_unvers

        for filename in p.todo:
            s = p.status(filename)
            if s == 'F':
                print statfrmt('!', filename)
            elif s != ' ':
                print statfrmt(s, filename)


def add(args):
    """Mark files to be added upon next 'checkin'

usage: osc add file1 file2 ...
    """

    if not args:
        print '%s requires at least one argument' % cmd
        sys.exit(1)

    filenames = parseargs(args)

    for filename in filenames:
        if not os.path.exists(filename):
            print "file '%s' does not exist" % filename
            sys.exit(1)

    pacs = findpacs(filenames)

    for pac in pacs:
        for filename in pac.todo:
            if filename in exclude_stuff:
                continue

            pac.addfile(filename)
            print statfrmt('A', filename)


def addremove(args):
    """addremove: Adds all new files in local copy and removes all disappeared files.

usage: osc addremove
    """

    args = parseargs(args)
    pacs = findpacs(args)
    for p in pacs:

        p.todo = p.filenamelist + p.filenamelist_unvers

        for filename in p.todo:
            if filename in exclude_stuff:
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



def checkin(args):
    """commit (ci): Upload change content from your working copy to the repository

usage: osc ci                   # current dir
       osc ci <dir>
       osc ci file1 file2 ...
    """

    init_basicauth()

    args = parseargs(args)

    pacs = findpacs(args)

    for p in pacs:

        # commit only if the upstream revision is the same as the working copy's
        upstream_rev = show_upstream_rev(p.prjname, p.name)
        if p.rev != upstream_rev:
            print 'Working copy \'%s\' is out of date (rev %s vs rev %s).' % (p.absdir, p.rev, upstream_rev)
            print 'Looks as if you need to update it first.'
            sys.exit(1)

        p.todo = p.filenamelist_unvers + p.filenamelist

        for filename in p.todo:
            st = p.status(filename)
            if st == 'A' or st == 'M':
                p.todo_send.append(filename)
                print 'Sending        %s' % filename
            elif st == 'D':
                p.todo_delete.append(filename)
                print 'Deleting       %s' % filename

        if not p.todo_send and not p.todo_delete:
            print 'nothing to do for package %s' % p.name
            continue

        print 'Transmitting file data ', 
        for filename in p.todo_send:
            sys.stdout.write('.')
            p.put_source_file(filename)
        for filename in p.todo_delete:
            p.delete_source_file(filename)
            p.to_be_deleted.remove(filename)

        p.update_filesmeta()
        p.write_deletelist()
        print


def update(args):
    """Update a working copy

usage: osc up
       osc up [pac_dir]         # update a single package by its path
       osc up *                 # from within a project dir, update all packages
       osc up                   # from within a project dir, update all packages
                               AND check out all newly added packages
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

    for p in pacs:

        # save filelist and (modified) status before replacing the meta file
        saved_filenames = p.filenamelist
        saved_modifiedfiles = [ f for f in p.filenamelist if p.status(f) == 'M' ]

        oldp = p
        p.update_filesmeta()
        p = Package(p.dir)

        # which files do no longer exist upstream?
        disappeared = [ f for f in saved_filenames if f not in p.filenamelist ]
            

        for filename in saved_filenames:
            if filename in disappeared:
                print statfrmt('D', filename)
                p.delete_localfile(filename)
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
                p.updatefile(filename)
                print statfrmt('U', filename)
            elif state == '!':
                p.updatefile(filename)
                print 'Restored \'%s\'' % filename
            elif state == 'F':
                p.updatefile(filename)
                print statfrmt('A', filename)
            elif state == ' ':
                pass


        p.update_pacmeta()

        #print ljust(p.name, 45), 'At revision %s.' % p.rev
        print 'At revision %s.' % p.rev
                


        
def delete(args):
    """rm (remove, del, delete): Mark files to be deleted upon next 'checkin'

usage: osc rm file1 file2 ...
    """

    if not args:
        print 'delete requires at least one argument'
        sys.exit(1)

    args = parseargs(args)
    pacs = findpacs(args)

    for p in pacs:

        for filename in p.todo:
            p.put_on_deletelist(filename)
            p.write_deletelist()
            try:
                os.unlink(os.path.join(p.dir, filename))
                os.unlink(os.path.join(p.storedir, filename))
            except:
                pass
            print statfrmt('D', filename)


def resolved(args):
    """If an update can't be merged automatically, a file is in 'C' (conflict)
state, and conflicts are marked with special <<<<<<< and >>>>>>> lines. 
After manually resolving the problem, use

usage: osc resolved <filename>
"""

    if not args:
        print 'this command requires at least one argument'
        sys.exit(1)

    args = parseargs(args)
    pacs = findpacs(args)

    for p in pacs:

        for filename in p.todo:
            print "Resolved conflicted state of '%s'" % filename
            p.clear_from_conflictlist(filename)


def userid(args):
    """id:  show metadata about user <userid>

usage: osc id <userid>
    """

    if not args:
        print 'this command requires at least one argument'
        sys.exit(1)

    r = get_user_id(args[0])
    if r:
        print ''.join(r)


def platforms(args):
    """platforms: Shows platforms

usage 1. osc platforms
            Shows available platforms/build targets

      2. osc platforms <project>
            Shows the configured platforms/build targets of a project
    """

    if args:
        project = args[0]
        print '\n'.join(get_platforms_of_project(project))
    else:
        print '\n'.join(get_platforms())


def results_meta(args):
    """Shows the build results of the package in raw XML

usage: osc results_meta [platform]
    """
    wd = os.curdir
    package = store_read_package(wd)
    project = store_read_project(wd)
    if args:
        platform = args[0]
        print ''.join(show_results_meta(project, package, platform))
    else:
        for platform in get_platforms_of_project(project):
            print ''.join(show_results_meta(project, package, platform))

            
def results(args):
    """Shows the build results of a package

usage: 1. osc results                   # package = current dir
       2. osc results <packagedir>
    """

    if args and len(args) > 1:
        print 'getting results for more than one package is not supported'
        print sys.exit(1)
        
    if args:
        wd = args[0]
    else:
        wd = os.curdir
    package = store_read_package(wd)
    project = store_read_project(wd)

    for platform in get_platforms_of_project(project):
        print '\n'.join(get_results(project, package, platform))

            
def log(args):
    """log: Shows the log file from a package (you need to be inside a package directory)

usage: osc log <platform> <arch>

To find out <platform> and <arch>, you can use 'osc results'

    """
    wd = os.curdir
    package = store_read_package(wd)
    project = store_read_project(wd)

    platform = args[0]
    arch = args[1]
    offset = 0
    while True:
        log_chunk = get_log(project, package, platform, arch, offset)
        if len(log_chunk) == 0:
            break
        offset += len(log_chunk)
        print log_chunk.strip()


def history(args):
    """history: Shows the build history of a package (NOT IMPLEMENTED YET)

usage: osc history <pacdir>
    """
    args = parseargs(args)
    pacs = findpacs(args)

    for p in pacs:
        print ''.join(get_history(p.prjname, p.name))


def rebuildpac(args):
    """rebuildpac: Triggers a package rebuild for all repositories/architectures of the package

usage: osc rebuildpac <pacdir>
    """ 
    args = parseargs(args)
    pacs = findpacs(args)

    for p in pacs:
        print p.name + ':', cmd_rebuild(p.prjname, p.name)


def help(args):
    """help: Describe the usage of this program or its subcommands.

usage: osc help [SUBCOMMAND...]
    """
    if args:
        cmd = resolve_cmd_alias(args[0])

        try:
            print cmd_dict[cmd].func_doc

        except KeyError:
            print 'unknown command \'%s\'' % cmd
            sys.exit(1)
    else:
        print usage_general


def resolve_cmd_alias(cmd):
    if cmd in ['commit', 'ci']: return 'checkin'
    if cmd == 'co': return 'checkout'
    if cmd == 'st': return 'status'
    if cmd == 'up': return 'update'
    if cmd == 'list': return 'ls'
    if cmd == 'hist': return 'history'
    if cmd in ['del', 'remove', 'rm']: return 'delete'
    return cmd
    

cmd_dict = {
    'add':          add,
    'addremove':    addremove,
    'checkin':      checkin,
    'checkout':     checkout,
    'updatepacmetafromspec':     updatepacmetafromspec,
    'diff':         diff,
    'editmeta':     editmeta,
    'help':         help,
    'history':      history,
    'id':           userid,         # <- small difference here
    'init':         init,           # depracated
    'log':          log,
    'ls':           ls,
    'meta':         meta,
    'platforms':    platforms,
    'delete':       delete,
    'repourls':     repourls,
    'resolved':     resolved,
    'results':      results,
    'results_meta': results_meta,
    'rebuildpac':   rebuildpac,
    'status':       status,
    'update':       update,
}

def main():
    """handling of commandline arguments, and dispatching to subcommands"""

    # which subcommand?
    if len(sys.argv) < 2:
        print "Type 'osc help' for usage."
        sys.exit(0)

    cmd = resolve_cmd_alias(sys.argv[1])

    # more arguments?
    if len(sys.argv) > 2:
        args = sys.argv[2:]
    else:
        args = None

    # run subcommand
    if cmd not in cmd_dict:
        print 'unknown command \'%s\'' % cmd
        print "Type 'osc help' for usage."
        sys.exit(1)
    cmd_dict[cmd](args)


if __name__ == '__main__':
    init_basicauth()
    main()

