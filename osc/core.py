#!/usr/bin/python

# Copyright (C) 2006 Peter Poeml.  All rights reserved.
# This program is free software; it may be used, copied, modified
# and distributed under the terms of the GNU General Public Licence,
# either version 2, or (at your option) any later version.

__version__ = '0.6'

import os
import sys
import urllib2
from urlparse import urlunsplit
import cElementTree as ET
from cStringIO import StringIO
import shutil


netloc = 'api.opensuse.org'
scheme = 'http'

BUFSIZE = 1024*1024
store = '.osc'
exclude_stuff = [store, '.svn', 'CVS']


new_project_templ = """\
<project name="%s">

  <title>Short title of NewProject</title>

  <description>This project aims at providing some foo and bar.

It also does some weird stuff.
</description>

  <person role="maintainer" userid="%s" />

<!-- remove this comment to enable one or more build targets

  <repository name="SUSE_Linux_Factory">
    <path project="SUSE:Factory" repository="standard" />
    <arch>x86_64</arch>
    <arch>i586</arch>
  </repository>
  <repository name="SUSE_Linux_10.1">
    <path project="SUSE:SL-10.1" repository="standard" />
    <arch>x86_64</arch>
    <arch>i586</arch>
  </repository>
  <repository name="SUSE_Linux_10.0">
    <path project="SUSE:SL-10.0" repository="standard" />
    <arch>x86_64</arch>
    <arch>i586</arch>
  </repository>
  <repository name="SUSE_Linux_9.3">
    <path project="SUSE:SL-9.3" repository="standard" />
    <arch>x86_64</arch>
    <arch>i586</arch>
  </repository>
  <repository name="Fedora_Core_5">
    <path project="Fedora:Core5" repository="standard" />
    <arch>i586</arch>
  </repository>
  <repository name="SUSE_SLES-9">
    <path project="SUSE:SLES-9" repository="standard" />
    <arch>x86_64</arch>
    <arch>i586</arch>
-->
 
</project>
                        """

new_package_templ = """\
<package name="%s">

  <title>Title of New Package</title>

  <description>LONG DESCRIPTION 
GOES 
HERE
  </description>

  <person role="maintainer" userid="%s"/>


<!-- 
  use on of the examples below to disable building of this package 
  on a certain architecture, in a certain repository, 
  or a combination thereof:
  
  <disable arch="x86_64"/>
  <disable repository="SUSE_SLES-9"/>
  <disable repository="SUSE_SLES-9" arch="x86_64"/>

-->

</package>
"""


class File:
    """represent a file, including its metadata"""
    def __init__(self, name, md5, size, mtime):
        self.name = name
        self.md5 = md5
        self.size = size
        self.mtime = mtime
    def __str__(self):
        return self.name


class Project:
    """represent a project directory, holding packages"""
    def __init__(self, dir):
        self.dir = dir
        self.absdir = os.path.abspath(dir)

        self.name = store_read_project(self.dir)

        self.pacs_available = meta_get_packagelist(self.name)

        self.pacs_have = [ i for i in os.listdir(self.dir) if i in self.pacs_available ]

        self.pacs_missing = [ i for i in self.pacs_available if i not in self.pacs_have ]

    def checkout_missing_pacs(self):
        for pac in self.pacs_missing:
            print 'checking out new package %s' % pac
            olddir = os.getcwd()
            os.chdir(os.pardir)
            checkout_package(self.name, pac)
            os.chdir(olddir)


    def __str__(self):
        r = []
        r.append('*****************************************************')
        r.append('Project %s (dir=%s, absdir=%s)' % (self.name, self.dir, self.absdir))
        r.append('have pacs:\n%s' % ', '.join(self.pacs_have))
        r.append('missing pacs:\n%s' % ', '.join(self.pacs_missing))
        r.append('*****************************************************')
        return '\n'.join(r)



