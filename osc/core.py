#!/usr/bin/python

# Copyright (C) 2006 Peter Poeml / Novell Inc.  All rights reserved.
# This program is free software; it may be used, copied, modified
# and distributed under the terms of the GNU General Public Licence,
# either version 2, or (at your option) any later version.

__version__ = '0.99'

import os
import sys
import urllib2
from urllib import pathname2url, quote_plus
from urlparse import urlsplit, urlunsplit
from cStringIO import StringIO
import shutil
import conf
try:
    from xml.etree import cElementTree as ET
except ImportError:
    import cElementTree as ET



BUFSIZE = 1024*1024
store = '.osc'
exclude_stuff = [store, '.svn', 'CVS', '.git', '.gitignore', '.pc', '*~', '.*.swp', '.swp']


new_project_templ = """\
<project name="%s">

  <title>Short title of NewProject</title>

  <description>This project aims at providing some foo and bar.

It also does some weird stuff.
</description>

  <person role="maintainer" userid="%s" />

<!-- remove this block to publish your packages on the mirrors -->
  <publish>
    <disable />
  </publish>
  <build>
    <enable />
  </build>
  <debuginfo>
    <disable />
  </debuginfo>

<!-- remove this comment to enable one or more build targets

  <repository name="openSUSE_Factory">
    <path project="openSUSE:Factory" repository="standard" />
    <arch>x86_64</arch>
    <arch>i586</arch>
  </repository>
 <repository name="openSUSE_10.2">
    <path project="openSUSE:10.2" repository="standard"/>
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
  <repository name="Fedora_7">
    <path project="Fedora:7" repository="standard" />
    <arch>x86_64</arch>
    <arch>i586</arch>
  </repository>
  <repository name="SLE_10">
    <path project="SUSE:SLE-10:SDK" repository="standard" />
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
  use one of the examples below to disable building of this package 
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
  <login>%s</login>
  <email>PUT_EMAIL_ADDRESS_HERE</email>
  <realname>PUT_REAL_NAME_HERE</realname>
  <watchlist>
    <project name="home:%s"/>
  </watchlist>
</person>
"""

info_templ = """\
Path: %s
API URL: %s
Repository UUID: %s
Revision: %s
"""

