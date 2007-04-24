#!/usr/bin/python

# Copyright (C) 2006 Peter Poeml / Novell Inc.  All rights reserved.
# This program is free software; it may be used, copied, modified
# and distributed under the terms of the GNU General Public Licence,
# either version 2, or (at your option) any later version.

__version__ = '0.95'

import os
import sys
import urllib2
from urllib import pathname2url, quote_plus
from urlparse import urlunsplit
from cStringIO import StringIO
import shutil
import conf
try:
    from xml.etree import cElementTree as ET
except ImportError:
    import cElementTree as ET



BUFSIZE = 1024*1024
store = '.osc'
exclude_stuff = [store, '.svn', 'CVS', '.git', '.gitignore', '.pc', '*~', '.*.swp']


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
  </repository>
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
  <disable repository="SUSE_SLE-10"/>
  <disable repository="SUSE_SLE-10" arch="x86_64"/>

-->

</package>
"""

new_user_template = """\
<person>
  <login>%(user)s</login>
  <email>PUT_EMAIL_ADDRESS_HERE</email>
  <realname>PUT_REAL_NAME_HERE</realname>
  <source_backend>
    <host></host>
    <port></port>
  </source_backend>
  <rpm_backend>
    <host></host>
    <port></port>
  </rpm_backend>
  <watchlist>
    <project name="home:%(user)s"/>
  </watchlist>