class Package:
    """represent a package (its directory) and read/keep/write its metadata"""
    def __init__(self, workingdir):
        self.dir = workingdir
        self.absdir = os.path.abspath(self.dir)
        self.storedir = os.path.join(self.dir, store)

        check_store_version(self.dir)

        self.prjname = store_read_project(self.dir)
        self.name = store_read_package(self.dir)

        files_tree = read_filemeta(self.dir)
        files_tree_root = files_tree.getroot()

        self.rev = files_tree_root.get('rev')

        self.filenamelist = []
        self.filelist = []
        for node in files_tree_root.findall('entry'):
            try: 
                f = File(node.get('name'), 
                         node.get('md5'), 
                         int(node.get('size')), 
                         int(node.get('mtime')))
            except: 
                # okay, a very old version of _files, which didn't contain any metadata yet... 
                f = File(node.get('name'), '', 0, 0)
            self.filelist.append(f)
            self.filenamelist.append(f.name)

        self.to_be_deleted = read_tobedeleted(self.dir)
        self.in_conflict = read_inconflict(self.dir)

        self.todo = []
        self.todo_send = []
        self.todo_delete = []

        # gather unversioned files (the ones not listed in _meta)
        self.filenamelist_unvers = [ i for i in os.listdir(self.dir)
                                     if i not in exclude_stuff
                                     if i not in self.filenamelist ]

    def addfile(self, n):
        st = os.stat(os.path.join(self.dir, n))
        f = File(n, None, st.st_size, st.st_mtime)
        self.filelist.append(f)
        self.filenamelist.append(n)
        self.filenamelist_unvers.remove(n) 
        shutil.copy2(os.path.join(self.dir, n), os.path.join(self.storedir, n))
        
    def delete_localfile(self, n):
        try: os.unlink(os.path.join(self.dir, n))
        except: pass
        try: os.unlink(os.path.join(self.storedir, n))
        except: pass

    def put_on_deletelist(self, n):
        if n not in self.to_be_deleted:
            self.to_be_deleted.append(n)

    def put_on_conflictlist(self, n):
        if n not in self.in_conflict:
            self.in_conflict.append(n)

    def clear_from_conflictlist(self, n):
        """delete an entry from the file, and remove the file if it would be empty"""
        if n in self.in_conflict:

            filename = os.path.join(self.dir, n)
            storefilename = os.path.join(self.storedir, n)
            myfilename = os.path.join(self.dir, n + '.mine')
            upfilename = os.path.join(self.dir, n + '.r' + self.rev)

            try:
                os.unlink(myfilename)
                # the working copy may be updated, so the .r* ending may be obsolete...
                # then we don't care
                os.unlink(upfilename)
            except: 
                pass

            self.in_conflict.remove(n)

            self.write_conflictlist()

    def write_deletelist(self):
        if len(self.to_be_deleted) == 0:
            try:
                os.unlink(os.path.join(self.storedir, '_to_be_deleted'))
            except:
                pass
        else:
            fname = os.path.join(self.storedir, '_to_be_deleted')
            f = open(fname, 'w')
            f.write('\n'.join(self.to_be_deleted))
            f.write('\n')
            f.close()

    def delete_source_file(self, n):
        import othermethods
        
        u = makeurl(['source', self.prjname, self.name, n])
        othermethods.delfile(u, n, username, password)

        self.delete_localfile(n)

    def put_source_file(self, n):
        import othermethods
        
        # escaping '+' in the URL path (note: not in the URL query string) is 
        # only a workaround for ruby on rails, which swallows it otherwise
        u = makeurl(['source', self.prjname, self.name, n.replace('+', '%2B')])
        othermethods.putfile(u, os.path.join(self.dir, n), username, password)

        shutil.copy2(os.path.join(self.dir, n), os.path.join(self.storedir, n))

    def write_conflictlist(self):
        if len(self.in_conflict) == 0:
            os.unlink(os.path.join(self.storedir, '_in_conflict'))
        else:
            fname = os.path.join(self.storedir, '_in_conflict')
            f = open(fname, 'w')
            f.write('\n'.join(self.in_conflict))
            f.write('\n')
            f.close()

    def updatefile(self, n):
        filename = os.path.join(self.dir, n)
        storefilename = os.path.join(self.storedir, n)
        mtime = self.findfilebyname(n).mtime

        get_source_file(self.prjname, self.name, n, targetfilename=filename)
        os.utime(filename, (-1, mtime))

        shutil.copy2(filename, storefilename)

    def mergefile(self, n):
        filename = os.path.join(self.dir, n)
        storefilename = os.path.join(self.storedir, n)
        myfilename = os.path.join(self.dir, n + '.mine')
        upfilename = os.path.join(self.dir, n + '.r' + self.rev)
        os.rename(filename, myfilename)

        mtime = self.findfilebyname(n).mtime
        get_source_file(self.prjname, self.name, n, targetfilename=upfilename)
        os.utime(upfilename, (-1, mtime))

        if binary_file(myfilename) or binary_file(upfilename):
                # don't try merging
                shutil.copy2(upfilename, filename)
                shutil.copy2(upfilename, storefilename)
                self.in_conflict.append(n)
                self.write_conflictlist()
                return 'C'
        else:
            # try merging
            ret = os.system('diff3 -m -E %s %s %s > %s' \
                % (myfilename, storefilename, upfilename, filename))
            if ret == 0:
                # merge was successful... clean up
                os.rename(upfilename, filename)
                shutil.copy2(filename, storefilename)
                os.unlink(myfilename)
                return 'G'
            else:
                # unsuccessful merge
                self.in_conflict.append(n)
                self.write_conflictlist()
                return 'C'



    def update_filesmeta(self):
        meta = ''.join(show_files_meta(self.prjname, self.name))
        f = open(os.path.join(self.storedir, '_files'), 'w')
        f.write(meta)
        f.close()
        
    def update_pacmeta(self):
        meta = ''.join(show_package_meta(self.prjname, self.name))
        f = open(os.path.join(self.storedir, '_meta'), 'w')
        f.write(meta)
        f.close()

    def findfilebyname(self, n):
        for i in self.filelist:
            if i.name == n:
                return i

    def status(self, n):
        """
        status can be:

         file  storefile  file present  STATUS
        exists  exists      in _files

          x       x            -        'A'
          x       x            x        ' ' if digest differs: 'M'
                                            and if in conflicts file: 'C'
          x       -            -        '?'
          x       -            x        'D' and listed in _to_be_deleted
          -       x            x        '!'
          -       x            -        'D' (when file in working copy is already deleted)
          -       -            x        'F' (new in repo, but not yet in working copy)
          -       -            -        NOT DEFINED

        """

        known_by_meta = False
        exists = False
        exists_in_store = False
        if n in self.filenamelist:
            known_by_meta = True
        if os.path.exists(os.path.join(self.dir, n)):
            exists = True
        if os.path.exists(os.path.join(self.storedir, n)):
            exists_in_store = True


        if exists and not exists_in_store and known_by_meta:
            state = 'D'
        elif n in self.to_be_deleted:
            state = 'D'
        elif n in self.in_conflict:
            state = 'C'
        elif exists and exists_in_store and known_by_meta:
            #print self.findfilebyname(n)
            if dgst(os.path.join(self.dir, n)) != self.findfilebyname(n).md5:
                state = 'M'
            else:
                state = ' '
        elif exists and not exists_in_store and not known_by_meta:
            state = '?'
        elif exists and exists_in_store and not known_by_meta:
            state = 'A'
        elif not exists and exists_in_store and known_by_meta:
            state = '!'
        elif not exists and not exists_in_store and known_by_meta:
            state = 'F'
        elif not exists and exists_in_store and not known_by_meta:
            state = 'D'
        elif not exists and not exists_in_store and not known_by_meta:
            print '%s: not exists and not exists_in_store and not nown_by_meta' % n
            print 'this code path should never be reached!'
            sys.exit(1)
        
        return state


    def merge(self, otherpac):
        self.todo += otherpac.todo

    def __str__(self):
        r = """
name: %s
prjname: %s
workingdir: %s
localfilelist: %s
rev: %s
'todo' files: %s
""" % (self.name, 
        self.prjname, 
        self.dir, 
        '\n               '.join(self.filenamelist), 
        self.rev, 
        self.todo)

        return r


    def read_meta_from_spec(self):
        specfile = os.path.join(self.dir, self.name + '.spec')
        name, summary, descr = read_meta_from_spec(specfile)

        if name != self.name:
            print 'name from spec does not match name of package... this is probably a problem'
            sys.exit(1)
        self.summary = summary
        self.descr = descr


    def update_pac_meta(self):
        import othermethods
        import tempfile

        (f, filename) = tempfile.mkstemp(prefix = 'osc_editmeta.', suffix = '.xml', dir = '/tmp')

        try:
            m = show_package_meta(self.prjname, self.name)
        except urllib2.HTTPError, e:
            if e.code == 404:
                print 'package does not exist yet... creating it'
                m = new_package_templ % (pac, username)
            else:
                print 'error getting package meta for project \'%s\' package \'%s\':' % (prj, pac)
                print e
                sys.exit(1)

        f = open(filename, 'w')
        f.write(''.join(m))
        f.close()

        tree = ET.parse(filename)
        tree.find('title').text = self.summary
        tree.find('description').text = ''.join(self.descr)
        tree.write(filename)

        # FIXME: escape stuff for xml
        print '*' * 36, 'old', '*' * 36
        print ''.join(m)
        print '*' * 36, 'new', '*' * 36
        tree.write(sys.stdout)
        print '*' * 72

        # FIXME: for testing...
        # open the new description in $EDITOR instead?
        repl = raw_input('Write? (y/N) ')
        if repl == 'y':
            print 'Sending meta data...', 
            u = makeurl(['source', self.prjname, self.name, '_meta'])
            othermethods.putfile(u, filename, username, password)
            print 'Done.'
        else:
            print 'discarding', filename

        os.unlink(filename)




