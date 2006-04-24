#!/usr/bin/python

# Copyright (C) 2006 Peter Poeml.  All rights reserved.
# This program is free software; it may be used, copied, modified
# and distributed under the terms of the GNU General Public Licence,
# either version 2, or (at your option) any later version.


import os
import sys
import urllib2
from xml.utils import qp_xml
import netrc
from urlparse import urlunsplit

# the needed entry in .netrc looks like this:
# machine api.opensuse.org login your_login password your_pass
info = netrc.netrc()
username, account, password = info.authenticators("api.opensuse.org")

from xml.dom.ext.reader import Sax2
from xml.dom.ext import PrettyPrint

netloc = 'api.opensuse.org'
scheme = 'http'

BUFSIZE = 1024*1024
store = '.osc'
exclude_stuff = [store, '.svn', 'CVS']


def makeurl(l):
    """given a list of path compoments, construct a complete URL"""
    return urlunsplit((scheme, netloc, '/'.join(l), '', ''))               


def copy_file(src, dst):
    s = open(src)
    d = open(dst, 'w')
    while 1:
        buf = s.read(BUFSIZE)
        if not buf: break
        d.write(buf)
    s.close()
    d.close()


def init_basicauth():

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

    f = open('_meta', 'w')
    f.write(''.join(show_package_meta(project, package)))
    f.close()

    return


def meta_get_packagelist(prj):

    reader = Sax2.Reader()
    u = makeurl(['source', prj, '_meta'])
    f = urllib2.urlopen(u)
    doc = reader.fromStream(f)

    r = []
    for i in doc.getElementsByTagName('package'):
        r.append(i.getAttribute('name'))
    return r


def meta_get_filelist(prj, package):

    reader = Sax2.Reader()
    u = makeurl(['source', prj, package, '_meta'])
    f = urllib2.urlopen(u)
    doc = reader.fromStream(f)

    r = []
    for i in doc.getElementsByTagName('file'):
        r.append(i.getAttribute('filename'))
    return r


def localmeta_addfile(filename):

    if filename in localmeta_get_filelist():
        return

    reader = Sax2.Reader()
    f = open(os.path.join(store, '_meta')).read()
    doc = reader.fromString(f)

    new = doc.createElement('file')
    new.setAttribute('filetype', 'source')
    new.setAttribute('filename', filename)
    doc.documentElement.appendChild(new)

    o = open(os.path.join(store, '_meta'), 'w')
    PrettyPrint(doc, stream=o)
    o.close()
    
def localmeta_removefile(filename):

    reader = Sax2.Reader()
    f = open(os.path.join(store, '_meta')).read()
    doc = reader.fromString(f)

    for i in doc.getElementsByTagName('file'):
        if i.getAttribute('filename') == filename:
            i.parentNode.removeChild(i)

    o = open(os.path.join(store, '_meta'), 'w')
    PrettyPrint(doc, stream=o)
    o.close()
    

def localmeta_get_filelist():

    reader = Sax2.Reader()
    f = open(os.path.join(store, '_meta')).read()
    doc = reader.fromString(f)

    r = []
    for i in doc.getElementsByTagName('file'):
        r.append(i.getAttribute('filename'))
    return r


def get_slash_source():
    u = makeurl(['source'])
    f = urllib2.urlopen(u)

    parser = qp_xml.Parser()
    root = parser.parse(f)
    r = []
    for entry in root.children:
        r.append(entry.attrs[('', 'name')])
    return r

def show_project_meta(prj):
    f = urllib2.urlopen(makeurl(['source', prj, '_meta']))
    return f.readlines()


def show_package_meta(prj, pac):
    f = urllib2.urlopen(makeurl(['source', prj, pac, '_meta']))
    return f.readlines()

def get_user_id(user):
    u = makeurl(['person', user])
    f = urllib2.urlopen(u)
    return f.readlines()


def get_source_file(prj, package, filename):
    u = makeurl(['source', prj, package, filename])
    #print 'checking out', u
    f = urllib2.urlopen(u)

    o = open(filename, 'w')
    while 1:
        buf = f.read(BUFSIZE)
        if not buf: break
        o.write(buf)
    o.close()



def dgst(file):

    if not os.path.exists(file):
        return None

    import sha
    s = sha.new()
    f = open(file, 'r')
    while 1:
        buf = f.read(BUFSIZE)
        if not buf: break
        s.update(buf)
    return s.digest()


