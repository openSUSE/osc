#!/usr/bin/python

# Copyright (C) 2006 Peter Poeml.  All rights reserved.
# This program is free software; it may be used, copied, modified
# and distributed under the terms of the GNU General Public Licence,
# either version 2, or (at your option) any later version.

__version__ = '0.3'

import os
import sys
import urllib2
from urlparse import urlunsplit
import cElementTree as ET
from cStringIO import StringIO


from xml.dom.ext.reader import Sax2
from xml.dom.ext import PrettyPrint

netloc = 'api.opensuse.org'
scheme = 'http'

BUFSIZE = 1024*1024
store = '.osc'
exclude_stuff = [store, '.svn', 'CVS']


class File:
    """represent a file, including its metadata"""
    def __init__(self, name, md5, size, mtime):
        self.name = name
        self.md5 = md5
        self.size = size
        self.mtime = mtime
    def __str__(self):
        return self.name


class Package:
    """represent a package (its directory) and read/keep/write its metadata"""
    def __init__(self, workingdir):
        self.dir = workingdir
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
            f = File(node.get('name'), 
                     node.get('md5'), 
                     node.get('size'), 
                     node.get('mtime'))
            self.filelist.append(f)
            self.filenamelist.append(f.name)

        self.to_be_deleted = read_tobedeleted(self.dir)

        self.todo = []
        self.todo_send = []
        self.todo_delete = []

        # gather unversioned files (the ones not listed in _meta)
        self.filenamelist_unvers = []
        for i in os.listdir(self.dir):
            if i in exclude_stuff:
                continue
            if not i in self.filenamelist:
                self.filenamelist_unvers.append(i) 

    def addfile(self, n):
        st = os.stat(os.path.join(self.dir, n))
        f = File(n, dgst(os.path.join(self.dir, n)), st[6], st[8])
        self.filelist.append(f)
        self.filenamelist.append(n)
        self.filenamelist_unvers.remove(n) 
        copy_file(os.path.join(self.dir, n), os.path.join(self.storedir, n))
        
    def delfile(self, n):
        os.unlink(os.path.join(self.dir, n))
        os.unlink(os.path.join(self.storedir, n))

    def put_on_deletelist(self, n):
        if n not in self.to_be_deleted:
            self.to_be_deleted.append(n)

    def write_deletelist(self):
        fname = os.path.join(self.storedir, '_to_be_deleted')
        f = open(fname, 'w')
        f.write('\n'.join(self.to_be_deleted))
        f.write('\n')
        f.close()

    def updatefile(self, n):
        filename = os.path.join(self.dir, n)
        storefilename = os.path.join(self.storedir, n)
        mtime = int(self.findfilebyname(n).mtime)

        get_source_file(self.prjname, self.name, n, targetfilename=filename)
        os.utime(filename, (-1, mtime))

        copy_file(filename, storefilename)
        os.utime(storefilename, (-1, mtime))

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
          x       x            x        'M', if digest differs, else ' '
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

        for i in open(fname, 'r').readlines():
            r.append(i.strip())

    return r


def parseargs():
        if len(sys.argv) > 2:
            args = sys.argv[2:]
        else:
            args = [ os.curdir ]
        return args


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


def copy_file(src, dst):
    # fixme: preserve mtime by default?
    s = open(src)
    d = open(dst, 'w')
    while 1:
        buf = s.read(BUFSIZE)
        if not buf: break
        d.write(buf)
    s.close()
    d.close()


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
        if v == '0.2':
            # 0.2 is fine, no migration needed
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
    f = urllib2.urlopen(u)

    tree = ET.parse(f)
    root = tree.getroot()

    r = []
    for node in root.findall('package'):
        r.append(node.get('name'))
    return r


def meta_get_filelist(prj, package):

    u = makeurl(['source', prj, package])
    f = urllib2.urlopen(u)
    tree = ET.parse(f)

    r = []
    for node in tree.getroot():
        r.append(node.get('name'))
    return r


def localmeta_addfile(filename):

    if filename in localmeta_get_filelist():
        return

    reader = Sax2.Reader()
    f = open(os.path.join(store, '_files')).read()
    doc = reader.fromString(f)

    new = doc.createElement('entry')
    #new.setAttribute('filetype', 'source')
    new.setAttribute('name', filename)
    doc.documentElement.appendChild(new)

    o = open(os.path.join(store, '_files'), 'w')
    PrettyPrint(doc, stream=o)
    o.close()

    
def localmeta_removefile(filename):

    reader = Sax2.Reader()
    f = open(os.path.join(store, '_files')).read()
    doc = reader.fromString(f)

    for i in doc.getElementsByTagName('entry'):
        if i.getAttribute('name') == filename:
            i.parentNode.removeChild(i)

    o = open(os.path.join(store, '_files'), 'w')
    PrettyPrint(doc, stream=o)
    o.close()
    

def localmeta_get_filelist():

    tree = ET.parse(os.path.join(store, '_files'))
    root = tree.getroot()

    r = []
    for node in root.findall('entry'):
        r.append(node.get('name'))
    return r


def get_slash_source():
    u = makeurl(['source'])
    tree = ET.parse(urllib2.urlopen(u))

    r = []
    for node in tree.getroot():
        r.append(node.get('name'))
    r.sort()
    return r