</person>
"""

buildstatus_symbols = {'succeeded':       '.',
                       'disabled':        ' ',
                       'expansion error': 'E',
                       'failed':          'F',
                       'broken':          'B',
                       'blocked':         'b',
                       'building':        '%',
                       'scheduled':       's',
}


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
        import fnmatch
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

        # gather unversioned files, but ignore some stuff
        self.excluded = [ i for i in os.listdir(self.dir) 
                          for j in exclude_stuff 
                          if fnmatch.fnmatch(i, j) ]
        self.filenamelist_unvers = [ i for i in os.listdir(self.dir)
                                     if i not in self.excluded
                                     if i not in self.filenamelist ]

    def addfile(self, n):
        st = os.stat(os.path.join(self.dir, n))
        f = File(n, None, st.st_size, st.st_mtime)
        self.filelist.append(f)
        self.filenamelist.append(n)
        self.filenamelist_unvers.remove(n) 
        shutil.copy2(os.path.join(self.dir, n), os.path.join(self.storedir, n))
        
    def delete_storefile(self, n):
        try: os.unlink(os.path.join(self.storedir, n))
        except: pass

    def delete_localfile(self, n):
        try: os.unlink(os.path.join(self.dir, n))
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
        
        u = makeurl(['source', self.prjname, self.name, pathname2url(n)])
        http_DELETE(u)

        self.delete_localfile(n)
        self.delete_storefile(n)

    def put_source_file(self, n):
        
        # escaping '+' in the URL path (note: not in the URL query string) is 
        # only a workaround for ruby on rails, which swallows it otherwise
        u = makeurl(['source', self.prjname, self.name, pathname2url(n)])
        if conf.config['do_commits'] == '1':
            u += '?rev=upload'
        http_PUT(u, file = os.path.join(self.dir, n))

        shutil.copy2(os.path.join(self.dir, n), os.path.join(self.storedir, n))

    def commit(self, msg=''):
        
        u = makeurl(['source', self.prjname, self.name])
        u += '?cmd=commit&rev=upload'
        u += '&user=%s' % conf.config['user']
        u += '&comment=%s' % quote_plus(msg)
        #print u
        f = http_POST(u)
        #print f.read()

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
            # diff3 OPTIONS... MINE OLDER YOURS
            merge_cmd = 'diff3 -m -E %s %s %s > %s' % (myfilename, storefilename, upfilename, filename)
            # we would rather use the subprocess module, but it is not availablebefore 2.4
            ret = os.system(merge_cmd) / 256
            
            #   "An exit status of 0 means `diff3' was successful, 1 means some
            #   conflicts were found, and 2 means trouble."
            if ret == 0:
                # merge was successful... clean up
                shutil.copy2(upfilename, storefilename)
                os.unlink(upfilename)
                os.unlink(myfilename)
                return 'G'
            elif ret == 1:
                # unsuccessful merge
                shutil.copy2(upfilename, storefilename)
                self.in_conflict.append(n)
                self.write_conflictlist()
                return 'C'
            else:
                print >>sys.stderr, '\ndiff3 got in trouble... exit code:', ret
                print >>sys.stderr, 'the command line was:'
                print >>sys.stderr, merge_cmd
                sys.exit(1)



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


    def update_pac_meta(self, template=new_package_templ):
        import tempfile

        (fd, filename) = tempfile.mkstemp(prefix = 'osc_editmeta.', suffix = '.xml', dir = '/tmp')

        try:
            u = makeurl(['source', self.prjname, self.name, '_meta'])
            m = http_GET(u).readlines() 
        except urllib2.HTTPError, e:
            if e.code == 404:
                print 'package does not exist yet... creating it'
                m = template % (pac, conf.config['user'])
            else:
                print 'error getting package meta for project \'%s\' package \'%s\':' % (prj, pac)
                print e
                sys.exit(1)

        f = os.fdopen(fd, 'w')
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
            http_PUT(u, file=filename)
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

        
def is_package_dir(d):
    if os.path.exists(os.path.join(d, store, '_project')) and \
       os.path.exists(os.path.join(d, store, '_package')):
        return True
    else:
        return False

        
def findpacs(files):
    pacs = []
    for f in files:
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

    else:
        wd = os.path.dirname(f)
        if wd == '':
            wd = os.curdir
        p = Package(wd)
        p.todo = [ os.path.basename(f) ]

    return p


def statfrmt(statusletter, filename):
    return '%s    %s' % (statusletter, filename)


def pathjoin(a, *p):
    """Join two or more pathname components, inserting '/' as needed. Cut leading ./"""
    path = os.path.join(a, *p)
    if path.startswith('./'):
        path = path[2:]
    return path


def makeurl(l):
    """given a list of path compoments, construct a complete URL"""
    return urlunsplit((conf.config['scheme'], conf.config['apisrv'], '/'.join(l), '', ''))               


def http_request(method, url, data=None, file=None):
    """wrapper around urllib2.urlopen for error handling,
    and to support additional (PUT, DELETE) methods"""

    filefd = None

    if conf.config['http_debug']:
        print 
        print
        print '--', method, url

    if method == 'POST' and not file and not data:
        # adding data to an urllib2 request transforms it into a POST
        data = ''
        
    req = urllib2.Request(url)
    req.get_method = lambda: method

    if file and not data:
        size = os.path.getsize(file)
        if size < 1024*512:
            data = open(file).read()
        else:
            import mmap
            filefd = open(file, 'r+')
            data = mmap.mmap(filefd.fileno(), os.path.getsize(file))

    fd = urllib2.urlopen(req, data=data)

    if hasattr(conf.cookiejar, 'save'):
        conf.cookiejar.save(ignore_discard=True)

    if filefd: filefd.close()
    return fd


def http_GET(*args, **kwargs):    return http_request('GET', *args, **kwargs)
def http_POST(*args, **kwargs):   return http_request('POST', *args, **kwargs)
def http_PUT(*args, **kwargs):    return http_request('PUT', *args, **kwargs)
def http_DELETE(*args, **kwargs): return http_request('DELETE', *args, **kwargs)


def urlopen(url, data=None):
    """wrapper around urllib2.urlopen for error handling"""
    print 'core.urlopen() is deprecated -- use http_GET et al.'

    try:
        # adding data to the request makes it a POST
        if not data:
            fd = http_GET(url)
        else:
            fd = http_POST(url, data=data)

    except urllib2.HTTPError, e:
        print >>sys.stderr, 'Error: can\'t get \'%s\'' % url
        print >>sys.stderr, e
        if e.code == 500:
            print >>sys.stderr, '\nDebugging output follows.\nurl:\n%s\nresponse:\n%s' % (url, e.read())
        sys.exit(1)

    return fd


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
        if v in ['0.2', '0.3', '0.4', '0.5', '0.6', '0.7', '0.8', '0.9']:
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

    u = makeurl(['source', prj])
    f = http_GET(u)
    root = ET.parse(f).getroot()
    return [ node.get('name') for node in root.findall('entry') ]


def meta_get_filelist(prj, package):

    u = makeurl(['source', prj, package])
    f = http_GET(u)
    root = ET.parse(f).getroot()
    return [ node.get('name') for node in root ]


def meta_get_project_list():
    u = makeurl(['source'])
    f = http_GET(u)
    root = ET.parse(f).getroot()
    return sorted([ node.get('name') for node in root ])


def show_project_meta(prj):
    url = makeurl(['source', prj, '_meta'])
    f = http_GET(url)
    return f.readlines()


def show_package_meta(prj, pac):
    try:
        url = makeurl(['source', prj, pac, '_meta'])
        f = http_GET(url)
    except urllib2.HTTPError, e:
        print >>sys.stderr, 'error getting meta for project \'%s\' package \'%s\'' % (prj, pac)
        print >>sys.stderr, e
        if e.code == 500:
            print >>sys.stderr, '\nDebugging output follows.\nurl:\n%s\nresponse:\n%s' % (url, e.read())
        sys.exit(1)
    return f.readlines()

class metafile:
    """metafile that can be manipulated and is stored back after manipulation."""
    def __init__(self, prj, pac, template=new_package_templ, change_is_required=True):
        import tempfile

        self.change_is_required = change_is_required

        (fd, self.filename) = tempfile.mkstemp(prefix = 'osc_editmeta.', suffix = '.xml', dir = '/tmp')

        
        if pac:
            # package meta
            self.url = makeurl(['source', prj, pac, '_meta'])
            try:
                m = http_GET(self.url).readlines() 
            except urllib2.HTTPError, e:
                if e.code == 404:
                    m = template % (pac, conf.config['user'])
                else:
                    print 'error getting package meta for project \'%s\' package \'%s\':' % (prj, pac)
                    print e
                    sys.exit(1)

        else:
            # project meta
            self.url = makeurl(['source', prj, '_meta'])
            try:
                m = http_GET(self.url).readlines()
            # when testing this offline:
            #except urllib2.URLError, e:
            #    m = new_project_templ % (prj, conf.config['user'])
            except urllib2.HTTPError, e:
                if e.code == 404:
                    m = new_project_templ % (prj, conf.config['user'])
                else:
                    print 'error getting package meta for project \'%s\':' % prj
                    print e
                    sys.exit(1)

        f = os.fdopen(fd, 'w')
        f.write(''.join(m))
        f.close()

        self.timestamp = os.path.getmtime(self.filename)

    def sync(self):
        if self.change_is_required == True and os.path.getmtime(self.filename) == self.timestamp:
            print 'File unchanged. Not saving.'
            os.unlink(self.filename)

        else:
            print 'Sending meta data...', 
            http_PUT(self.url, file=self.filename)
            os.unlink(self.filename)
            print 'Done.'
    
def edit_meta(prj, pac, template=new_package_templ, change_is_required=True):
    f=metafile(prj, pac, template, change_is_required)

    editor = os.getenv('EDITOR', default='vim')
    os.system('%s %s' % (editor, f.filename))

    if change_is_required == True:
        f.sync()

def edit_user_meta(user, change_is_required=True):
    import tempfile

    u = makeurl(['person', quote_plus(user)])

    try:
        m = http_GET(u).readlines() 
    except urllib2.HTTPError, e:
        if e.code == 404:
            m = new_user_template % { 'user': user }
        else:
            print 'error getting metadata for user \'%s\':' % user
            print e
            sys.exit(1)

    (fd, filename) = tempfile.mkstemp(prefix = 'osc_edituser.', suffix = '.xml', dir = '/tmp')
    f = os.fdopen(fd, 'w')
    f.write(''.join(m))
    f.close()
    timestamp = os.path.getmtime(filename)

    editor = os.getenv('EDITOR', default='vim')
    os.system('%s %s' % (editor, filename))

    if change_is_required == True and os.path.getmtime(filename) == timestamp:
        print 'File unchanged. Not saving.'
        os.unlink(filename)

    else:
        print 'Sending meta data...', 
        http_PUT(u, file=filename)
        os.unlink(filename)
        print 'Done.'


def show_files_meta(prj, pac):
    f = http_GET(makeurl(['source', prj, pac]))
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


def get_user_meta(user):
    u = makeurl(['person', quote_plus(user)])
    try:
        f = http_GET(u)
        return ''.join(f.readlines())
    except urllib2.HTTPError:
        print 'user \'%s\' not found' % user
        return None


def get_source_file(prj, package, filename, targetfilename=None):
    u = makeurl(['source', prj, package, pathname2url(filename)])
    f = http_GET(u)

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


def link_pac(src_project, src_package, dst_project, dst_package):
    """
    create a linked package
     - "src" is the original package
     - "dst" is the "link" package that we are creating here
    """

    import tempfile


    src_meta = show_package_meta(src_project, src_package)

    # replace package name and username
    # using a string buffer
    # and create the package
    tree = ET.parse(StringIO(''.join(src_meta)))
    root = tree.getroot()
    root.set('name', '%s')
    tree.find('person').set('userid', '%s')
    buf = StringIO()
    tree.write(buf)
    src_meta = buf.getvalue()


    edit_meta(dst_project, dst_package, template=src_meta, change_is_required=False)

    # create the _link file
    # but first, make sure not to overwrite an existing one
    if '_link' in meta_get_filelist(dst_project, dst_package):
        print
        print '_link file already exists...! Aborting'
        sys.exit(1)

    print 'Creating _link...',
    link_template = """\