def is_project_dir(d):
    if os.path.exists(os.path.join(d, store, '_project')) and not \
       os.path.exists(os.path.join(d, store, '_package')):
        return True
    else:
        return False

        
def findpacs(files):
    pacs = []
    for f in files:
        if f in exclude_stuff:
            break

        p = filedir_to_pac(f)
        known = None
        for i in pacs:
            if i.name == p.name:
                known = i
                break
        if known:
            i.merge(p)
        else:
            pacs.append(p)
    return pacs
        

def read_filemeta(dir):
    return ET.parse(os.path.join(dir, store, '_files'))


def read_tobedeleted(dir):
    r = []
    fname = os.path.join(dir, store, '_to_be_deleted')

    if os.path.exists(fname):
        r = [ line.strip() for line in open(fname) ]

    return r


def read_inconflict(dir):
    r = []
    fname = os.path.join(dir, store, '_in_conflict')

    if os.path.exists(fname):
        r = [ line.strip() for line in open(fname) ]

    return r


def parseargs(list_of_args):
        if list_of_args:
            return list_of_args
        else:
            return [ os.curdir ]


def filedir_to_pac(f):

    if os.path.isdir(f):
        wd = f
        p = Package(wd)

    elif os.path.isfile(f):
        wd = os.path.dirname(f)
        if wd == '':
            wd = os.curdir
        p = Package(wd)
        p.todo = [ os.path.basename(f) ]

    else:
        wd = os.path.dirname(f)
        if wd == '':
            wd = os.curdir
        p = Package(wd)
        p.todo = [ os.path.basename(f) ]
        

    #else:
    #    print 
    #    print 'error: %s is neither a valid file or directory' % f
    #    sys.exit(1)

    return p