new_pattern_template = """\
<!-- See http://svn.opensuse.org/svn/zypp/trunk/libzypp/zypp/parser/yum/schema/patterns.rng -->

<pattern>
</pattern>
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
        self.apiurl = store_read_apiurl(self.dir)

        self.pacs_available = meta_get_packagelist(self.apiurl, self.name)

        self.pacs_have = [ i for i in os.listdir(self.dir) if i in self.pacs_available ]

        self.pacs_missing = [ i for i in self.pacs_available if i not in self.pacs_have ]

    def checkout_missing_pacs(self):
        for pac in self.pacs_missing:
            print 'checking out new package %s' % pac
            olddir = os.getcwd()
            os.chdir(os.pardir)
            checkout_package(self.apiurl, self.name, pac)
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
        self.storedir = os.path.join(self.absdir, store)

        check_store_version(self.dir)

        self.prjname = store_read_project(self.dir)
        self.name = store_read_package(self.dir)
        self.apiurl = store_read_apiurl(self.dir)

        self.update_datastructs()

        self.todo = []
        self.todo_send = []
        self.todo_delete = []

    def info(self):
        return info_templ % (self.dir, self.apiurl, self.srcmd5, self.rev)

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
        
        u = makeurl(self.apiurl, ['source', self.prjname, self.name, pathname2url(n)])
        http_DELETE(u)

        self.delete_localfile(n)
        self.delete_storefile(n)

    def put_source_file(self, n):
        
        # escaping '+' in the URL path (note: not in the URL query string) is 
        # only a workaround for ruby on rails, which swallows it otherwise
        query = ['rev=upload']
        u = makeurl(self.apiurl, ['source', self.prjname, self.name, pathname2url(n)], query=query)
        http_PUT(u, file = os.path.join(self.dir, n))

        shutil.copy2(os.path.join(self.dir, n), os.path.join(self.storedir, n))

    def commit(self, msg=''):
        # commit only if the upstream revision is the same as the working copy's
        upstream_rev = show_upstream_rev(self.apiurl, self.prjname, self.name)
        if self.rev != upstream_rev:
            print >>sys.stderr, 'Working copy \'%s\' is out of date (rev %s vs rev %s).' \
                                % (self.absdir, self.rev, upstream_rev)
            print >>sys.stderr, 'Looks as if you need to update it first.'
            sys.exit(1)

        if not self.todo:
            self.todo = self.filenamelist_unvers + self.filenamelist

        for filename in self.todo:
            st = self.status(filename)
            if st == 'A' or st == 'M':
                self.todo_send.append(filename)
                print 'Sending        %s' % filename
            elif st == 'D':
                self.todo_delete.append(filename)
                print 'Deleting       %s' % filename

        if not self.todo_send and not self.todo_delete:
            print 'nothing to do for package %s' % self.name
            sys.exit(1)

        print 'Transmitting file data ', 
        for filename in self.todo_delete:
            self.delete_source_file(filename)
            self.to_be_deleted.remove(filename)
        for filename in self.todo_send:
            sys.stdout.write('.')
            sys.stdout.flush()
            self.put_source_file(filename)
        # all source files are committed - now comes the log
        query = []
        query.append('cmd=commit')
        query.append('rev=upload')
        query.append('user=%s' % conf.config['user'])
        query.append('comment=%s' % quote_plus(msg))
        u = makeurl(self.apiurl, ['source', self.prjname, self.name], query=query)
        #print u
        f = http_POST(u)
        root = ET.parse(f).getroot()
        self.rev = int(root.get('rev'))
        print
        print 'Committed revision %s.' % self.rev

        self.update_local_filesmeta()
        self.write_deletelist()

    def write_conflictlist(self):
        if len(self.in_conflict) == 0:
            os.unlink(os.path.join(self.storedir, '_in_conflict'))
        else:
            fname = os.path.join(self.storedir, '_in_conflict')
            f = open(fname, 'w')
            f.write('\n'.join(self.in_conflict))
            f.write('\n')
            f.close()

    def updatefile(self, n, revision):
        filename = os.path.join(self.dir, n)
        storefilename = os.path.join(self.storedir, n)
        mtime = self.findfilebyname(n).mtime

        get_source_file(self.apiurl, self.prjname, self.name, n, targetfilename=filename, revision=revision)
        os.utime(filename, (-1, mtime))

        shutil.copy2(filename, storefilename)

    def mergefile(self, n):
        filename = os.path.join(self.dir, n)
        storefilename = os.path.join(self.storedir, n)
        myfilename = os.path.join(self.dir, n + '.mine')
        upfilename = os.path.join(self.dir, n + '.r' + self.rev)
        os.rename(filename, myfilename)

        mtime = self.findfilebyname(n).mtime
        get_source_file(self.apiurl, self.prjname, self.name, n, targetfilename=upfilename)
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



    def update_local_filesmeta(self, revision=None):
        """
        Update the local _files file in the store.
        It is replaced with the version pulled from upstream.
        """
        meta = ''.join(show_files_meta(self.apiurl, self.prjname, self.name, revision))
        f = open(os.path.join(self.storedir, '_files'), 'w')
        f.write(meta)
        f.close()

    def update_datastructs(self):
        """
        Update the internal data structures if the local _files
        file has changed (e.g. update_local_filesmeta() has been
        called).
        """
        import fnmatch
        files_tree = read_filemeta(self.dir)
        files_tree_root = files_tree.getroot()

        self.rev = files_tree_root.get('rev')
        self.srcmd5 = files_tree_root.get('srcmd5')

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

        # gather unversioned files, but ignore some stuff
        self.excluded = [ i for i in os.listdir(self.dir) 
                          for j in exclude_stuff 
                          if fnmatch.fnmatch(i, j) ]
        self.filenamelist_unvers = [ i for i in os.listdir(self.dir)
                                     if i not in self.excluded
                                     if i not in self.filenamelist ]

    def update_local_pacmeta(self):
        """
        Update the local _meta file in the store.
        It is replaced with the version pulled from upstream.
        """
        meta = ''.join(show_package_meta(self.apiurl, self.prjname, self.name))
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
        if os.path.exists(os.path.join(self.absdir, n)):
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
            if dgst(os.path.join(self.absdir, n)) != self.findfilebyname(n).md5:
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
            print >>sys.stderr, '%s: not exists and not exists_in_store and not nown_by_meta' % n
            print >>sys.stderr, 'this code path should never be reached!'
            sys.exit(1)
        
        return state

    def comparePac(self, pac):
        """
        This method compares the local filelist with
        the filelist of the passed package to see which files
        were added, removed and changed.
        """
        
        changed_files = []
        added_files = []
        removed_files = []

        for file in self.filenamelist:
            if not file in self.to_be_deleted:
                if file in pac.filenamelist:
                    if dgst(file) != pac.findfilebyname(file).md5:
                        changed_files.append(file)
                else:
                    added_files.append(file)

        for file in pac.filenamelist:
            if (not file in self.filenamelist) or (file in self.to_be_deleted):
                removed_files.append(file)

        return changed_files, added_files, removed_files

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


    def read_meta_from_spec(self, spec = None):
        import glob
        if spec:
            specfile = spec
        else:
            # scan for spec files
            speclist = glob.glob(os.path.join(self.dir, '*.spec'))
            if len(speclist) == 1:
                specfile = speclist[0]
            elif len(speclist) > 1:
                print 'the following specfiles were found:'
                for file in speclist:
                    print file
                print 'please specify one with --specfile'
                sys.exit(1)
            else:
                print 'no specfile was found - please specify one ' \
                      'with --specfile'
                sys.exit(1)     

        data = read_meta_from_spec(specfile, 'Summary:', '%description')
        self.summary = data['Summary:']
        self.descr = data['%description']


    def update_package_meta(self):
        """
        for the updatepacmetafromspec subcommand
        """

        import tempfile
        (fd, filename) = tempfile.mkstemp(prefix = 'osc_editmeta.', suffix = '.xml', dir = '/tmp')

        m = ''.join(show_package_meta(self.apiurl, self.prjname, self.name))

        f = os.fdopen(fd, 'w')
        f.write(m)
        f.close()

        tree = ET.parse(filename)
        tree.find('title').text = self.summary
        tree.find('description').text = ''.join(self.descr)
        tree.write(filename)

        print '*' * 36, 'old', '*' * 36
        print m
        print '*' * 36, 'new', '*' * 36
        tree.write(sys.stdout)
        print '*' * 72

        # FIXME: for testing...
        # open the new description in $EDITOR instead?
        repl = raw_input('Write? (y/N) ')
        if repl == 'y':
            print 'Sending meta data...', 
            u = makeurl(self.apiurl, ['source', self.prjname, self.name, '_meta'])
            http_PUT(u, file=filename)
            print 'Done.'
        else:
            print 'discarding', filename

        os.unlink(filename)


def shorttime(t):
    """format time as Apr 02 18:19
    or                Apr 02  2005
    depending on whether it is in the current year
    """
    import time

    if time.localtime()[0] == time.localtime(t)[0]:
        # same year
        return time.strftime('%b %d %H:%M',time.localtime(t))
    else:
        return time.strftime('%b %d  %Y',time.localtime(t))


def is_project_dir(d):
    return os.path.exists(os.path.join(d, store, '_project')) and not \
           os.path.exists(os.path.join(d, store, '_package'))

        
def is_package_dir(d):
    return os.path.exists(os.path.join(d, store, '_project')) and \
           os.path.exists(os.path.join(d, store, '_package'))

        
def slash_split(l):
    """Split command line arguments like 'foo/bar' into 'foo' 'bar'.
    This is handy to allow copy/paste a project/package combination in this form.
    """
    r = []
    for i in l:
        r += i.split('/')
    return r


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


def makeurl(baseurl, l, query=[]):
    """given a list of path compoments, construct a complete URL"""

    #print 'makeurl:', baseurl, l, query

    scheme, netloc = urlsplit(baseurl)[0:2]
    return urlunsplit((scheme, netloc, '/'.join(l), '&'.join(query), ''))               


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

    # POST requests are application/x-www-form-urlencoded per default
    # since we change the request into PUT, we also need to adjust the content type header
    if method == 'PUT':
        req.add_header('Content-Type', 'application/octet-stream')

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

def init_project_dir(apiurl, dir, project):
    if not os.path.exists(dir):
        os.mkdir(dir)
        os.mkdir(os.path.join(dir, store))

    store_write_project(dir, project)
    store_write_apiurl(dir, apiurl)

def init_package_dir(apiurl, project, package, dir, revision=None):
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
    f.write(''.join(show_files_meta(apiurl, project, package, revision)))
    f.close()

    f = open('_osclib_version', 'w')
    f.write(__version__ + '\n')
    f.close()

    store_write_apiurl(os.path.pardir, apiurl)

    os.chdir(os.pardir)
    return


def check_store_version(dir):
    versionfile = os.path.join(dir, store, '_osclib_version')
    try:
        v = open(versionfile).read().strip()
    except:
        v = ''

    if v == '':
        print >>sys.stderr, 'error: "%s" is not an osc working copy' % dir
        sys.exit(1)

    if v != __version__:
        if v in ['0.2', '0.3', '0.4', '0.5', '0.6', '0.7', '0.8', '0.9', '0.95', '0.96', '0.97', '0.98']:
            # version is fine, no migration needed
            f = open(versionfile, 'w')
            f.write(__version__ + '\n')
            f.close()
            return 
        print >>sys.stderr
        print >>sys.stderr, 'the osc metadata of your working copy "%s"' % dir
        print >>sys.stderr, 'has the wrong version (%s), should be %s' % (v, __version__)
        print >>sys.stderr, 'please do a fresh checkout'
        print >>sys.stderr
        sys.exit(1)
    

def meta_get_packagelist(apiurl, prj):

    u = makeurl(apiurl, ['source', prj])
    f = http_GET(u)
    root = ET.parse(f).getroot()
    return [ node.get('name') for node in root.findall('entry') ]


def meta_get_filelist(apiurl, prj, package, verbose=False):
    """return a list of file names,
    or a list File() instances if verbose=True"""

    u = makeurl(apiurl, ['source', prj, package])
    f = http_GET(u)
    root = ET.parse(f).getroot()

    if not verbose:
        return [ node.get('name') for node in root ]

    else:
        l = []
        rev = int(root.get('rev'))
        for node in root:
            f = File(node.get('name'), 
                     node.get('md5'), 
                     int(node.get('size')), 
                     int(node.get('mtime')))
            f.rev = rev
            l.append(f)
        return l


def meta_get_project_list(apiurl):
    u = makeurl(apiurl, ['source'])
    f = http_GET(u)
    root = ET.parse(f).getroot()
    return sorted([ node.get('name') for node in root ])


def show_project_meta(apiurl, prj):
    url = makeurl(apiurl, ['source', prj, '_meta'])
    f = http_GET(url)
    return f.readlines()


def show_project_conf(apiurl, prj):
    url = makeurl(apiurl, ['source', prj, '_config'])
    f = http_GET(url)
    return f.readlines()


def show_package_meta(apiurl, prj, pac):
    try:
        url = makeurl(apiurl, ['source', prj, pac, '_meta'])
        f = http_GET(url)
    except urllib2.HTTPError, e:
        print >>sys.stderr, 'error getting meta for project \'%s\' package \'%s\'' % (prj, pac)
        print >>sys.stderr, e
        if e.code == 500:
            print >>sys.stderr, '\nDebugging output follows.\nurl:\n%s\nresponse:\n%s' % (url, e.read())
        sys.exit(1)
    return f.readlines()


def show_pattern_metalist(apiurl, prj):
    url = makeurl(apiurl, ['source', prj, '_pattern'])
    f = http_GET(url)
    tree = ET.parse(f)
    r = [ node.get('name') for node in tree.getroot() ]
    r.sort()
    return r


def show_pattern_meta(apiurl, prj, pattern):
    url = makeurl(apiurl, ['source', prj, '_pattern', pattern])
    try:
        f = http_GET(url)
    except urllib2.HTTPError, e:
        print >>sys.stderr, 'error getting pattern \'%s\' for project \'%s\'' % (pattern, prj)
        print >>sys.stderr, e
        sys.exit(1)
    return f.readlines()


class metafile:
    """metafile that can be manipulated and is stored back after manipulation."""
    def __init__(self, url, input, change_is_required=False):
        import tempfile

        self.url = url
        self.change_is_required = change_is_required

        (fd, self.filename) = tempfile.mkstemp(prefix = 'osc_metafile.', suffix = '.xml', dir = '/tmp')

        f = os.fdopen(fd, 'w')
        f.write(''.join(input))
        f.close()

        self.hash_orig = dgst(self.filename)

    def sync(self):
        hash = dgst(self.filename)
        if self.change_is_required == True and hash == self.hash_orig:
            print 'File unchanged. Not saving.'
            os.unlink(self.filename)
            return True

        try:
            print 'Sending meta data...'
            http_PUT(self.url, file=self.filename)
            os.unlink(self.filename)
            print 'Done.'
            return True
        except urllib2.HTTPError, e:
            # internal server error (probably the xml file is incorrect)
            if e.code == 400:
                print >>sys.stderr, 'Cannot save meta data.'
                print >>sys.stderr, e
                print >>sys.stderr, e.read()
                return False
            if e.code == 500:
                print >>sys.stderr, 'Cannot save meta data. Unknown error.'
                print >>sys.stderr, e
                # this may be unhelpful... because it may just print a big blob of uninteresting
                # ichain html and javascript... however it could potentially be useful if the orign
                # server returns an information body
                if conf.config['http_debug']:
                    print >>sys.stderr, e.read()
                return False
            else:
                print >> sys.stderr, 'cannot save meta data - an unexpected error occured'
                return False
    

# different types of metadata
metatypes = { 'prj':     { 'path': 'source/%s/_meta',
                           'template': new_project_templ,
                         },
              'pkg':     { 'path'     : 'source/%s/%s/_meta',
                           'template': new_package_templ,
                         },
              'prjconf': { 'path': 'source/%s/_config',
                           'template': '',
                         },
              'user':    { 'path': 'person/%s',
                           'template': new_user_template,
                         },
              'pattern': { 'path': 'source/%s/_pattern/%s',
                           'template': new_pattern_template,
                         },
            }

def meta_exists(metatype,
                path_args=None,
                template_args=None,
                create_new=True):

    data = None
    url = make_meta_url(metatype, path_args)
    try:
        data = http_GET(url).readlines()
    except urllib2.HTTPError, e:
        if e.code == 404:
            if create_new:
                data = metatypes[metatype]['template']
                if template_args:
                    data = data % template_args
        else:
            print >>sys.stderr, 'error getting metadata for type \'%s\' at URL \'%s\':' \
                                % (metatype, url)
    return data

def make_meta_url(metatype, path_args=None):
    if metatype not in metatypes.keys():
        sys.exit('unknown metatype %s' % metatype)
    path = metatypes[metatype]['path']

    if path_args:
        path = path % path_args

    return makeurl(conf.config['apiurl'], [path])


def edit_meta(metatype, 
              path_args=None, 
              data=None, 
              template_args=None, 
              edit=False,
              change_is_required=False):

    if not data:
        data = meta_exists(metatype,
                           path_args,
                           template_args,
                           create_new=True)

    if edit:
        change_is_required = True

    url = make_meta_url(metatype, path_args)
    f=metafile(url, data, change_is_required)

    if edit:
        editor = os.getenv('EDITOR', default='vim')
        while 1:
            os.system('%s %s' % (editor, f.filename))
            if change_is_required == True:
                if not f.sync():
                    input = raw_input('Try again? (yY = Yes - nN = No): ')
                    if input != 'y' and input != 'Y':
                        break
                else:
                    break
            else:
                f.sync()
                break
    else:
        f.sync()


def show_files_meta(apiurl, prj, pac, revision=None):
    query = []
    if revision:
        query.append('rev=%s' % revision)
    f = http_GET(makeurl(apiurl, ['source', prj, pac], query=query))
    return f.readlines()


def show_upstream_rev(apiurl, prj, pac):
    m = show_files_meta(apiurl, prj, pac)
    return ET.parse(StringIO(''.join(m))).getroot().get('rev')


def read_meta_from_spec(specfile, *args):
    import codecs, locale
    """
    Read tags and sections from spec file. To read out
    a tag the passed argument must end with a colon. To
    read out a section the passed argument must start with
    a '%'.
    This method returns a dictionary which contains the
    requested data.
    """

    if not os.path.isfile(specfile):
        print 'file \'%s\' is not a readable file' % specfile
        sys.exit(1)

    try:
        lines = codecs.open(specfile, 'r', locale.getpreferredencoding()).readlines()
    except UnicodeDecodeError:
        lines = open(specfile).readlines()

    tags = []
    sections = []
    spec_data = {}

    for itm in args:
        if itm.endswith(':'):
            tags.append(itm)
        elif itm.startswith('%'):
            sections.append(itm)
        else:
            print >>sys.stderr, 'error - \'%s\' is not a tag nor a section' % itm
            sys.exit(1)

    for tag in tags:
        for line in lines:
            if line.startswith(tag):
                spec_data[tag] = line.split(':')[1].strip()
                break
        if not spec_data.has_key(tag):
            print >>sys.stderr, 'error - tag \'%s\' does not exist' % tag
            sys.exit(1)

    for section in sections:
        try:
            start = lines.index(section + '\n') + 1
        except ValueError:
            print >>sys.stderr, 'error - section \'%s\' does not exist' % section
            sys.exit(1)
        data = []
        for line in lines[start:]:
            if line.startswith('%'):
                break
            data.append(line)
        spec_data[section] = data

    return spec_data


def get_user_meta(apiurl, user):
    u = makeurl(apiurl, ['person', quote_plus(user)])
    try:
        f = http_GET(u)
        return ''.join(f.readlines())
    except urllib2.HTTPError:
        print 'user \'%s\' not found' % user
        return None


def get_user_data(apiurl, user, *tags):
    """get specified tags from the user meta"""
    meta = get_user_meta(apiurl, user)
    data = []
    if meta != None:
        root = ET.fromstring(meta)
        for tag in tags:
            try:
                if root.find(tag).text != None:
                    data.append(root.find(tag).text)
                else:
                    # tag is empty
                    data.append('-')
            except AttributeError:
                # this part is reached if the tags tuple contains an invalid tag
                print 'The xml file for user \'%s\' seems to be broken' % user
                return None
        return data
    else:
        return None


def get_source_file(apiurl, prj, package, filename, targetfilename=None, revision = None):
    query = []
    if revision:
        query.append('rev=%s' % quote_plus(revision))

    u = makeurl(apiurl, ['source', prj, package, pathname2url(filename)], query=query)
    # print 'url: %s' % u
    f = http_GET(u)

    o = open(targetfilename or filename, 'w')
    while 1:
        buf = f.read(BUFSIZE)
        if not buf: break
        o.write(buf)
    o.close()


def get_binary_file(apiurl, prj, repo, arch, 
                    filename, targetfilename=None, 
                    package=None,
                    progress_meter=False):

    where = package or '_repository'
    u = makeurl(apiurl, ['build', prj, repo, arch, where, filename])

    if progress_meter:
        sys.stdout.write("Downloading %s [  0%%]" % filename)
        sys.stdout.flush()

    f = http_GET(u)
    binsize = int(f.headers['content-length'])

    import tempfile
    (fd, tmpfilename) = tempfile.mkstemp(prefix = filename + '.', suffix = '.osc', dir = '/tmp')

    o = os.fdopen(fd, 'w')

    downloaded = 0
    while 1:
        #buf = f.read(BUFSIZE)
        buf = f.read(16384)
        if not buf: break
        o.write(buf)
        downloaded += len(buf)
        if progress_meter:
            completion = str(int((float(downloaded)/binsize)*100))
            sys.stdout.write('%s%*s%%]' % ('\b'*5, 3, completion))
            sys.stdout.flush()
    o.close()

    if progress_meter:
        sys.stdout.write('\n')

    shutil.move(tmpfilename, targetfilename or filename)


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
    f.close()


def binary(s):
    """return true if a string is binary data using diff's heuristic"""
    if s and '\0' in s[:4096]:
        return True
    return False