def show_project_meta(prj):
    f = urllib2.urlopen(makeurl(['source', prj, '_meta']))
    return f.readlines()


def show_package_meta(prj, pac):
    f = urllib2.urlopen(makeurl(['source', prj, pac, '_meta']))
    return f.readlines()


def show_files_meta(prj, pac):
    f = urllib2.urlopen(makeurl(['source', prj, pac]))
    return f.readlines()


def read_meta_from_spec(specfile):
    """read Name, Summary and %description from spec file"""
    in_descr = False
    descr = []

    if not os.path.isfile(specfile):
        print 'file \'%s\' is not a readable file' % specfile
        return None

    for line in open(specfile, 'r'):
        if line.startswith('Name:'):
            name = line.split(':')[1].strip()
        if line.startswith('Summary:'):
            summary = line.split(':')[1].strip()
        if line.startswith('%description'):
            in_descr = True
            continue
        if in_descr and line.startswith('%'):
            break
        if in_descr:
            descr.append(line)
    
    return name, summary, descr


def get_user_id(user):
    u = makeurl(['person', user])
    f = urllib2.urlopen(u)
    return f.readlines()


def get_source_file(prj, package, filename, targetfilename=None):
    u = makeurl(['source', prj, package, filename])
    #print 'checking out', u
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


def get_source_file_diff_upstream(prj, package, filename):
    url = makeurl(['source', prj, package, filename])
    f = urllib2.urlopen(url)

    localfile = open(filename, 'r')

    import difflib
    #print url
    d = difflib.unified_diff(f.readlines(), localfile.readlines(), fromfile = url, tofile = filename)

    localfile.close()

    return ''.join(d)


def get_source_file_diff(dir, filename, rev):
    import difflib

    file1 = os.path.join(dir, filename)
    file2 = os.path.join(dir, store, filename)

    f1 = open(file1, 'r')
    f2 = open(file2, 'r')

    d = difflib.unified_diff(\
        f1.readlines(), \
        f2.readlines(), \
        fromfile = '%s     (revision %s)' % (filename, rev), \
        tofile = '%s     (working copy)' % filename)

    f1.close()
    f2.close()

    return ''.join(d)


def put_source_file(prj, package, filename):
    import othermethods
    
    sys.stdout.write('.')
    u = makeurl(['source', prj, package, os.path.basename(filename)])
    othermethods.putfile(u, filename, username, password)


def del_source_file(prj, package, filename):
    import othermethods
    
    u = makeurl(['source', prj, package, filename])
    othermethods.delfile(u, filename, username, password)

    wcfilename = os.path.join(store, filename)
    if os.path.exists(filename): os.unlink(filename)
    if os.path.exists(wcfilename): os.unlink(wcfilename)


def make_dir(project, package):
    #print "creating directory '%s'" % project
    print statfrmt('A', project)
    if not os.path.exists(project):
        os.mkdir(project)
        os.mkdir(os.path.join(project, store))

        f = open(os.path.join(project, store, '_project'), 'w')
        f.write(project + '\n')
        f.close()

    #print "creating directory '%s/%s'" % (project, package)
    print statfrmt('A', '%s/%s' % (project, package))    
    if not os.path.exists(os.path.join(project, package)):
        os.mkdir(os.path.join(project, package))
        os.mkdir(os.path.join(project, package, store))

    return(os.path.join(project, package))


def checkout_package(project, package):
    olddir = os.getcwd()

    os.chdir(make_dir(project, package))
    for filename in meta_get_filelist(project, package):
        get_source_file(project, package, filename)
        copy_file(filename, os.path.join(store, filename))
        print 'A   ', os.path.join(project, package, filename)

    init_package_dir(project, package, store)

    os.chdir(olddir)


def get_platforms():
    f = urllib2.urlopen(makeurl(['platform']))
    tree = ET.parse(f)
    r = []
    for node in tree.getroot():
        r.append(node.get('name'))
    r.sort()
    return r


def get_platforms_of_project(prj):
    f = show_project_meta(prj)
    tree = ET.parse(StringIO(''.join(f)))

    r = []
    for node in tree.findall('repository'):
        r.append(node.get('name'))
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

        if rmap['status'] == 'expansion error':
            rmap['status'] += ': ' + statusnode.find('summary').text

        if rmap['status'] == 'failed':
            rmap['status'] += ': %s://%s' % (scheme, netloc) + \
                '/result/%(prj)s/%(rep)s/%(pac)s/%(arch)s/log' % rmap

        r.append(result_line_templ % rmap)
    return r


def get_log(prj, package, platform, arch):
    u = makeurl(['result', prj, platform, package, arch, 'log'])
    f = urllib2.urlopen(u)
    return f.readlines()


def get_history(prj, package):
    # http://api.opensuse.org/rpm/Apache/factory/i586/apache2/history ?
    # http://api.opensuse.org/package/Apache/apache2/history ?
    u = makeurl(['package', prj, package, 'history'])
    print u
    f = urllib2.urlopen(u)
    return f.readlines()


def store_read_project(dir):
    p = open(os.path.join(dir, store, '_project')).readlines()[0].strip()
    return p


def store_read_package(dir):
    p = open(os.path.join(dir, store, '_package')).readlines()[0].strip()
    return p