def statfrmt(statusletter, filename):
    return '%s    %s' % (statusletter, filename)


def makeurl(l):
    """given a list of path compoments, construct a complete URL"""
    return urlunsplit((scheme, netloc, '/'.join(l), '', ''))               


def readauth():
    """look for the credentials. If there aren't any, ask and store them"""

    #
    # try .netrc first
    #

    # the needed entry in .netrc looks like this:
    # machine api.opensuse.org login your_login password your_pass
    # but it is not able for credentials containing spaces
    import netrc
    global username, password

    try:
        info = netrc.netrc()
        username, account, password = info.authenticators(netloc)
        return username, password

    except (IOError, TypeError):
        pass

    #
    # try .oscrc next
    #
    import ConfigParser
    conffile = os.path.expanduser('~/.oscrc')
    if os.path.exists(conffile):
        config = ConfigParser.ConfigParser()
        config.read(conffile)
        username = config.get(netloc, 'user')
        password = config.get(netloc, 'pass')
        return username, password

    #
    # create .oscrc
    #
    import getpass
    print >>sys.stderr, \
"""your user account / password are not configured yet.
You will be asked for them below, and they will be stored in
%s for later use.
""" % conffile

    username = raw_input('Username: ')
    password = getpass.getpass()

    fd = open(conffile, 'w')
    os.chmod(conffile, 0600)
    print >>fd, '[%s]\nuser: %s\npass: %s' % (netloc, username, password)
    fd.close()
        
    return username, password
        