def binary_file(fn):
    """read 4096 bytes from a file named fn, and call binary() on the data"""
    return binary(open(fn, 'r').read(4096))


def get_source_file_diff(dir, filename, rev, oldfilename = None, olddir = None, origfilename = None):
    """
    This methods diffs oldfilename against filename (so filename will
    be shown as the new file).
    The variable origfilename is used if filename and oldfilename differ
    in their names (for instance if a tempfile is used for filename etc.)
    """

    import difflib

    if not oldfilename:
        oldfilename = filename

    if not olddir:
        olddir = os.path.join(dir, store)

    if not origfilename:
        origfilename = filename

    file1 = os.path.join(olddir, oldfilename)   # old/stored original
    file2 = os.path.join(dir, filename)         # working copy

    f1 = open(file1, 'r')
    s1 = f1.read()
    f1.close()

    f2 = open(file2, 'r')
    s2 = f2.read()
    f2.close()

    if binary(s1) or binary (s2):
        d = ['Binary file %s has changed\n' % origfilename]

    else:
        d = difflib.unified_diff(\
            s1.splitlines(1), \
            s2.splitlines(1), \
            fromfile = '%s     (revision %s)' % (origfilename, rev), \
            tofile = '%s     (working copy)' % origfilename)

        # if file doesn't end with newline, we need to append one in the diff result
        d = list(d)
        for i, line in enumerate(d):
            if not line.endswith('\n'):
                d[i] += '\n\\ No newline at end of file'
                if i+1 != len(d):
                    d[i] += '\n'

    return ''.join(d)