def get_file_status(prj, package, filename, filelist=None):
    """
    status can be:

     file  storefile  file present  STATUS
    exists  exists      in _meta

      x       x            -        'D'
      x       x            x        'M', if digest differs, else ' '
      x       -            -        '?'
      x       -            x        'A'
      -       x            x        '!'
      -       x            -        NOT DEFINED
      -       -            x        NOT DEFINED
      -       -            -        NEVER REACHED

    """
    known_by_meta = False
    exists = False
    exists_in_store = False

    if not filelist:
        filelist = localmeta_get_filelist()

    if filename in filelist:
        known_by_meta = True

    if os.path.exists(filename):
        exists = True

    if os.path.exists(os.path.join(store, filename)):
        exists_in_store = True

    if exists and exists_in_store and not known_by_meta:
        state = 'D'
    elif exists and exists_in_store and known_by_meta:
        if dgst(filename) != dgst(os.path.join(store, filename)):
            state = 'M'
        else:
            state = ' '
    elif exists and not exists_in_store and not known_by_meta:
        state = '?'
    elif exists and not exists_in_store and known_by_meta:
        state = 'A'
    elif not exists and exists_in_store and known_by_meta:
        state = '!'
    elif not exists and not exists_in_store and known_by_meta:
        print 'not exists and not exists_in_store and known_by_meta'
        print 'this state is undefined!'
        sys.exit(1)
    elif not exists and exists_in_store and not known_by_meta:
        print 'not exists and exists_in_store and not nown_by_meta'
        print 'this state is undefined!'
        sys.exit(1)
    elif not exists and not exists_in_store and not known_by_meta:
        print 'not exists and not exists_in_store and not nown_by_meta'
        print 'this code path should never be reached!'
        sys.exit(1)
        
        
    return '%s    %s' % (state, filename)


def get_source_file_diff(prj, package, filename):
    url = makeurl(['source', prj, package, filename])
    f = urllib2.urlopen(url)

    localfile = open(filename, 'r')

    import difflib
    #print url
    d = difflib.unified_diff(f.readlines(), localfile.readlines(), fromfile = url, tofile = filename)

    localfile.close()

    return ''.join(d)


#def put_source_file_and_meta(prj, package, filename):
#    if filename == '_meta':
#        put_source_file(prj, package, filename)
#        return
#
#    get_source_file(prj, package, '_meta')
#    localmeta_addfile(os.path.basename(filename))
#    put_source_file(prj, package, filename)
#    put_source_file(prj, package, '_meta')


def put_source_file(prj, package, filename):
    import othermethods
    
    sys.stdout.write('.')
    u = makeurl(['source', prj, package, os.path.basename(filename)])
    othermethods.putfile(u, filename, username, password)
    #f = urllib2.urlopen(u)

    #o = open(filename, 'w')
    #o.write(f.read())
    #o.close()

def del_source_file(prj, package, filename):
    import othermethods
    
    u = makeurl(['source', prj, package, filename])
    # not implemented in the server yet... thus, we are cheating by only removing
    # the file from _meta
    #othermethods.delfile(u, filename, username, password)

    wcfilename = os.path.join(store, filename)
    if os.path.exists(filename): os.unlink(filename)
    if os.path.exists(wcfilename): os.unlink(wcfilename)


def make_dir(project, package):
    #print "creating directory '%s'" % project
    print 'A    %s' % project
    if not os.path.exists(project):
        os.mkdir(project)
        os.mkdir(os.path.join(project, store))

    #print "creating directory '%s/%s'" % (project, package)
    print 'A    %s/%s' % (project, package)
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

    parser = qp_xml.Parser()
    root = parser.parse(f)
    r = []
    for entry in root.children:
        r.append(entry.attrs[('', 'name')])
    return r

def get_platforms_of_project(prj):
    f = show_project_meta(prj)

    parser = qp_xml.Parser()
    root = parser.parse('\n'.join(f))
    r = []
    for entry in root.children:
        if entry.name == 'repository':
            r.append(entry.attrs[('', 'name')])
    return r

def get_results(prj, package, platform):
    u = makeurl(['result', prj, platform, package, 'result'])
    f = urllib2.urlopen(u)
    return f.readlines()

def get_log(prj, package, platform, arch):
    u = makeurl(['result', prj, platform, package, arch, 'log'])
    f = urllib2.urlopen(u)
    return f.readlines()

def store_read_project(dir):
    p = open(os.path.join(dir, store, '_project')).readlines()[0].strip()
    return p

def store_read_package(dir):
    p = open(os.path.join(dir, store, '_package')).readlines()[0].strip()
    return p
    #p = open(os.path.join(dir, store, '_meta')).readlines()[0]
    #p = p.split('"')[1]
    #return p