def init_basicauth():

    username, password = readauth()

    passmgr = urllib2.HTTPPasswordMgrWithDefaultRealm()
    # this creates a password manager
    passmgr.add_password(None, netloc, username, password)
    # because we have put None at the start it will always
    # use this username/password combination for  urls
    # for which `netloc` is a super-url

    authhandler = urllib2.HTTPBasicAuthHandler(passmgr)
    # create the AuthHandler

    opener = urllib2.build_opener(authhandler)
    opener.addheaders = [('User-agent', 'osc/%s' % __version__)]

    urllib2.install_opener(opener)
    # All calls to urllib2.urlopen will now use our handler
    # Make sure not to include the protocol in with the URL, or
    # HTTPPasswordMgrWithDefaultRealm will be very confused.
    # You must (of course) use it when fetching the page though.


def init_package_dir(project, package, dir):
    if not os.path.isdir(store):
        os.mkdir(store)
    os.chdir(store)
    f = open('_project', 'w')
    f.write(project + '\n')
    f.close
    f = open('_package', 'w')
    f.write(package + '\n')
    f.close

    f = open('_files', 'w')
    f.write(''.join(show_files_meta(project, package)))
    f.close()

    f = open('_osclib_version', 'w')
    f.write(__version__ + '\n')
    f.close()

    os.chdir(os.pardir)
    return


def check_store_version(dir):
    versionfile = os.path.join(dir, store, '_osclib_version')
    try:
        v = open(versionfile).read().strip()
    except:
        v = ''

    if v == '':
        print 'error: "%s" is not an osc working copy' % dir
        sys.exit(1)

    if v != __version__:
        if v in ['0.2', '0.3', '0.4', '0.5']:
            # version is fine, no migration needed
            f = open(versionfile, 'w')
            f.write(__version__ + '\n')
            f.close()
            return 
        print 
        print 'the osc metadata of your working copy "%s"' % dir
        print 'has the wrong version (%s), should be %s' % (v, __version__)
        print 'please do a fresh checkout'
        print 
        sys.exit(1)
    

def meta_get_packagelist(prj):

    u = makeurl(['source', prj, '_meta'])

    try:
        f = urllib2.urlopen(u)
    except urllib2.HTTPError, e:
        if e.code == 404:
            print 'project \'%s\' does not exist' % prj
            sys.exit(1)
        else:
            print e
            print 'url: \'%s\'' % u
            sys.exit(1)

    tree = ET.parse(f)
    root = tree.getroot()

    return [ node.get('name') for node in root.findall('package') ]


def meta_get_filelist(prj, package):

    u = makeurl(['source', prj, package])
    f = urllib2.urlopen(u)
    root = ET.parse(f).getroot()

    return [ node.get('name') for node in root ]


def get_slash_source():
    u = makeurl(['source'])
    root = ET.parse(urllib2.urlopen(u)).getroot()

    return sorted([ node.get('name') for node in root ])


def show_project_meta(prj):
    f = urllib2.urlopen(makeurl(['source', prj, '_meta']))
    return f.readlines()


def show_package_meta(prj, pac):
    f = urllib2.urlopen(makeurl(['source', prj, pac, '_meta']))
    return f.readlines()


