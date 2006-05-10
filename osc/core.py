#!/usr/bin/python

# Copyright (C) 2006 Peter Poeml.  All rights reserved.
# This program is free software; it may be used, copied, modified
# and distributed under the terms of the GNU General Public Licence,
# either version 2, or (at your option) any later version.

__version__ = '0.2'

import os
import sys
import urllib2
import netrc
from urlparse import urlunsplit
import cElementTree as ET
from cStringIO import StringIO

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

    f = open('_files', 'w')
    f.write(''.join(show_files_meta(project, package)))
    f.close()

    f = open('_osclib_version', 'w')
    f.write(__version__ + '\n')
    f.close()

    return


def check_store_version():
    try:
        v = open(os.path.join(store, '_osclib_version')).read().strip()
    except:
        v = ''

    if v != __version__:
        print 
        print 'the osc metadata of your working copy'
        print '   %s' % os.getcwd()
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
    exists  exists      in _files

      x       x            -        'D'
      x       x            x        'M', if digest differs, else ' '
      x       -            -        '?'
      x       -            x        'A'
      -       x            x        '!'
      -       x            -        'D' (when file in working copy is already deleted)
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
        print '%s: not exists and not exists_in_store and known_by_meta' % filename
        print 'this state is undefined!'
        sys.exit(1)
    elif not exists and exists_in_store and not known_by_meta:
        state = 'D'
    elif not exists and not exists_in_store and not known_by_meta:
        print '%s: not exists and not exists_in_store and not nown_by_meta' % filename
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
    othermethods.delfile(u, filename, username, password)

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
    result_line_templ = '%(rep)-15s %(arch)-10s %(status)s %(hint)s'

    f = show_results_meta(prj, package, platform)
    tree = ET.parse(StringIO(''.join(f)))

    root = tree.getroot()

    rmap = {}
    rmap['hint'] = ''
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
            rmap['status'] += ':'
            rmap['hint'] = '\'osc log %(rep)s %(arch)s\' -> ' % rmap + \
                            '(%s://%s' % (scheme, netloc) + \
                            '/result/%(prj)s/%(rep)s/%(pac)s/%(arch)s/log)' % rmap

        r.append(result_line_templ % rmap)
    return r


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