def make_diff(wc, revision):
    import tempfile
    changed_files = []
    added_files = []
    removed_files = []
    cmp_pac = None
    diff_hdr = 'Index: %s\n'
    diff_hdr += '===================================================================\n'
    diff = []
    if not revision:
        # normal diff
        if wc.todo:
            for file in wc.todo:
                if file in wc.filenamelist+wc.filenamelist_unvers:
                    state = wc.status(file)
                    if state == 'A':
                        added_files.append(file)
                    elif state == 'D':
                        removed_files.append(file)
                    elif state == 'M' or state == 'C':
                        changed_files.append(file)
                else:
                    diff.append('osc: \'%s\' is not under version control' % file)
        else:
            for file in wc.filenamelist+wc.filenamelist_unvers:
                state = wc.status(file)
                if state == 'M' or state == 'C':
                    changed_files.append(file)
                elif state == 'A':
                    added_files.append(file)
                elif state == 'D':
                    removed_files.append(file)
    else:
        olddir = os.getcwd()
        tmpdir  = tempfile.mkdtemp(revision, wc.name, '/tmp')
        os.chdir(tmpdir)
        init_package_dir(conf.config['apiurl'], wc.prjname, wc.name, tmpdir, revision)
        cmp_pac = Package(tmpdir)
        if wc.todo:
            for file in wc.todo:
                if file in cmp_pac.filenamelist:
                    if file in wc.filenamelist:
                        changed_files.append(file)
                    else:
                        diff.append('osc: \'%s\' is not under version control' % file)
                else:
                    diff.append('osc: unable to find \'%s\' in revision %s' % (file, cmp_pac.rev))
        else:
            for file in wc.filenamelist+wc.filenamelist_unvers:
                state = wc.status(file)
                if state == 'A' and (not file in cmp_pac.filenamelist):
                    added_files.append(file)
                elif file in cmp_pac.filenamelist and state == 'D':
                    removed_files.append(file)
                elif state == ' ' and not file in cmp_pac.filenamelist:
                    added_files.append(file)
                elif file in cmp_pac.filenamelist and state != 'A' and state != '?':
                    if dgst(os.path.join(wc.absdir, file)) != cmp_pac.findfilebyname(file).md5:
                        changed_files.append(file)
            for file in cmp_pac.filenamelist:
                if not file in wc.filenamelist:
                    removed_files.append(file)
            removed_files = set(removed_files)

    for file in changed_files:
        diff.append(diff_hdr % file)
        if cmp_pac == None:
            diff.append(get_source_file_diff(wc.absdir, file, wc.rev))
        else:
            cmp_pac.updatefile(file, revision)
            diff.append(get_source_file_diff(wc.absdir, file, revision, file,
                                             cmp_pac.absdir, file))
    (fd, tmpfile) = tempfile.mkstemp(dir='/tmp')
    for file in added_files:
        diff.append(diff_hdr % file)
        if cmp_pac == None:
            diff.append(get_source_file_diff(wc.absdir, file, wc.rev, os.path.basename(tmpfile),
                                             os.path.dirname(tmpfile), file))
        else:
            diff.append(get_source_file_diff(wc.absdir, file, revision, os.path.basename(tmpfile),
                                             os.path.dirname(tmpfile), file))

    # FIXME: this is ugly but it cannot be avoided atm
    #        if a file is deleted via "osc rm file" we should keep the storefile.
    tmp_pac = None
    if cmp_pac == None:
        olddir = os.getcwd()
        tmpdir  = tempfile.mkdtemp(dir='/tmp')
        os.chdir(tmpdir)
        init_package_dir(conf.config['apiurl'], wc.prjname, wc.name, tmpdir, wc.rev)
        tmp_pac = Package(tmpdir)
        os.chdir(olddir)

    for file in removed_files:
        diff.append(diff_hdr % file)
        if cmp_pac == None:
            tmp_pac.updatefile(file, tmp_pac.rev)
            diff.append(get_source_file_diff(os.path.dirname(tmpfile), os.path.basename(tmpfile),
                                             wc.rev, file, tmp_pac.storedir, file))
        else:
            cmp_pac.updatefile(file, revision)
            diff.append(get_source_file_diff(os.path.dirname(tmpfile), os.path.basename(tmpfile),
                                             revision, file, cmp_pac.storedir, file))

    os.chdir(olddir)
    if cmp_pac != None:
        delete_tmpdir(cmp_pac.absdir)
    if tmp_pac != None:
        delete_tmpdir(tmp_pac.absdir)
    return diff


