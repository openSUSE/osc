#!/usr/bin/python

# Copyright (C) 2006 Peter Poeml.  All rights reserved.
# This program is free software; it may be used, copied, modified
# and distributed under the terms of the GNU General Public Licence,
# either version 2, or (at your option) any later version.

from core import *

def main():

    cmd = sys.argv[1]
    project = package = filename = None
    # try: 
    #     project = sys.argv[2]
    #     package = sys.argv[3]
    #     filename = sys.argv[4]
    # except: 
    #     pass

    if cmd == 'init':
        project = sys.argv[2]
        package = sys.argv[3]
        init_package_dir(project, package, os.path.curdir)
        print 'Initializing %s (Project: %s, Package: %s)' % (os.curdir, project, package)

    elif cmd == 'ls':
        if len(sys.argv) == 2:
            print '\n'.join(get_slash_source())
        if len(sys.argv) == 3:
            project = sys.argv[2]
            print '\n'.join(meta_get_packagelist(project))
        if len(sys.argv) == 4:
            project = sys.argv[2]
            package = sys.argv[3]
            print '\n'.join(meta_get_filelist(project, package))

    elif cmd == 'meta':
        if len(sys.argv) == 4:
            project = sys.argv[2]
            package = sys.argv[3]
            print ''.join(show_package_meta(project, package))
            print ''.join(show_files_meta(project, package))
        elif len(sys.argv) == 3:
            project = sys.argv[2]
            print ''.join(show_project_meta(project))

    elif cmd == 'diff':
        args = parseargs()
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
                

    elif cmd == 'co' or cmd == 'checkout':

        try: 
            project = sys.argv[2]
            package = sys.argv[3]
            filename = sys.argv[4]
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


    elif cmd == 'st' or cmd == 'status':

        args = parseargs()
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


    elif cmd == 'add':
        if len(sys.argv) < 3:
            print '%s requires at least one argument' % cmd
            sys.exit(1)

        filenames = parseargs()

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


    elif cmd == 'addremove':
        args = parseargs()
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




    elif cmd == 'ci' or cmd == 'checkin':
        init_basicauth()

        args = parseargs()

        pacs = findpacs(args)

        for p in pacs:
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
                put_source_file(p.prjname, p.name, os.path.join(p.dir, filename))
                #copy_file(filename, os.path.join(store, filename))
            for filename in p.todo_delete:
                del_source_file(p.prjname, p.name, filename)
                p.to_be_deleted.remove(filename)

            p.update_filesmeta()
            p.write_deletelist()
            print


    elif cmd == 'up' or cmd == 'update':

        args = parseargs()

        for arg in args:

            # when 'update' is run inside a project dir, it should...
            if is_project_dir(arg):

                prj = Project(arg)

                # (a) update all packages
                for i in prj.pacs_have:
                    args.append(i)

                # (b) fetch new packages
                prj.checkout_missing_pacs()
                args.remove(arg)


        pacs = findpacs(args)

        for p in pacs:

            # save filelist and (modified) status before replacing the meta file
            saved_filenames = p.filenamelist
            saved_modifiedfiles = []
            for i in p.filenamelist:
                if p.status(i) == 'M':
                    saved_modifiedfiles.append(i)
            p.update_filesmeta()
            p = Package(p.dir)

            # which files do no longer exist upstream?
            disappeared = []
            for filename in saved_filenames:
                if filename not in p.filenamelist:
                    disappeared.append(filename)
                

            for filename in saved_filenames:
                if filename in disappeared:
                    print statfrmt('D', filename)
                    p.delfile(filename)
                    continue

            for filename in p.filenamelist:

                state = p.status(filename)
                if state == 'M' and filename in saved_modifiedfiles:
                    print 'merging'
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
                    


            

    elif cmd == 'rm' or cmd == 'delete':
        if len(sys.argv) < 3:
            print '%s requires at least one argument' % cmd
            sys.exit(1)

        args = parseargs()
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


    elif cmd == 'resolved':
        if len(sys.argv) < 3:
            print '%s requires at least one argument' % cmd
            sys.exit(1)

        args = parseargs()
        pacs = findpacs(args)

        for p in pacs:

            for filename in p.todo:
                print "Resolved conflicted state of '%s'" % filename
                p.clear_from_conflictlist(filename)


    elif cmd == 'id':
        r = get_user_id(sys.argv[2])
        if r:
            print ''.join(r)


    elif cmd == 'platforms':
        if len(sys.argv) > 2:
            project = sys.argv[2]
            print '\n'.join(get_platforms_of_project(project))
        else:
            print '\n'.join(get_platforms())


    elif cmd == 'results_meta':
        wd = os.curdir
        package = store_read_package(wd)
        project = store_read_project(wd)
        if len(sys.argv) > 2:
            platform = sys.argv[2]
            print ''.join(show_results_meta(project, package, platform))
        else:
            for platform in get_platforms_of_project(project):
                print ''.join(show_results_meta(project, package, platform))

                
    elif cmd == 'results':
        if len(sys.argv) > 3:
            print 'getting results for more than one package is not supported'
            print sys.exit(1)
            
        if len(sys.argv) == 3:
            wd = sys.argv[2]
        else:
            wd = os.curdir
        package = store_read_package(wd)
        project = store_read_project(wd)

        for platform in get_platforms_of_project(project):
            print '\n'.join(get_results(project, package, platform))

                
    elif cmd == 'log':
        wd = os.curdir
        package = store_read_package(wd)
        project = store_read_project(wd)

        platform = sys.argv[2]
        arch = sys.argv[3]
        print ''.join(get_log(project, package, platform, arch))


    elif cmd == 'hist' or cmd == 'history':
        args = parseargs()
        pacs = findpacs(args)

        for p in pacs:
            print ''.join(get_history(p.prjname, p.name))


    else:
        print "unknown command '%s'" % cmd


if __name__ == '__main__':
    init_basicauth()
    main()