def edit_meta(prj, pac):
    import othermethods
    import tempfile

    (f, filename) = tempfile.mkstemp(prefix = 'osc_editmeta.', suffix = '.xml', dir = '/tmp')

    if pac:
        # package meta
        u = makeurl(['source', prj, pac, '_meta'])
        try:
            m = show_package_meta(prj, pac)
        except urllib2.HTTPError, e:
            if e.code == 404:
                m = new_package_templ % (pac, username)
            else:
                print 'error getting package meta for project \'%s\' package \'%s\':' % (prj, pac)
                print e
                sys.exit(1)

    else:
        # project meta
        u = makeurl(['source', prj, '_meta'])
        try:
            m = show_project_meta(prj)
        except urllib2.HTTPError, e:
            if e.code == 404:
                m = new_project_templ % (prj, username)
            else:
                print 'error getting package meta for project \'%s\':' % prj
                print e
                sys.exit(1)

    f = open(filename, 'w')
    f.write(''.join(m))
    f.close()

    timestamp = os.path.getmtime(filename)

    editor = os.getenv('EDITOR', default='vim')
    os.system('%s %s' % (editor, filename))

    if os.path.getmtime(filename) == timestamp:
        print 'File unchanged. Not saving.'
        os.unlink(filename)

    else:
        print 'Sending meta data...', 
        othermethods.putfile(u, filename, username, password)
        os.unlink(filename)
        print 'Done.'


def show_files_meta(prj, pac):
    f = urllib2.urlopen(makeurl(['source', prj, pac]))
    return f.readlines()


def show_upstream_rev(prj, pac):
    m = show_files_meta(prj, pac)
    return ET.parse(StringIO(''.join(m))).getroot().get('rev')


def read_meta_from_spec(specfile):
    """read Name, Summary and %description from spec file"""

    if not os.path.isfile(specfile):
        print 'file \'%s\' is not a readable file' % specfile
        return None

    lines = open(specfile).readlines()

    for line in lines:
        if line.startswith('Name:'):
            name = line.split(':')[1].strip()
            break
        
    for line in lines:
        if line.startswith('Summary:'):
            summary = line.split(':')[1].strip()
            break

    descr = []
    start = lines.index('%description\n') + 1
    for line in lines[start:]:
        if line.startswith('%'):
            break
        descr.append(line)
    
    return name, summary, descr


def get_user_id(user):
    u = makeurl(['person', user.replace(' ', '+')])
    try:
        f = urllib2.urlopen(u)
        return ''.join(f.readlines())
    except urllib2.HTTPError:
        print 'user \'%s\' not found' % user
        return None


def get_source_file(prj, package, filename, targetfilename=None):
    u = makeurl(['source', prj, package, filename.replace('+', '%2B')])
    f = urllib2.urlopen(u)

    o = open(targetfilename or filename, 'w')
    while 1:
        buf = f.read(BUFSIZE)
        if not buf: break
        o.write(buf)
    o.close()


def dgst(file):

    #if not os.path.exists(file):
        #return None

    import md5
    s = md5.new()
    f = open(file, 'r')
    while 1:
        buf = f.read(BUFSIZE)
        if not buf: break
        s.update(buf)
    return s.hexdigest()


def binary(s):
    """return true if a string is binary data using diff's heuristic"""
    if s and '\0' in s[:4096]:
        return True
    return False


def binary_file(fn):
    """read 4096 bytes from a file named fn, and call binary() on the data"""
    return binary(open(fn, 'r').read(4096))


def get_source_file_diff(dir, filename, rev):
    import difflib

    file1 = os.path.join(dir, store, filename)  # stored original
    file2 = os.path.join(dir, filename)         # working copy

    f1 = open(file1, 'r')
    s1 = f1.read()
    f1.close()

    f2 = open(file2, 'r')
    s2 = f2.read()
    f2.close()

    if binary(s1) or binary (s2):
        d = ['Binary file %s has changed\n' % filename]

    else:
        d = difflib.unified_diff(\
            s1.splitlines(1), \
            s2.splitlines(1), \
            fromfile = '%s     (revision %s)' % (filename, rev), \
            tofile = '%s     (working copy)' % filename)

    return ''.join(d)