def pretty_diff(apiurl,
                old_project, old_package, old_revision,
                new_project, new_package, new_revision):

    query = []
    query.append('cmd=diff')
    if old_project:
        query.append('oproject=%s' % quote_plus(old_project))
    if old_package:
        query.append('opackage=%s' % quote_plus(old_package))
    if old_revision:
        query.append('orev=%s' % quote_plus(old_revision))
    if new_revision:
        query.append('rev=%s' % quote_plus(new_revision))

    u = makeurl(apiurl, ['source', new_project, new_package], query=query)

    f = http_POST(u)
    return f.read()


def make_dir(apiurl, project, package):
    #print "creating directory '%s'" % project
    if not os.path.exists(project):
        print statfrmt('A', project)
        init_project_dir(apiurl, project, project)

    #print "creating directory '%s/%s'" % (project, package)
    if not os.path.exists(os.path.join(project, package)):
        print statfrmt('A', '%s/%s' % (project, package))    
        os.mkdir(os.path.join(project, package))
        os.mkdir(os.path.join(project, package, store))

    return(os.path.join(project, package))


def checkout_package(apiurl, project, package, revision=None):
    olddir = os.getcwd()

    path = (quote_plus(project), quote_plus(package))
    if meta_exists(metatype='pkg', path_args=path, create_new=False) == None:
        print >>sys.stderr, 'error 404 - package or package does not exist'
        sys.exit(1)
 
    os.chdir(make_dir(apiurl, project, package))
    init_package_dir(apiurl, project, package, store, revision)
    p = Package(os.curdir)

    for filename in p.filenamelist:
        p.updatefile(filename, revision)
        print 'A   ', os.path.join(project, package, filename)

    os.chdir(olddir)


def replace_pkg_meta(pkgmeta, new_name, new_prj):
    """
    update pkgmeta with new new_name and new_prj and set calling user as the
    only maintainer
    """
    root = ET.fromstring(''.join(pkgmeta))
    root.set('name', new_name)
    root.set('project', new_prj)
    for person in root.findall('person'):
        root.remove(person)
    ET.SubElement(root, 'person',
                  userid = conf.config['user'], role = 'maintainer')
    return ET.tostring(root)

def link_pac(src_project, src_package, dst_project, dst_package):
    """
    create a linked package
     - "src" is the original package
     - "dst" is the "link" package that we are creating here
    """

    src_meta = show_package_meta(conf.config['apiurl'], src_project, src_package)
    src_meta = replace_pkg_meta(src_meta, dst_package, dst_project)

    edit_meta('pkg',
              path_args=(dst_project, dst_package), 
              data=src_meta)

    # create the _link file
    # but first, make sure not to overwrite an existing one
    if '_link' in meta_get_filelist(conf.config['apiurl'], dst_project, dst_package):
        print >>sys.stderr
        print >>sys.stderr, '_link file already exists...! Aborting'
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

    u = makeurl(conf.config['apiurl'], ['source', dst_project, dst_package, '_link'])
    http_PUT(u, data=link_template)
    print 'Done.'

def aggregate_pac(src_project, src_package, dst_project, dst_package):
    """
    aggregate package
     - "src" is the original package
     - "dst" is the "aggregate" package that we are creating here
    """

    src_meta = show_package_meta(conf.config['apiurl'], src_project, src_package)
    src_meta = replace_pkg_meta(src_meta, dst_package, dst_project)

    edit_meta('pkg',
              path_args=(dst_project, dst_package), 
              data=src_meta)

    # create the _aggregate file
    # but first, make sure not to overwrite an existing one
    if '_aggregate' in meta_get_filelist(conf.config['apiurl'], dst_project, dst_package):
        print >>sys.stderr
        print >>sys.stderr, '_aggregate file already exists...! Aborting'
        sys.exit(1)

    print 'Creating _aggregate...',
    aggregate_template = """\
<aggregatelist>
  <aggregate project="%s">
    <package>%s</package>
  </aggregate>
</aggregatelist>
""" % (src_project, src_package)

    u = makeurl(conf.config['apiurl'], ['source', dst_project, dst_package, '_aggregate'])
    http_PUT(u, data=aggregate_template)
    print 'Done.'