<link project="%s" package="%s">
<patches>
  <!-- <apply name="patch" /> -->
  <!-- <topadd>%%define build_with_feature_x 1</topadd> -->
</patches>
</link>
""" % (src_project, src_package)

    u = makeurl(['source', dst_project, dst_package, '_link'])
    http_PUT(u, data=link_template)
    print 'Done.'


def copy_pac(src_project, src_package, dst_project, dst_package):
    """
    create a copy of a package
    """

    import tempfile

    src_meta = show_package_meta(src_project, src_package)

    # replace project and package name
    # using a string buffer
    # and create the package
    tree = ET.parse(StringIO(''.join(src_meta)))
    root = tree.getroot()
    root.set('name', dst_package)
    root.set('project', dst_project)
    buf = StringIO()
    tree.write(buf)
    src_meta = buf.getvalue()

    print 'Sending meta data...'
    u = makeurl(['source', dst_project, dst_package, '_meta'])
    http_PUT(u, data=src_meta)

    # copy one file after the other
    print 'Copying files...'
    tmpdir = tempfile.mkdtemp(prefix='osc_copypac', dir = '/tmp')
    os.chdir(tmpdir)
    for n in meta_get_filelist(src_project, src_package):
        print '  ', n
        get_source_file(src_project, src_package, n, targetfilename=n)
        u = makeurl(['source', dst_project, dst_package, pathname2url(n)])
        http_PUT(u, file = n)
        os.unlink(n)
    print 'Done.'
    os.rmdir(tmpdir)


def delete_package(prj, pac):
    
    u = makeurl(['source', prj, pac])
    http_DELETE(u)


def delete_project(prj):
    
    u = makeurl(['source', prj])
    http_DELETE(u)


def get_platforms():
    f = http_GET(makeurl(['platform']))
    tree = ET.parse(f)
    r = [ node.get('name') for node in tree.getroot() ]
    r.sort()
    return r


def get_platforms_of_project(prj):
    f = show_project_meta(prj)
    tree = ET.parse(StringIO(''.join(f)))

    r = [ node.get('name') for node in tree.findall('repository')]
    return r


def get_repos_of_project(prj):
    f = show_project_meta(prj)
    tree = ET.parse(StringIO(''.join(f)))

    repo_line_templ = '%-15s %-10s'
    r = []
    for node in tree.findall('repository'):
        for node2 in node.findall('arch'):
            r.append(repo_line_templ % (node.get('name'), node2.text))
    return r


def show_results_meta(prj, package):
    u = makeurl(['build', prj, '_result?package=%s' % pathname2url(package)])
    f = http_GET(u)
    return f.readlines()


def show_prj_results_meta(prj):
    u = makeurl(['build', prj, '_result'])
    f = http_GET(u)
    return f.readlines()


def get_results(prj, package):
    r = []
    result_line_templ = '%(rep)-15s %(arch)-10s %(status)s'

    f = show_results_meta(prj, package)
    tree = ET.parse(StringIO(''.join(f)))
    root = tree.getroot()

    for node in root.findall('result'):
        rmap = {}
        rmap['prj'] = prj
        rmap['pac'] = package
        rmap['rep'] = node.get('repository')
        rmap['arch'] = node.get('arch')

        statusnode =  node.find('status')
        rmap['status'] = statusnode.get('code')

        if rmap['status'] in ['expansion error', 'broken']:
            rmap['status'] += ': ' + statusnode.find('details').text

        if rmap['status'] == 'failed':
            rmap['status'] += ': %s://%s' % (conf.config['scheme'], conf.config['apisrv']) + \
                '/result/%(prj)s/%(rep)s/%(pac)s/%(arch)s/log' % rmap

        r.append(result_line_templ % rmap)
    return r

def get_prj_results(prj, show_legend=False):
    #print '----------------------------------------'

    r = []
    #result_line_templ = '%(prj)-15s %(pac)-15s %(rep)-15s %(arch)-10s %(status)s'
    result_line_templ = '%(rep)-15s %(arch)-10s %(status)s'

    f = show_prj_results_meta(prj)
    tree = ET.parse(StringIO(''.join(f)))
    root = tree.getroot()

    pacs = []
    for node in root.find('result'):
        pacs.append(node.get('package'))
    pacs.sort()

    max_pacs = 40
    for startpac in range(0, len(pacs), max_pacs):
        offset = 0
        for pac in pacs[startpac:startpac+max_pacs]:
            r.append(' |' * offset + ' ' + pac)
            offset += 1

        target = {}
        for node in root.findall('result'):
            target['repo'] = node.get('repository')
            target['arch'] = node.get('arch')

            status = {}
            for pacnode in node.findall('status'):
                try:
                    status[pacnode.get('package')] = buildstatus_symbols[pacnode.get('code')]
                except:
                    print 'osc: warn: unknown status \'%s\'...' % pacnode.get('code')
                    print 'please edit osc/core.py, and extend the buildstatus_symbols dictionary.'
                    status[pacnode.get('package')] = '?'

            line = []
            line.append(' ')
            for pac in pacs[startpac:startpac+max_pacs]:
                line.append(status[pac])
                line.append(' ')
            line.append(' %s %s' % (target['repo'], target['arch']))
            line = ''.join(line)

            r.append(line)

        r.append('')

    if show_legend:
        r.append(' Legend:')
        for i, j in buildstatus_symbols.items():
            r.append('  %s %s' % (j, i))

    return r


def get_log(prj, package, platform, arch, offset):
    u = makeurl(['result', prj, platform, package, arch, 'log?nostream=1&start=%s' % offset])
    f = http_GET(u)
    return f.read()


def get_buildinfo(prj, package, platform, arch, specfile=None):
    # http://api.opensuse.org/rpm/Subversion/Apache_SuSE_Linux_10.1/i586/subversion/buildinfo
    u = makeurl(['rpm', prj, platform, arch, package, 'buildinfo'])
    if specfile:
        f = http_POST(u, data=specfile)
    else:
        f = http_GET(u)
    return f.read()


def get_buildconfig(prj, package, platform, arch):
    # http://api.opensuse.org/rpm/<proj>/<repo>/_repository/<arch>/_buildconfig
    u = makeurl(['rpm', prj, platform, '_repository', arch, '_buildconfig'])
    f = http_GET(u)
    return f.read()


def get_buildhistory(prj, package, platform, arch):
    import time

    u = makeurl(['rpm', prj, platform, arch, package, 'history'])
    f = http_GET(u)
    root = ET.parse(f).getroot()

    r = []
    for node in root.findall('entry'):
        rev = int(node.get('rev'))
        srcmd5 = node.get('srcmd5') 
        versrel = node.get('versrel') 
        bcnt = int(node.get('bcnt'))
        t = time.localtime(int(node.get('time')))
        t = time.strftime('%Y-%m-%d %H:%M:%S', t)

        r.append('%s   %s %6d   %2d   %s' % (t, srcmd5, rev, bcnt, versrel))

    r.insert(0, 'time                  srcmd5                              rev  bcnt  vers-rel')

    return r


def cmd_rebuild(prj, package, repo, arch, code=None):
    cmd = prj
    cmd += '?cmd=rebuild'
    if package:
        cmd += '&package=%s' % package
    if repo:
        cmd += '&repo=%s' % repo
    if arch:
        cmd += '&arch=%s' % arch
    if code:
        cmd += '&code=%s' % code

    u = makeurl(['build', cmd])
    try:
        f = http_POST(u)
    except urllib2.HTTPError, e:
        print >>sys.stderr, 'could not trigger rebuild for project \'%s\' package \'%s\'' % (prj, package)
        print >>sys.stderr, u
        print >>sys.stderr, e
        sys.exit(1)

    root = ET.parse(f).getroot()
    return root.get('code')


def store_read_project(dir):
    p = open(os.path.join(dir, store, '_project')).readlines()[0].strip()
    return p


def store_read_package(dir):
    p = open(os.path.join(dir, store, '_package')).readlines()[0].strip()
    return p


def get_osc_version():
    return __version__