def make_dir(project, package):
    #print "creating directory '%s'" % project
    if not os.path.exists(project):
        print statfrmt('A', project)
        os.mkdir(project)
        os.mkdir(os.path.join(project, store))

        f = open(os.path.join(project, store, '_project'), 'w')
        f.write(project + '\n')
        f.close()

    #print "creating directory '%s/%s'" % (project, package)
    if not os.path.exists(os.path.join(project, package)):
        print statfrmt('A', '%s/%s' % (project, package))    
        os.mkdir(os.path.join(project, package))
        os.mkdir(os.path.join(project, package, store))

    return(os.path.join(project, package))


def checkout_package(project, package):
    olddir = os.getcwd()

    os.chdir(make_dir(project, package))
    init_package_dir(project, package, store)
    p = Package(os.curdir)

    for filename in p.filenamelist:
        p.updatefile(filename)
        print 'A   ', os.path.join(project, package, filename)

    os.chdir(olddir)


def get_platforms():
    f = urllib2.urlopen(makeurl(['platform']))
    tree = ET.parse(f)
    r = [ node.get('name') for node in tree.getroot() ]
    r.sort()
    return r


def get_platforms_of_project(prj):
    f = show_project_meta(prj)
    tree = ET.parse(StringIO(''.join(f)))

    r = [ node.get('name') for node in tree.findall('repository')]
    return r


def show_results_meta(prj, package, platform):
    u = makeurl(['result', prj, platform, package, 'result'])
    f = urllib2.urlopen(u)
    return f.readlines()


def get_results(prj, package, platform):
    #print '----------------------------------------'

    r = []
    #result_line_templ = '%(prj)-15s %(pac)-15s %(rep)-15s %(arch)-10s %(status)s'
    result_line_templ = '%(rep)-15s %(arch)-10s %(status)s'

    f = show_results_meta(prj, package, platform)
    tree = ET.parse(StringIO(''.join(f)))

    root = tree.getroot()

    rmap = {}
    rmap['prj'] = root.get('project')
    rmap['pac'] = root.get('package')
    rmap['rep'] = root.get('repository')

    for node in root.findall('archresult'):
        rmap['arch'] = node.get('arch')

        statusnode =  node.find('status')
        rmap['status'] = statusnode.get('code')

        if rmap['status'] in ['expansion error', 'broken']:
            rmap['status'] += ': ' + statusnode.find('summary').text

        if rmap['status'] == 'failed':
            rmap['status'] += ': %s://%s' % (scheme, netloc) + \
                '/result/%(prj)s/%(rep)s/%(pac)s/%(arch)s/log' % rmap

        r.append(result_line_templ % rmap)
    return r


def get_log(prj, package, platform, arch, offset):
    u = makeurl(['result', prj, platform, package, arch, 'log?nostream=1&start=%s' % offset])
    f = urllib2.urlopen(u)
    return f.read()


def get_history(prj, package):
    # http://api.opensuse.org/rpm/Apache/factory/i586/apache2/history ?
    # http://api.opensuse.org/package/Apache/apache2/history ?
    u = makeurl(['package', prj, package, 'history'])
    print u
    f = urllib2.urlopen(u)
    return f.readlines()


def cmd_rebuild(prj, package):
    u = makeurl(['source', prj, package, '?cmd=rebuild'])
    try:
        # adding data to the request makes it a POST
        f = urllib2.urlopen(u, data=' ')
    except urllib2.HTTPError, e:
        print >>sys.stderr, 'could not trigger rebuild for project \'%s\' package \'%s\'' % (prj, package)
        print >>sys.stderr, u
        print >>sys.stderr, e
        sys.exit(1)

    root = ET.parse(f).getroot()
    #code = root.get('code')
    return root.find('summary').text


def store_read_project(dir):
    p = open(os.path.join(dir, store, '_project')).readlines()[0].strip()
    return p


def store_read_package(dir):
    p = open(os.path.join(dir, store, '_package')).readlines()[0].strip()
    return p

def get_osc_version():
    return __version__