def copy_pac(src_apiurl, src_project, src_package, 
             dst_apiurl, dst_project, dst_package):
    """
    create a copy of a package
    """

    import tempfile

    src_meta = show_package_meta(src_apiurl, src_project, src_package)
    src_meta = replace_pkg_meta(src_meta, dst_package, dst_project)

    print 'Sending meta data...'
    u = makeurl(dst_apiurl, ['source', dst_project, dst_package, '_meta'])
    http_PUT(u, data=src_meta)

    # copy one file after the other
    print 'Copying files...'
    tmpdir = tempfile.mkdtemp(prefix='osc_copypac', dir='/tmp')
    os.chdir(tmpdir)
    for n in meta_get_filelist(src_apiurl, src_project, src_package):
        print '  ', n
        get_source_file(src_apiurl, src_project, src_package, n, targetfilename=n)
        u = makeurl(dst_apiurl, ['source', dst_project, dst_package, pathname2url(n)])
        http_PUT(u, file = n)
        os.unlink(n)
    print 'Done.'
    os.rmdir(tmpdir)


def delete_package(apiurl, prj, pac):
    u = makeurl(apiurl, ['source', prj, pac])
    try:
        http_DELETE(u)
    except urllib2.HTTPError, e:
        if e.code == 404:
            print >>sys.stderr, 'Package \'%s\' does not exist' % pac
            sys.exit(1)
        else:
            print >>sys.stderr, 'an unexpected error occured while deleting ' \
                                '\'%s\'' % pac
            sys.exit(1)            


def delete_project(apiurl, prj):
    u = makeurl(apiurl, ['source', prj])
    try:
        http_DELETE(u)
    except urllib2.HTTPError, e:
        if e.code == 404:
            print >>sys.stderr, 'Package \'%s\' does not exist' % pac
            sys.exit(1)
        else:
            print >>sys.stderr, 'an unexpected error occured while deleting ' \
                                '\'%s\'' % pac
            sys.exit(1)


def get_platforms(apiurl):
    f = http_GET(makeurl(apiurl, ['platform']))
    tree = ET.parse(f)
    r = [ node.get('name') for node in tree.getroot() ]
    r.sort()
    return r


def get_platforms_of_project(apiurl, prj):
    f = show_project_meta(apiurl, prj)
    tree = ET.parse(StringIO(''.join(f)))

    r = [ node.get('name') for node in tree.findall('repository')]
    return r


def get_repos_of_project(apiurl, prj):
    f = show_project_meta(apiurl, prj)
    tree = ET.parse(StringIO(''.join(f)))

    repo_line_templ = '%-15s %-10s'
    for node in tree.findall('repository'):
        for node2 in node.findall('arch'):
            yield repo_line_templ % (node.get('name'), node2.text)


def get_binarylist(apiurl, prj, repo, arch, package=None):
    what = package or '_repository'
    u = makeurl(apiurl, ['build', prj, repo, arch, what])
    f = http_GET(u)
    tree = ET.parse(f)
    r = [ node.get('filename') for node in tree.findall('binary')]
    return r


def get_binarylist_published(apiurl, prj, repo, arch):
    u = makeurl(apiurl, ['published', prj, repo, arch])
    f = http_GET(u)
    tree = ET.parse(f)
    r = [ node.get('name') for node in tree.findall('entry')]
    return r


def show_results_meta(apiurl, prj, package=None):
    query = []
    if package:
        query.append('package=%s' % pathname2url(package))
    u = makeurl(apiurl, ['build', prj, '_result'], query=query)
    f = http_GET(u)
    return f.readlines()


def show_prj_results_meta(apiurl, prj):
    u = makeurl(apiurl, ['build', prj, '_result'])
    f = http_GET(u)
    return f.readlines()


def get_results(apiurl, prj, package):
    r = []
    result_line_templ = '%(rep)-15s %(arch)-10s %(status)s'

    f = show_results_meta(apiurl, prj, package=package)
    tree = ET.parse(StringIO(''.join(f)))
    root = tree.getroot()

    for node in root.findall('result'):
        rmap = {}
        rmap['prj'] = prj
        rmap['pac'] = package
        rmap['rep'] = node.get('repository')
        rmap['arch'] = node.get('arch')

        statusnode =  node.find('status')
        try:
            rmap['status'] = statusnode.get('code')
        except:
            # code can be missing when package is too new:
            return {}

        if rmap['status'] in ['expansion error', 'broken']:
            rmap['status'] += ': ' + statusnode.find('details').text

        if rmap['status'] == 'failed':
            rmap['status'] += ': %s://%s' % (conf.config['scheme'], conf.config['apisrv']) + \
                '/result/%(prj)s/%(rep)s/%(pac)s/%(arch)s/log' % rmap

        r.append(result_line_templ % rmap)
    return r

def get_prj_results(apiurl, prj, show_legend=False):
    #print '----------------------------------------'

    r = []
    #result_line_templ = '%(prj)-15s %(pac)-15s %(rep)-15s %(arch)-10s %(status)s'
    result_line_templ = '%(rep)-15s %(arch)-10s %(status)s'

    f = show_prj_results_meta(apiurl, prj)
    tree = ET.parse(StringIO(''.join(f)))
    root = tree.getroot()

    pacs = []
    if not root.find('result'):
        return []
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
                if not status.has_key(pac):     # for newly added packages, status may be missing
                    status[pac] = '?'
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


def get_buildlog(apiurl, prj, package, platform, arch, offset):
    u = makeurl(apiurl, ['build', prj, platform, arch, package, '_log?nostream=1&start=%s' % offset])
    f = http_GET(u)
    return f.read()

def print_buildlog(apiurl, prj, package, platform, arch, offset = 0):
    """prints out the buildlog on stdout"""
    try:
        while True:
            log_chunk = get_buildlog(apiurl, prj, package, platform, arch, offset)
            if len(log_chunk) == 0:
                break
            offset += len(log_chunk)
            print log_chunk.strip()
    except urllib2.HTTPError, e:
        print >>sys.stderr, 'Can\'t get logfile'
        print >>sys.stderr, e
    except KeyboardInterrupt:
        pass

def get_buildinfo(apiurl, prj, package, platform, arch, specfile=None, addlist=None):
    query = []
    if addlist:
        for i in addlist:
            query.append('add=%s' % quote_plus(i))

    u = makeurl(apiurl, ['build', prj, platform, arch, package, '_buildinfo'], query=query)

    if specfile:
        f = http_POST(u, data=specfile)
    else:
        f = http_GET(u)
    return f.read()


def get_buildconfig(apiurl, prj, package, platform, arch):
    u = makeurl(apiurl, ['build', prj, platform, '_buildconfig'])
    f = http_GET(u)
    return f.read()


def get_buildhistory(apiurl, prj, package, platform, arch):
    import time
    u = makeurl(apiurl, ['build', prj, platform, arch, package, '_history'])
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


def get_commitlog(apiurl, prj, package, revision):
    import time, locale
    u = makeurl(apiurl, ['source', prj, package, '_history'])
    f = http_GET(u)
    root = ET.parse(f).getroot()

    r = []
    revisions = root.findall('revision')
    revisions.reverse()
    for node in revisions:
        try:
            rev = int(node.get('rev'))
            #vrev = int(node.get('vrev')) # what is the meaning of vrev?
            if revision and rev != int(revision):
                continue
        except ValueError:
            # this part should _never_ be reached but...
            return [ 'an unexpected error occured - please file a bug' ]
        srcmd5 = node.find('srcmd5').text
        version = node.find('version').text
        user = node.find('user').text
        try:
            comment = node.find('comment').text.encode(locale.getpreferredencoding(), 'replace')
        except:
            comment = '<no message>'
        t = time.localtime(int(node.find('time').text))
        t = time.strftime('%Y-%m-%d %H:%M:%S', t)

        s = '-' * 76 + \
            '\nr%s | %s | %s | %s | %s\n' % (rev, user, t, srcmd5, version) + \
            '\n' + comment
        r.append(s)

    r.append('-' * 76)
    return r


def rebuild(apiurl, prj, package, repo, arch, code=None):
    query = []
    query.append('cmd=rebuild')
    if package:
        query.append('package=%s' % quote_plus(package))
    if repo:
        query.append('repository=%s' % quote_plus(repo))
    if arch:
        query.append('arch=%s' % quote_plus(arch))
    if code:
        query.append('code=%s' % quote_plus(code))

    u = makeurl(apiurl, ['build', prj], query=query)
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
    try:
        p = open(os.path.join(dir, store, '_project')).readlines()[0].strip()
    except IOError:
        print >>sys.stderr, 'error: \'%s\' is not an osc project dir ' \
                            'or working copy' % dir
        sys.exit(1)                         
    return p


def store_read_package(dir):
    try:
        p = open(os.path.join(dir, store, '_package')).readlines()[0].strip()
    except IOError:
        print >>sys.stderr, 'error: \'%s\' is not an osc working copy' % dir
        sys.exit(1)
    return p

def store_read_apiurl(dir):
    fname = os.path.join(dir, store, '_apiurl')
    try:
        apiurl = open(fname).readlines()[0].strip()
    except:
        apiurl = conf.config['scheme'] + '://' + conf.config['apisrv']
        #store_write_apiurl(dir, apiurl)
    return apiurl

def store_write_project(dir, project):
    fname = os.path.join(dir, store, '_project')
    open(fname, 'w').write(project + '\n')

def store_write_apiurl(dir, apiurl):
    fname = os.path.join(dir, store, '_apiurl')
    open(fname, 'w').write(apiurl + '\n')

def get_osc_version():
    return __version__


def abortbuild(apiurl, project, package=None, arch=None, repo=None):
    query = []
    query.append('cmd=abortbuild')
    if package:
        query.append('package=%s' % quote_plus(package))
    if arch:
        query.append('arch=%s' % quote_plus(arch))
    if repo:
        query.append('repository=%s' % quote_plus(repo))
    u = makeurl(apiurl, ['build', project], query)
    try:
        f = http_POST(u)
    except urllib2.HTTPError, e:
        err_str = 'abortion failed for project %s' % project
        if package:
            err_str += ' package %s' % package
        if arch:
            err_str += ' arch %s' % arch
        if repo:
            err_str += ' repo %s' % repo
        print >> sys.stderr, err_str
        print >> sys.stderr, u
        print >> sys.stderr, e
        sys.exit(1)
    root = ET.parse(f).getroot()
    return root.get('code')


def wipebinaries(apiurl, project, package=None, arch=None, repo=None, code=None):
    query = []
    query.append('cmd=wipe')
    if package:
        query.append('package=%s' % quote_plus(package))
    if arch:
        query.append('arch=%s' % quote_plus(arch))
    if repo:
        query.append('repository=%s' % quote_plus(repo))
    if code:
        query.append('code=%s' % quote_plus(code))

    u = makeurl(apiurl, ['build', project], query)
    try:
        f = http_POST(u)
    except urllib2.HTTPError, e:
        err_str = 'wipe binary rpms failed for project %s' % project
        if package:
            err_str += ' package %s' % package
        if arch:
            err_str += ' arch %s' % arch
        if repo:
            err_str += ' repository %s' % repo
        if code:
            err_str += ' code=%s' % code
        print >> sys.stderr, err_str
        print >> sys.stderr, u
        print >> sys.stderr, e
        sys.exit(1)
    root = ET.parse(f).getroot()
    return root.get('code')


def parseRevisionOption(string):
    """
    returns a tuple which contains the revisions
    """

    if string:
        if ':' in string:
            splitted_rev = string.split(':')
            try:
                for i in splitted_rev:
                    int(i)
                return splitted_rev
            except ValueError:
                print >>sys.stderr, 'your revision \'%s\' will be ignored' % string
                return None, None
        else:
            if string.isdigit():
                return string, None
            else:
                print >>sys.stderr, 'your revision \'%s\' will be ignored' % string
                return None, None
    else:
        return None, None

def checkRevision(prj, pac, revision):
    """
    check if revision is valid revision
    """
    try:
        if int(revision) > int(show_upstream_rev(conf.config['apiurl'], prj, pac)) \
           or int(revision) <= 0:
            return False
        else:
            return True
    except (ValueError, TypeError):
        return False

def build_xpath_predicate(search_list, search_term, exact_matches):
    """
    Builds and returns a xpath predicate
    """

    predicate = ['[']
    for i, elem in enumerate(search_list):
        if i > 0 and i < len(search_list):
            predicate.append(' or ')
        if exact_matches:
            predicate.append('%s=\'%s\'' % (elem, search_term))
        else:
            predicate.append('contains(%s, \'%s\')' % (elem, search_term))
    predicate.append(']')
    return predicate

def build_table(col_num, data = [], headline = [], width=1):
    """
    This method builds a simple table.
    Example1: build_table(2, ['foo', 'bar', 'suse', 'osc'], ['col1', 'col2'], 2)
        col1  col2
        foo   bar
        suse  osc
    """

    longest_col = []
    for i in range(col_num):
        longest_col.append(0)
    if headline:
        data[0:0] = headline
    # find longest entry in each column
    i = 0
    for itm in data:
        if longest_col[i] < len(itm):
            longest_col[i] = len(itm)
        if i == col_num - 1:
            i = 0
        else:
            i += 1
    # calculate length for each column
    for i, row in enumerate(longest_col):
        longest_col[i] = row + width
    # build rows   
    row = []
    table = []
    i = 0
    for itm in data:
        if i % col_num == 0:
            if row:
                table.append(''.join(row))
            i = 0
            row = [itm.ljust(longest_col[i])]
        else:
            # there is no need to justify the entries of the last column
            if i == col_num -1:
                row.append(itm)
            else:
                row.append(itm.ljust(longest_col[i]))
        i += 1
    table.append(''.join(row))
    return table

def search(apiurl, search_list, kind, search_term, verbose = False, exact_matches = False, repos_baseurl = False):
    """
    Perform a search for 'search_term'. A list which contains the
    results will be returned on success otherwise 'None'. If 'verbose' is true
    and the title-tag-text (<title>TEXT</title>) is longer than 60 chars it'll we
    truncated.
    """

    predicate = build_xpath_predicate(search_list, search_term, exact_matches)
    u = makeurl(apiurl, ['search', kind], ['match=%s' % quote_plus(''.join(predicate))])
    f = http_GET(u)
    root = ET.parse(f).getroot()
    result = []
    for node in root.findall(kind):
        # TODO: clarify if we need to check if node.get() returns 'None'.
        #       If it returns 'None' something is broken anyway...
        if kind == 'package':
            project = node.get('project')
            package = node.get('name')
            result.append(package)
        else:
            project = node.get('name')
        result.append(project)
        if verbose:
            title = node.findtext('title').strip()
            if len(title) > 60:
                title = title[:61] + '...'
            result.append(title)
        if repos_baseurl:
            result.append('http://download.opensuse.org/repositories/%s/' % project.replace(':', ':/'))
    if result:
        return result
    else:
        return None

def delete_tmpdir(tmpdir):
    """
    This method deletes a tempdir. This tempdir
    must be located under /tmp/$DIR. If "tmpdir" is not
    a valid tempdir it'll return False. If os.unlink() / os.rmdir()
    throws an exception we will return False too - otherwise
    True.
    """

    # small security checks
    if os.path.islink(tmpdir):
        return False
    elif os.path.abspath(tmpdir) == '/':
        return False
    
    head, tail = os.path.split(tmpdir)
    if not head.startswith('/tmp') or not tail:
        return False

    if not os.path.isdir(tmpdir):
        return False

    for dirpath, dirnames, filenames in os.walk(tmpdir, topdown=False):
        for file in filenames:
            try:
                os.unlink(os.path.join(dirpath, file))
            except:
                return False
        for dirname in dirnames:
            try:
                os.rmdir(os.path.join(dirpath, dirname))
            except:
                return False
    try:
        os.rmdir(tmpdir)
    except:
        return False
    return True

def unpack_srcrpm(srpm, dir, *files):
    """
    This method unpacks the passed srpm into the
    passed dir. If arguments are passed to the \'files\' tuple
    only this files will be unpacked.
    """
    if not is_srcrpm(srpm):
        print >>sys.stderr, 'error - \'%s\' is not a source rpm.' % srpm
        sys.exit(1)
    curdir = os.getcwd()
    if not os.path.isdir(dir):
        dir = curdir
    else:
        os.chdir(dir)
    cmd = 'rpm2cpio %s | cpio -i %s &> /dev/null' % (srpm, ' '.join(files))
    ret = os.system(cmd)
    if ret != 0:
        print >>sys.stderr, 'error \'%s\' - cannot extract \'%s\'' % (ret, srpm)
        sys.exit(1)
    os.chdir(curdir)

def tag_to_rpmpy(tag):
    """
    maps a spec file tag/section to a valid
    rpm-python RPMTAG
    """

    try:
        import rpm
        tags = { 'Name:' : rpm.RPMTAG_NAME,
                 'Summary:' : rpm.RPMTAG_SUMMARY,
                 '%description' : rpm.RPMTAG_DESCRIPTION
               }
        if tag in tags.keys():
            return tags[tag]
        else:
            return None
    except ImportError:
        return None

def data_from_rpm(rpm_file, *rpmdata):
    """
    This method reads the given rpmdata
    from a rpm.
    """

    try:
        import rpm
        ts = rpm.TransactionSet()
        file = open(rpm_file, 'r')
        header = ts.hdrFromFdno(file.fileno())
        file.close()
        data = {}
        for itm in rpmdata:
            rpmpy = tag_to_rpmpy(itm)
            if rpmpy:
                data[itm] = header[rpmpy]
            else:
                print >>sys.stderr, 'invalid data \'%s\'' % itm
                sys.exit(1)
        return data
    except ImportError:
        print >>sys.stderr, 'warning: rpm-python not found'
        return None

def is_rpm(f):
    """check if the named file is an RPM package"""
    try:                                                                                                                                
        h = open(f).read(4)
    except:
        return False

    if h == '\xed\xab\xee\xdb':
        return True
    else:
        return False

def is_srcrpm(f):
    """check if the named file is a source RPM"""

    if not is_rpm(f):
        return False

    try:
        h = open(f).read(8)
    except:
        return False

    if h[7] == '\x01':
        return True
    else:
        return False   

def delete_server_files(apiurl, prj, pac, files):
    """
    This method deletes the given filelist on the
    server. No local data will be touched.
    """

    for file in files:
        try:
            u = makeurl(apiurl, ['source', prj, pac, file])
            http_DELETE(u)
        except:
            # we do not handle all exceptions here - we need another solution
            # see bug #280034
            print >>sys.stderr, 'error while deleting file \'%s\'' % file
            sys.exit(1)

def addMaintainer(apiurl, prj, pac, user):
    """ add a new maintainer to a package or project """
    path = quote_plus(prj),
    kind = 'prj'
    if pac:
        path = path + (quote_plus(pac),)
        kind = 'pkg'
    data = meta_exists(metatype=kind,
                       path_args=path,
                       template_args=None,
                       create_new=False)
                       
    if data and get_user_meta(apiurl, user) != None:
        tree = ET.fromstring(''.join(data))
        found = False
        for person in tree.getiterator('person'):
            if person.get('userid') == user:
                found = True
                print "user already exists"
                break
        if not found:
            # the xml has a fixed structure
            tree.insert(2, ET.Element('person', role='maintainer', userid=user))
            print 'user \'%s\' added to \'%s\'' % (user, pac or prj)
            edit_meta(metatype=kind,
                      path_args=path,
                      data=ET.tostring(tree))
    else:
        print "osc: an error occured"

def delMaintainer(apiurl, prj, pac, user):
    """ delete a maintainer from a package or project """
    path = quote_plus(prj), 
    kind = 'prj'
    if pac:
        path = path + (quote_plus(pac), )
        kind = 'pkg'
    data = meta_exists(metatype=kind,
                       path_args=path,
                       template_args=None,
                       create_new=False)
    if data:
        tree = ET.fromstring(''.join(data))
        found = False
        for person in tree.getiterator('person'):
            if person.get('userid') == user:
                tree.remove(person)
                found = True
                print "user \'%s\' removed" % user
        if found:
            edit_meta(metatype=kind,
                      path_args=path,
                      data=ET.tostring(tree))
        else:
            print "user \'%s\' not found in \'%s\'" % (user, pac or prj)
    else:
        print "an error occured"
