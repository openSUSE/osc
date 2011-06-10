# Copyright (C) 2006 Novell Inc.  All rights reserved.
# This program is free software; it may be used, copied, modified
# and distributed under the terms of the GNU General Public Licence,
# either version 2, or version 3 (at your option).

__version__ = '0.132.3'

# __store_version__ is to be incremented when the format of the working copy
# "store" changes in an incompatible way. Please add any needed migration
# functionality to check_store_version().
__store_version__ = '1.0'

import os
import os.path
import sys
import urllib2
from urllib import pathname2url, quote_plus, urlencode, unquote
from urlparse import urlsplit, urlunsplit
from cStringIO import StringIO
import shutil
import oscerr
import conf
import subprocess
import re
import socket
try:
    from xml.etree import cElementTree as ET
except ImportError:
    import cElementTree as ET



DISTURL_RE = re.compile(r"^(?P<bs>.*)://(?P<apiurl>.*?)/(?P<project>.*?)/(?P<repository>.*?)/(?P<revision>.*)-(?P<source>.*)$")
BUILDLOGURL_RE = re.compile(r"^(?P<apiurl>https?://.*?)/build/(?P<project>.*?)/(?P<repository>.*?)/(?P<arch>.*?)/(?P<package>.*?)/_log$")
BUFSIZE = 1024*1024
store = '.osc'

new_project_templ = """\
<project name="%(name)s">

  <title></title> <!-- Short title of NewProject -->
  <description>
    <!-- This is for a longer description of the purpose of the project -->
  </description>

  <person role="maintainer" userid="%(user)s" />
  <person role="bugowner" userid="%(user)s" />
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
  <repository name="openSUSE_11.2">
    <path project="openSUSE:11.2" repository="standard"/>
    <arch>x86_64</arch>
    <arch>i586</arch>
  </repository>
  <repository name="openSUSE_11.1">
    <path project="openSUSE:11.1" repository="standard"/>
    <arch>x86_64</arch>
    <arch>i586</arch>
  </repository>
  <repository name="Fedora_12">
    <path project="Fedora:12" repository="standard" />
    <arch>x86_64</arch>
    <arch>i586</arch>
  </repository>
  <repository name="SLE_11">
    <path project="SUSE:SLE-11" repository="standard" />
    <arch>x86_64</arch>
    <arch>i586</arch>
  </repository>
-->

</project>
"""

new_package_templ = """\
<package name="%(name)s">

  <title></title> <!-- Title of package -->

  <description>
<!-- for long description -->
  </description>

<!-- following roles are inherited from the parent project
  <person role="maintainer" userid="%(user)s"/>
  <person role="bugowner" userid="%(user)s"/>
-->
<!--
  <url>PUT_UPSTREAM_URL_HERE</url>
-->

<!--
  use one of the examples below to disable building of this package
  on a certain architecture, in a certain repository,
  or a combination thereof:

  <disable arch="x86_64"/>
  <disable repository="SUSE_SLE-10"/>
  <disable repository="SUSE_SLE-10" arch="x86_64"/>

  Possible sections where you can use the tags above:
  <build>
  </build>
  <debuginfo>
  </debuginfo>
  <publish>
  </publish>
  <useforbuild>
  </useforbuild>

  Please have a look at:
  http://en.opensuse.org/Restricted_formats
  Packages containing formats listed there are NOT allowed to
  be packaged in the openSUSE Buildservice and will be deleted!

-->

</package>
"""

new_attribute_templ = """\
<attributes>
  <attribute namespace="" name="">
    <value><value>
  </attribute>
</attributes>
"""

new_user_template = """\
<person>
  <login>%(user)s</login>
  <email>PUT_EMAIL_ADDRESS_HERE</email>
  <realname>PUT_REAL_NAME_HERE</realname>
  <watchlist>
    <project name="home:%(user)s"/>
  </watchlist>
</person>
"""

info_templ = """\
Project name: %s
Package name: %s
Path: %s
API URL: %s
Source URL: %s
srcmd5: %s
Revision: %s
Link info: %s
"""

new_pattern_template = """\
<!-- See http://svn.opensuse.org/svn/zypp/trunk/libzypp/zypp/parser/yum/schema/patterns.rng -->

<pattern>
</pattern>
"""

buildstatus_symbols = {'succeeded':       '.',
                       'disabled':        ' ',
                       'expansion error': 'U',  # obsolete with OBS 2.0
                       'unresolvable':    'U',
                       'failed':          'F',
                       'broken':          'B',
                       'blocked':         'b',
                       'building':        '%',
                       'finished':        'f',
                       'scheduled':       's',
                       'excluded':        'x',
                       'dispatching':     'd',
                       'signing':         'S',
}


# os.path.samefile is available only under Unix
def os_path_samefile(path1, path2):
    try:
        return os.path.samefile(path1, path2)
    except:
        return os.path.realpath(path1) == os.path.realpath(path2)

class File:
    """represent a file, including its metadata"""
    def __init__(self, name, md5, size, mtime, skipped=False):
        self.name = name
        self.md5 = md5
        self.size = size
        self.mtime = mtime
        self.skipped = skipped
    def __repr__(self):
        return self.name
    def __str__(self):
        return self.name


class Serviceinfo:
    """Source service content
    """
    def __init__(self):
        """creates an empty serviceinfo instance"""
        self.services = None

    def read(self, serviceinfo_node, append=False):
        """read in the source services <services> element passed as
        elementtree node.
        """
        if serviceinfo_node == None:
            return
        if not append or self.services == None:
            self.services = []
        services = serviceinfo_node.findall('service')

        for service in services:
            name = service.get('name')
            mode = service.get('mode', None)
            data = { 'name' : name, 'mode' : '' }
            if mode:
                data['mode'] = mode
            try:
                for param in service.findall('param'):
                    option = param.get('name', None)
                    value = param.text
                    name += " --" + option + " '" + value + "'"
                data['command'] = name
                self.services.append(data)
            except:
                msg = 'invalid service format:\n%s' % ET.tostring(serviceinfo_node)
                raise oscerr.APIError(msg)

    def getProjectGlobalServices(self, apiurl, project, package):
        # get all project wide services in one file, we don't store it yet
        u = makeurl(apiurl, ['source', project, package], query='cmd=getprojectservices')
        try:
            f = http_POST(u)
            root = ET.parse(f).getroot()
            self.read(root, True)
        except urllib2.HTTPError, e:
            if e.code != 400:
                raise e

    def addVerifyFile(self, serviceinfo_node, filename):
        import hashlib

        f = open(filename, 'r')
        digest = hashlib.sha256(f.read()).hexdigest()
        f.close()

        r = serviceinfo_node
        s = ET.Element( "service", name="verify_file" )
        ET.SubElement(s, "param", name="file").text = filename
        ET.SubElement(s, "param", name="verifier").text  = "sha256"
        ET.SubElement(s, "param", name="checksum").text = digest

        r.append( s )
        return r


    def addDownloadUrl(self, serviceinfo_node, url_string):
        from urlparse import urlparse
        url = urlparse( url_string )
        protocol = url.scheme
        host = url.netloc
        path = url.path

        r = serviceinfo_node
        s = ET.Element( "service", name="download_url" )
        ET.SubElement(s, "param", name="protocol").text = protocol
        ET.SubElement(s, "param", name="host").text     = host
        ET.SubElement(s, "param", name="path").text     = path

        r.append( s )
        return r

    def addGitUrl(self, serviceinfo_node, url_string):
        r = serviceinfo_node
        s = ET.Element( "service", name="tar_scm" )
        ET.SubElement(s, "param", name="url").text = url_string
        ET.SubElement(s, "param", name="scm").text = "git"
        r.append( s )
        return r

    def addRecompressTar(self, serviceinfo_node):
        r = serviceinfo_node
        s = ET.Element( "service", name="recompress" )
        ET.SubElement(s, "param", name="file").text = "*.tar"
        ET.SubElement(s, "param", name="compression").text = "bz2"
        r.append( s )
        return r

    def execute(self, dir, callmode = None, singleservice = None, verbose = None):
        import tempfile

        # cleanup existing generated files
        for filename in os.listdir(dir):
            if filename.startswith('_service:') or filename.startswith('_service_'):
                os.unlink(os.path.join(dir, filename))

        allservices = self.services or []
        if singleservice and not singleservice in allservices:
            # set array to the manual specified singleservice, if it is not part of _service file
            data = { 'name' : singleservice, 'command' : singleservice, 'mode' : '' }
            allservices = [data]

        # recreate files
        ret = 0
        for service in allservices:
            if singleservice and service['name'] != singleservice:
                continue
            if service['mode'] == "disabled" and callmode != "disabled":
                continue
            if service['mode'] != "disabled" and callmode == "disabled":
                continue
            if service['mode'] != "trylocal" and service['mode'] != "localonly" and callmode == "trylocal":
                continue
            call = service['command']
            temp_dir = tempfile.mkdtemp()
            name = call.split(None, 1)[0]
            if not os.path.exists("/usr/lib/obs/service/"+name):
                raise oscerr.PackageNotInstalled("obs-service-"+name)
            c = "/usr/lib/obs/service/" + call + " --outdir " + temp_dir
            if conf.config['verbose'] > 1 or verbose:
                print "Run source service:", c
            r = subprocess.call(c, shell=True)
            if r != 0:
                print "ERROR: service call failed: " + c
                # FIXME: addDownloadUrlService calls si.execute after 
                #        updating _services.
                print "       (your _services file may be corrupt now)"
                ret = r

            if service['mode'] == "disabled" or service['mode'] == "trylocal" or service['mode'] == "localonly" or callmode == "local" or callmode == "trylocal":
                for filename in os.listdir(temp_dir):
                    shutil.move( os.path.join(temp_dir, filename), os.path.join(dir, filename) )
            else:
                for filename in os.listdir(temp_dir):
                    shutil.move( os.path.join(temp_dir, filename), os.path.join(dir, "_service:"+name+":"+filename) )
            os.rmdir(temp_dir)

        return ret

class Linkinfo:
    """linkinfo metadata (which is part of the xml representing a directory
    """
    def __init__(self):
        """creates an empty linkinfo instance"""
        self.project = None
        self.package = None
        self.xsrcmd5 = None
        self.lsrcmd5 = None
        self.srcmd5 = None
        self.error = None
        self.rev = None
        self.baserev = None

    def read(self, linkinfo_node):
        """read in the linkinfo metadata from the <linkinfo> element passed as
        elementtree node.
        If the passed element is None, the method does nothing.
        """
        if linkinfo_node == None:
            return
        self.project = linkinfo_node.get('project')
        self.package = linkinfo_node.get('package')
        self.xsrcmd5 = linkinfo_node.get('xsrcmd5')
        self.lsrcmd5 = linkinfo_node.get('lsrcmd5')
        self.srcmd5  = linkinfo_node.get('srcmd5')
        self.error   = linkinfo_node.get('error')
        self.rev     = linkinfo_node.get('rev')
        self.baserev = linkinfo_node.get('baserev')

    def islink(self):
        """returns True if the linkinfo is not empty, otherwise False"""
        if self.xsrcmd5 or self.lsrcmd5:
            return True
        return False

    def isexpanded(self):
        """returns True if the package is an expanded link"""
        if self.lsrcmd5 and not self.xsrcmd5:
            return True
        return False

    def haserror(self):
        """returns True if the link is in error state (could not be applied)"""
        if self.error:
            return True
        return False

    def __str__(self):
        """return an informatory string representation"""
        if self.islink() and not self.isexpanded():
            return 'project %s, package %s, xsrcmd5 %s, rev %s' \
                    % (self.project, self.package, self.xsrcmd5, self.rev)
        elif self.islink() and self.isexpanded():
            if self.haserror():
                return 'broken link to project %s, package %s, srcmd5 %s, lsrcmd5 %s: %s' \
                        % (self.project, self.package, self.srcmd5, self.lsrcmd5, self.error)
            else:
                return 'expanded link to project %s, package %s, srcmd5 %s, lsrcmd5 %s' \
                        % (self.project, self.package, self.srcmd5, self.lsrcmd5)
        else:
            return 'None'


# http://effbot.org/zone/element-lib.htm#prettyprint
def xmlindent(elem, level=0):
    i = "\n" + level*"  "
    if len(elem):
        if not elem.text or not elem.text.strip():
            elem.text = i + "  "
        for e in elem:
            xmlindent(e, level+1)
            if not e.tail or not e.tail.strip():
                e.tail = i + "  "
        if not e.tail or not e.tail.strip():
            e.tail = i
    else:
        if level and (not elem.tail or not elem.tail.strip()):
            elem.tail = i

class Project:
    """represent a project directory, holding packages"""
    REQ_STOREFILES = ('_project', '_apiurl')
    if conf.config['do_package_tracking']:
        REQ_STOREFILES += ('_packages',)
    def __init__(self, dir, getPackageList=True, progress_obj=None, wc_check=True):
        import fnmatch
        self.dir = dir
        self.absdir = os.path.abspath(dir)
        self.progress_obj = progress_obj

        self.name = store_read_project(self.dir)
        self.apiurl = store_read_apiurl(self.dir, defaulturl=not wc_check)

        dirty_files = []
        if wc_check:
            dirty_files = self.wc_check()
        if dirty_files:
            msg = 'Your working copy \'%s\' is in an inconsistent state.\n' \
                'Please run \'osc repairwc %s\' and check the state\n' \
                'of the working copy afterwards (via \'osc status %s\')' % (self.dir, self.dir, self.dir)
            raise oscerr.WorkingCopyInconsistent(self.name, None, dirty_files, msg)

        if getPackageList:
            self.pacs_available = meta_get_packagelist(self.apiurl, self.name)
        else:
            self.pacs_available = []

        if conf.config['do_package_tracking']:
            self.pac_root = self.read_packages().getroot()
            self.pacs_have = [ pac.get('name') for pac in self.pac_root.findall('package') ]
            self.pacs_excluded = [ i for i in os.listdir(self.dir)
                                   for j in conf.config['exclude_glob']
                                   if fnmatch.fnmatch(i, j) ]
            self.pacs_unvers = [ i for i in os.listdir(self.dir) if i not in self.pacs_have and i not in self.pacs_excluded ]
            # store all broken packages (e.g. packages which where removed by a non-osc cmd)
            # in the self.pacs_broken list
            self.pacs_broken = []
            for p in self.pacs_have:
                if not os.path.isdir(os.path.join(self.absdir, p)):
                    # all states will be replaced with the '!'-state
                    # (except it is already marked as deleted ('D'-state))
                    self.pacs_broken.append(p)
        else:
            self.pacs_have = [ i for i in os.listdir(self.dir) if i in self.pacs_available ]

        self.pacs_missing = [ i for i in self.pacs_available if i not in self.pacs_have ]

    def wc_check(self):
        global store
        dirty_files = []
        for fname in Project.REQ_STOREFILES:
            if not os.path.exists(os.path.join(self.absdir, store, fname)):
                dirty_files.append(fname)
        return dirty_files

    def wc_repair(self, apiurl=None):
        global store
        if not os.path.exists(os.path.join(self.dir, store, '_apiurl')) or apiurl:
            if apiurl is None:
                msg = 'cannot repair wc: the \'_apiurl\' file is missing but ' \
                    'no \'apiurl\' was passed to wc_repair'
                # hmm should we raise oscerr.WrongArgs?
                raise oscerr.WorkingCopyInconsistent(self.prjname, self.name, [], msg)
            # sanity check
            conf.parse_apisrv_url(None, apiurl)
            store_write_apiurl(self.dir, apiurl)
            self.apiurl = store_read_apiurl(self.dir, defaulturl=False)

    def checkout_missing_pacs(self, expand_link=False):
        for pac in self.pacs_missing:

            if conf.config['do_package_tracking'] and pac in self.pacs_unvers:
                # pac is not under version control but a local file/dir exists
                msg = 'can\'t add package \'%s\': Object already exists' % pac
                raise oscerr.PackageExists(self.name, pac, msg)
            else:
                print 'checking out new package %s' % pac
                checkout_package(self.apiurl, self.name, pac, \
                                 pathname=getTransActPath(os.path.join(self.dir, pac)), \
                                 prj_obj=self, prj_dir=self.dir, expand_link=expand_link, progress_obj=self.progress_obj)

    def status(self, pac):
        exists = os.path.exists(os.path.join(self.absdir, pac))
        st = self.get_state(pac)
        if st is None and exists:
            return '?'
        elif st is None:
            raise oscerr.OscIOError(None, 'osc: \'%s\' is not under version control' % pac)
        elif st in ('A', ' ') and not exists:
            return '!'
        elif st == 'D' and not exists:
            return 'D'
        else:
            return st

    def get_status(self, *exclude_states):
        res = []
        for pac in self.pacs_have:
            st = self.status(pac)
            if not st in exclude_states:
                res.append((st, pac))
        if not '?' in exclude_states:
            res.extend([('?', pac) for pac in self.pacs_unvers])
        return res

    def get_pacobj(self, pac, *pac_args, **pac_kwargs):
        try:
            st = self.status(pac)
            if st in ('?', '!') or st == 'D' and not os.path.exists(os.path.join(self.dir, pac)):
                return None
            return Package(os.path.join(self.dir, pac), *pac_args, **pac_kwargs)
        except oscerr.OscIOError:
            return None

    def set_state(self, pac, state):
        node = self.get_package_node(pac)
        if node == None:
            self.new_package_entry(pac, state)
        else:
            node.set('state', state)

    def get_package_node(self, pac):
        for node in self.pac_root.findall('package'):
            if pac == node.get('name'):
                return node
        return None

    def del_package_node(self, pac):
        for node in self.pac_root.findall('package'):
            if pac == node.get('name'):
                self.pac_root.remove(node)

    def get_state(self, pac):
        node = self.get_package_node(pac)
        if node != None:
            return node.get('state')
        else:
            return None

    def new_package_entry(self, name, state):
        ET.SubElement(self.pac_root, 'package', name=name, state=state)

    def read_packages(self):
        global store

        packages_file = os.path.join(self.absdir, store, '_packages')
        if os.path.isfile(packages_file) and os.path.getsize(packages_file):
            return ET.parse(packages_file)
        else:
            # scan project for existing packages and migrate them
            cur_pacs = []
            for data in os.listdir(self.dir):
                pac_dir = os.path.join(self.absdir, data)
                # we cannot use self.pacs_available because we cannot guarantee that the package list
                # was fetched from the server
                if data in meta_get_packagelist(self.apiurl, self.name) and is_package_dir(pac_dir) \
                   and Package(pac_dir).name == data:
                    cur_pacs.append(ET.Element('package', name=data, state=' '))
            store_write_initial_packages(self.absdir, self.name, cur_pacs)
            return ET.parse(os.path.join(self.absdir, store, '_packages'))

    def write_packages(self):
        xmlindent(self.pac_root)
        store_write_string(self.absdir, '_packages', ET.tostring(self.pac_root))

    def addPackage(self, pac):
        import fnmatch
        for i in conf.config['exclude_glob']:
            if fnmatch.fnmatch(pac, i):
                msg = 'invalid package name: \'%s\' (see \'exclude_glob\' config option)' % pac
                raise oscerr.OscIOError(None, msg)
        state = self.get_state(pac)
        if state == None or state == 'D':
            self.new_package_entry(pac, 'A')
            self.write_packages()
            # sometimes the new pac doesn't exist in the list because
            # it would take too much time to update all data structs regularly
            if pac in self.pacs_unvers:
                self.pacs_unvers.remove(pac)
        else:
            raise oscerr.PackageExists(self.name, pac, 'package \'%s\' is already under version control' % pac)

    def delPackage(self, pac, force = False):
        state = self.get_state(pac.name)
        can_delete = True
        if state == ' ' or state == 'D':
            del_files = []
            for filename in pac.filenamelist + pac.filenamelist_unvers:
                filestate = pac.status(filename)
                if filestate == 'M' or filestate == 'C' or \
                   filestate == 'A' or filestate == '?':
                    can_delete = False
                else:
                    del_files.append(filename)
            if can_delete or force:
                for filename in del_files:
                    pac.delete_localfile(filename)
                    if pac.status(filename) != '?':
                        # this is not really necessary
                        pac.put_on_deletelist(filename)
                        print statfrmt('D', getTransActPath(os.path.join(pac.dir, filename)))
                print statfrmt('D', getTransActPath(os.path.join(pac.dir, os.pardir, pac.name)))
                pac.write_deletelist()
                self.set_state(pac.name, 'D')
                self.write_packages()
            else:
                print 'package \'%s\' has local modifications (see osc st for details)' % pac.name
        elif state == 'A':
            if force:
                delete_dir(pac.absdir)
                self.del_package_node(pac.name)
                self.write_packages()
                print statfrmt('D', pac.name)
            else:
                print 'package \'%s\' has local modifications (see osc st for details)' % pac.name
        elif state == None:
            print 'package is not under version control'
        else:
            print 'unsupported state'

    def update(self, pacs = (), expand_link=False, unexpand_link=False, service_files=False):
        if len(pacs):
            for pac in pacs:
                Package(os.path.join(self.dir, pac), progress_obj=self.progress_obj).update()
        else:
            # we need to make sure that the _packages file will be written (even if an exception
            # occurs)
            try:
                # update complete project
                # packages which no longer exists upstream
                upstream_del = [ pac for pac in self.pacs_have if not pac in self.pacs_available and self.get_state(pac) != 'A']

                for pac in upstream_del:
                    p = Package(os.path.join(self.dir, pac))
                    self.delPackage(p, force = True)
                    delete_storedir(p.storedir)
                    try:
                        os.rmdir(pac)
                    except:
                        pass
                    self.pac_root.remove(self.get_package_node(p.name))
                    self.pacs_have.remove(pac)

                for pac in self.pacs_have:
                    state = self.get_state(pac)
                    if pac in self.pacs_broken:
                        if self.get_state(pac) != 'A':
                            checkout_package(self.apiurl, self.name, pac,
                                             pathname=getTransActPath(os.path.join(self.dir, pac)), prj_obj=self, \
                                             prj_dir=self.dir, expand_link=not unexpand_link, progress_obj=self.progress_obj)
                    elif state == ' ':
                        # do a simple update
                        p = Package(os.path.join(self.dir, pac), progress_obj=self.progress_obj)
                        rev = None
                        if expand_link and p.islink() and not p.isexpanded():
                            if p.haslinkerror():
                                try:
                                    rev = show_upstream_xsrcmd5(p.apiurl, p.prjname, p.name, revision=p.rev)
                                except:
                                    rev = show_upstream_xsrcmd5(p.apiurl, p.prjname, p.name, revision=p.rev, linkrev="base")
                                    p.mark_frozen()
                            else:
                                rev = p.linkinfo.xsrcmd5
                            print 'Expanding to rev', rev
                        elif unexpand_link and p.islink() and p.isexpanded():
                            rev = p.linkinfo.lsrcmd5
                            print 'Unexpanding to rev', rev
                        elif p.islink() and p.isexpanded():
                            rev = p.latest_rev()
                        print 'Updating %s' % p.name
                        p.update(rev, service_files)
                        if unexpand_link:
                            p.unmark_frozen()
                    elif state == 'D':
                        # TODO: Package::update has to fixed to behave like svn does
                        if pac in self.pacs_broken:
                            checkout_package(self.apiurl, self.name, pac,
                                             pathname=getTransActPath(os.path.join(self.dir, pac)), prj_obj=self, \
                                             prj_dir=self.dir, expand_link=expand_link, progress_obj=self.progress_obj)
                        else:
                            Package(os.path.join(self.dir, pac), progress_obj=self.progress_obj).update()
                    elif state == 'A' and pac in self.pacs_available:
                        # file/dir called pac already exists and is under version control
                        msg = 'can\'t add package \'%s\': Object already exists' % pac
                        raise oscerr.PackageExists(self.name, pac, msg)
                    elif state == 'A':
                        # do nothing
                        pass
                    else:
                        print 'unexpected state.. package \'%s\'' % pac

                self.checkout_missing_pacs(expand_link=not unexpand_link)
            finally:
                self.write_packages()

    # TO BE OBSOLETED WITH SOURCE SERVICE VALIDATORS
    def validate_pacs(self, validators, verbose_validation=False, *pacs):
        if len(pacs) == 0:
            for pac in self.pacs_broken:
                if self.get_state(pac) != 'D':
                    msg = 'validation failed: package \'%s\' is missing' % pac
                    raise oscerr.PackageMissing(self.name, pac, msg)
            pacs = self.pacs_have
        for pac in pacs:
            if pac in self.pacs_broken and self.get_state(pac) != 'D':
                msg = 'validation failed: package \'%s\' is missing' % pac
                raise oscerr.PackageMissing(self.name, pac, msg)
            if os_path_samefile(os.path.join(self.dir, pac), os.getcwd()):
                p = Package('.')
            else:
                p = Package(os.path.join(self.dir, pac))
            p.validate(validators, verbose_validation)


    def commit(self, pacs = (), msg = '', files = {}, validators_dir = None, verbose = False, skip_local_service_run = False):
        if len(pacs):
            try:
                for pac in pacs:
                    todo = []
                    if files.has_key(pac):
                        todo = files[pac]
                    state = self.get_state(pac)
                    if state == 'A':
                        self.commitNewPackage(pac, msg, todo, validators_dir=validators_dir, verbose=verbose, skip_local_service_run=skip_local_service_run)
                    elif state == 'D':
                        self.commitDelPackage(pac)
                    elif state == ' ':
                        # display the correct dir when sending the changes
                        if os_path_samefile(os.path.join(self.dir, pac), os.getcwd()):
                            p = Package('.')
                        else:
                            p = Package(os.path.join(self.dir, pac))
                        p.todo = todo
                        p.commit(msg, validators_dir=validators_dir, verbose=verbose, skip_local_service_run=skip_local_service_run)
                    elif pac in self.pacs_unvers and not is_package_dir(os.path.join(self.dir, pac)):
                        print 'osc: \'%s\' is not under version control' % pac
                    elif pac in self.pacs_broken:
                        print 'osc: \'%s\' package not found' % pac
                    elif state == None:
                        self.commitExtPackage(pac, msg, todo, validators_dir=validators_dir, verbose=verbose)
            finally:
                self.write_packages()
        else:
            # if we have packages marked as '!' we cannot commit
            for pac in self.pacs_broken:
                if self.get_state(pac) != 'D':
                    msg = 'commit failed: package \'%s\' is missing' % pac
                    raise oscerr.PackageMissing(self.name, pac, msg)
            try:
                for pac in self.pacs_have:
                    state = self.get_state(pac)
                    if state == ' ':
                        # do a simple commit
                        Package(os.path.join(self.dir, pac)).commit(msg, validators_dir=validators_dir, verbose=verbose, skip_local_service_run=skip_local_service_run)
                    elif state == 'D':
                        self.commitDelPackage(pac)
                    elif state == 'A':
                        self.commitNewPackage(pac, msg, validators_dir=validators_dir, verbose=verbose, skip_local_service_run=skip_local_service_run)
            finally:
                self.write_packages()

    def commitNewPackage(self, pac, msg = '', files = [], validators_dir = None, verbose = False, skip_local_service_run = False):
        """creates and commits a new package if it does not exist on the server"""
        if pac in self.pacs_available:
            print 'package \'%s\' already exists' % pac
        else:
            user = conf.get_apiurl_usr(self.apiurl)
            edit_meta(metatype='pkg',
                      path_args=(quote_plus(self.name), quote_plus(pac)),
                      template_args=({
                              'name': pac,
                              'user': user}),
                      apiurl=self.apiurl)
            # display the correct dir when sending the changes
            olddir = os.getcwd()
            if os_path_samefile(os.path.join(self.dir, pac), os.curdir):
                os.chdir(os.pardir)
                p = Package(pac)
            else:
                p = Package(os.path.join(self.dir, pac))
            p.todo = files
            print statfrmt('Sending', os.path.normpath(p.dir))
            p.commit(msg=msg, validators_dir=validators_dir, verbose=verbose, skip_local_service_run=skip_local_service_run)
            self.set_state(pac, ' ')
            os.chdir(olddir)

    def commitDelPackage(self, pac):
        """deletes a package on the server and in the working copy"""
        try:
            # display the correct dir when sending the changes
            if os_path_samefile(os.path.join(self.dir, pac), os.curdir):
                pac_dir = pac
            else:
                pac_dir = os.path.join(self.dir, pac)
            p = Package(os.path.join(self.dir, pac))
            #print statfrmt('Deleting', os.path.normpath(os.path.join(p.dir, os.pardir, pac)))
            delete_storedir(p.storedir)
            try:
                os.rmdir(p.dir)
            except:
                pass
        except OSError:
            pac_dir = os.path.join(self.dir, pac)
        #print statfrmt('Deleting', getTransActPath(os.path.join(self.dir, pac)))
        print statfrmt('Deleting', getTransActPath(pac_dir))
        delete_package(self.apiurl, self.name, pac)
        self.del_package_node(pac)

    def commitExtPackage(self, pac, msg, files = [], validators_dir=None, verbose=False):
        """commits a package from an external project"""
        if os_path_samefile(os.path.join(self.dir, pac), os.getcwd()):
            pac_path = '.'
        else:
            pac_path = os.path.join(self.dir, pac)

        project = store_read_project(pac_path)
        package = store_read_package(pac_path)
        apiurl = store_read_apiurl(pac_path, defaulturl=False)
        if not meta_exists(metatype='pkg',
                           path_args=(quote_plus(project), quote_plus(package)),
                           template_args=None, create_new=False, apiurl=apiurl):
            user = conf.get_apiurl_usr(self.apiurl)
            edit_meta(metatype='pkg',
                      path_args=(quote_plus(project), quote_plus(package)),
                      template_args=({'name': pac, 'user': user}), apiurl=apiurl)
        p = Package(pac_path)
        p.todo = files
        p.commit(msg=msg, validators_dir=validators_dir, verbose=verbose)

    def __str__(self):
        r = []
        r.append('*****************************************************')
        r.append('Project %s (dir=%s, absdir=%s)' % (self.name, self.dir, self.absdir))
        r.append('have pacs:\n%s' % ', '.join(self.pacs_have))
        r.append('missing pacs:\n%s' % ', '.join(self.pacs_missing))
        r.append('*****************************************************')
        return '\n'.join(r)

    @staticmethod
    def init_project(apiurl, dir, project, package_tracking=True, getPackageList=True, progress_obj=None, wc_check=True):
        global store

        if not os.path.exists(dir):
            # use makedirs (checkout_no_colon config option might be enabled)
            os.makedirs(dir)
        elif not os.path.isdir(dir):
            raise oscerr.OscIOError(None, 'error: \'%s\' is no directory' % dir)
        if os.path.exists(os.path.join(dir, store)):
            raise oscerr.OscIOError(None, 'error: \'%s\' is already an initialized osc working copy' % dir)
        else:
            os.mkdir(os.path.join(dir, store))

        store_write_project(dir, project)
        store_write_apiurl(dir, apiurl)
        if package_tracking:
            store_write_initial_packages(dir, project, [])
        return Project(dir, getPackageList, progress_obj, wc_check)


class Package:
    """represent a package (its directory) and read/keep/write its metadata"""

    # should _meta be a required file?
    REQ_STOREFILES = ('_project', '_package', '_apiurl', '_files', '_osclib_version')
    OPT_STOREFILES = ('_to_be_added', '_to_be_deleted', '_in_conflict', '_in_update',
        '_in_commit', '_meta', '_meta_mode', '_frozenlink', '_pulled', '_linkrepair',
        '_size_limit', '_commit_msg')

    def __init__(self, workingdir, progress_obj=None, size_limit=None, wc_check=True):
        global store

        self.dir = workingdir
        self.absdir = os.path.abspath(self.dir)
        self.storedir = os.path.join(self.absdir, store)
        self.progress_obj = progress_obj
        self.size_limit = size_limit
        if size_limit and size_limit == 0:
            self.size_limit = None

        check_store_version(self.dir)

        self.prjname = store_read_project(self.dir)
        self.name = store_read_package(self.dir)
        self.apiurl = store_read_apiurl(self.dir, defaulturl=not wc_check)

        self.update_datastructs()
        dirty_files = []
        if wc_check:
            dirty_files = self.wc_check()
        if dirty_files:
            msg = 'Your working copy \'%s\' is in an inconsistent state.\n' \
                'Please run \'osc repairwc %s\' (Note this might _remove_\n' \
                'files from the .osc/ dir). Please check the state\n' \
                'of the working copy afterwards (via \'osc status %s\')' % (self.dir, self.dir, self.dir)
            raise oscerr.WorkingCopyInconsistent(self.prjname, self.name, dirty_files, msg)

        self.todo = []

    def wc_check(self):
        dirty_files = []
        for fname in self.filenamelist:
            if not os.path.exists(os.path.join(self.storedir, fname)) and not fname in self.skipped:
                dirty_files.append(fname)
        for fname in Package.REQ_STOREFILES:
            if not os.path.isfile(os.path.join(self.storedir, fname)):
                dirty_files.append(fname)
        for fname in os.listdir(self.storedir):
            if fname in Package.REQ_STOREFILES or fname in Package.OPT_STOREFILES or \
                fname.startswith('_build'):
                continue
            elif fname in self.filenamelist and fname in self.skipped:
                dirty_files.append(fname)
            elif not fname in self.filenamelist:
                dirty_files.append(fname)
        for fname in self.to_be_deleted[:]:
            if not fname in self.filenamelist:
                dirty_files.append(fname)
        for fname in self.in_conflict[:]:
            if not fname in self.filenamelist:
                dirty_files.append(fname)
        return dirty_files

    def wc_repair(self, apiurl=None):
        if not os.path.exists(os.path.join(self.storedir, '_apiurl')) or apiurl:
            if apiurl is None:
                msg = 'cannot repair wc: the \'_apiurl\' file is missing but ' \
                    'no \'apiurl\' was passed to wc_repair'
                # hmm should we raise oscerr.WrongArgs?
                raise oscerr.WorkingCopyInconsistent(self.prjname, self.name, [], msg)
            # sanity check
            conf.parse_apisrv_url(None, apiurl)
            store_write_apiurl(self.dir, apiurl)
            self.apiurl = store_read_apiurl(self.dir, defaulturl=False)
        # all files which are present in the filelist have to exist in the storedir
        for f in self.filelist:
            # XXX: should we also check the md5?
            if not os.path.exists(os.path.join(self.storedir, f.name)) and not f.name in self.skipped:
                # if get_source_file fails we're screwed up...
                get_source_file(self.apiurl, self.prjname, self.name, f.name,
                    targetfilename=os.path.join(self.storedir, f.name), revision=self.rev,
                    mtime=f.mtime)
        for fname in os.listdir(self.storedir):
            if fname in Package.REQ_STOREFILES or fname in Package.OPT_STOREFILES or \
                fname.startswith('_build'):
                continue
            elif not fname in self.filenamelist or fname in self.skipped:
                # this file does not belong to the storedir so remove it
                os.unlink(os.path.join(self.storedir, fname))
        for fname in self.to_be_deleted[:]:
            if not fname in self.filenamelist:
                self.to_be_deleted.remove(fname)
                self.write_deletelist()
        for fname in self.in_conflict[:]:
            if not fname in self.filenamelist:
                self.in_conflict.remove(fname)
                self.write_conflictlist()

    def info(self):
        source_url = makeurl(self.apiurl, ['source', self.prjname, self.name])
        r = info_templ % (self.prjname, self.name, self.absdir, self.apiurl, source_url, self.srcmd5, self.rev, self.linkinfo)
        return r

    def addfile(self, n):
        if not os.path.exists(os.path.join(self.absdir, n)):
            raise oscerr.OscIOError(None, 'error: file \'%s\' does not exist' % n)
        if n in self.to_be_deleted:
            self.to_be_deleted.remove(n)
#            self.delete_storefile(n)
            self.write_deletelist()
        elif n in self.filenamelist or n in self.to_be_added:
            raise oscerr.PackageFileConflict(self.prjname, self.name, n, 'osc: warning: \'%s\' is already under version control' % n)
#        shutil.copyfile(os.path.join(self.dir, n), os.path.join(self.storedir, n))
        if self.dir != '.':
            pathname = os.path.join(self.dir, n)
        else:
            pathname = n
        self.to_be_added.append(n)
        self.write_addlist()
        print statfrmt('A', pathname)

    def delete_file(self, n, force=False):
        """deletes a file if possible and marks the file as deleted"""
        state = '?'
        try:
            state = self.status(n)
        except IOError, ioe:
            if not force:
                raise ioe
        if state in ['?', 'A', 'M', 'R', 'C'] and not force:
            return (False, state)
        # special handling for skipped files: if file exists, simply delete it
        if state == 'S':
            exists = os.path.exists(os.path.join(self.dir, n))
            self.delete_localfile(n)
            return (exists, 'S')

        self.delete_localfile(n)
        was_added = n in self.to_be_added
        if state in ('A', 'R') or state == '!' and was_added:
            self.to_be_added.remove(n)
            self.write_addlist()
        elif state == 'C':
            # don't remove "merge files" (*.r, *.mine...)
            # that's why we don't use clear_from_conflictlist
            self.in_conflict.remove(n)
            self.write_conflictlist()
        if not state in ('A', '?') and not (state == '!' and was_added):
            self.put_on_deletelist(n)
            self.write_deletelist()
        return (True, state)

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

    def put_on_addlist(self, n):
        if n not in self.to_be_added:
            self.to_be_added.append(n)

    def clear_from_conflictlist(self, n):
        """delete an entry from the file, and remove the file if it would be empty"""
        if n in self.in_conflict:

            filename = os.path.join(self.dir, n)
            storefilename = os.path.join(self.storedir, n)
            myfilename = os.path.join(self.dir, n + '.mine')
            if self.islinkrepair() or self.ispulled():
                upfilename = os.path.join(self.dir, n + '.new')
            else:
                upfilename = os.path.join(self.dir, n + '.r' + self.rev)

            try:
                os.unlink(myfilename)
                # the working copy may be updated, so the .r* ending may be obsolete...
                # then we don't care
                os.unlink(upfilename)
                if self.islinkrepair() or self.ispulled():
                    os.unlink(os.path.join(self.dir, n + '.old'))
            except:
                pass

            self.in_conflict.remove(n)

            self.write_conflictlist()

    # XXX: this isn't used at all
    def write_meta_mode(self):
        # XXX: the "elif" is somehow a contradiction (with current and the old implementation
        #      it's not possible to "leave" the metamode again) (except if you modify pac.meta
        #      which is really ugly:) )
        if self.meta:
            store_write_string(self.absdir, '_meta_mode', '')
        elif self.ismetamode():
            os.unlink(os.path.join(self.storedir, '_meta_mode'))

    def write_sizelimit(self):
        if self.size_limit and self.size_limit <= 0:
            try:
                os.unlink(os.path.join(self.storedir, '_size_limit'))
            except:
                pass
        else:
            store_write_string(self.absdir, '_size_limit', str(self.size_limit) + '\n')

    def write_addlist(self):
        self.__write_storelist('_to_be_added', self.to_be_added)

    def write_deletelist(self):
        self.__write_storelist('_to_be_deleted', self.to_be_deleted)

    def delete_source_file(self, n):
        """delete local a source file"""
        self.delete_localfile(n)
        self.delete_storefile(n)

    def delete_remote_source_file(self, n):
        """delete a remote source file (e.g. from the server)"""
        query = 'rev=upload'
        u = makeurl(self.apiurl, ['source', self.prjname, self.name, pathname2url(n)], query=query)
        http_DELETE(u)

    def put_source_file(self, n, copy_only=False):
        cdir = os.path.join(self.storedir, '_in_commit')
        try:
            if not os.path.isdir(cdir):
                os.mkdir(cdir)
            query = 'rev=repository'
            tmpfile = os.path.join(cdir, n)
            shutil.copyfile(os.path.join(self.dir, n), tmpfile)
            # escaping '+' in the URL path (note: not in the URL query string) is
            # only a workaround for ruby on rails, which swallows it otherwise
            if not copy_only:
                u = makeurl(self.apiurl, ['source', self.prjname, self.name, pathname2url(n)], query=query)
                http_PUT(u, file = os.path.join(self.dir, n))
            os.rename(tmpfile, os.path.join(self.storedir, n))
        finally:
            if os.path.isdir(cdir):
                shutil.rmtree(cdir)
        if n in self.to_be_added:
            self.to_be_added.remove(n)

    def __generate_commitlist(self, todo_send):
        root = ET.Element('directory')
        keys = todo_send.keys()
        keys.sort()
        for i in keys:
            ET.SubElement(root, 'entry', name=i, md5=todo_send[i])
        return root

    def __send_commitlog(self, msg, local_filelist):
        """send the commitlog and the local filelist to the server"""
        query = {'cmd'    : 'commitfilelist',
                 'user'   : conf.get_apiurl_usr(self.apiurl),
                 'comment': msg}
        if self.islink() and self.isexpanded():
            query['keeplink'] = '1'
            if conf.config['linkcontrol'] or self.isfrozen():
                query['linkrev'] = self.linkinfo.srcmd5
            if self.ispulled():
                query['repairlink'] = '1'
                query['linkrev'] = self.get_pulled_srcmd5()
        if self.islinkrepair():
            query['repairlink'] = '1'
        u = makeurl(self.apiurl, ['source', self.prjname, self.name], query=query)
        f = http_POST(u, data=ET.tostring(local_filelist))
        root = ET.parse(f).getroot()
        return root

    def __get_todo_send(self, server_filelist):
        """parse todo from a previous __send_commitlog call"""
        error = server_filelist.get('error')
        if error is None:
            return []
        elif error != 'missing':
            raise oscerr.PackageInternalError(self.prjname, self.name,
                '__get_todo_send: unexpected \'error\' attr: \'%s\'' % error)
        todo = []
        for n in server_filelist.findall('entry'):
            name = n.get('name')
            if name is None:
                raise oscerr.APIError('missing \'name\' attribute:\n%s\n' % ET.tostring(server_filelist))
            todo.append(n.get('name'))
        return todo

    def validate(self, validators_dir, verbose_validation=False):
        import subprocess
        import stat
        if validators_dir is None or self.name.startswith('_'):
            return
        for validator in sorted(os.listdir(validators_dir)):
            if validator.startswith('.'):
                continue
            fn = os.path.join(validators_dir, validator)
            mode = os.stat(fn).st_mode
            if stat.S_ISREG(mode):
                if verbose_validation:
                    print 'osc runs source validator: %s' % fn
                    p = subprocess.Popen([fn, '--verbose'], close_fds=True)
                else:
                    p = subprocess.Popen([fn], close_fds=True)
                if p.wait() != 0:
                    raise oscerr.ExtRuntimeError('ERROR: source_validator failed:\n%s' % p.stdout, validator)

    def commit(self, msg='', validators_dir=None, verbose=False, skip_local_service_run=False):
        # commit only if the upstream revision is the same as the working copy's
        upstream_rev = self.latest_rev()
        if self.rev != upstream_rev:
            raise oscerr.WorkingCopyOutdated((self.absdir, self.rev, upstream_rev))

        if not skip_local_service_run:
            r = self.run_source_services(mode="trylocal", verbose=verbose)
            if r is not 0:
                print "osc: source service run failed", r
                raise oscerr.ServiceRuntimeError(r)

        if not validators_dir is None:
            self.validate(validators_dir, verbose)

        if not self.todo:
            self.todo = [i for i in self.to_be_added if not i in self.filenamelist] + self.filenamelist

        pathn = getTransActPath(self.dir)

        todo_send = {}
        todo_delete = []
        real_send = []
        for filename in self.filenamelist + [i for i in self.to_be_added if not i in self.filenamelist]:
            if filename.startswith('_service:') or filename.startswith('_service_'):
                continue
            st = self.status(filename)
            if st == 'C':
                print 'Please resolve all conflicts before committing using "osc resolved FILE"!'
                return 1
            elif filename in self.todo:
                if st in ('A', 'R', 'M'):
                    todo_send[filename] = dgst(os.path.join(self.absdir, filename))
                    real_send.append(filename)
                    print statfrmt('Sending', os.path.join(pathn, filename))
                elif st in (' ', '!', 'S'):
                    if st == '!' and filename in self.to_be_added:
                        print 'file \'%s\' is marked as \'A\' but does not exist' % filename
                        return 1
                    f = self.findfilebyname(filename)
                    if f is None:
                        raise oscerr.PackageInternalError(self.prjname, self.name,
                            'error: file \'%s\' with state \'%s\' is not known by meta' \
                            % (filename, st))
                    todo_send[filename] = f.md5
                elif st == 'D':
                    todo_delete.append(filename)
                    print statfrmt('Deleting', os.path.join(pathn, filename))
            elif st in ('R', 'M', 'D', ' ', '!', 'S'):
                # ignore missing new file (it's not part of the current commit)
                if st == '!' and filename in self.to_be_added:
                    continue
                f = self.findfilebyname(filename)
                if f is None:
                    raise oscerr.PackageInternalError(self.prjname, self.name,
                        'error: file \'%s\' with state \'%s\' is not known by meta' \
                        % (filename, st))
                todo_send[filename] = f.md5

        if not real_send and not todo_delete and not self.islinkrepair() and not self.ispulled():
            print 'nothing to do for package %s' % self.name
            return 1

        print 'Transmitting file data ',
        filelist = self.__generate_commitlist(todo_send)
        sfilelist = self.__send_commitlog(msg, filelist)
        send = self.__get_todo_send(sfilelist)
        real_send = [i for i in real_send if not i in send]
        # abort after 3 tries
        tries = 3
        while len(send) and tries:
            for filename in send[:]:
                sys.stdout.write('.')
                sys.stdout.flush()
                self.put_source_file(filename)
                send.remove(filename)
            tries -= 1
            sfilelist = self.__send_commitlog(msg, filelist)
            send = self.__get_todo_send(sfilelist)
        if len(send):
            raise oscerr.PackageInternalError(self.prjname, self.name,
                'server does not accept filelist:\n%s\nmissing:\n%s\n' \
                % (ET.tostring(filelist), ET.tostring(sfilelist)))
        # these files already exist on the server
        # just copy them into the storedir
        for filename in real_send:
            self.put_source_file(filename, copy_only=True)

        self.rev = sfilelist.get('rev')
        print
        print 'Committed revision %s.' % self.rev

        if self.ispulled():
            os.unlink(os.path.join(self.storedir, '_pulled'))
        if self.islinkrepair():
            os.unlink(os.path.join(self.storedir, '_linkrepair'))
            self.linkrepair = False
            # XXX: mark package as invalid?
            print 'The source link has been repaired. This directory can now be removed.'

        if self.islink() and self.isexpanded():
            li = Linkinfo()
            li.read(sfilelist.find('linkinfo'))
            if li.xsrcmd5 is None:
                raise oscerr.APIError('linkinfo has no xsrcmd5 attr:\n%s\n' % ET.tostring(sfilelist))
            sfilelist = ET.fromstring(self.get_files_meta(revision=li.xsrcmd5))
        for i in sfilelist.findall('entry'):
            if i.get('name') in self.skipped:
                i.set('skipped', 'true')
        store_write_string(self.absdir, '_files', ET.tostring(sfilelist) + '\n')
        for filename in todo_delete:
            self.to_be_deleted.remove(filename)
            self.delete_storefile(filename)
        self.write_deletelist()
        self.write_addlist()
        self.update_datastructs()

        print_request_list(self.apiurl, self.prjname, self.name)

        if self.findfilebyname("_service"):
            print 'Waiting for server side source service run',
            u = makeurl(self.apiurl, ['source', self.prjname, self.name])
            while 1:
                f = http_GET(u)
                sfilelist = ET.parse(f).getroot()
                s = sfilelist.find('serviceinfo')
                if s != None and s.get('code') == "running":
                   sys.stdout.write('.')
                   sys.stdout.flush()
                else:
                   break
            print ""
            rev=self.latest_rev()
            self.update(rev=rev)
            

    def __write_storelist(self, name, data):
        if len(data) == 0:
            try:
                os.unlink(os.path.join(self.storedir, name))
            except:
                pass
        else:
            store_write_string(self.absdir, name, '%s\n' % '\n'.join(data))

    def write_conflictlist(self):
        self.__write_storelist('_in_conflict', self.in_conflict)

    def updatefile(self, n, revision, mtime=None):
        filename = os.path.join(self.dir, n)
        storefilename = os.path.join(self.storedir, n)
        origfile_tmp = os.path.join(self.storedir, '_in_update', '%s.copy' % n)
        origfile = os.path.join(self.storedir, '_in_update', n)
        if os.path.isfile(filename):
            shutil.copyfile(filename, origfile_tmp)
            os.rename(origfile_tmp, origfile)
        else:
            origfile = None

        get_source_file(self.apiurl, self.prjname, self.name, n, targetfilename=storefilename,
                revision=revision, progress_obj=self.progress_obj, mtime=mtime, meta=self.meta)

        shutil.copyfile(storefilename, filename)
        if not origfile is None:
            os.unlink(origfile)

    def mergefile(self, n, revision, mtime=None):
        filename = os.path.join(self.dir, n)
        storefilename = os.path.join(self.storedir, n)
        myfilename = os.path.join(self.dir, n + '.mine')
        upfilename = os.path.join(self.dir, n + '.r' + self.rev)
        origfile_tmp = os.path.join(self.storedir, '_in_update', '%s.copy' % n)
        origfile = os.path.join(self.storedir, '_in_update', n)
        shutil.copyfile(filename, origfile_tmp)
        os.rename(origfile_tmp, origfile)
        os.rename(filename, myfilename)

        get_source_file(self.apiurl, self.prjname, self.name, n,
                        revision=revision, targetfilename=upfilename,
                        progress_obj=self.progress_obj, mtime=mtime, meta=self.meta)

        if binary_file(myfilename) or binary_file(upfilename):
            # don't try merging
            shutil.copyfile(upfilename, filename)
            shutil.copyfile(upfilename, storefilename)
            os.unlink(origfile)
            self.in_conflict.append(n)
            self.write_conflictlist()
            return 'C'
        else:
            # try merging
            # diff3 OPTIONS... MINE OLDER YOURS
            merge_cmd = 'diff3 -m -E %s %s %s > %s' % (myfilename, storefilename, upfilename, filename)
            # we would rather use the subprocess module, but it is not availablebefore 2.4
            ret = subprocess.call(merge_cmd, shell=True)

            #   "An exit status of 0 means `diff3' was successful, 1 means some
            #   conflicts were found, and 2 means trouble."
            if ret == 0:
                # merge was successful... clean up
                shutil.copyfile(upfilename, storefilename)
                os.unlink(upfilename)
                os.unlink(myfilename)
                os.unlink(origfile)
                return 'G'
            elif ret == 1:
                # unsuccessful merge
                shutil.copyfile(upfilename, storefilename)
                os.unlink(origfile)
                self.in_conflict.append(n)
                self.write_conflictlist()
                return 'C'
            else:
                raise oscerr.ExtRuntimeError('diff3 failed with exit code: %s' % ret, merge_cmd)

    def update_local_filesmeta(self, revision=None):
        """
        Update the local _files file in the store.
        It is replaced with the version pulled from upstream.
        """
        meta = self.get_files_meta(revision=revision)
        store_write_string(self.absdir, '_files', meta + '\n')

    def get_files_meta(self, revision='latest', skip_service=True):
        fm = show_files_meta(self.apiurl, self.prjname, self.name, revision=revision, meta=self.meta)
        # look for "too large" files according to size limit and mark them
        root = ET.fromstring(fm)
        for e in root.findall('entry'):
            size = e.get('size')
            if size and self.size_limit and int(size) > self.size_limit \
                or skip_service and (e.get('name').startswith('_service:') or e.get('name').startswith('_service_')):
                e.set('skipped', 'true')
        return ET.tostring(root)

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

        self.linkinfo = Linkinfo()
        self.linkinfo.read(files_tree_root.find('linkinfo'))

        self.filenamelist = []
        self.filelist = []
        self.skipped = []
        for node in files_tree_root.findall('entry'):
            try:
                f = File(node.get('name'),
                         node.get('md5'),
                         int(node.get('size')),
                         int(node.get('mtime')))
                if node.get('skipped'):
                    self.skipped.append(f.name)
                    f.skipped = True
            except:
                # okay, a very old version of _files, which didn't contain any metadata yet...
                f = File(node.get('name'), '', 0, 0)
            self.filelist.append(f)
            self.filenamelist.append(f.name)

        self.to_be_added = read_tobeadded(self.absdir)
        self.to_be_deleted = read_tobedeleted(self.absdir)
        self.in_conflict = read_inconflict(self.absdir)
        self.linkrepair = os.path.isfile(os.path.join(self.storedir, '_linkrepair'))
        self.size_limit = read_sizelimit(self.dir)
        self.meta = self.ismetamode()

        # gather unversioned files, but ignore some stuff
        self.excluded = []
        for i in os.listdir(self.dir):
            for j in conf.config['exclude_glob']:
                if fnmatch.fnmatch(i, j):
                    self.excluded.append(i)
                    break
        self.filenamelist_unvers = [ i for i in os.listdir(self.dir)
                                     if i not in self.excluded
                                     if i not in self.filenamelist ]

    def islink(self):
        """tells us if the package is a link (has 'linkinfo').
        A package with linkinfo is a package which links to another package.
        Returns True if the package is a link, otherwise False."""
        return self.linkinfo.islink()

    def isexpanded(self):
        """tells us if the package is a link which is expanded.
        Returns True if the package is expanded, otherwise False."""
        return self.linkinfo.isexpanded()

    def islinkrepair(self):
        """tells us if we are repairing a broken source link."""
        return self.linkrepair

    def ispulled(self):
        """tells us if we have pulled a link."""
        return os.path.isfile(os.path.join(self.storedir, '_pulled'))

    def isfrozen(self):
        """tells us if the link is frozen."""
        return os.path.isfile(os.path.join(self.storedir, '_frozenlink'))

    def ismetamode(self):
        """tells us if the package is in meta mode"""
        return os.path.isfile(os.path.join(self.storedir, '_meta_mode'))

    def get_pulled_srcmd5(self):
        pulledrev = None
        for line in open(os.path.join(self.storedir, '_pulled'), 'r'):
            pulledrev = line.strip()
        return pulledrev

    def haslinkerror(self):
        """
        Returns True if the link is broken otherwise False.
        If the package is not a link it returns False.
        """
        return self.linkinfo.haserror()

    def linkerror(self):
        """
        Returns an error message if the link is broken otherwise None.
        If the package is not a link it returns None.
        """
        return self.linkinfo.error

    def update_local_pacmeta(self):
        """
        Update the local _meta file in the store.
        It is replaced with the version pulled from upstream.
        """
        meta = ''.join(show_package_meta(self.apiurl, self.prjname, self.name))
        store_write_string(self.absdir, '_meta', meta + '\n')

    def findfilebyname(self, n):
        for i in self.filelist:
            if i.name == n:
                return i

    def get_status(self, excluded=False, *exclude_states):
        global store
        todo = self.todo
        if not todo:
            todo = self.filenamelist + self.to_be_added + \
                [i for i in self.filenamelist_unvers if not os.path.isdir(os.path.join(self.absdir, i))]
            if excluded:
                todo.extend([i for i in self.excluded if i != store])
            todo = set(todo)
        res = []
        for fname in sorted(todo):
            st = self.status(fname)
            if not st in exclude_states:
                res.append((st, fname))
        return res

    def status(self, n):
        """
        status can be:

         file  storefile  file present  STATUS
        exists  exists      in _files

          x       -            -        'A' and listed in _to_be_added
          x       x            -        'R' and listed in _to_be_added
          x       x            x        ' ' if digest differs: 'M'
                                            and if in conflicts file: 'C'
          x       -            -        '?'
          -       x            x        'D' and listed in _to_be_deleted
          x       x            x        'D' and listed in _to_be_deleted (e.g. if deleted file was modified)
          x       x            x        'C' and listed in _in_conflict
          x       -            x        'S' and listed in self.skipped
          -       -            x        'S' and listed in self.skipped
          -       x            x        '!'
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

        if n in self.to_be_deleted:
            state = 'D'
        elif n in self.in_conflict:
            state = 'C'
        elif n in self.skipped:
            state = 'S'
        elif n in self.to_be_added and exists and exists_in_store:
            state = 'R'
        elif n in self.to_be_added and exists:
            state = 'A'
        elif exists and exists_in_store and known_by_meta:
            if dgst(os.path.join(self.absdir, n)) != self.findfilebyname(n).md5:
                state = 'M'
            else:
                state = ' '
        elif n in self.to_be_added and not exists:
            state = '!'
        elif not exists and exists_in_store and known_by_meta and not n in self.to_be_deleted:
            state = '!'
        elif exists and not exists_in_store and not known_by_meta:
            state = '?'
        elif not exists_in_store and known_by_meta:
            # XXX: this codepath shouldn't be reached (we restore the storefile
            #      in update_datastructs)
            raise oscerr.PackageInternalError(self.prjname, self.name,
                'error: file \'%s\' is known by meta but no storefile exists.\n'
                'This might be caused by an old wc format. Please backup your current\n'
                'wc and checkout the package again. Afterwards copy all files (except the\n'
                '.osc/ dir) into the new package wc.' % n)
        else:
            # this case shouldn't happen (except there was a typo in the filename etc.)
            raise oscerr.OscIOError(None, 'osc: \'%s\' is not under version control' % n)

        return state

    def get_diff(self, revision=None, ignoreUnversioned=False):
        import tempfile
        diff_hdr = 'Index: %s\n'
        diff_hdr += '===================================================================\n'
        kept = []
        added = []
        deleted = []
        def diff_add_delete(fname, add, revision):
            diff = []
            diff.append(diff_hdr % fname)
            tmpfile = None
            origname = fname
            if add:
                diff.append('--- %s\t(revision 0)\n' % fname)
                rev = 'revision 0'
                if revision and not fname in self.to_be_added:
                    rev = 'working copy'
                diff.append('+++ %s\t(%s)\n' % (fname, rev))
                fname = os.path.join(self.absdir, fname)
            else:
                diff.append('--- %s\t(revision %s)\n' % (fname, revision or self.rev))
                diff.append('+++ %s\t(working copy)\n' % fname)
                fname = os.path.join(self.storedir, fname)
               
            try:
                if revision is not None and not add:
                    (fd, tmpfile) = tempfile.mkstemp(prefix='osc_diff')
                    get_source_file(self.apiurl, self.prjname, self.name, origname, tmpfile, revision)
                    fname = tmpfile
                if binary_file(fname):
                    what = 'added'
                    if not add:
                        what = 'deleted'
                    diff = diff[:1]
                    diff.append('Binary file \'%s\' %s.\n' % (origname, what))
                    return diff
                tmpl = '+%s'
                ltmpl = '@@ -0,0 +1,%d @@\n'
                if not add:
                    tmpl = '-%s'
                    ltmpl = '@@ -1,%d +0,0 @@\n'
                lines = [tmpl % i for i in open(fname, 'r').readlines()]
                if len(lines):
                    diff.append(ltmpl % len(lines))
                    if not lines[-1].endswith('\n'):
                        lines.append('\n\\ No newline at end of file\n')
                diff.extend(lines)
            finally:
                if tmpfile is not None:
                    os.close(fd)
                    os.unlink(tmpfile)
            return diff

        if revision is None:
            todo = self.todo or [i for i in self.filenamelist if not i in self.to_be_added]+self.to_be_added
            for fname in todo:
                if fname in self.to_be_added and self.status(fname) == 'A':
                    added.append(fname)
                elif fname in self.to_be_deleted:
                    deleted.append(fname)
                elif fname in self.filenamelist:
                    kept.append(self.findfilebyname(fname))
                elif fname in self.to_be_added and self.status(fname) == '!':
                    raise oscerr.OscIOError(None, 'file \'%s\' is marked as \'A\' but does not exist\n'\
                        '(either add the missing file or revert it)' % fname)
                elif not ignoreUnversioned:
                    raise oscerr.OscIOError(None, 'file \'%s\' is not under version control' % fname)
        else:
            fm = self.get_files_meta(revision=revision)
            root = ET.fromstring(fm)
            rfiles = self.__get_files(root)
            # swap added and deleted
            kept, deleted, added, services = self.__get_rev_changes(rfiles)
            added = [f.name for f in added]
            added.extend([f for f in self.to_be_added if not f in kept])
            deleted = [f.name for f in deleted]
            deleted.extend(self.to_be_deleted)
            for f in added[:]:
                if f in deleted:
                    added.remove(f)
                    deleted.remove(f)
#        print kept, added, deleted
        for f in kept:
            state = self.status(f.name)
            if state in ('S', '?', '!'):
                continue
            elif state == ' ' and revision is None:
                continue
            elif revision and self.findfilebyname(f.name).md5 == f.md5 and state != 'M':
                continue
            yield [diff_hdr % f.name]
            if revision is None:
                yield get_source_file_diff(self.absdir, f.name, self.rev)
            else:
                tmpfile = None
                diff = []
                try:
                    (fd, tmpfile) = tempfile.mkstemp(prefix='osc_diff')
                    get_source_file(self.apiurl, self.prjname, self.name, f.name, tmpfile, revision)
                    diff = get_source_file_diff(self.absdir, f.name, revision,
                        os.path.basename(tmpfile), os.path.dirname(tmpfile), f.name)
                finally:
                    if tmpfile is not None:
                        os.close(fd)
                        os.unlink(tmpfile)
                yield diff

        for f in added:
            yield diff_add_delete(f, True, revision)
        for f in deleted:
            yield diff_add_delete(f, False, revision)

    def merge(self, otherpac):
        self.todo += otherpac.todo

    def __str__(self):
        r = """
name: %s
prjname: %s
workingdir: %s
localfilelist: %s
linkinfo: %s
rev: %s
'todo' files: %s
""" % (self.name,
        self.prjname,
        self.dir,
        '\n               '.join(self.filenamelist),
        self.linkinfo,
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
                for filename in speclist:
                    print filename
                print 'please specify one with --specfile'
                sys.exit(1)
            else:
                print 'no specfile was found - please specify one ' \
                      'with --specfile'
                sys.exit(1)

        data = read_meta_from_spec(specfile, 'Summary', 'Url', '%description')
        self.summary = data.get('Summary', '')
        self.url = data.get('Url', '')
        self.descr = data.get('%description', '')


    def update_package_meta(self, force=False):
        """
        for the updatepacmetafromspec subcommand
            argument force supress the confirm question
        """

        m = ''.join(show_package_meta(self.apiurl, self.prjname, self.name))

        root = ET.fromstring(m)
        root.find('title').text = self.summary
        root.find('description').text = ''.join(self.descr)
        url = root.find('url')
        if url == None:
            url = ET.SubElement(root, 'url')
        url.text = self.url

        u = makeurl(self.apiurl, ['source', self.prjname, self.name, '_meta'])
        mf = metafile(u, ET.tostring(root))

        if not force:
            print '*' * 36, 'old', '*' * 36
            print m
            print '*' * 36, 'new', '*' * 36
            print ET.tostring(root)
            print '*' * 72
            repl = raw_input('Write? (y/N/e) ')
        else:
            repl = 'y'

        if repl == 'y':
            mf.sync()
        elif repl == 'e':
            mf.edit()

        mf.discard()

    def mark_frozen(self):
        store_write_string(self.absdir, '_frozenlink', '')
        print
        print "The link in this package is currently broken. Checking"
        print "out the last working version instead; please use 'osc pull'"
        print "to repair the link."
        print

    def unmark_frozen(self):
        if os.path.exists(os.path.join(self.storedir, '_frozenlink')):
            os.unlink(os.path.join(self.storedir, '_frozenlink'))

    def latest_rev(self, include_service_files=False):
        if self.islinkrepair():
            upstream_rev = show_upstream_xsrcmd5(self.apiurl, self.prjname, self.name, linkrepair=1, meta=self.meta, include_service_files=include_service_files)
        elif self.islink() and self.isexpanded():
            if self.isfrozen() or self.ispulled():
                upstream_rev = show_upstream_xsrcmd5(self.apiurl, self.prjname, self.name, linkrev=self.linkinfo.srcmd5, meta=self.meta, include_service_files=include_service_files)
            else:
                try:
                    upstream_rev = show_upstream_xsrcmd5(self.apiurl, self.prjname, self.name, meta=self.meta, include_service_files=include_service_files)
                except:
                    try:
                        upstream_rev = show_upstream_xsrcmd5(self.apiurl, self.prjname, self.name, linkrev=self.linkinfo.srcmd5, meta=self.meta, include_service_files=include_service_files)
                    except:
                        upstream_rev = show_upstream_xsrcmd5(self.apiurl, self.prjname, self.name, linkrev="base", meta=self.meta, include_service_files=include_service_files)
                    self.mark_frozen()
        else:
            upstream_rev = show_upstream_rev(self.apiurl, self.prjname, self.name, meta=self.meta, include_service_files=include_service_files)
        return upstream_rev

    def __get_files(self, fmeta_root):
        f = []
        if fmeta_root.get('rev') is None and len(fmeta_root.findall('entry')) > 0:
            raise oscerr.APIError('missing rev attribute in _files:\n%s' % ''.join(ET.tostring(fmeta_root)))
        for i in fmeta_root.findall('entry'):
            skipped = i.get('skipped') is not None
            f.append(File(i.get('name'), i.get('md5'),
                     int(i.get('size')), int(i.get('mtime')), skipped))
        return f

    def __get_rev_changes(self, revfiles):
        kept = []
        added = []
        deleted = []
        services = []
        revfilenames = []
        for f in revfiles:
            revfilenames.append(f.name)
            # treat skipped like deleted files
            if f.skipped:
                if f.name.startswith('_service:'):
                    services.append(f)
                else:
                    deleted.append(f)
                continue
            # treat skipped like added files
            # problem: this overwrites existing files during the update
            # (because skipped files aren't in self.filenamelist_unvers)
            if f.name in self.filenamelist and not f.name in self.skipped:
                kept.append(f)
            else:
                added.append(f)
        for f in self.filelist:
            if not f.name in revfilenames:
                deleted.append(f)

        return kept, added, deleted, services

    def update(self, rev = None, service_files = False, size_limit = None):
        import tempfile
        rfiles = []
        # size_limit is only temporary for this update
        old_size_limit = self.size_limit
        if not size_limit is None:
            self.size_limit = int(size_limit)
        if os.path.isfile(os.path.join(self.storedir, '_in_update', '_files')):
            print 'resuming broken update...'
            root = ET.parse(os.path.join(self.storedir, '_in_update', '_files')).getroot()
            rfiles = self.__get_files(root)
            kept, added, deleted, services = self.__get_rev_changes(rfiles)
            # check if we aborted in the middle of a file update
            broken_file = os.listdir(os.path.join(self.storedir, '_in_update'))
            broken_file.remove('_files')
            if len(broken_file) == 1:
                origfile = os.path.join(self.storedir, '_in_update', broken_file[0])
                wcfile = os.path.join(self.absdir, broken_file[0])
                origfile_md5 = dgst(origfile)
                origfile_meta = self.findfilebyname(broken_file[0])
                if origfile.endswith('.copy'):
                    # ok it seems we aborted at some point during the copy process
                    # (copy process == copy wcfile to the _in_update dir). remove file+continue
                    os.unlink(origfile)
                elif self.findfilebyname(broken_file[0]) is None:
                    # should we remove this file from _in_update? if we don't
                    # the user has no chance to continue without removing the file manually
                    raise oscerr.PackageInternalError(self.prjname, self.name,
                        '\'%s\' is not known by meta but exists in \'_in_update\' dir')
                elif os.path.isfile(wcfile) and dgst(wcfile) != origfile_md5:
                    (fd, tmpfile) = tempfile.mkstemp(dir=self.absdir, prefix=broken_file[0]+'.')
                    os.close(fd)
                    os.rename(wcfile, tmpfile)
                    os.rename(origfile, wcfile)
                    print 'warning: it seems you modified \'%s\' after the broken ' \
                          'update. Restored original file and saved modified version ' \
                          'to \'%s\'.' % (wcfile, tmpfile)
                elif not os.path.isfile(wcfile):
                    # this is strange... because it existed before the update. restore it
                    os.rename(origfile, wcfile)
                else:
                    # everything seems to be ok
                    os.unlink(origfile)
            elif len(broken_file) > 1:
                raise oscerr.PackageInternalError(self.prjname, self.name, 'too many files in \'_in_update\' dir')
            tmp = rfiles[:]
            for f in tmp:
                if os.path.exists(os.path.join(self.storedir, f.name)):
                    if dgst(os.path.join(self.storedir, f.name)) == f.md5:
                        if f in kept:
                            kept.remove(f)
                        elif f in added:
                            added.remove(f)
                        # this can't happen
                        elif f in deleted:
                            deleted.remove(f)
            if not service_files:
                services = []
            self.__update(kept, added, deleted, services, ET.tostring(root), root.get('rev'))
            os.unlink(os.path.join(self.storedir, '_in_update', '_files'))
            os.rmdir(os.path.join(self.storedir, '_in_update'))
        # ok everything is ok (hopefully)...
        fm = self.get_files_meta(revision=rev)
        root = ET.fromstring(fm)
        rfiles = self.__get_files(root)
        store_write_string(self.absdir, '_files', fm + '\n', subdir='_in_update')
        kept, added, deleted, services = self.__get_rev_changes(rfiles)
        if not service_files:
            services = []
        self.__update(kept, added, deleted, services, fm, root.get('rev'))
        os.unlink(os.path.join(self.storedir, '_in_update', '_files'))
        if os.path.isdir(os.path.join(self.storedir, '_in_update')):
            os.rmdir(os.path.join(self.storedir, '_in_update'))
        self.size_limit = old_size_limit

    def __update(self, kept, added, deleted, services, fm, rev):
        pathn = getTransActPath(self.dir)
        # check for conflicts with existing files
        for f in added:
            if f.name in self.filenamelist_unvers:
                raise oscerr.PackageFileConflict(self.prjname, self.name, f.name,
                    'failed to add file \'%s\' file/dir with the same name already exists' % f.name)
        # ok, the update can't fail due to existing files
        for f in added:
            self.updatefile(f.name, rev, f.mtime)
            print statfrmt('A', os.path.join(pathn, f.name))
        for f in deleted:
            # if the storefile doesn't exist we're resuming an aborted update:
            # the file was already deleted but we cannot know this
            # OR we're processing a _service: file (simply keep the file)
            if os.path.isfile(os.path.join(self.storedir, f.name)) and self.status(f.name) != 'M':
#            if self.status(f.name) != 'M':
                self.delete_localfile(f.name)
            self.delete_storefile(f.name)
            print statfrmt('D', os.path.join(pathn, f.name))
            if f.name in self.to_be_deleted:
                self.to_be_deleted.remove(f.name)
                self.write_deletelist()

        for f in kept:
            state = self.status(f.name)
#            print f.name, state
            if state == 'M' and self.findfilebyname(f.name).md5 == f.md5:
                # remote file didn't change
                pass
            elif state == 'M':
                # try to merge changes
                merge_status = self.mergefile(f.name, rev, f.mtime)
                print statfrmt(merge_status, os.path.join(pathn, f.name))
            elif state == '!':
                self.updatefile(f.name, rev, f.mtime)
                print 'Restored \'%s\'' % os.path.join(pathn, f.name)
            elif state == 'C':
                get_source_file(self.apiurl, self.prjname, self.name, f.name,
                    targetfilename=os.path.join(self.storedir, f.name), revision=rev,
                    progress_obj=self.progress_obj, mtime=f.mtime, meta=self.meta)
                print 'skipping \'%s\' (this is due to conflicts)' % f.name
            elif state == 'D' and self.findfilebyname(f.name).md5 != f.md5:
                # XXX: in the worst case we might end up with f.name being
                # in _to_be_deleted and in _in_conflict... this needs to be checked
                if os.path.exists(os.path.join(self.absdir, f.name)):
                    merge_status = self.mergefile(f.name, rev, f.mtime)
                    print statfrmt(merge_status, os.path.join(pathn, f.name))
                    if merge_status == 'C':
                        # state changes from delete to conflict
                        self.to_be_deleted.remove(f.name)
                        self.write_deletelist()
                else:
                    # XXX: we cannot recover this case because we've no file
                    # to backup
                    self.updatefile(f.name, rev, f.mtime)
                    print statfrmt('U', os.path.join(pathn, f.name))
            elif state == ' ' and self.findfilebyname(f.name).md5 != f.md5:
                self.updatefile(f.name, rev, f.mtime)
                print statfrmt('U', os.path.join(pathn, f.name))

        # checkout service files
        for f in services:
            get_source_file(self.apiurl, self.prjname, self.name, f.name,
                targetfilename=os.path.join(self.absdir, f.name), revision=rev,
                progress_obj=self.progress_obj, mtime=f.mtime, meta=self.meta)
            print statfrmt('A', os.path.join(pathn, f.name))
        store_write_string(self.absdir, '_files', fm + '\n')
        if not self.meta:
            self.update_local_pacmeta()
        self.update_datastructs()

        print 'At revision %s.' % self.rev

    def run_source_services(self, mode=None, singleservice=None, verbose=None):
        if self.name.startswith("_"):
            return 0
        curdir = os.getcwd()
        os.chdir(self.absdir) # e.g. /usr/lib/obs/service/verify_file fails if not inside the project dir.
        si = Serviceinfo()
        if self.filenamelist.count('_service') or self.filenamelist_unvers.count('_service'):
            service = ET.parse(os.path.join(self.absdir, '_service')).getroot()
            si.read(service)
        si.getProjectGlobalServices(self.apiurl, self.prjname, self.name)
        r = si.execute(self.absdir, mode, singleservice, verbose)
        os.chdir(curdir)
        return r

    def prepare_filelist(self):
        """Prepare a list of files, which will be processed by process_filelist
        method. This allows easy modifications of a file list in commit
        phase.
        """
        if not self.todo:
            self.todo = self.filenamelist + self.filenamelist_unvers
        self.todo.sort()

        ret = ""
        for f in [f for f in self.todo if not os.path.isdir(f)]:
            action = 'leave'
            status = self.status(f)
            if status == 'S':
                continue
            if status == '!':
                action = 'remove'
            ret += "%s %s %s\n" % (action, status, f)

        ret += """
# Edit a filelist for package \'%s\'
# Commands:
# l, leave = leave a file as is
# r, remove = remove a file
# a, add   = add a file
#
# If you remove file from a list, it will be unchanged
# If you remove all, commit will be aborted""" % self.name

        return ret

    def edit_filelist(self):
        """Opens a package list in editor for editing. This allows easy
        modifications of it just by simple text editing
        """

        import tempfile
        (fd, filename) = tempfile.mkstemp(prefix = 'osc-filelist', suffix = '.txt')
        f = os.fdopen(fd, 'w')
        f.write(self.prepare_filelist())
        f.close()
        mtime_orig = os.stat(filename).st_mtime

        while 1:
            run_editor(filename)
            mtime = os.stat(filename).st_mtime
            if mtime_orig < mtime:
                filelist = open(filename).readlines()
                os.unlink(filename)
                break
            else:
                raise oscerr.UserAbort()

        return self.process_filelist(filelist)

    def process_filelist(self, filelist):
        """Process a filelist - it add/remove or leave files. This depends on
        user input. If no file is processed, it raises an ValueError
        """

        loop = False
        for line in [l.strip() for l in filelist if (l[0] != "#" or l.strip() != '')]:

            foo = line.split(' ')
            if len(foo) == 4:
                action, state, name = (foo[0], ' ', foo[3])
            elif len(foo) == 3:
                action, state, name = (foo[0], foo[1], foo[2])
            else:
                break
            action = action.lower()
            loop = True

            if action in ('r', 'remove'):
                if self.status(name) == '?':
                    os.unlink(name)
                    if name in self.todo:
                        self.todo.remove(name)
                else:
                    self.delete_file(name, True)
            elif action in ('a', 'add'):
                if self.status(name) != '?':
                    print "Cannot add file %s with state %s, skipped" % (name, self.status(name))
                else:
                    self.addfile(name)
            elif action in ('l', 'leave'):
                pass
            else:
                raise ValueError("Unknow action `%s'" % action)

        if not loop:
            raise ValueError("Empty filelist")

    def revert(self, filename):
        if not filename in self.filenamelist and not filename in self.to_be_added:
            raise oscerr.OscIOError(None, 'file \'%s\' is not under version control' % filename)
        elif filename in self.skipped:
            raise oscerr.OscIOError(None, 'file \'%s\' is marked as skipped and cannot be reverted' % filename)
        if filename in self.filenamelist and not os.path.exists(os.path.join(self.storedir, filename)):
            raise oscerr.PackageInternalError('file \'%s\' is listed in filenamelist but no storefile exists' % filename)
        state = self.status(filename)
        if not (state == 'A' or state == '!' and filename in self.to_be_added):
            shutil.copyfile(os.path.join(self.storedir, filename), os.path.join(self.absdir, filename))
        if state == 'D':
            self.to_be_deleted.remove(filename)
            self.write_deletelist()
        elif state == 'C':
            self.clear_from_conflictlist(filename)
        elif state in ('A', 'R') or state == '!' and filename in self.to_be_added:
            self.to_be_added.remove(filename)
            self.write_addlist()

    @staticmethod
    def init_package(apiurl, project, package, dir, size_limit=None, meta=False, progress_obj=None):
        global store

        if not os.path.exists(dir):
            os.mkdir(dir)
        elif not os.path.isdir(dir):
            raise oscerr.OscIOError(None, 'error: \'%s\' is no directory' % dir)
        if os.path.exists(os.path.join(dir, store)):
            raise oscerr.OscIOError(None, 'error: \'%s\' is already an initialized osc working copy' % dir)
        else:
            os.mkdir(os.path.join(dir, store))
        store_write_project(dir, project)
        store_write_string(dir, '_package', package + '\n')
        store_write_apiurl(dir, apiurl)
        if meta:
            store_write_string(dir, '_meta_mode', '')
        if size_limit:
            store_write_string(dir, '_size_limit', str(size_limit) + '\n')
        store_write_string(dir, '_files', '<directory />' + '\n')
        store_write_string(dir, '_osclib_version', __store_version__ + '\n')
        return Package(dir, progress_obj=progress_obj, size_limit=size_limit)


class AbstractState:
    """
    Base class which represents state-like objects (<review />, <state />).
    """
    def __init__(self, tag):
        self.__tag = tag

    def get_node_attrs(self):
        """return attributes for the tag/element"""
        raise NotImplementedError()

    def get_node_name(self):
        """return tag/element name"""
        return self.__tag

    def get_comment(self):
        """return data from <comment /> tag"""
        raise NotImplementedError()

    def to_xml(self):
        """serialize object to XML"""
        root = ET.Element(self.get_node_name())
        for attr in self.get_node_attrs():
            val = getattr(self, attr)
            if not val is None:
                root.set(attr, val)
        if self.get_comment():
            ET.SubElement(root, 'comment').text = self.get_comment()
        return root

    def to_str(self):
        """return "pretty" XML data"""
        root = self.to_xml()
        xmlindent(root)
        return ET.tostring(root)


class ReviewState(AbstractState):
    """Represents the review state in a request"""
    def __init__(self, review_node):
        if not review_node.get('state'):
            raise oscerr.APIError('invalid review node (state attr expected): %s' % \
                ET.tostring(review_node))
        AbstractState.__init__(self, review_node.tag)
        self.state = review_node.get('state')
        self.by_user = review_node.get('by_user')
        self.by_group = review_node.get('by_group')
        self.by_project = review_node.get('by_project')
        self.by_package = review_node.get('by_package')
        self.who = review_node.get('who')
        self.when = review_node.get('when')
        self.comment = ''
        if not review_node.find('comment') is None and \
            review_node.find('comment').text:
            self.comment = review_node.find('comment').text.strip()

    def get_node_attrs(self):
        return ('state', 'by_user', 'by_group', 'by_project', 'by_package', 'who', 'when')

    def get_comment(self):
        return self.comment


class RequestState(AbstractState):
    """Represents the state of a request"""
    def __init__(self, state_node):
        if not state_node.get('name'):
            raise oscerr.APIError('invalid request state node (name attr expected): %s' % \
                ET.tostring(state_node))
        AbstractState.__init__(self, state_node.tag)
        self.name = state_node.get('name')
        self.who = state_node.get('who')
        self.when = state_node.get('when')
        self.comment = ''
        if not state_node.find('comment') is None and \
            state_node.find('comment').text:
            self.comment = state_node.find('comment').text.strip()

    def get_node_attrs(self):
        return ('name', 'who', 'when')

    def get_comment(self):
        return self.comment


class Action:
    """
    Represents a <action /> element of a Request.
    This class is quite common so that it can be used for all different
    action types. Note: instances only provide attributes for their specific
    type.
    Examples:
      r = Action('set_bugowner', tgt_project='foo', person_name='buguser')
      # available attributes: r.type (== 'set_bugowner'), r.tgt_project (== 'foo'), r.tgt_package (== None)
      r.to_str() ->
      <action type="set_bugowner">
        <target project="foo" />
        <person name="buguser" />
      </action>
      ##
      r = Action('delete', tgt_project='foo', tgt_package='bar')
      # available attributes: r.type (== 'delete'), r.tgt_project (== 'foo'), r.tgt_package (=='bar')
      r.to_str() ->
      <action type="delete">
        <target package="bar" project="foo" />
      </action>
    """

    # allowed types + the corresponding (allowed) attributes
    type_args = {'submit': ('src_project', 'src_package', 'src_rev', 'tgt_project', 'tgt_package', 'opt_sourceupdate',
                            'acceptinfo_rev', 'acceptinfo_srcmd5', 'acceptinfo_xsrcmd5', 'acceptinfo_osrcmd5',
                            'acceptinfo_oxsrcmd5', 'opt_updatelink'),
        'add_role': ('tgt_project', 'tgt_package', 'person_name', 'person_role', 'group_name', 'group_role'),
        'set_bugowner': ('tgt_project', 'tgt_package', 'person_name'), # obsoleted by add_role
        'maintenance_release': ('src_project', 'src_package', 'src_rev', 'tgt_project', 'tgt_package', 'person_name'),
        'maintenance_incident': ('src_project', 'tgt_project', 'person_name'),
        'delete': ('tgt_project', 'tgt_package'),
        'change_devel': ('src_project', 'src_package', 'tgt_project', 'tgt_package')}
    # attribute prefix to element name map (only needed for abbreviated attributes)
    prefix_to_elm = {'src': 'source', 'tgt': 'target', 'opt': 'options'}

    def __init__(self, type, **kwargs):
        if not type in Action.type_args.keys():
            raise oscerr.WrongArgs('invalid action type: \'%s\'' % type)
        self.type = type
        for i in kwargs.keys():
            if not i in Action.type_args[type]:
                raise oscerr.WrongArgs('invalid argument: \'%s\'' % i)
        # set all type specific attributes
        for i in Action.type_args[type]:
            if kwargs.has_key(i):
                setattr(self, i, kwargs[i])
            else:
                setattr(self, i, None)

    def to_xml(self):
        """
        Serialize object to XML.
        The xml tag names and attributes are constructed from the instance's attributes.
        Example:
          self.group_name  -> tag name is "group", attribute name is "name"
          self.src_project -> tag name is "source" (translated via prefix_to_elm dict),
                              attribute name is "project"
        Attributes prefixed with "opt_" need a special handling, the resulting xml should
        look like this: opt_updatelink -> <options><updatelink>value</updatelink></options>.
        Attributes which are "None" will be skipped.
        """
        root = ET.Element('action', type=self.type)
        for i in Action.type_args[self.type]:
            prefix, attr = i.split('_', 1)
            val = getattr(self, i)
            if val is None:
                continue
            elm = root.find(Action.prefix_to_elm.get(prefix, prefix))
            if elm is None:
                elm = ET.Element(Action.prefix_to_elm.get(prefix, prefix))
                root.append(elm)
            if prefix == 'opt':
                ET.SubElement(elm, attr).text = val
            else:
                elm.set(attr, val)
        return root

    def to_str(self):
        """return "pretty" XML data"""
        root = self.to_xml()
        xmlindent(root)
        return ET.tostring(root)

    @staticmethod
    def from_xml(action_node):
        """create action from XML"""
        if action_node is None or \
            not action_node.get('type') in Action.type_args.keys() or \
            not action_node.tag in ('action', 'submit'):
            raise oscerr.WrongArgs('invalid argument')
        elm_to_prefix = dict([(i[1], i[0]) for i in Action.prefix_to_elm.items()])
        kwargs = {}
        for node in action_node:
            prefix = elm_to_prefix.get(node.tag, node.tag)
            if prefix == 'opt':
                data = [('opt_%s' % opt.tag, opt.text.strip()) for opt in node if opt.text]
            else:
                data = [('%s_%s' % (prefix, k), v) for k, v in node.items()]
            kwargs.update(dict(data))
        return Action(action_node.get('type'), **kwargs)


class Request:
    """Represents a request (<request />)"""

    def __init__(self):
        self._init_attributes()

    def _init_attributes(self):
        """initialize attributes with default values"""
        self.reqid = None
        self.title = ''
        self.description = ''
        self.state = None
        self.actions = []
        self.statehistory = []
        self.reviews = []

    def read(self, root):
        """read in a request"""
        self._init_attributes()
        if not root.get('id'):
            raise oscerr.APIError('invalid request: %s\n' % ET.tostring(root))
        self.reqid = root.get('id')
        if root.find('state') is None:
            raise oscerr.APIError('invalid request (state expected): %s\n' % ET.tostring(root))
        self.state = RequestState(root.find('state'))
        action_nodes = root.findall('action')
        if not action_nodes:
            # check for old-style requests
            for i in root.findall('submit'):
                i.set('type', 'submit')
                action_nodes.append(i)
        for action in action_nodes:
            self.actions.append(Action.from_xml(action))
        for review in root.findall('review'):
            self.reviews.append(ReviewState(review))
        for hist_state in root.findall('history'):
            self.statehistory.append(RequestState(hist_state))
        if not root.find('title') is None:
            self.title = root.find('title').text.strip()
        if not root.find('description') is None and root.find('description').text:
            self.description = root.find('description').text.strip()

    def add_action(self, type, **kwargs):
        """add a new action to the request"""
        self.actions.append(Action(type, **kwargs))

    def get_actions(self, *types):
        """
        get all actions with a specific type
        (if types is empty return all actions)
        """
        if not types:
            return self.actions
        return [i for i in self.actions if i.type in types]

    def get_creator(self):
        """return the creator of the request"""
        if len(self.statehistory):
            return self.statehistory[0].who
        return self.state.who

    def to_xml(self):
        """serialize object to XML"""
        root = ET.Element('request')
        if not self.reqid is None:
            root.set('id', self.reqid)
        for action in self.actions:
            root.append(action.to_xml())
        if not self.state is None:
            root.append(self.state.to_xml())
        for review in self.reviews:
            root.append(review.to_xml())
        for hist in self.statehistory:
            root.append(hist.to_xml())
        if self.title:
            ET.SubElement(root, 'title').text = self.title
        if self.description:
            ET.SubElement(root, 'description').text = self.description
        return root

    def to_str(self):
        """return "pretty" XML data"""
        root = self.to_xml()
        xmlindent(root)
        return ET.tostring(root)

    @staticmethod
    def format_review(review, show_srcupdate=False):
        """
        format a review depending on the reviewer's type.
        A dict which contains the formatted str's is returned.
        """

        d = {'state': '%s:' % review.state}
        if review.by_package:
           d['by'] = '%s/%s' % (review.by_project, review.by_package)
           d['type'] = 'Package'
        elif review.by_project:
           d['by'] = '%s' % review.by_project
           d['type'] = 'Project'
        elif review.by_group:
           d['by'] = '%s' % review.by_group
           d['type'] = 'Group'
        else:
           d['by'] = '%s' % review.by_user
           d['type'] = 'User'
        if review.who:
           d['by'] += '(%s)' % review.who
        return d

    @staticmethod
    def format_action(action, show_srcupdate=False):
        """
        format an action depending on the action's type.
        A dict which contains the formatted str's is returned.
        """
        def prj_pkg_join(prj, pkg):
            if not pkg:
                return prj or ''
            return '%s/%s' % (prj, pkg)

        d = {'type': '%s:' % action.type}
        if action.type == 'set_bugowner':
            d['source'] = action.person_name
            d['target'] = prj_pkg_join(action.tgt_project, action.tgt_package)
        elif action.type == 'change_devel':
            d['source'] = prj_pkg_join(action.tgt_project, action.tgt_package)
            d['target'] = 'developed in %s' % prj_pkg_join(action.src_project, action.src_package)
        elif action.type == 'maintenance_incident':
            d['source'] = '%s ->' % action.src_project
            d['target'] = action.tgt_project
        elif action.type == 'maintenance_release':
            d['source'] = '%s ->' % prj_pkg_join(action.src_project, action.src_package)
            d['target'] = prj_pkg_join(action.tgt_project, action.tgt_package)
        elif action.type == 'submit':
            srcupdate = ' '
            if action.opt_sourceupdate and show_srcupdate:
                srcupdate = '(%s)' % action.opt_sourceupdate
            d['source'] = '%s%s ->' % (prj_pkg_join(action.src_project, action.src_package), srcupdate)
            tgt_package = action.tgt_package
            if action.src_package == action.tgt_package:
                tgt_package = ''
            d['target'] = prj_pkg_join(action.tgt_project, tgt_package)
        elif action.type == 'add_role':
            roles = []
            if action.person_name and action.person_role:
                roles.append('person: %s as %s' % (action.person_name, action.person_role))
            if action.group_name and action.group_role:
                roles.append('group: %s as %s' % (action.group_name, action.group_role))
            d['source'] = ', '.join(roles)
            d['target'] = prj_pkg_join(action.tgt_project, action.tgt_package)
        elif action.type == 'delete':
            d['source'] = ''
            d['target'] = prj_pkg_join(action.tgt_project, action.tgt_package)
        return d

    def list_view(self):
        """return "list view" format"""
        import textwrap
        lines = ['%6s  State:%-10s By:%-12s When:%-19s' % (self.reqid, self.state.name, self.state.who, self.state.when)]
        tmpl = '        %(type)-16s %(source)-50s %(target)s'
        for action in self.actions:
            lines.append(tmpl % Request.format_action(action))
        tmpl = '        Review by %(type)-10s is %(state)-10s %(by)-50s'
        for review in self.reviews:
            lines.append(tmpl % Request.format_review(review))
        history = ['%s(%s)' % (hist.name, hist.who) for hist in self.statehistory]
        if history:
            lines.append('        From: %s' % ' -> '.join(history))
        if self.description:
            lines.append(textwrap.fill(self.description, width=80, initial_indent='        Descr: ',
                subsequent_indent='               '))
        return '\n'.join(lines)

    def __str__(self):
        """return "detailed" format"""
        lines = ['Request: #%s\n' % self.reqid]
        for action in self.actions:
            tmpl = '  %(type)-13s %(source)s %(target)s'
            if action.type == 'delete':
                # remove 1 whitespace because source is empty
                tmpl = '  %(type)-12s %(source)s %(target)s'
            lines.append(tmpl % Request.format_action(action, show_srcupdate=True))
        lines.append('\n\nMessage:')
        if self.description:
            lines.append(self.description)
        else:
            lines.append('<no message>')
        if self.state:
            lines.append('\nState:   %-10s %-12s %s' % (self.state.name, self.state.when, self.state.who))
            lines.append('Comment: %s' % (self.state.comment or '<no comment>'))

        indent = '\n         '
        tmpl = '%(state)-10s %(by)-50s %(when)-12s %(who)-20s  %(comment)s'
        reviews = []
        for review in reversed(self.reviews):
            d = {'state': review.state}
            if review.by_user:
              d['by'] = "User: " + review.by_user
            if review.by_group:
              d['by'] = "Group: " + review.by_group
            if review.by_package:
              d['by'] = "Package: " + review.by_project + "/" + review.by_package 
            elif review.by_project:
              d['by'] = "Project: " + review.by_project
            d['when'] = review.when or ''
            d['who'] = review.who or ''
            d['comment'] = review.comment or ''
            reviews.append(tmpl % d)
        if reviews:
            lines.append('\nReview:  %s' % indent.join(reviews))

        tmpl = '%(name)-10s %(when)-12s %(who)s'
        histories = []
        for hist in reversed(self.statehistory):
            d = {'name': hist.name, 'when': hist.when,
                'who': hist.who}
            histories.append(tmpl % d)
        if histories:
            lines.append('\nHistory: %s' % indent.join(histories))

        return '\n'.join(lines)

    def __cmp__(self, other):
        return cmp(int(self.reqid), int(other.reqid))

    def create(self, apiurl):
        """create a new request"""
        u = makeurl(apiurl, ['request'], query='cmd=create')
        f = http_POST(u, data=self.to_str())
        root = ET.fromstring(f.read())
        self.read(root)

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
    global store

    return os.path.exists(os.path.join(d, store, '_project')) and not \
           os.path.exists(os.path.join(d, store, '_package'))


def is_package_dir(d):
    global store

    return os.path.exists(os.path.join(d, store, '_project')) and \
           os.path.exists(os.path.join(d, store, '_package'))

def parse_disturl(disturl):
    """Parse a disturl, returns tuple (apiurl, project, source, repository,
    revision), else raises an oscerr.WrongArgs exception
    """

    global DISTURL_RE

    m = DISTURL_RE.match(disturl)
    if not m:
        raise oscerr.WrongArgs("`%s' does not look like disturl" % disturl)

    apiurl = m.group('apiurl')
    if apiurl.split('.')[0] != 'api':
        apiurl = 'https://api.' + ".".join(apiurl.split('.')[1:])
    return (apiurl, m.group('project'), m.group('source'), m.group('repository'), m.group('revision'))

def parse_buildlogurl(buildlogurl):
    """Parse a build log url, returns a tuple (apiurl, project, package,
    repository, arch), else raises oscerr.WrongArgs exception"""

    global BUILDLOGURL_RE

    m = BUILDLOGURL_RE.match(buildlogurl)
    if not m:
        raise oscerr.WrongArgs('\'%s\' does not look like url with a build log' % buildlogurl)

    return (m.group('apiurl'), m.group('project'), m.group('package'), m.group('repository'), m.group('arch'))

def slash_split(l):
    """Split command line arguments like 'foo/bar' into 'foo' 'bar'.
    This is handy to allow copy/paste a project/package combination in this form.

    Trailing slashes are removed before the split, because the split would
    otherwise give an additional empty string.
    """
    r = []
    for i in l:
        i = i.rstrip('/')
        r += i.split('/')
    return r

def expand_proj_pack(args, idx=0, howmany=0):
    """looks for occurance of '.' at the position idx.
    If howmany is 2, both proj and pack are expanded together
    using the current directory, or none of them, if not possible.
    If howmany is 0, proj is expanded if possible, then, if there
    is no idx+1 element in args (or args[idx+1] == '.'), pack is also
    expanded, if possible.
    If howmany is 1, only proj is expanded if possible.

    If args[idx] does not exists, an implicit '.' is assumed.
    if not enough elements up to idx exist, an error is raised.

    See also parseargs(args), slash_split(args), findpacs(args)
    All these need unification, somehow.
    """

    # print args,idx,howmany

    if len(args) < idx:
        raise oscerr.WrongArgs('not enough argument, expected at least %d' % idx)

    if len(args) == idx:
        args += '.'
    if args[idx+0] == '.':
        if howmany == 0 and len(args) > idx+1:
            if args[idx+1] == '.':
                # we have two dots.
                # remove one dot and make sure to expand both proj and pack
                args.pop(idx+1)
                howmany = 2
            else:
                howmany = 1
        # print args,idx,howmany

        args[idx+0] = store_read_project('.')
        if howmany == 0:
            try:
                package = store_read_package('.')
                args.insert(idx+1, package)
            except:
                pass
        elif howmany == 2:
            package = store_read_package('.')
            args.insert(idx+1, package)
    return args


def findpacs(files, progress_obj=None):
    """collect Package objects belonging to the given files
    and make sure each Package is returned only once"""
    pacs = []
    for f in files:
        p = filedir_to_pac(f, progress_obj)
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


def filedir_to_pac(f, progress_obj=None):
    """Takes a working copy path, or a path to a file inside a working copy,
    and returns a Package object instance

    If the argument was a filename, add it onto the "todo" list of the Package """

    if os.path.isdir(f):
        wd = f
        p = Package(wd, progress_obj=progress_obj)
    else:
        wd = os.path.dirname(f) or os.curdir
        p = Package(wd, progress_obj=progress_obj)
        p.todo = [ os.path.basename(f) ]
    return p


def read_filemeta(dir):
    global store

    msg = '\'%s\' is not a valid working copy.' % dir
    filesmeta = os.path.join(dir, store, '_files')
    if not is_package_dir(dir):
        raise oscerr.NoWorkingCopy(msg)
    if not os.path.isfile(filesmeta):
        raise oscerr.NoWorkingCopy('%s (%s does not exist)' % (msg, filesmeta))

    try:
        r = ET.parse(filesmeta)
    except SyntaxError, e:
        raise oscerr.NoWorkingCopy('%s\nWhen parsing .osc/_files, the following error was encountered:\n%s' % (msg, e))
    return r

def store_readlist(dir, name):
    global store

    r = []
    if os.path.exists(os.path.join(dir, store, name)):
        r = [line.strip() for line in open(os.path.join(dir, store, name), 'r')]
    return r

def read_tobeadded(dir):
    return store_readlist(dir, '_to_be_added')

def read_tobedeleted(dir):
    return store_readlist(dir, '_to_be_deleted')

def read_sizelimit(dir):
    global store

    r = None
    fname = os.path.join(dir, store, '_size_limit')

    if os.path.exists(fname):
        r = open(fname).readline().strip()

    if r is None or not r.isdigit():
        return None
    return int(r)

def read_inconflict(dir):
    return store_readlist(dir, '_in_conflict')

def parseargs(list_of_args):
    """Convenience method osc's commandline argument parsing.

    If called with an empty tuple (or list), return a list containing the current directory.
    Otherwise, return a list of the arguments."""
    if list_of_args:
        return list(list_of_args)
    else:
        return [os.curdir]


def statfrmt(statusletter, filename):
    return '%s    %s' % (statusletter, filename)


def pathjoin(a, *p):
    """Join two or more pathname components, inserting '/' as needed. Cut leading ./"""
    path = os.path.join(a, *p)
    if path.startswith('./'):
        path = path[2:]
    return path


def makeurl(baseurl, l, query=[]):
    """Given a list of path compoments, construct a complete URL.

    Optional parameters for a query string can be given as a list, as a
    dictionary, or as an already assembled string.
    In case of a dictionary, the parameters will be urlencoded by this
    function. In case of a list not -- this is to be backwards compatible.
    """

    if conf.config['verbose'] > 1:
        print 'makeurl:', baseurl, l, query

    if type(query) == type(list()):
        query = '&'.join(query)
    elif type(query) == type(dict()):
        query = urlencode(query)

    scheme, netloc = urlsplit(baseurl)[0:2]
    return urlunsplit((scheme, netloc, '/'.join(l), query, ''))


def http_request(method, url, headers={}, data=None, file=None, timeout=100):
    """wrapper around urllib2.urlopen for error handling,
    and to support additional (PUT, DELETE) methods"""

    filefd = None

    if conf.config['http_debug']:
        print >>sys.stderr, '\n\n--', method, url

    if method == 'POST' and not file and not data:
        # adding data to an urllib2 request transforms it into a POST
        data = ''

    req = urllib2.Request(url)
    api_host_options = {}
    if conf.is_known_apiurl(url):
        # ok no external request
        urllib2.install_opener(conf._build_opener(url))
        api_host_options = conf.get_apiurl_api_host_options(url)
        for header, value in api_host_options['http_headers']:
            req.add_header(header, value)

    req.get_method = lambda: method

    # POST requests are application/x-www-form-urlencoded per default
    # since we change the request into PUT, we also need to adjust the content type header
    if method == 'PUT' or (method == 'POST' and data):
        req.add_header('Content-Type', 'application/octet-stream')

    if type(headers) == type({}):
        for i in headers.keys():
            print headers[i]
            req.add_header(i, headers[i])

    if file and not data:
        size = os.path.getsize(file)
        if size < 1024*512:
            data = open(file, 'rb').read()
        else:
            import mmap
            filefd = open(file, 'rb')
            try:
                if sys.platform[:3] != 'win':
                    data = mmap.mmap(filefd.fileno(), os.path.getsize(file), mmap.MAP_SHARED, mmap.PROT_READ)
                else:
                    data = mmap.mmap(filefd.fileno(), os.path.getsize(file))
                data = buffer(data)
            except EnvironmentError, e:
                if e.errno == 19:
                    sys.exit('\n\n%s\nThe file \'%s\' could not be memory mapped. It is ' \
                             '\non a filesystem which does not support this.' % (e, file))
                elif hasattr(e, 'winerror') and e.winerror == 5:
                    # falling back to the default io
                    data = open(file, 'rb').read()
                else:
                    raise

    if conf.config['debug']: print >>sys.stderr, method, url

    old_timeout = socket.getdefaulttimeout()
    # XXX: dirty hack as timeout doesn't work with python-m2crypto
    if old_timeout != timeout and not api_host_options.get('sslcertck'):
        socket.setdefaulttimeout(timeout)
    try:
        fd = urllib2.urlopen(req, data=data)
    finally:
        if old_timeout != timeout and not api_host_options.get('sslcertck'):
            socket.setdefaulttimeout(old_timeout)
        if hasattr(conf.cookiejar, 'save'):
            conf.cookiejar.save(ignore_discard=True)

    if filefd: filefd.close()

    return fd


def http_GET(*args, **kwargs):    return http_request('GET', *args, **kwargs)
def http_POST(*args, **kwargs):   return http_request('POST', *args, **kwargs)
def http_PUT(*args, **kwargs):    return http_request('PUT', *args, **kwargs)
def http_DELETE(*args, **kwargs): return http_request('DELETE', *args, **kwargs)


def check_store_version(dir):
    global store

    versionfile = os.path.join(dir, store, '_osclib_version')
    try:
        v = open(versionfile).read().strip()
    except:
        v = ''

    if v == '':
        msg = 'Error: "%s" is not an osc package working copy.' % os.path.abspath(dir)
        if os.path.exists(os.path.join(dir, '.svn')):
            msg = msg + '\nTry svn instead of osc.'
        raise oscerr.NoWorkingCopy(msg)

    if v != __store_version__:
        if v in ['0.2', '0.3', '0.4', '0.5', '0.6', '0.7', '0.8', '0.9', '0.95', '0.96', '0.97', '0.98', '0.99']:
            # version is fine, no migration needed
            f = open(versionfile, 'w')
            f.write(__store_version__ + '\n')
            f.close()
            return
        msg = 'The osc metadata of your working copy "%s"' % dir
        msg += '\nhas __store_version__ = %s, but it should be %s' % (v, __store_version__)
        msg += '\nPlease do a fresh checkout or update your client. Sorry about the inconvenience.'
        raise oscerr.WorkingCopyWrongVersion, msg


def meta_get_packagelist(apiurl, prj, deleted=None):

    query = {}
    if deleted:
       query['deleted'] = 1

    u = makeurl(apiurl, ['source', prj], query)
    f = http_GET(u)
    root = ET.parse(f).getroot()
    return [ node.get('name') for node in root.findall('entry') ]


def meta_get_filelist(apiurl, prj, package, verbose=False, expand=False, revision=None, meta=False):
    """return a list of file names,
    or a list File() instances if verbose=True"""

    query = {}
    if expand:
        query['expand'] = 1
    if meta:
        query['meta'] = 1
    if revision:
        query['rev'] = revision
    else:
        query['rev'] = 'latest'

    u = makeurl(apiurl, ['source', prj, package], query=query)
    f = http_GET(u)
    root = ET.parse(f).getroot()

    if not verbose:
        return [ node.get('name') for node in root.findall('entry') ]

    else:
        l = []
        # rev = int(root.get('rev'))    # don't force int. also allow srcmd5 here.
        rev = root.get('rev')
        for node in root.findall('entry'):
            f = File(node.get('name'),
                     node.get('md5'),
                     int(node.get('size')),
                     int(node.get('mtime')))
            f.rev = rev
            l.append(f)
        return l


def meta_get_project_list(apiurl, deleted=None):
    query = {}
    if deleted:
        query['deleted'] = 1

    u = makeurl(apiurl, ['source'], query)
    f = http_GET(u)
    root = ET.parse(f).getroot()
    return sorted([ node.get('name') for node in root if node.get('name')])


def show_project_meta(apiurl, prj):
    url = makeurl(apiurl, ['source', prj, '_meta'])
    f = http_GET(url)
    return f.readlines()


def show_project_conf(apiurl, prj):
    url = makeurl(apiurl, ['source', prj, '_config'])
    f = http_GET(url)
    return f.readlines()


def show_package_trigger_reason(apiurl, prj, pac, repo, arch):
    url = makeurl(apiurl, ['build', prj, repo, arch, pac, '_reason'])
    try:
        f = http_GET(url)
        return f.read()
    except urllib2.HTTPError, e:
        e.osc_msg = 'Error getting trigger reason for project \'%s\' package \'%s\'' % (prj, pac)
        raise


def show_package_meta(apiurl, prj, pac, meta=False):
    query = {}
    if meta:
        query['meta'] = 1

    # packages like _pattern and _project do not have a _meta file
    if pac.startswith('_pattern') or pac.startswith('_project'):
        return ""

    url = makeurl(apiurl, ['source', prj, pac, '_meta'], query)
    try:
        f = http_GET(url)
        return f.readlines()
    except urllib2.HTTPError, e:
        e.osc_msg = 'Error getting meta for project \'%s\' package \'%s\'' % (prj, pac)
        raise


def show_attribute_meta(apiurl, prj, pac, subpac, attribute, with_defaults, with_project):
    path=[]
    path.append('source')
    path.append(prj)
    if pac:
        path.append(pac)
    if pac and subpac:
        path.append(subpac)
    path.append('_attribute')
    if attribute:
        path.append(attribute)
    query=[]
    if with_defaults:
        query.append("with_default=1")
    if with_project:
        query.append("with_project=1")
    url = makeurl(apiurl, path, query)
    try:
        f = http_GET(url)
        return f.readlines()
    except urllib2.HTTPError, e:
        e.osc_msg = 'Error getting meta for project \'%s\' package \'%s\'' % (prj, pac)
        raise


def show_develproject(apiurl, prj, pac, xml_node=False):
    m = show_package_meta(apiurl, prj, pac)
    node = ET.fromstring(''.join(m)).find('devel')
    if not node is None:
        if xml_node:
            return node
        return node.get('project')
    return None


def show_package_disabled_repos(apiurl, prj, pac):
    m = show_package_meta(apiurl, prj, pac)
    #FIXME: don't work if all repos of a project are disabled and only some are enabled since <disable/> is empty
    try:
        root = ET.fromstring(''.join(m))
        elm = root.find('build')
        r = [ node.get('repository') for node in elm.findall('disable')]
        return r
    except:
        return None


def show_pattern_metalist(apiurl, prj):
    url = makeurl(apiurl, ['source', prj, '_pattern'])
    try:
        f = http_GET(url)
        tree = ET.parse(f)
    except urllib2.HTTPError, e:
        e.osc_msg = 'show_pattern_metalist: Error getting pattern list for project \'%s\'' % prj
        raise
    r = [ node.get('name') for node in tree.getroot() ]
    r.sort()
    return r


def show_pattern_meta(apiurl, prj, pattern):
    url = makeurl(apiurl, ['source', prj, '_pattern', pattern])
    try:
        f = http_GET(url)
        return f.readlines()
    except urllib2.HTTPError, e:
        e.osc_msg = 'show_pattern_meta: Error getting pattern \'%s\' for project \'%s\'' % (pattern, prj)
        raise


class metafile:
    """metafile that can be manipulated and is stored back after manipulation."""
    def __init__(self, url, input, change_is_required=False, file_ext='.xml'):
        import tempfile

        self.url = url
        self.change_is_required = change_is_required
        (fd, self.filename) = tempfile.mkstemp(prefix = 'osc_metafile.', suffix = file_ext)
        f = os.fdopen(fd, 'w')
        f.write(''.join(input))
        f.close()
        self.hash_orig = dgst(self.filename)

    def sync(self):
        if self.change_is_required and self.hash_orig == dgst(self.filename):
            print 'File unchanged. Not saving.'
            os.unlink(self.filename)
            return

        print 'Sending meta data...'
        # don't do any exception handling... it's up to the caller what to do in case
        # of an exception
        http_PUT(self.url, file=self.filename)
        os.unlink(self.filename)
        print 'Done.'

    def edit(self):
        try:
            while 1:
                run_editor(self.filename)
                try:
                    self.sync()
                    break
                except urllib2.HTTPError, e:
                    error_help = "%d" % e.code
                    if e.headers.get('X-Opensuse-Errorcode'):
                        error_help = "%s (%d)" % (e.headers.get('X-Opensuse-Errorcode'), e.code)

                    print >>sys.stderr, 'BuildService API error:', error_help
                    # examine the error - we can't raise an exception because we might want
                    # to try again
                    data = e.read()
                    if '<summary>' in data:
                        print >>sys.stderr, data.split('<summary>')[1].split('</summary>')[0]
                    ri = raw_input('Try again? ([y/N]): ')
                    if ri not in ['y', 'Y']:
                        break
        finally:
            self.discard()

    def discard(self):
        if os.path.exists(self.filename):
            print 'discarding %s' % self.filename
            os.unlink(self.filename)


# different types of metadata
metatypes = { 'prj':     { 'path': 'source/%s/_meta',
                           'template': new_project_templ,
                           'file_ext': '.xml'
                         },
              'pkg':     { 'path'     : 'source/%s/%s/_meta',
                           'template': new_package_templ,
                           'file_ext': '.xml'
                         },
              'attribute':     { 'path'     : 'source/%s/%s/_meta',
                           'template': new_attribute_templ,
                           'file_ext': '.xml'
                         },
              'prjconf': { 'path': 'source/%s/_config',
                           'template': '',
                           'file_ext': '.txt'
                         },
              'user':    { 'path': 'person/%s',
                           'template': new_user_template,
                           'file_ext': '.xml'
                         },
              'pattern': { 'path': 'source/%s/_pattern/%s',
                           'template': new_pattern_template,
                           'file_ext': '.xml'
                         },
            }

def meta_exists(metatype,
                path_args=None,
                template_args=None,
                create_new=True,
                apiurl=None):

    global metatypes

    if not apiurl:
        apiurl = conf.config['apiurl']
    url = make_meta_url(metatype, path_args, apiurl)
    try:
        data = http_GET(url).readlines()
    except urllib2.HTTPError, e:
        if e.code == 404 and create_new:
            data = metatypes[metatype]['template']
            if template_args:
                data = StringIO(data % template_args).readlines()
        else:
            raise e

    return data

def make_meta_url(metatype, path_args=None, apiurl=None, force=False):
    global metatypes

    if not apiurl:
        apiurl = conf.config['apiurl']
    if metatype not in metatypes.keys():
        raise AttributeError('make_meta_url(): Unknown meta type \'%s\'' % metatype)
    path = metatypes[metatype]['path']

    if path_args:
        path = path % path_args

    query = {}
    if force:
        query = { 'force': '1' }

    return makeurl(apiurl, [path], query)


def edit_meta(metatype,
              path_args=None,
              data=None,
              template_args=None,
              edit=False,
              force=False,
              change_is_required=False,
              apiurl=None):

    global metatypes

    if not apiurl:
        apiurl = conf.config['apiurl']
    if not data:
        data = meta_exists(metatype,
                           path_args,
                           template_args,
                           create_new = metatype != 'prjconf', # prjconf always exists, 404 => unknown prj
                           apiurl=apiurl)

    if edit:
        change_is_required = True

    url = make_meta_url(metatype, path_args, apiurl, force)
    f=metafile(url, data, change_is_required, metatypes[metatype]['file_ext'])

    if edit:
        f.edit()
    else:
        f.sync()


def show_files_meta(apiurl, prj, pac, revision=None, expand=False, linkrev=None, linkrepair=False, meta=False):
    query = {}
    if revision:
        query['rev'] = revision
    else:
        query['rev'] = 'latest'
    if linkrev:
        query['linkrev'] = linkrev
    elif conf.config['linkcontrol']:
        query['linkrev'] = 'base'
    if meta:
        query['meta'] = 1
    if expand:
        query['expand'] = 1
    if linkrepair:
        query['emptylink'] = 1
    f = http_GET(makeurl(apiurl, ['source', prj, pac], query=query))
    return f.read()

def show_upstream_srcmd5(apiurl, prj, pac, expand=False, revision=None, meta=False, include_service_files=False):
    m = show_files_meta(apiurl, prj, pac, expand=expand, revision=revision, meta=meta)
    et = ET.fromstring(''.join(m))
    if include_service_files:
        try:
            if et.find('serviceinfo') and et.find('serviceinfo').get('xsrcmd5'):
                return et.find('serviceinfo').get('xsrcmd5')
        except:
            pass
    return et.get('srcmd5')


def show_upstream_xsrcmd5(apiurl, prj, pac, revision=None, linkrev=None, linkrepair=False, meta=False, include_service_files=False):
    m = show_files_meta(apiurl, prj, pac, revision=revision, linkrev=linkrev, linkrepair=linkrepair, meta=meta, expand=include_service_files)
    et = ET.fromstring(''.join(m))
    if include_service_files:
        return et.get('srcmd5')
    try:
        # only source link packages have a <linkinfo> element.
        li_node = et.find('linkinfo')
    except:
        return None

    li = Linkinfo()
    li.read(li_node)

    if li.haserror():
        raise oscerr.LinkExpandError(prj, pac, li.error)
    return li.xsrcmd5


def show_upstream_rev(apiurl, prj, pac, revision=None, expand=False, linkrev=None, meta=False, include_service_files=False):
    m = show_files_meta(apiurl, prj, pac, revision=revision, expand=expand, linkrev=linkrev, meta=meta)
    et = ET.fromstring(''.join(m))
    if include_service_files:
        try:
            return et.find('serviceinfo').get('xsrcmd5')
        except:
            pass
    return et.get('rev')


def read_meta_from_spec(specfile, *args):
    import codecs, locale, re
    """
    Read tags and sections from spec file. To read out
    a tag the passed argument mustn't end with a colon. To
    read out a section the passed argument must start with
    a '%'.
    This method returns a dictionary which contains the
    requested data.
    """

    if not os.path.isfile(specfile):
        raise oscerr.OscIOError(None, '\'%s\' is not a regular file' % specfile)

    try:
        lines = codecs.open(specfile, 'r', locale.getpreferredencoding()).readlines()
    except UnicodeDecodeError:
        lines = open(specfile).readlines()

    tags = []
    sections = []
    spec_data = {}

    for itm in args:
        if itm.startswith('%'):
            sections.append(itm)
        else:
            tags.append(itm)

    tag_pat = '(?P<tag>^%s)\s*:\s*(?P<val>.*)'
    for tag in tags:
        m = re.compile(tag_pat % tag, re.I | re.M).search(''.join(lines))
        if m and m.group('val'):
            spec_data[tag] = m.group('val').strip()

    section_pat = '^%s\s*?$'
    for section in sections:
        m = re.compile(section_pat % section, re.I | re.M).search(''.join(lines))
        if m:
            start = lines.index(m.group()+'\n') + 1
        data = []
        for line in lines[start:]:
            if line.startswith('%'):
                break
            data.append(line)
        spec_data[section] = data

    return spec_data

def get_default_editor():
    import platform
    system = platform.system()
    if system == 'Windows':
        return 'notepad'
    if system == 'Linux':
        try:
            # Python 2.6
            dist = platform.linux_distribution()[0]
        except AttributeError:
            dist = platform.dist()[0]
        if dist == 'debian':
            return 'editor'
        elif dist == 'fedora':
            return 'vi'
        return 'vim'
    return 'vi'

def get_default_pager():
    import platform
    system = platform.system()
    if system == 'Windows':
        return 'less'
    if system == 'Linux':
        try:
            # Python 2.6
            dist = platform.linux_distribution()[0]
        except AttributeError:
            dist = platform.dist()[0]
        if dist == 'debian':
            return 'pager'
        return 'less'
    return 'more'

def run_pager(message, tmp_suffix=''):
    import tempfile, sys

    if not message:
        return

    if not sys.stdout.isatty():
        print message
    else:
        tmpfile = tempfile.NamedTemporaryFile(suffix=tmp_suffix)
        tmpfile.write(message)
        tmpfile.flush()
        pager = os.getenv('PAGER', default=get_default_pager())
        try:
            try:
                subprocess.call('%s %s' % (pager, tmpfile.name), shell=True)
            except OSError, e:
                raise oscerr.ExtRuntimeError('cannot run pager \'%s\': %s' % (pager, e.strerror), pager)
        finally:
            tmpfile.close()

def run_editor(filename):
    editor = os.getenv('EDITOR', default=get_default_editor())
    cmd = editor.split(' ')
    cmd.append(filename)
    try:
        return subprocess.call(cmd)
    except OSError, e:
        raise oscerr.ExtRuntimeError('cannot run editor \'%s\': %s' % (editor, e.strerror), editor)

def edit_message(footer='', template='', templatelen=30):
    delim = '--This line, and those below, will be ignored--\n'
    import tempfile
    (fd, filename) = tempfile.mkstemp(prefix = 'osc-commitmsg', suffix = '.diff')
    f = os.fdopen(fd, 'w')
    if template != '':
        if not templatelen is None:
            lines = template.splitlines()
            template = '\n'.join(lines[:templatelen])
            if lines[templatelen:]:
                footer = '%s\n\n%s' % ('\n'.join(lines[templatelen:]), footer)
        f.write(template)
    f.write('\n')
    f.write(delim)
    f.write('\n')
    f.write(footer)
    f.close()

    try:
        while 1:
            run_editor(filename)
            msg = open(filename).read().split(delim)[0].rstrip()

            if len(msg):
                break
            else:
                ri = raw_input('Log message not specified\n'
                               'a)bort, c)ontinue, e)dit: ')
                if ri in 'aA':
                    raise oscerr.UserAbort()
                elif ri in 'cC':
                    break
                elif ri in 'eE':
                    pass
    finally:
        os.unlink(filename)
    return msg

def clone_request(apiurl, reqid, msg=None):
    query = {'cmd': 'branch', 'request': reqid}
    url = makeurl(apiurl, ['source'], query)
    r = http_POST(url, data=msg)
    root = ET.fromstring(r.read())
    project = None
    for i in root.findall('data'):
        if i.get('name') == 'targetproject':
            project = i.text.strip()
    if not project:
        raise oscerr.APIError('invalid data from clone request:\n%s\n' % ET.tostring(root))
    return project

# create a maintenance release request
def create_release_request(apiurl, src_project, message=''):
    import cgi
    r = Request()
    # api will complete the request
    r.add_action('maintenance_release', src_project=src_project)
    # XXX: clarify why we need the unicode(...) stuff
    r.description = cgi.escape(unicode(message, 'utf8'))
    r.create(apiurl)
    return r

# create a maintenance incident per request
def create_maintenance_request(apiurl, src_project, tgt_project, message=''):
    import cgi
    r = Request()
    r.add_action('maintenance_incident', src_project=src_project, tgt_project=tgt_project)
    # XXX: clarify why we need the unicode(...) stuff
    r.description = cgi.escape(unicode(message, 'utf8'))
    r.create(apiurl)
    return r

# This creates an old style submit request for server api 1.0
def create_submit_request(apiurl,
                         src_project, src_package,
                         dst_project=None, dst_package=None,
                         message="", orev=None, src_update=None):

    import cgi
    options_block=""
    if src_update:
        options_block="""<options><sourceupdate>%s</sourceupdate></options> """ % (src_update)

    # Yes, this kind of xml construction is horrible
    targetxml = ""
    if dst_project:
        packagexml = ""
        if dst_package:
            packagexml = """package="%s" """ %( dst_package )
        targetxml = """<target project="%s" %s /> """ %( dst_project, packagexml )
    # XXX: keep the old template for now in order to work with old obs instances
    xml = """\
<request type="submit">
    <submit>
        <source project="%s" package="%s" rev="%s"/>
        %s
        %s
    </submit>
    <state name="new"/>
    <description>%s</description>
</request>
""" % (src_project,
       src_package,
       orev or show_upstream_rev(apiurl, src_project, src_package),
       targetxml,
       options_block,
       cgi.escape(message))

    # Don't do cgi.escape(unicode(message, "utf8"))) above.
    # Promoting the string to utf8, causes the post to explode with:
    #   uncaught exception: Fatal error: Start tag expected, '&lt;' not found at :1.
    # I guess, my original workaround was not that bad.

    u = makeurl(apiurl, ['request'], query='cmd=create')
    f = http_POST(u, data=xml)

    root = ET.parse(f).getroot()
    return root.get('id')


def get_request(apiurl, reqid):
    u = makeurl(apiurl, ['request', reqid])
    f = http_GET(u)
    root = ET.parse(f).getroot()

    r = Request()
    r.read(root)
    return r


def change_review_state(apiurl, reqid, newstate, by_user='', by_group='', by_project='', by_package='', message='', supersed=None):
    query = {'cmd': 'changereviewstate', 'newstate': newstate }
    if by_user:
        query['by_user'] = by_user
    if by_group:
        query['by_group'] = by_group
    if by_project:
        query['by_project'] = by_project
    if by_package:
        query['by_package'] = by_package
    if supersed:
        query['superseded_by'] = supersed
    u = makeurl(apiurl, ['request', reqid], query=query)
    f = http_POST(u, data=message)
    root = ET.parse(f).getroot()
    return root.get('code')

def change_request_state(apiurl, reqid, newstate, message='', supersed=None, force=False):
    query={'cmd': 'changestate', 'newstate': newstate }
    if supersed:
        query['superseded_by'] = supersed
    if force:
        query['force'] = "1"
    u = makeurl(apiurl,
                ['request', reqid], query=query)
    f = http_POST(u, data=message)

    r = f.read()
    if r.startswith('<status code="'):
        r = r.split('<status code="')[1]
        r = r.split('" />')[0]

    return r

def change_request_state_template(req, newstate):
    if not len(req.actions):
        return ''
    action = req.actions[0]
    tmpl_name = '%srequest_%s_template' % (action.type, newstate)
    tmpl = conf.config.get(tmpl_name, '')
    tmpl = tmpl.replace('\\t', '\t').replace('\\n', '\n')    
    data = {'reqid': req.reqid, 'type': action.type, 'who': req.get_creator()}
    if req.actions[0].type == 'submit':
        data.update({'src_project': action.src_project,
            'src_package': action.src_package, 'src_rev': action.src_rev,
            'dst_project': action.tgt_project, 'dst_package': action.tgt_package,
            'tgt_project': action.tgt_project, 'tgt_package': action.tgt_package})
    try:
        return tmpl % data
    except KeyError, e:
        print >>sys.stderr, 'error: cannot interpolate \'%s\' in \'%s\'' % (e.args[0], tmpl_name)
        return ''

def get_review_list(apiurl, project='', package='', byuser='', bygroup='', byproject='', bypackage='', states=('new')):
    xpath = ''
    xpath = xpath_join(xpath, 'state/@name=\'review\'', inner=True)
    if not 'all' in states:
        for state in states:
            xpath = xpath_join(xpath, 'review/@state=\'%s\'' % state, inner=True)
    if byuser:
        xpath = xpath_join(xpath, 'review/@by_user=\'%s\'' % byuser, op='and')
    if bygroup:
        xpath = xpath_join(xpath, 'review/@by_group=\'%s\'' % bygroup, op='and')
    if bypackage:
        xpath = xpath_join(xpath, 'review/[@by_project=\'%s\' and @by_package=\'%s\']' % (byproject, bypackage), op='and')
    elif byproject:
        xpath = xpath_join(xpath, 'review/@by_project=\'%s\'' % byproject, op='and')

    # XXX: we cannot use the '|' in the xpath expression because it is not supported
    #      in the backend
    todo = {}
    if project:
        todo['project'] = project
    if package:
        todo['package'] = package
    for kind, val in todo.iteritems():
        xpath_base = 'action/target/@%(kind)s=\'%(val)s\' or ' \
                     'submit/target/@%(kind)s=\'%(val)s\''

        if conf.config['include_request_from_project']:
            xpath_base = xpath_join(xpath_base, 'action/source/@%(kind)s=\'%(val)s\' or ' \
                                                'submit/source/@%(kind)s=\'%(val)s\'', op='or', inner=True)
        xpath = xpath_join(xpath, xpath_base % {'kind': kind, 'val': val}, op='and', nexpr_parentheses=True)

    if conf.config['verbose'] > 1:
        print '[ %s ]' % xpath
    res = search(apiurl, request=xpath)
    collection = res['request']
    requests = []
    for root in collection.findall('request'):
        r = Request()
        r.read(root)
        requests.append(r)
    return requests

def get_request_list(apiurl, project='', package='', req_who='', req_state=('new','review',), req_type=None, exclude_target_projects=[]):
    xpath = ''
    if not 'all' in req_state:
        for state in req_state:
            xpath = xpath_join(xpath, 'state/@name=\'%s\'' % state, inner=True)
    if req_who:
        xpath = xpath_join(xpath, '(state/@who=\'%(who)s\' or history/@who=\'%(who)s\')' % {'who': req_who}, op='and')

    # XXX: we cannot use the '|' in the xpath expression because it is not supported
    #      in the backend
    todo = {}
    if project:
        todo['project'] = project
    if package:
        todo['package'] = package
    for kind, val in todo.iteritems():
        xpath_base = 'action/target/@%(kind)s=\'%(val)s\' or ' \
                     'submit/target/@%(kind)s=\'%(val)s\''

        if conf.config['include_request_from_project']:
            xpath_base = xpath_join(xpath_base, 'action/source/@%(kind)s=\'%(val)s\' or ' \
                                                'submit/source/@%(kind)s=\'%(val)s\'', op='or', inner=True)
        xpath = xpath_join(xpath, xpath_base % {'kind': kind, 'val': val}, op='and', nexpr_parentheses=True)

    if req_type:
        xpath = xpath_join(xpath, 'action/@type=\'%s\'' % req_type, op='and')
    for i in exclude_target_projects:
        xpath = xpath_join(xpath, '(not(action/target/@project=\'%(prj)s\' or ' \
                                  'submit/target/@project=\'%(prj)s\'))' % {'prj': i}, op='and')

    if conf.config['verbose'] > 1:
        print '[ %s ]' % xpath
    res = search(apiurl, request=xpath)
    collection = res['request']
    requests = []
    for root in collection.findall('request'):
        r = Request()
        r.read(root)
        requests.append(r)
    return requests

# old style search, this is to be removed
def get_user_projpkgs_request_list(apiurl, user, req_state=('new','review',), req_type=None, exclude_projects=[], projpkgs={}):
    """OBSOLETE: user involved request search is supported by OBS 2.2 server side in a better way
       Return all running requests for all projects/packages where is user is involved"""
    if not projpkgs:
        res = get_user_projpkgs(apiurl, user, exclude_projects=exclude_projects)
        projects = []
        for i in res['project_id'].findall('project'):
            projpkgs[i.get('name')] = []
            projects.append(i.get('name'))
        for i in res['package_id'].findall('package'):
            if not i.get('project') in projects:
                projpkgs.setdefault(i.get('project'), []).append(i.get('name'))
    xpath = ''
    for prj, pacs in projpkgs.iteritems():
        if not len(pacs):
            xpath = xpath_join(xpath, 'action/target/@project=\'%s\'' % prj, inner=True)
        else:
            xp = ''
            for p in pacs:
                xp = xpath_join(xp, 'action/target/@package=\'%s\'' % p, inner=True)
            xp = xpath_join(xp, 'action/target/@project=\'%s\'' % prj, op='and')
            xpath = xpath_join(xpath, xp, inner=True)
    if req_type:
        xpath = xpath_join(xpath, 'action/@type=\'%s\'' % req_type, op='and')
    if not 'all' in req_state:
        xp = ''
        for state in req_state:
            xp = xpath_join(xp, 'state/@name=\'%s\'' % state, inner=True)
        xpath = xpath_join(xp, xpath, op='and', nexpr_parentheses=True)
    res = search(apiurl, request=xpath)
    result = []
    for root in res['request'].findall('request'):
        r = Request()
        r.read(root)
        result.append(r)
    return result

def get_request_log(apiurl, reqid):
    r = get_request(apiurl, reqid)
    data = []
    frmt = '-' * 76 + '\n%s | %s | %s\n\n%s'
    r.statehistory.reverse()
    # the description of the request is used for the initial log entry
    # otherwise its comment attribute would contain None
    if len(r.statehistory) >= 1:
        r.statehistory[-1].comment = r.description
    else:
        r.state.comment = r.description
    for state in [ r.state ] + r.statehistory:
        s = frmt % (state.name, state.who, state.when, str(state.comment))
        data.append(s)
    return data


def get_group(apiurl, group):
    u = makeurl(apiurl, ['group', quote_plus(group)])
    try:
        f = http_GET(u)
        return ''.join(f.readlines())
    except urllib2.HTTPError:
        print 'user \'%s\' not found' % group
        return None

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
                return []
    return data


def download(url, filename, progress_obj = None, mtime = None):
    import tempfile, shutil
    global BUFSIZE

    o = None
    try:
        prefix = os.path.basename(filename)
        path = os.path.dirname(filename)
        (fd, tmpfile) = tempfile.mkstemp(dir=path, prefix = prefix, suffix = '.osctmp')
        os.chmod(tmpfile, 0644)
        try:
            o = os.fdopen(fd, 'wb')
            for buf in streamfile(url, http_GET, BUFSIZE, progress_obj=progress_obj):
                o.write(buf)
            o.close()
            os.rename(tmpfile, filename)
        except:
            os.unlink(tmpfile)
            raise
    finally:
        if o is not None:
            o.close()

    if mtime:
        os.utime(filename, (-1, mtime))

def get_source_file(apiurl, prj, package, filename, targetfilename=None, revision=None, progress_obj=None, mtime=None, meta=False):
    targetfilename = targetfilename or filename
    query = {}
    if meta:
        query['rev'] = 1
    if revision:
        query['rev'] = revision
    u = makeurl(apiurl, ['source', prj, package, pathname2url(filename)], query=query)
    download(u, targetfilename, progress_obj, mtime)

def get_binary_file(apiurl, prj, repo, arch,
                    filename,
                    package = None,
                    target_filename = None,
                    target_mtime = None,
                    progress_meter = False):
    progress_obj = None
    if progress_meter:
        from meter import TextMeter
        progress_obj = TextMeter()

    target_filename = target_filename or filename

    where = package or '_repository'
    u = makeurl(apiurl, ['build', prj, repo, arch, where, filename])
    download(u, target_filename, progress_obj, target_mtime)

def dgst_from_string(str):
    # Python 2.5 depracates the md5 modules
    # Python 2.4 doesn't have hashlib yet
    try:
        import hashlib
        md5_hash = hashlib.md5()
    except ImportError:
        import md5
        md5_hash = md5.new()
    md5_hash.update(str)
    return md5_hash.hexdigest()

def dgst(file):

    #if not os.path.exists(file):
        #return None

    global BUFSIZE

    try:
        import hashlib
        md5 = hashlib
    except ImportError:
        import md5
        md5 = md5
    s = md5.md5()
    f = open(file, 'rb')
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
    return binary(open(fn, 'rb').read(4096))


def get_source_file_diff(dir, filename, rev, oldfilename = None, olddir = None, origfilename = None):
    """
    This methods diffs oldfilename against filename (so filename will
    be shown as the new file).
    The variable origfilename is used if filename and oldfilename differ
    in their names (for instance if a tempfile is used for filename etc.)
    """

    import difflib

    global store

    if not oldfilename:
        oldfilename = filename

    if not olddir:
        olddir = os.path.join(dir, store)

    if not origfilename:
        origfilename = filename

    file1 = os.path.join(olddir, oldfilename)   # old/stored original
    file2 = os.path.join(dir, filename)         # working copy
    if binary_file(file1) or binary_file(file2):
        return ['Binary file \'%s\' has changed.\n' % origfilename]

    f1 = f2 = None
    try:
        f1 = open(file1, 'rb')
        s1 = f1.readlines()
        f1.close()

        f2 = open(file2, 'rb')
        s2 = f2.readlines()
        f2.close()
    finally:
        if f1:
            f1.close()
        if f2:
            f2.close()

    d = difflib.unified_diff(s1, s2,
        fromfile = '%s\t(revision %s)' % (origfilename, rev), \
        tofile = '%s\t(working copy)' % origfilename)
    d = list(d)
    # python2.7's difflib slightly changed the format
    # adapt old format to the new format
    if len(d) > 1:
        d[0] = d[0].replace(' \n', '\n')
        d[1] = d[1].replace(' \n', '\n')

    # if file doesn't end with newline, we need to append one in the diff result
    for i, line in enumerate(d):
        if not line.endswith('\n'):
            d[i] += '\n\\ No newline at end of file'
            if i+1 != len(d):
                d[i] += '\n'
    return d

def server_diff(apiurl,
                old_project, old_package, old_revision,
                new_project, new_package, new_revision,
                unified=False, missingok=False, meta=False, expand=True):
    query = {'cmd': 'diff'}
    if expand:
        query['expand'] = 1
    if old_project:
        query['oproject'] = old_project
    if old_package:
        query['opackage'] = old_package
    if old_revision:
        query['orev'] = old_revision
    if new_revision:
        query['rev'] = new_revision
    if unified:
        query['unified'] = 1
    if missingok:
        query['missingok'] = 1
    if meta:
        query['meta'] = 1

    u = makeurl(apiurl, ['source', new_project, new_package], query=query)

    f = http_POST(u)
    return f.read()

def server_diff_noex(apiurl,
                old_project, old_package, old_revision,
                new_project, new_package, new_revision,
                unified=False, missingok=False, meta=False, expand=True):
    try:
        return server_diff(apiurl,
                            old_project, old_package, old_revision,
                            new_project, new_package, new_revision,
                            unified, missingok, meta, expand)
    except urllib2.HTTPError, e:
        msg = None
        body = None
        try:
            body = e.read()
            if not 'bad link' in body:
                return '# diff failed: ' + body
        except:
            return '# diff failed with unknown error'

        if expand:
            rdiff =  "## diff on expanded link not possible, showing unexpanded version\n"
            try:
                rdiff += server_diff_noex(apiurl,
                    old_project, old_package, old_revision,
                    new_project, new_package, new_revision,
                    unified, missingok, meta, False)
            except:
                elm = ET.fromstring(body).find('summary')
                summary = ''
                if not elm is None:
                    summary = elm.text
                return 'error: diffing failed: %s' % summary
            return rdiff


def request_diff(apiurl, reqid):
    u = makeurl(apiurl, ['request', reqid], query={'cmd': 'diff'} )

    f = http_POST(u)
    return f.read()

def submit_action_diff(apiurl, action):
    """diff a single submit action"""
    # backward compatiblity: only a recent api/backend supports the missingok parameter
    try:
        return server_diff(apiurl, action.tgt_project, action.tgt_package, None,
            action.src_project, action.src_package, action.src_rev, True, True)
    except urllib2.HTTPError, e:
        if e.code == 400:
            try:
                return server_diff(apiurl, action.tgt_project, action.tgt_package, None,
                    action.src_project, action.src_package, action.src_rev, True, False)
            except urllib2.HTTPError, e:
                if e.code != 404:
                    raise e
                root = ET.fromstring(e.read())
                return 'error: \'%s\' does not exist' % root.find('summary').text
        elif e.code == 404:
            root = ET.fromstring(e.read())
            return 'error: \'%s\' does not exist' % root.find('summary').text
        raise e

def make_dir(apiurl, project, package, pathname=None, prj_dir=None, package_tracking=True):
    """
    creates the plain directory structure for a package dir.
    The 'apiurl' parameter is needed for the project dir initialization.
    The 'project' and 'package' parameters specify the name of the
    project and the package. The optional 'pathname' parameter is used
    for printing out the message that a new dir was created (default: 'prj_dir/package').
    The optional 'prj_dir' parameter specifies the path to the project dir (default: 'project').
    """
    prj_dir = prj_dir or project

    # FIXME: carefully test each patch component of prj_dir,
    # if we have a .osc/_files entry at that level.
    #   -> if so, we have a package/project clash,
    #      and should rename this path component by appending '.proj'
    #      and give user a warning message, to discourage such clashes

    pathname = pathname or getTransActPath(os.path.join(prj_dir, package))
    if is_package_dir(prj_dir):
        # we want this to become a project directory,
        # but it already is a package directory.
        raise oscerr.OscIOError(None, 'checkout_package: package/project clash. Moving myself away not implemented')

    if not is_project_dir(prj_dir):
        # this directory could exist as a parent direory for one of our earlier
        # checked out sub-projects. in this case, we still need to initialize it.
        print statfrmt('A', prj_dir)
        Project.init_project(apiurl, prj_dir, project, package_tracking)

    if is_project_dir(os.path.join(prj_dir, package)):
        # the thing exists, but is a project directory and not a package directory
        # FIXME: this should be a warning message to discourage package/project clashes
        raise oscerr.OscIOError(None, 'checkout_package: package/project clash. Moving project away not implemented')

    if not os.path.exists(os.path.join(prj_dir, package)):
        print statfrmt('A', pathname)
        os.mkdir(os.path.join(prj_dir, package))
#        os.mkdir(os.path.join(prj_dir, package, store))

    return os.path.join(prj_dir, package)


def checkout_package(apiurl, project, package,
                     revision=None, pathname=None, prj_obj=None,
                     expand_link=False, prj_dir=None, server_service_files = None, service_files=None, progress_obj=None, size_limit=None, meta=False):
    try:
        # the project we're in might be deleted.
        # that'll throw an error then.
        olddir = os.getcwd()
    except:
        olddir = os.environ.get("PWD")

    if not prj_dir:
        prj_dir = olddir
    else:
        if sys.platform[:3] == 'win':
            prj_dir = prj_dir[:2] + prj_dir[2:].replace(':', ';')
        else:
            if conf.config['checkout_no_colon']:
                prj_dir = prj_dir.replace(':', '/')

    root_dots = '.'
    if conf.config['checkout_rooted']:
        if prj_dir[:1] == '/':
            if conf.config['verbose'] > 1:
              print "checkout_rooted ignored for %s" % prj_dir
            # ?? should we complain if not is_project_dir(prj_dir) ??
        else:
            # if we are inside a project or package dir, ascend to parent
            # directories, so that all projects are checked out relative to
            # the same root.
            if is_project_dir(".."):
                # if we are in a package dir, goto parent.
                # Hmm, with 'checkout_no_colon' in effect, we have directory levels that
                # do not easily reveal the fact, that they are part of a project path.
                # At least this test should find that the parent of 'home/username/branches' 
                #  is a project (hack alert). Also goto parent in this case.
                root_dots = "../"
            elif is_project_dir("../.."):
                # testing two levels is better than one.
                # May happen in case of checkout_no_colon, or 
                # if project roots were previously inconsistent 
                root_dots = "../../"
            if is_project_dir(root_dots):
                if conf.config['checkout_no_colon']:
                    oldproj = store_read_project(root_dots)
                    n = len(oldproj.split(':'))
                else:
                    n = 1
                root_dots = root_dots + "../" * n

    if root_dots != '.':
        if conf.config['verbose']:
            print "found root of %s at %s" % (oldproj, root_dots)
        prj_dir = root_dots + prj_dir

    if not pathname:
        pathname = getTransActPath(os.path.join(prj_dir, package))

    # before we create directories and stuff, check if the package actually
    # exists
    show_package_meta(apiurl, project, package, meta)

    isfrozen = False
    if expand_link:
        # try to read from the linkinfo
        # if it is a link we use the xsrcmd5 as the revision to be
        # checked out
        try:
            x = show_upstream_xsrcmd5(apiurl, project, package, revision=revision, meta=meta, include_service_files=server_service_files)
        except:
            x = show_upstream_xsrcmd5(apiurl, project, package, revision=revision, meta=meta, linkrev='base', include_service_files=server_service_files)
            if x:
                isfrozen = True
        if x:
            revision = x
    directory = make_dir(apiurl, project, package, pathname, prj_dir, conf.config['do_package_tracking'])
    p = Package.init_package(apiurl, project, package, directory, size_limit, meta, progress_obj)
    if isfrozen:
        p.mark_frozen()
    if conf.config['do_package_tracking']:
        # check if we can re-use an existing project object
        if prj_obj is None:
            prj_obj = Project(prj_dir)
        prj_obj.set_state(p.name, ' ')
        prj_obj.write_packages()
    p.update(revision, server_service_files, size_limit)
    if service_files:
        print 'Running all source services local'
        p.run_source_services()

def replace_pkg_meta(pkgmeta, new_name, new_prj, keep_maintainers = False,
                     dst_userid = None, keep_develproject = False):
    """
    update pkgmeta with new new_name and new_prj and set calling user as the
    only maintainer (unless keep_maintainers is set). Additionally remove the
    develproject entry (<devel />) unless keep_develproject is true.
    """
    root = ET.fromstring(''.join(pkgmeta))
    root.set('name', new_name)
    root.set('project', new_prj)
    if not keep_maintainers:
        for person in root.findall('person'):
            root.remove(person)
    if not keep_develproject:
        for dp in root.findall('devel'):
            root.remove(dp)
    return ET.tostring(root)

def link_to_branch(apiurl, project,  package):
    """
     convert a package with a _link + project.diff to a branch
    """

    if '_link' in meta_get_filelist(apiurl, project, package):
        u = makeurl(apiurl, ['source', project, package], 'cmd=linktobranch')
        http_POST(u)
    else:
        raise oscerr.OscIOError(None, 'no _link file inside project \'%s\' package \'%s\'' % (project, package))

def link_pac(src_project, src_package, dst_project, dst_package, force, rev='', cicount='', disable_publish = False):
    """
    create a linked package
     - "src" is the original package
     - "dst" is the "link" package that we are creating here
    """
    meta_change = False
    dst_meta = ''
    apiurl = conf.config['apiurl']
    try:
        dst_meta = meta_exists(metatype='pkg',
                               path_args=(quote_plus(dst_project), quote_plus(dst_package)),
                               template_args=None,
                               create_new=False, apiurl=apiurl)
        root = ET.fromstring(''.join(dst_meta))
        if root.get('project') != dst_project:
            # The source comes from a different project via a project link, we need to create this instance
            meta_change = True
    except:
        meta_change = True

    if meta_change:
        src_meta = show_package_meta(apiurl, src_project, src_package)
        dst_meta = replace_pkg_meta(src_meta, dst_package, dst_project)

    if disable_publish:
        meta_change = True
        root = ET.fromstring(''.join(dst_meta))
        elm = root.find('publish')
        if not elm:
            elm = ET.SubElement(root, 'publish')
        elm.clear()
        ET.SubElement(elm, 'disable')
        dst_meta = ET.tostring(root)

    if meta_change:
        edit_meta('pkg',
                  path_args=(dst_project, dst_package),
                  data=dst_meta)
    # create the _link file
    # but first, make sure not to overwrite an existing one
    if '_link' in meta_get_filelist(apiurl, dst_project, dst_package):
        if force:
            print >>sys.stderr, 'forced overwrite of existing _link file'
        else:
            print >>sys.stderr
            print >>sys.stderr, '_link file already exists...! Aborting'
            sys.exit(1)

    if rev:
        rev = 'rev="%s"' % rev
    else:
        rev = ''

    if cicount:
        cicount = 'cicount="%s"' % cicount
    else:
        cicount = ''

    print 'Creating _link...',

    project = ''
    if src_project != dst_project:
        project = 'project="%s"' % src_project

    link_template = """\
<link %s package="%s" %s %s>
<patches>
  <!-- <apply name="patch" /> apply a patch on the source directory  -->
  <!-- <topadd>%%define build_with_feature_x 1</topadd> add a line on the top (spec file only) -->
  <!-- <add>file.patch</add> add a patch to be applied after %%setup (spec file only) -->
  <!-- <delete>filename</delete> delete a file -->
</patches>
</link>
""" % (project, src_package, rev, cicount)

    u = makeurl(apiurl, ['source', dst_project, dst_package, '_link'])
    http_PUT(u, data=link_template)
    print 'Done.'

def aggregate_pac(src_project, src_package, dst_project, dst_package, repo_map = {}, disable_publish = False, nosources = False):
    """
    aggregate package
     - "src" is the original package
     - "dst" is the "aggregate" package that we are creating here
     - "map" is a dictionary SRC => TARGET repository mappings
    """
    meta_change = False
    dst_meta = ''
    apiurl = conf.config['apiurl']
    try:
        dst_meta = meta_exists(metatype='pkg',
                               path_args=(quote_plus(dst_project), quote_plus(dst_package)),
                               template_args=None,
                               create_new=False, apiurl=apiurl)
        root = ET.fromstring(''.join(dst_meta))
        if root.get('project') != dst_project:
            # The source comes from a different project via a project link, we need to create this instance
            meta_change = True
    except:
        meta_change = True

    if meta_change:
        src_meta = show_package_meta(apiurl, src_project, src_package)
        dst_meta = replace_pkg_meta(src_meta, dst_package, dst_project)
        meta_change = True

    if disable_publish:
        meta_change = True
        root = ET.fromstring(''.join(dst_meta))
        elm = root.find('publish')
        if not elm:
            elm = ET.SubElement(root, 'publish')
        elm.clear()
        ET.SubElement(elm, 'disable')
        dst_meta = ET.tostring(root)
    if meta_change:
        edit_meta('pkg',
                  path_args=(dst_project, dst_package),
                  data=dst_meta)

    # create the _aggregate file
    # but first, make sure not to overwrite an existing one
    if '_aggregate' in meta_get_filelist(apiurl, dst_project, dst_package):
        print >>sys.stderr
        print >>sys.stderr, '_aggregate file already exists...! Aborting'
        sys.exit(1)

    print 'Creating _aggregate...',
    aggregate_template = """\
<aggregatelist>
  <aggregate project="%s">
""" % (src_project)

    aggregate_template += """\
    <package>%s</package>
""" % ( src_package)

    if nosources:
        aggregate_template += """\
    <nosources />
"""
    for src, tgt in repo_map.iteritems():
        aggregate_template += """\
    <repository target="%s" source="%s" />
""" % (tgt, src)

    aggregate_template += """\
  </aggregate>
</aggregatelist>
"""

    u = makeurl(apiurl, ['source', dst_project, dst_package, '_aggregate'])
    http_PUT(u, data=aggregate_template)
    print 'Done.'


def attribute_branch_pkg(apiurl, attribute, maintained_update_project_attribute, package, targetproject, return_existing=False, force=False, noaccess=False):
    """
    Branch packages defined via attributes (via API call)
    """
    query = { 'cmd': 'branch' }
    query['attribute'] = attribute
    if targetproject:
        query['target_project'] = targetproject
    if force:
        query['force'] = "1"
    if noaccess:
        query['noaccess'] = "1"
    if package:
        query['package'] = package
    if maintained_update_project_attribute:
        query['update_project_attribute'] = maintained_update_project_attribute

    u = makeurl(apiurl, ['source'], query=query)
    f = None
    try:
        f = http_POST(u)
    except urllib2.HTTPError, e:
        msg = ''.join(e.readlines())
        msg = msg.split('<summary>')[1]
        msg = msg.split('</summary>')[0]
        raise oscerr.APIError(msg)

    r = f.read()
    r = r.split('targetproject">')[1]
    r = r.split('</data>')[0]
    return r


def branch_pkg(apiurl, src_project, src_package, nodevelproject=False, rev=None, target_project=None, target_package=None, return_existing=False, msg='', force=False, noaccess=False):
    """
    Branch a package (via API call)
    """
    query = { 'cmd': 'branch' }
    if nodevelproject:
        query['ignoredevel'] = '1'
    if force:
        query['force'] = '1'
    if noaccess:
        query['noaccess'] = '1'
    if rev:
        query['rev'] = rev
    if target_project:
        query['target_project'] = target_project
    if target_package:
        query['target_package'] = target_package
    if msg:
        query['comment'] = msg
    u = makeurl(apiurl, ['source', src_project, src_package], query=query)
    try:
        f = http_POST(u)
    except urllib2.HTTPError, e:
        if not return_existing:
            raise
        root = ET.fromstring(e.read())
        summary = root.find('summary')
        if summary is None:
            raise oscerr.APIError('unexpected response:\n%s' % ET.tostring(root))
        m = re.match(r"branch target package already exists: (\S+)/(\S+)", summary.text)
        if not m:
            e.msg += '\n' + summary.text
            raise
        return (True, m.group(1), m.group(2), None, None)

    data = {}
    for i in ET.fromstring(f.read()).findall('data'):
        data[i.get('name')] = i.text
    return (False, data.get('targetproject', None), data.get('targetpackage', None),
            data.get('sourceproject', None), data.get('sourcepackage', None))


def copy_pac(src_apiurl, src_project, src_package,
             dst_apiurl, dst_project, dst_package,
             client_side_copy = False,
             keep_maintainers = False,
             keep_develproject = False,
             expand = False,
             revision = None,
             comment = None):
    """
    Create a copy of a package.

    Copying can be done by downloading the files from one package and commit
    them into the other by uploading them (client-side copy) --
    or by the server, in a single api call.
    """

    if not (src_apiurl == dst_apiurl and src_project == dst_project \
        and src_package == dst_package):
        src_meta = show_package_meta(src_apiurl, src_project, src_package)
        dst_userid = conf.get_apiurl_usr(dst_apiurl)
        src_meta = replace_pkg_meta(src_meta, dst_package, dst_project, keep_maintainers,
                                    dst_userid, keep_develproject)

        print 'Sending meta data...'
        u = makeurl(dst_apiurl, ['source', dst_project, dst_package, '_meta'])
        http_PUT(u, data=src_meta)

    print 'Copying files...'
    if not client_side_copy:
        query = {'cmd': 'copy', 'oproject': src_project, 'opackage': src_package }
        if expand:
            query['expand'] = '1'
        if revision:
            query['orev'] = revision
        if comment:
            query['comment'] = comment
        u = makeurl(dst_apiurl, ['source', dst_project, dst_package], query=query)
        f = http_POST(u)
        return f.read()

    else:
        # copy one file after the other
        import tempfile
        query = {'rev': 'upload'}
        revision = show_upstream_srcmd5(src_apiurl, src_project, src_package, expand=expand, revision=revision)
        for n in meta_get_filelist(src_apiurl, src_project, src_package, expand=expand, revision=revision):
            if n.startswith('_service:') or n.startswith('_service_'):
                continue
            print '  ', n
            tmpfile = None
            try:
                (fd, tmpfile) = tempfile.mkstemp(prefix='osc-copypac')
                get_source_file(src_apiurl, src_project, src_package, n, targetfilename=tmpfile, revision=revision)
                u = makeurl(dst_apiurl, ['source', dst_project, dst_package, pathname2url(n)], query=query)
                http_PUT(u, file = tmpfile)
            finally:
                if not tmpfile is None:
                    os.unlink(tmpfile)
        if comment:
            query['comment'] = comment
        query['cmd'] = 'commit'
        u = makeurl(dst_apiurl, ['source', dst_project, dst_package], query=query)
        http_POST(u)
        return 'Done.'


def undelete_package(apiurl, prj, pac, msg=None):
    query={'cmd': 'undelete'}
    if msg:
        query['comment'] = msg
    else:
        query['comment'] = 'undeleted via osc'
    u = makeurl(apiurl, ['source', prj, pac], query)
    http_POST(u)

def undelete_project(apiurl, prj, msg=None):
    query={'cmd': 'undelete'}
    if msg:
        query['comment'] = msg
    else:
        query['comment'] = 'undeleted via osc'
    u = makeurl(apiurl, ['source', prj], query)
    http_POST(u)


def delete_package(apiurl, prj, pac, force=False, msg=None):
    query = {}
    if force:
        query['force'] = "1"
    u = makeurl(apiurl, ['source', prj, pac], query)
    http_DELETE(u)

def delete_project(apiurl, prj, force=False, msg=None):
    query = {}
    if force:
        query['force'] = "1"
    if msg:
        query['comment'] = msg
    u = makeurl(apiurl, ['source', prj], query)
    http_DELETE(u)

def delete_files(apiurl, prj, pac, files):
    for filename in files:
        u = makeurl(apiurl, ['source', prj, pac, filename], query={'comment': 'removed %s' % (filename, )})
        http_DELETE(u)


# old compat lib call
def get_platforms(apiurl):
    return get_repositories(apiurl)

def get_repositories(apiurl):
    f = http_GET(makeurl(apiurl, ['platform']))
    tree = ET.parse(f)
    r = [ node.get('name') for node in tree.getroot() ]
    r.sort()
    return r


def get_distibutions(apiurl, discon=False):
    r = []

    # FIXME: this is just a naming convention on api.opensuse.org, but not a general valid apparoach
    if discon:
        result_line_templ = '%(name)-25s %(project)s'
        f = http_GET(makeurl(apiurl, ['build']))
        root = ET.fromstring(''.join(f))

        for node in root.findall('entry'):
            if node.get('name').startswith('DISCONTINUED:'):
                rmap = {}
                rmap['name'] = node.get('name').replace('DISCONTINUED:','').replace(':', ' ')
                rmap['project'] = node.get('name')
                r.append (result_line_templ % rmap)

        r.insert(0,'distribution              project')
        r.insert(1,'------------              -------')

    else:
        result_line_templ = '%(name)-25s %(project)-25s %(repository)-25s %(reponame)s'
        f = http_GET(makeurl(apiurl, ['distributions']))
        root = ET.fromstring(''.join(f))

        for node in root.findall('distribution'):
            rmap = {}
            for node2 in node.findall('name'):
                rmap['name'] = node2.text
            for node3 in node.findall('project'):
                rmap['project'] = node3.text
            for node4 in node.findall('repository'):
                rmap['repository'] = node4.text
            for node5 in node.findall('reponame'):
                rmap['reponame'] = node5.text
            r.append(result_line_templ % rmap)

        r.insert(0,'distribution              project                   repository                reponame')
        r.insert(1,'------------              -------                   ----------                --------')

    return r


# old compat lib call
def get_platforms_of_project(apiurl, prj):
    return get_repositories_of_project(apiurl, prj)

def get_repositories_of_project(apiurl, prj):
    f = show_project_meta(apiurl, prj)
    root = ET.fromstring(''.join(f))

    r = [ node.get('name') for node in root.findall('repository')]
    return r


class Repo:
    repo_line_templ = '%-15s %-10s'

    def __init__(self, name, arch):
        self.name = name
        self.arch = arch

    def __str__(self):
        return self.repo_line_templ % (self.name, self.arch)

def get_repos_of_project(apiurl, prj):
    f = show_project_meta(apiurl, prj)
    root = ET.fromstring(''.join(f))

    for node in root.findall('repository'):
        for node2 in node.findall('arch'):
            yield Repo(node.get('name'), node2.text)

def get_binarylist(apiurl, prj, repo, arch, package=None, verbose=False):
    what = package or '_repository'
    u = makeurl(apiurl, ['build', prj, repo, arch, what])
    f = http_GET(u)
    tree = ET.parse(f)
    if not verbose:
        return [ node.get('filename') for node in tree.findall('binary')]
    else:
        l = []
        for node in tree.findall('binary'):
            f = File(node.get('filename'),
                     None,
                     int(node.get('size')),
                     int(node.get('mtime')))
            l.append(f)
        return l


def get_binarylist_published(apiurl, prj, repo, arch):
    u = makeurl(apiurl, ['published', prj, repo, arch])
    f = http_GET(u)
    tree = ET.parse(f)
    r = [ node.get('name') for node in tree.findall('entry')]
    return r


def show_results_meta(apiurl, prj, package=None, lastbuild=None, repository=[], arch=[]):
    query = {}
    if package:
        query['package'] = package
    if lastbuild:
        query['lastbuild'] = 1
    u = makeurl(apiurl, ['build', prj, '_result'], query=query)
    for repo in repository:
        u = u + '&repository=%s' % repo
    for a in arch:
        u = u + '&arch=%s' % a
    f = http_GET(u)
    return f.readlines()


def show_prj_results_meta(apiurl, prj):
    u = makeurl(apiurl, ['build', prj, '_result'])
    f = http_GET(u)
    return f.readlines()


def get_package_results(apiurl, prj, package, lastbuild=None, repository=[], arch=[]):
    """ return a package results as a list of dicts """
    r = []

    f = show_results_meta(apiurl, prj, package, lastbuild, repository, arch)
    root = ET.fromstring(''.join(f))

    for node in root.findall('result'):
        rmap = {}
        rmap['project'] = rmap['prj'] = prj
        rmap['pkg'] = rmap['package'] = rmap['pac'] = package
        rmap['repository'] = rmap['repo'] = rmap['rep'] = node.get('repository')
        rmap['arch'] = node.get('arch')
        rmap['state'] = node.get('state')
        rmap['dirty'] = node.get('dirty')

        rmap['details'] = ''
        statusnode =  node.find('status')
        if statusnode != None:
            rmap['code'] = statusnode.get('code', '')
        else:
            rmap['code'] = ''

        if rmap['code'] in ('unresolvable', 'expansion error', 'broken', 'blocked', 'finished'):
            details = statusnode.find('details')
            if details != None:
                rmap['details'] = details.text

        rmap['dirty'] = rmap['dirty'] == 'true'

        r.append(rmap)
    return r

def format_results(results, format):
    """apply selected format on each dict in results and return it as a list of strings"""
    return [format % r for r in results]

def get_results(apiurl, prj, package, lastbuild=None, repository=[], arch=[], verbose=False):
    r = []
    result_line_templ = '%(rep)-20s %(arch)-10s %(status)s'

    for res in get_package_results(apiurl, prj, package, lastbuild, repository, arch):
        res['status'] = res['code']
        if verbose and res['details'] != '':
            if res['status'] in ('unresolvable', 'expansion error'):
                lines = res['details'].split(',')
                res['status'] += ': ' + '\n     '.join(lines)

            else:
                res['status'] += ': %s' % (res['details'], )
        if res['dirty']:
            if verbose:
                res['status'] = 'outdated (was: %s)' % res['status']
            else:
                res['status'] += '*'

        r.append(result_line_templ % res)

    return r

def get_prj_results(apiurl, prj, hide_legend=False, csv=False, status_filter=None, name_filter=None, arch=None, repo=None, vertical=None, show_excluded=None):
    #print '----------------------------------------'
    global buildstatus_symbols

    r = []

    f = show_prj_results_meta(apiurl, prj)
    root = ET.fromstring(''.join(f))

    pacs = []
    # sequence of (repo,arch) tuples
    targets = []
    # {package: {(repo,arch): status}}
    status = {}
    if root.find('result') == None:
        return []
    for results in root.findall('result'):
        for node in results:
            pacs.append(node.get('package'))
    pacs = sorted(list(set(pacs)))
    for node in root.findall('result'):
        # filter architecture and repository
        if arch != None and node.get('arch') not in arch:
            continue
        if repo != None and node.get('repository') not in repo:
            continue
        if node.get('dirty') == "true":
            state = "outdated"
        else:
            state = node.get('state')
        tg = (node.get('repository'), node.get('arch'), state)
        targets.append(tg)
        for pacnode in node.findall('status'):
            pac = pacnode.get('package')
            if pac not in status:
                status[pac] = {}
            status[pac][tg] = pacnode.get('code')
    targets.sort()

    # filter option
    if status_filter or name_filter or not show_excluded:

        pacs_to_show = []
        targets_to_show = []

        #filtering for Package Status
        if status_filter:
            if status_filter in buildstatus_symbols.values():
                for txt, sym in buildstatus_symbols.items():
                    if sym == status_filter:
                        filt_txt = txt
                for pkg in status.keys():
                    for repo in status[pkg].keys():
                        if status[pkg][repo] == filt_txt:
                            if not name_filter:
                                pacs_to_show.append(pkg)
                                targets_to_show.append(repo)
                            elif name_filter in pkg:
                                pacs_to_show.append(pkg)

        #filtering for Package Name
        elif name_filter:
            for pkg in pacs:
                if name_filter in pkg:
                    pacs_to_show.append(pkg)

        #filter non building states
        elif not show_excluded:
            enabled = {}
            for pkg in status.keys():
                showpkg = False
                for repo in status[pkg].keys():
                    if status[pkg][repo] != "excluded":
                        enabled[repo] = 1
                        showpkg = True

                if showpkg:
                    pacs_to_show.append(pkg)

            targets_to_show = enabled.keys()

        pacs = [ i for i in pacs if i in pacs_to_show ]
        if len(targets_to_show):
            targets = [ i for i in targets if i in targets_to_show ]

    # csv output
    if csv:
        # TODO: option to disable the table header
        row = ['_'] + ['/'.join(tg) for tg in targets]
        r.append(';'.join(row))
        for pac in pacs:
            row = [pac] + [status[pac][tg] for tg in targets]
            r.append(';'.join(row))
        return r

    if not vertical:
        # human readable output
        max_pacs = 40
        for startpac in range(0, len(pacs), max_pacs):
            offset = 0
            for pac in pacs[startpac:startpac+max_pacs]:
                r.append(' |' * offset + ' ' + pac)
                offset += 1

            for tg in targets:
                line = []
                line.append(' ')
                for pac in pacs[startpac:startpac+max_pacs]:
                    st = ''
                    if not status.has_key(pac) or not status[pac].has_key(tg):
                        # for newly added packages, status may be missing
                        st = '?'
                    else:
                        try:
                            st = buildstatus_symbols[status[pac][tg]]
                        except:
                            print 'osc: warn: unknown status \'%s\'...' % status[pac][tg]
                            print 'please edit osc/core.py, and extend the buildstatus_symbols dictionary.'
                            st = '?'
                            buildstatus_symbols[status[pac][tg]] = '?'
                    line.append(st)
                    line.append(' ')
                line.append(' %s %s (%s)' % tg)
                line = ''.join(line)

                r.append(line)

            r.append('')
    else:
        offset = 0
        for tg in targets:
            r.append('| ' * offset + '%s %s (%s)'%tg )
            offset += 1

        for pac in pacs:
            line = []
            for tg in targets:
                st = ''
                if not status.has_key(pac) or not status[pac].has_key(tg):
                    # for newly added packages, status may be missing
                    st = '?'
                else:
                    try:
                        st = buildstatus_symbols[status[pac][tg]]
                    except:
                        print 'osc: warn: unknown status \'%s\'...' % status[pac][tg]
                        print 'please edit osc/core.py, and extend the buildstatus_symbols dictionary.'
                        st = '?'
                        buildstatus_symbols[status[pac][tg]] = '?'
                line.append(st)
            line.append(' '+pac)
            r.append(' '.join(line))

        line = []
        for i in range(0, len(targets)):
            line.append(str(i%10))
        r.append(' '.join(line))

        r.append('')

    if not hide_legend and len(pacs):
        r.append(' Legend:')
        legend = []
        for i, j in buildstatus_symbols.items():
            if i == "expansion error":
                continue
            legend.append('%3s %-20s' % (j, i))

        if vertical:
            for i in range(0, len(targets)):
                s = '%1d %s %s (%s)' % (i%10, targets[i][0], targets[i][1], targets[i][2])
                if i < len(legend):
                    legend[i] += s
                else:
                    legend.append(' '*24 + s)

        r += legend

    return r


def streamfile(url, http_meth = http_GET, bufsize=8192, data=None, progress_obj=None, text=None):
    """
    performs http_meth on url and read bufsize bytes from the response
    until EOF is reached. After each read bufsize bytes are yielded to the
    caller.
    """
    cl = ''
    retries = 0
    # Repeat requests until we get reasonable Content-Length header
    # Server (or iChain) is corrupting data at some point, see bnc#656281
    while cl == '':
        if retries >= int(conf.config['http_retries']):
            raise oscerr.OscIOError(None, 'Content-Length is empty for %s, protocol violation' % url)
        retries = retries + 1
        if retries > 1 and conf.config['http_debug']:
            print >>sys.stderr, '\n\nRetry %d --' % (retries - 1), url
        f = http_meth.__call__(url, data = data)
        cl = f.info().get('Content-Length')

    if cl is not None:
        cl = int(cl)

    if progress_obj:
        import urlparse
        basename = os.path.basename(urlparse.urlsplit(url)[2])
        progress_obj.start(basename=basename, text=text, size=cl)
    data = f.read(bufsize)
    read = len(data)
    while len(data):
        if progress_obj:
            progress_obj.update(read)
        yield data
        data = f.read(bufsize)
        read += len(data)
    if progress_obj:
        progress_obj.end(read)
    f.close()

    if not cl is None and read != cl:
        raise oscerr.OscIOError(None, 'Content-Length is not matching file size for %s: %i vs %i file size' % (url, cl, read))


def print_buildlog(apiurl, prj, package, repository, arch, offset = 0):
    """prints out the buildlog on stdout"""
    query = {'nostream' : '1', 'start' : '%s' % offset}
    while True:
        query['start'] = offset
        start_offset = offset
        u = makeurl(apiurl, ['build', prj, repository, arch, package, '_log'], query=query)
        for data in streamfile(u):
            offset += len(data)
            sys.stdout.write(data)
        if start_offset == offset:
            break

def get_dependson(apiurl, project, repository, arch, packages=None, reverse=None):
    query = []
    if packages:
        for i in packages:
            query.append('package=%s' % quote_plus(i))

    if reverse:
        query.append('view=revpkgnames')
    else:
        query.append('view=pkgnames')

    u = makeurl(apiurl, ['build', project, repository, arch, '_builddepinfo'], query=query)
    f = http_GET(u)
    return f.read()

def get_buildinfo(apiurl, prj, package, repository, arch, specfile=None, addlist=None):
    query = []
    if addlist:
        for i in addlist:
            query.append('add=%s' % quote_plus(i))

    u = makeurl(apiurl, ['build', prj, repository, arch, package, '_buildinfo'], query=query)

    if specfile:
        f = http_POST(u, data=specfile)
    else:
        f = http_GET(u)
    return f.read()


def get_buildconfig(apiurl, prj, repository):
    u = makeurl(apiurl, ['build', prj, repository, '_buildconfig'])
    f = http_GET(u)
    return f.read()

 
def get_source_rev(apiurl, project, package, revision=None):
    # API supports ?deleted=1&meta=1&rev=4
    # but not rev=current,rev=latest,rev=top, or anything like this.
    # CAUTION: We have to loop through all rev and find the highest one, if none given.

    if revision:
      url = makeurl(apiurl, ['source', project, package, '_history'], {'rev':revision})
    else:
      url = makeurl(apiurl, ['source', project, package, '_history'])
    f = http_GET(url)
    xml = ET.parse(f)
    ent = None
    for new in xml.findall('revision'):
        # remember the newest one.
        if not ent:
            ent = new
        elif ent.find('time').text < new.find('time').text:
            ent = new
    if not ent:
        return { 'version': None, 'error':'empty revisionlist: no such package?' }
    e = {}
    for k in ent.keys():
         e[k] = ent.get(k)
    for k in list(ent):
         e[k.tag] = k.text
    return e

def get_buildhistory(apiurl, prj, package, repository, arch, format = 'text'):
    import time
    u = makeurl(apiurl, ['build', prj, repository, arch, package, '_history'])
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

        if format == 'csv':
            r.append('%s|%s|%d|%s.%d' % (t, srcmd5, rev, versrel, bcnt))
        else:
            r.append('%s   %s %6d    %s.%d' % (t, srcmd5, rev, versrel, bcnt))

    if format == 'text':
        r.insert(0, 'time                  srcmd5                              rev   vers-rel.bcnt')

    return r

def print_jobhistory(apiurl, prj, current_package, repository, arch, format = 'text', limit=20):
    import time
    query = {}
    if current_package:
        query['package'] = current_package
    if limit != None and int(limit) > 0:
        query['limit'] = int(limit)
    u = makeurl(apiurl, ['build', prj, repository, arch, '_jobhistory'], query )
    f = http_GET(u)
    root = ET.parse(f).getroot()

    if format == 'text':
        print "time                 package                                            reason           code              build time      worker"
    for node in root.findall('jobhist'):
        package = node.get('package')
        worker = node.get('workerid')
        reason = node.get('reason')
        if not reason:
            reason = "unknown"
        code = node.get('code')
        rt = int(node.get('readytime'))
        readyt = time.localtime(rt)
        readyt = time.strftime('%Y-%m-%d %H:%M:%S', readyt)
        st = int(node.get('starttime'))
        et = int(node.get('endtime'))
        endtime = time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(et))
        waittm = time.gmtime(et-st)
        if waittm.tm_hour:
            waitbuild = "%2dh %2dm %2ds" % (waittm.tm_hour, waittm.tm_min, waittm.tm_sec)
        else:
            waitbuild = "    %2dm %2ds" % (waittm.tm_min, waittm.tm_sec)

        if format == 'csv':
            print '%s|%s|%s|%s|%s|%s' % (endtime, package, reason, code, waitbuild, worker)
        else:
            print '%s  %-50s %-16s %-16s %-16s %-16s' % (endtime, package[0:49], reason[0:15], code[0:15], waitbuild, worker)


def get_commitlog(apiurl, prj, package, revision, format = 'text', meta = False, deleted = False):
    import time, locale

    query = {}
    if deleted:
        query['deleted'] = 1
    if meta:
        query['meta'] = 1

    u = makeurl(apiurl, ['source', prj, package, '_history'], query)
    f = http_GET(u)
    root = ET.parse(f).getroot()

    r = []
    if format == 'xml':
        r.append('<?xml version="1.0"?>')
        r.append('<log>')
    revisions = root.findall('revision')
    revisions.reverse()
    for node in revisions:
        srcmd5 = node.find('srcmd5').text
        try:
            rev = int(node.get('rev'))
            #vrev = int(node.get('vrev')) # what is the meaning of vrev?
            try:
                if revision and rev != int(revision):
                    continue
            except ValueError:
                if revision != srcmd5:
                    continue
        except ValueError:
            # this part should _never_ be reached but...
            return [ 'an unexpected error occured - please file a bug' ]
        version = node.find('version').text
        user = node.find('user').text
        try:
            comment = node.find('comment').text.encode(locale.getpreferredencoding(), 'replace')
        except:
            comment = '<no message>'
        try:
            requestid = node.find('requestid').text.encode(locale.getpreferredencoding(), 'replace')
        except:
            requestid = ""
        t = time.localtime(int(node.find('time').text))
        t = time.strftime('%Y-%m-%d %H:%M:%S', t)

        if format == 'csv':
            s = '%s|%s|%s|%s|%s|%s|%s' % (rev, user, t, srcmd5, version,
                comment.replace('\\', '\\\\').replace('\n', '\\n').replace('|', '\\|'), requestid)
            r.append(s)
        elif format == 'xml':
            r.append('<logentry')
            r.append('   revision="%s" srcmd5="%s">' % (rev, srcmd5))
            r.append('<author>%s</author>' % user)
            r.append('<date>%s</date>' % t)
            r.append('<requestid>%s</requestid>' % requestid)
            r.append('<msg>%s</msg>' %
                comment.replace('&', '&amp;').replace('<', '&gt;').replace('>', '&lt;'))
            r.append('</logentry>')
        else:
            if requestid:
                requestid="rq" + requestid
            s = '-' * 76 + \
                '\nr%s | %s | %s | %s | %s | %s\n' % (rev, user, t, srcmd5, version, requestid) + \
                '\n' + comment
            r.append(s)

    if format not in ['csv', 'xml']:
        r.append('-' * 76)
    if format == 'xml':
        r.append('</log>')
    return r


def runservice(apiurl, prj, package):
    u = makeurl(apiurl, ['source', prj, package], query={'cmd': 'runservice'})

    try:
        f = http_POST(u)
    except urllib2.HTTPError, e:
        e.osc_msg = 'could not trigger service run for project \'%s\' package \'%s\'' % (prj, package)
        raise

    root = ET.parse(f).getroot()
    return root.get('code')


def rebuild(apiurl, prj, package, repo, arch, code=None):
    query = { 'cmd': 'rebuild' }
    if package:
        query['package'] = package
    if repo:
        query['repository'] = repo
    if arch:
        query['arch'] = arch
    if code:
        query['code'] = code

    u = makeurl(apiurl, ['build', prj], query=query)
    try:
        f = http_POST(u)
    except urllib2.HTTPError, e:
        e.osc_msg = 'could not trigger rebuild for project \'%s\' package \'%s\'' % (prj, package)
        raise

    root = ET.parse(f).getroot()
    return root.get('code')


def store_read_project(dir):
    global store

    try:
        p = open(os.path.join(dir, store, '_project')).readlines()[0].strip()
    except IOError:
        msg = 'Error: \'%s\' is not an osc project dir or working copy' % os.path.abspath(dir)
        if os.path.exists(os.path.join(dir, '.svn')):
            msg += '\nTry svn instead of osc.'
        raise oscerr.NoWorkingCopy(msg)
    return p


def store_read_package(dir):
    global store

    try:
        p = open(os.path.join(dir, store, '_package')).readlines()[0].strip()
    except IOError:
        msg = 'Error: \'%s\' is not an osc package working copy' % os.path.abspath(dir)
        if os.path.exists(os.path.join(dir, '.svn')):
            msg += '\nTry svn instead of osc.'
        raise oscerr.NoWorkingCopy(msg)
    return p

def store_read_apiurl(dir, defaulturl=True):
    global store

    fname = os.path.join(dir, store, '_apiurl')
    try:
        url = open(fname).readlines()[0].strip()
        # this is needed to get a proper apiurl
        # (former osc versions may stored an apiurl with a trailing slash etc.)
        apiurl = conf.urljoin(*conf.parse_apisrv_url(None, url))
    except:
        if not defaulturl:
            if is_project_dir(dir):
                project = store_read_project(dir)
                package = None
            elif is_package_dir(dir):
                project = store_read_project(dir)
                package = None
            else:
                msg = 'Error: \'%s\' is not an osc package working copy' % os.path.abspath(dir)
                raise oscerr.NoWorkingCopy(msg)
            msg = 'Your working copy \'%s\' is in an inconsistent state.\n' \
                'Please run \'osc repairwc %s\' (Note this might _remove_\n' \
                'files from the .osc/ dir). Please check the state\n' \
                'of the working copy afterwards (via \'osc status %s\')' % (dir, dir, dir)
            raise oscerr.WorkingCopyInconsistent(project, package, ['_apiurl'], msg)
        apiurl = conf.config['apiurl']
    return apiurl

def store_write_string(dir, file, string, subdir=''):
    global store

    if subdir and not os.path.isdir(os.path.join(dir, store, subdir)):
        os.mkdir(os.path.join(dir, store, subdir))
    fname = os.path.join(dir, store, subdir, file)
    try:
        f = open(fname + '.new', 'w')
        f.write(string)
        f.close()
        os.rename(fname + '.new', fname)
    except:
        if os.path.exists(fname + '.new'):
            os.unlink(fname + '.new')
        raise

def store_write_project(dir, project):
    store_write_string(dir, '_project', project + '\n')

def store_write_apiurl(dir, apiurl):
    store_write_string(dir, '_apiurl', apiurl + '\n')

def store_unlink_file(dir, file):
    global store

    try: os.unlink(os.path.join(dir, store, file))
    except: pass

def store_read_file(dir, file):
    global store

    try:
        content = open(os.path.join(dir, store, file)).read()
        return content
    except:
        return None

def store_write_initial_packages(dir, project, subelements):
    global store

    fname = os.path.join(dir, store, '_packages')
    root = ET.Element('project', name=project)
    for elem in subelements:
        root.append(elem)
    ET.ElementTree(root).write(fname)

def get_osc_version():
    return __version__


def abortbuild(apiurl, project, package=None, arch=None, repo=None):
    query = { 'cmd': 'abortbuild' }
    if package:
        query['package'] = package
    if arch:
        query['arch'] = arch
    if repo:
        query['repository'] = repo
    u = makeurl(apiurl, ['build', project], query)
    try:
        f = http_POST(u)
    except urllib2.HTTPError, e:
        e.osc_msg = 'abortion failed for project %s' % project
        if package:
            e.osc_msg += ' package %s' % package
        if arch:
            e.osc_msg += ' arch %s' % arch
        if repo:
            e.osc_msg += ' repo %s' % repo
        raise

    root = ET.parse(f).getroot()
    return root.get('code')


def wipebinaries(apiurl, project, package=None, arch=None, repo=None, code=None):
    query = { 'cmd': 'wipe' }
    if package:
        query['package'] = package
    if arch:
        query['arch'] = arch
    if repo:
        query['repository'] = repo
    if code:
        query['code'] = code

    u = makeurl(apiurl, ['build', project], query)
    try:
        f = http_POST(u)
    except urllib2.HTTPError, e:
        e.osc_msg = 'wipe binary rpms failed for project %s' % project
        if package:
            e.osc_msg += ' package %s' % package
        if arch:
            e.osc_msg += ' arch %s' % arch
        if repo:
            e.osc_msg += ' repository %s' % repo
        if code:
            e.osc_msg += ' code=%s' % code
        raise

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
            elif string.isalnum() and len(string) == 32:
                # could be an md5sum
                return string, None
            else:
                print >>sys.stderr, 'your revision \'%s\' will be ignored' % string
                return None, None
    else:
        return None, None

def checkRevision(prj, pac, revision, apiurl=None, meta=False):
    """
    check if revision is valid revision, i.e. it is not
    larger than the upstream revision id
    """
    if len(revision) == 32:
        # there isn't a way to check this kind of revision for validity
        return True
    if not apiurl:
        apiurl = conf.config['apiurl']
    try:
        if int(revision) > int(show_upstream_rev(apiurl, prj, pac, meta)) \
           or int(revision) <= 0:
            return False
        else:
            return True
    except (ValueError, TypeError):
        return False

def build_table(col_num, data = [], headline = [], width=1, csv = False):
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
    if headline and not csv:
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
            i = 0
            row = []
            table.append(row)
        # there is no need to justify the entries of the last column
        # or when generating csv
        if i == col_num -1 or csv:
            row.append(itm)
        else:
            row.append(itm.ljust(longest_col[i]))
        i += 1
    if csv:
        separator = '|'
    else:
        separator = ''
    return [separator.join(row) for row in table]

def xpath_join(expr, new_expr, op='or', inner=False, nexpr_parentheses=False):
    """
    Join two xpath expressions. If inner is False expr will
    be surrounded with parentheses (unless it's not already
    surrounded). If nexpr_parentheses is True new_expr will be
    surrounded with parentheses.
    """
    if not expr:
        return new_expr
    elif not new_expr:
        return expr
    # NOTE: this is NO syntax check etc. (e.g. if a literal contains a '(' or ')'
    #       the check might fail and expr will be surrounded with parentheses or NOT)
    parentheses = not inner
    if not inner and expr.startswith('(') and expr.endswith(')'):
        parentheses = False
        braces = [i for i in expr if i == '(' or i == ')']
        closed = 0
        while len(braces):
            if braces.pop() == ')':
                closed += 1
                continue
            else:
                closed += -1
            while len(braces):
                if braces.pop() == '(':
                    closed += -1
                else:
                    closed += 1
            if closed != 0:
                parentheses = True
                break
    if parentheses:
        expr = '(%s)' % expr
    if nexpr_parentheses:
        new_expr = '(%s)' % new_expr
    return '%s %s %s' % (expr, op, new_expr)

def search(apiurl, **kwargs):
    """
    Perform a search request. The requests are constructed as follows:
    kwargs = {'kind1' => xpath1, 'kind2' => xpath2, ..., 'kindN' => xpathN}
    GET /search/kind1?match=xpath1
    ...
    GET /search/kindN?match=xpathN
    """
    res = {}
    for urlpath, xpath in kwargs.iteritems():
        u = makeurl(apiurl, ['search', urlpath], ['match=%s' % quote_plus(xpath)])
        f = http_GET(u)
        res[urlpath] = ET.parse(f).getroot()
    return res

def set_link_rev(apiurl, project, package, revision='', expand=False, baserev=False):
    """
    updates the rev attribute of the _link xml. If revision is set to None
    the rev attribute is removed from the _link xml. If revision is set to ''
    the "plain" upstream revision is used (if xsrcmd5 and baserev aren't specified).
    """
    url = makeurl(apiurl, ['source', project, package, '_link'])
    try:
        f = http_GET(url)
        root = ET.parse(f).getroot()
    except urllib2.HTTPError, e:
        e.osc_msg = 'Unable to get _link file in package \'%s\' for project \'%s\'' % (package, project)
        raise

    # set revision element
    src_project = root.get('project', project)
    src_package = root.get('package', package)
    linkrev=None
    if baserev:
        linkrev = 'base'
        expand = True
    if revision is None:
        if 'rev' in root.keys():
            del root.attrib['rev']
    elif revision == '' or expand:
        revision = show_upstream_rev(apiurl, src_project, src_package, revision=revision, linkrev=linkrev, expand=expand)

    if revision:
        root.set('rev', revision)

    l = ET.tostring(root)
    http_PUT(url, data=l)


def delete_dir(dir):
    # small security checks
    if os.path.islink(dir):
        raise oscerr.OscIOError(None, 'cannot remove linked dir')
    elif os.path.abspath(dir) == '/':
        raise oscerr.OscIOError(None, 'cannot remove \'/\'')

    for dirpath, dirnames, filenames in os.walk(dir, topdown=False):
        for filename in filenames:
            os.unlink(os.path.join(dirpath, filename))
        for dirname in dirnames:
            os.rmdir(os.path.join(dirpath, dirname))
    os.rmdir(dir)


def delete_storedir(store_dir):
    """
    This method deletes a store dir.
    """
    head, tail = os.path.split(store_dir)
    if tail == '.osc':
        delete_dir(store_dir)

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
    if os.path.isdir(dir):
        os.chdir(dir)
    cmd = 'rpm2cpio %s | cpio -i %s &> /dev/null' % (srpm, ' '.join(files))
    ret = subprocess.call(cmd, shell=True)
    if ret != 0:
        print >>sys.stderr, 'error \'%s\' - cannot extract \'%s\'' % (ret, srpm)
        sys.exit(1)
    os.chdir(curdir)

def is_rpm(f):
    """check if the named file is an RPM package"""
    try:
        h = open(f, 'rb').read(4)
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
        h = open(f, 'rb').read(8)
    except:
        return False

    if h[7] == '\x01':
        return True
    else:
        return False

def addMaintainer(apiurl, prj, pac, user):
    # for backward compatibility only
    addPerson(apiurl, prj, pac, user)

def addPerson(apiurl, prj, pac, user, role="maintainer"):
    """ add a new person to a package or project """
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
        root = ET.fromstring(''.join(data))
        found = False
        for person in root.getiterator('person'):
            if person.get('userid') == user and person.get('role') == role:
                found = True
                print "user already exists"
                break
        if not found:
            # the xml has a fixed structure
            root.insert(2, ET.Element('person', role=role, userid=user))
            print 'user \'%s\' added to \'%s\'' % (user, pac or prj)
            edit_meta(metatype=kind,
                      path_args=path,
                      data=ET.tostring(root))
    else:
        print "osc: an error occured"

def delMaintainer(apiurl, prj, pac, user):
    # for backward compatibility only
    delPerson(apiurl, prj, pac, user)

def delPerson(apiurl, prj, pac, user, role="maintainer"):
    """ delete a person from a package or project """
    path = quote_plus(prj),
    kind = 'prj'
    if pac:
        path = path + (quote_plus(pac), )
        kind = 'pkg'
    data = meta_exists(metatype=kind,
                       path_args=path,
                       template_args=None,
                       create_new=False)
    if data and get_user_meta(apiurl, user) != None:
        root = ET.fromstring(''.join(data))
        found = False
        for person in root.getiterator('person'):
            if person.get('userid') == user and person.get('role') == role:
                root.remove(person)
                found = True
                print "user \'%s\' removed" % user
        if found:
            edit_meta(metatype=kind,
                      path_args=path,
                      data=ET.tostring(root))
        else:
            print "user \'%s\' not found in \'%s\'" % (user, pac or prj)
    else:
        print "an error occured"

def setDevelProject(apiurl, prj, pac, dprj, dpkg=None):
    """ set the <devel project="..."> element to package metadata"""
    path = (quote_plus(prj),) + (quote_plus(pac),)
    data = meta_exists(metatype='pkg',
                       path_args=path,
                       template_args=None,
                       create_new=False)

    if data and show_project_meta(apiurl, dprj) != None:
        root = ET.fromstring(''.join(data))
        if not root.find('devel') != None:
            ET.SubElement(root, 'devel')
        elem = root.find('devel')
        if dprj:
            elem.set('project', dprj)
        else:
            if 'project' in elem.keys():
                del elem.attrib['project']
        if dpkg:
            elem.set('package', dpkg)
        else:
            if 'package' in elem.keys():
                del elem.attrib['package']
        edit_meta(metatype='pkg',
                  path_args=path,
                  data=ET.tostring(root))
    else:
        print "osc: an error occured"

def createPackageDir(pathname, prj_obj=None):
    """
    create and initialize a new package dir in the given project.
    prj_obj can be a Project() instance.
    """
    prj_dir, pac_dir = getPrjPacPaths(pathname)
    if is_project_dir(prj_dir):
        global store
        if not os.path.exists(pac_dir+store):
            prj = prj_obj or Project(prj_dir, False)
            Package.init_package(prj.apiurl, prj.name, pac_dir, pac_dir)
            prj.addPackage(pac_dir)
            print statfrmt('A', os.path.normpath(pathname))
        else:
            raise oscerr.OscIOError(None, 'file or directory \'%s\' already exists' % pathname)
    else:
        msg = '\'%s\' is not a working copy' % prj_dir
        if os.path.exists(os.path.join(prj_dir, '.svn')):
            msg += '\ntry svn instead of osc.'
        raise oscerr.NoWorkingCopy(msg)


def stripETxml(node):
    node.tail = None
    if node.text != None:
        node.text = node.text.replace(" ", "").replace("\n", "")
    for child in node.getchildren():
        stripETxml(child)

def addGitSource(url):
    service_file = os.path.join(os.getcwd(), '_service')
    addfile = False
    if os.path.exists( service_file ):
        services = ET.parse(os.path.join(os.getcwd(), '_service')).getroot()
    else:
        services = ET.fromstring("<services />")
        addfile = True
    stripETxml( services )
    si = Serviceinfo()
    s = si.addGitUrl(services, url)
    s = si.addRecompressTar(services)
    si.read(s)

    # for pretty output
    xmlindent(s)
    f = open(service_file, 'wb')
    f.write(ET.tostring(s))
    f.close()
    if addfile:
       addFiles( ['_service'] )

def addDownloadUrlService(url):
    service_file = os.path.join(os.getcwd(), '_service')
    addfile = False
    if os.path.exists( service_file ):
        services = ET.parse(os.path.join(os.getcwd(), '_service')).getroot()
    else:
        services = ET.fromstring("<services />")
        addfile = True
    stripETxml( services )
    si = Serviceinfo()
    s = si.addDownloadUrl(services, url)
    si.read(s)

    # for pretty output
    xmlindent(s)
    f = open(service_file, 'wb')
    f.write(ET.tostring(s))
    f.close()
    if addfile:
       addFiles( ['_service'] )

    # download file
    path = os.getcwd()
    files = os.listdir(path)
    si.execute(path)
    newfiles = os.listdir(path)

    # add verify service for new files
    for filename in files:
       newfiles.remove(filename)

    for filename in newfiles:
       if filename.startswith('_service:download_url:'):
          s = si.addVerifyFile(services, filename)

    # for pretty output
    xmlindent(s)
    f = open(service_file, 'wb')
    f.write(ET.tostring(s))
    f.close()


def addFiles(filenames, prj_obj = None):
    for filename in filenames:
        if not os.path.exists(filename):
            raise oscerr.OscIOError(None, 'file \'%s\' does not exist' % filename)

    # init a package dir if we have a normal dir in the "filenames"-list
    # so that it will be find by findpacs() later
    pacs = list(filenames)
    for filename in filenames:
        prj_dir, pac_dir = getPrjPacPaths(filename)
        if not is_package_dir(filename) and os.path.isdir(filename) and is_project_dir(prj_dir) \
           and conf.config['do_package_tracking']:
            prj_name = store_read_project(prj_dir)
            prj_apiurl = store_read_apiurl(prj_dir, defaulturl=False)
            Package.init_package(prj_apiurl, prj_name, pac_dir, filename)
        elif is_package_dir(filename) and conf.config['do_package_tracking']:
            raise oscerr.PackageExists(store_read_project(filename), store_read_package(filename),
                                       'osc: warning: \'%s\' is already under version control' % filename)
        elif os.path.isdir(filename) and is_project_dir(prj_dir):
            raise oscerr.WrongArgs('osc: cannot add a directory to a project unless ' \
                                   '\'do_package_tracking\' is enabled in the configuration file')
        elif os.path.isdir(filename):
            print 'skipping directory \'%s\'' % filename
            pacs.remove(filename)
    pacs = findpacs(pacs)
    for pac in pacs:
        if conf.config['do_package_tracking'] and not pac.todo:
            prj = prj_obj or Project(os.path.dirname(pac.absdir), False)
            if pac.name in prj.pacs_unvers:
                prj.addPackage(pac.name)
                print statfrmt('A', getTransActPath(os.path.join(pac.dir, os.pardir, pac.name)))
                for filename in pac.filenamelist_unvers:
                    if os.path.isdir(os.path.join(pac.dir, filename)):
                        print 'skipping directory \'%s\'' % os.path.join(pac.dir, filename)
                    else:
                        pac.todo.append(filename)
            elif pac.name in prj.pacs_have:
                print 'osc: warning: \'%s\' is already under version control' % pac.name
        for filename in pac.todo:
            if filename in pac.skipped:
                continue
            if filename in pac.excluded:
                print >>sys.stderr, 'osc: warning: \'%s\' is excluded from a working copy' % filename
                continue
            pac.addfile(filename)

def getPrjPacPaths(path):
    """
    returns the path for a project and a package
    from path. This is needed if you try to add
    or delete packages:
    Examples:
        osc add pac1/: prj_dir = CWD;
                       pac_dir = pac1
        osc add /path/to/pac1:
                       prj_dir = path/to;
                       pac_dir = pac1
        osc add /path/to/pac1/file
                       => this would be an invalid path
                          the caller has to validate the returned
                          path!
    """
    # make sure we hddave a dir: osc add bar vs. osc add bar/; osc add /path/to/prj_dir/new_pack
    # filename = os.path.join(tail, '')
    prj_dir, pac_dir = os.path.split(os.path.normpath(path))
    if prj_dir == '':
        prj_dir = os.getcwd()
    return (prj_dir, pac_dir)

def getTransActPath(pac_dir):
    """
    returns the path for the commit and update operations/transactions.
    Normally the "dir" attribute of a Package() object will be passed to
    this method.
    """
    if pac_dir != '.':
        pathn = os.path.normpath(pac_dir)
    else:
        pathn = ''
    return pathn

def get_commit_message_template(pac):
    """
    Read the difference in .changes file(s) and put them as a template to commit message.
    """
    diff = []
    template = []

    if pac.todo:
        todo = pac.todo
    else:
        todo = pac.filenamelist + pac.filenamelist_unvers

    files = [i for i in todo if i.endswith('.changes') and pac.status(i) in ('A', 'M')]

    for filename in files:
        if pac.status(filename) == 'M':
            diff += get_source_file_diff(pac.absdir, filename, pac.rev)
        elif pac.status(filename) == 'A':
            f = open(filename, 'r')
            for line in f:
                diff += '+' + line
            f.close()

    if diff:
        template = parse_diff_for_commit_message(''.join(diff))

    return template

def parse_diff_for_commit_message(diff, template = []):
    date_re = re.compile(r'\+(Mon|Tue|Wed|Thu|Fri|Sat|Sun) ([A-Z][a-z]{2}) ( ?[0-9]|[0-3][0-9]) .*')
    diff = diff.split('\n')

    # The first four lines contains a header of diff
    for line in diff[3:]:
        # this condition is magical, but it removes all unwanted lines from commit message
        if not(line) or (line and line[0] != '+') or \
        date_re.match(line) or \
        line == '+' or line[0:3] == '+++':
            continue

        if line == '+-------------------------------------------------------------------':
            template.append('')
        else:
            template.append(line[1:])

    return template

def get_commit_msg(wc_dir, pacs):
    template = store_read_file(wc_dir, '_commit_msg')
    # open editor for commit message
    # but first, produce status and diff to append to the template
    footer = []
    lines = []
    for p in pacs:
        states = sorted(p.get_status(False, ' ', '?'), lambda x, y: cmp(x[1], y[1]))
        changed = [statfrmt(st, os.path.normpath(os.path.join(p.dir, filename))) for st, filename in states]
        if changed:
            footer += changed
            footer.append('\nDiff for working copy: %s' % p.dir)
            footer.extend([''.join(i) for i in p.get_diff(ignoreUnversioned=True)])
            lines.extend(get_commit_message_template(p))
    if template is None:
        if lines and lines[0] == '':
            del lines[0]
        template = '\n'.join(lines)
    msg = ''
    # if footer is empty, there is nothing to commit, and no edit needed.
    if footer:
        msg = edit_message(footer='\n'.join(footer), template=template)
    if msg:
        store_write_string(wc_dir, '_commit_msg', msg + '\n')
    else:
        store_unlink_file(wc_dir, '_commit_msg')
    return msg

def check_filelist_before_commit(pacs):

    # warn if any of files has a ? status (usually a patch, or new source was not added to meta)
    for p in pacs:
        # no files given as argument? Take all files in current dir
        if not p.todo:
            p.todo = p.filenamelist + p.filenamelist_unvers
        p.todo.sort()
        for f in [f for f in p.todo if not os.path.isdir(f)]:
            if not f.startswith('_service:') and not f.startswith('_service_') and p.status(f) in ('?', '!'):
                print 'File "%s" found, but not listed in package meta.' % f
                resp = raw_input('(s)kip/(r)emove/(e)dit file lists/(c)ommit/(A)bort? ')
                if resp in ('s', 'S'):
                    continue
                elif resp in ('r', 'R', 'd', 'D'):
                    p.process_filelist(['r ? %s' % f])
                elif resp in ('e', 'E'):
                    try:
                        p.edit_filelist()
                    except ValueError:
                        print >>sys.stderr, "Error during processiong of file list."
                        raise oscerr.UserAbort()
                elif resp in ('c', 'C'):
                    break
                else:
                    raise oscerr.UserAbort()

def print_request_list(apiurl, project, package = None, states = ('new','review',), force = False):
    """
    prints list of pending requests for the specified project/package if "check_for_request_on_action"
    is enabled in the config or if "force" is set to True
    """
    if not conf.config['check_for_request_on_action'] and not force:
        return
    requests = get_request_list(apiurl, project, package, req_state=states)
    msg = 'Pending requests for %s: %s (%s)'
    if package is None and len(requests):
        print msg % ('project', project, len(requests))
    elif len(requests):
        print msg % ('package', '/'.join([project, package]), len(requests))
    for r in requests:
        print r.list_view(), '\n'

def request_interactive_review(apiurl, request, initial_cmd=''):
    """review the request interactively"""
    import tempfile, re

    tmpfile = None

    def print_request(request):
        print request

    print_request(request)
    try:
        prompt = '(a)ccept/(d)ecline/(r)evoke/c(l)one/(s)kip/(c)ancel > '
        sr_actions = request.get_actions('submit')
        if sr_actions:
            prompt = 'd(i)ff/(a)ccept/(d)ecline/(r)evoke/(b)uildstatus/c(l)one/(e)dit/(s)kip/(c)ancel > '
        editprj = ''
        orequest = None
        while True:
            if initial_cmd:
                repl = initial_cmd
                initial_cmd = ''
            else:
                repl = raw_input(prompt).strip()
            if repl == 'i' and sr_actions:
                if not orequest is None and tmpfile:
                    tmpfile.close()
                    tmpfile = None
                if tmpfile is None:
                    tmpfile = tempfile.NamedTemporaryFile(suffix='.diff')
                    for action in sr_actions:
                        diff = 'old: %s/%s\nnew: %s/%s\n' % (action.src_project, action.src_package,
                            action.tgt_project, action.tgt_package)
                        diff += submit_action_diff(apiurl, action)
                        diff += '\n\n'
                        tmpfile.write(diff)
                    tmpfile.flush()
                run_editor(tmpfile.name)
                print_request(request)
            elif repl == 's':
                print >>sys.stderr, 'skipping: #%s' % request.reqid
                break
            elif repl == 'c':
                print >>sys.stderr, 'Aborting'
                raise oscerr.UserAbort()
            elif repl == 'b' and sr_actions:
                for action in sr_actions:
                    print '%s/%s:' % (action.src_project, action.src_package)
                    print '\n'.join(get_results(apiurl, action.src_project, action.src_package))
            elif repl == 'e' and sr_actions:
                if not editprj:
                    editprj = clone_request(apiurl, request.reqid, 'osc editrequest')
                    orequest = request
                request = edit_submitrequest(apiurl, editprj, orequest, request)
                sr_actions = request.get_actions('submit')
                print_request(request)
                prompt = 'd(i)ff/(a)ccept/(b)uildstatus/(e)dit/(s)kip/(c)ancel > '
            else:
                state_map = {'a': 'accepted', 'd': 'declined', 'r': 'revoked'}
                mo = re.search('^([adrl])(?:\s+-m\s+(.*))?$', repl)
                if mo is None or orequest and mo.group(1) != 'a':
                    print >>sys.stderr, 'invalid choice: \'%s\'' % repl
                    continue
                state = state_map.get(mo.group(1))
                msg = mo.group(2)
                footer = ''
                msg_template = ''
                if not (state is None or request.state is None):
                    footer = 'changing request from state \'%s\' to \'%s\'\n\n' \
                        % (request.state.name, state)
                    msg_template = change_request_state_template(request, state)
                footer += str(request)
                if tmpfile is not None:
                    tmpfile.seek(0)
                    # the read bytes probably have a moderate size so the str won't be too large
                    footer += '\n\n' + tmpfile.read()
                if msg is None:
                    msg = edit_message(footer = footer, template=msg_template)
                else:
                    msg = msg.strip('\'').strip('"')
                if not orequest is None:
                    request.create(apiurl)
                    change_request_state(apiurl, request.reqid, 'accepted', msg)
                    repl = raw_input('Supersede original request? (y|N) ')
                    if repl in ('y', 'Y'):
                        change_request_state(apiurl, orequest.reqid, 'superseded',
                            'superseded by %s' % request.reqid, request.reqid)
                elif state is None:
                    clone_request(apiurl, request.reqid, msg)
                else:
                    change_request_state(apiurl, request.reqid, state, msg)
                break
    finally:
        if tmpfile is not None:
            tmpfile.close()

def edit_submitrequest(apiurl, project, orequest, new_request=None):
    """edit a submit action from orequest/new_request"""
    import tempfile, shutil, subprocess
    actions = orequest.get_actions('submit')
    oactions = actions
    if not orequest is None:
        actions = new_request.get_actions('submit')
    num = 0
    if len(actions) > 1:
        print 'Please chose one of the following submit actions:'
        for i in range(len(actions)):
            fmt = Request.format_action(actions[i])
            print '(%i)' % i, '%(source)s  %(target)s' % fmt
        num = raw_input('> ')
        try:
            num = int(num)
        except ValueError:
            raise oscerr.WrongArgs('\'%s\' is not a number.' % num)
        if num < 0 or num >= len(orequest.actions):
            raise oscerr.WrongArgs('number \'%s\' out of range.' % num)

    # the api replaced ':' with '_' in prj and pkg names (clone request)
    package = '%s.%s' % (oactions[num].src_package.replace(':', '_'),
        oactions[num].src_project.replace(':', '_'))
    tmpdir = None
    cleanup = True
    try:
        tmpdir = tempfile.mkdtemp(prefix='osc_editsr')
        p = Package.init_package(apiurl, project, package, tmpdir)
        p.update()
        shell = os.getenv('SHELL', default='/bin/sh')
        olddir = os.getcwd()
        os.chdir(tmpdir)
        print 'Checked out package \'%s\' to %s. Started a new shell (%s).\n' \
            'Please fix the package and close the shell afterwards.' % (package, tmpdir, shell)
        subprocess.call(shell)
        # the pkg might have uncommitted changes...
        cleanup = False
        os.chdir(olddir)
        # reread data
        p = Package(tmpdir)
        modified = p.get_status(False, ' ', '?', 'S')
        if modified:
            print 'Your working copy has the following modifications:'
            print '\n'.join([statfrmt(st, filename) for st, filename in modified])
            repl = raw_input('Do you want to commit the local changes first? (y|N) ')
            if repl in ('y', 'Y'):
                msg = get_commit_msg(p.absdir, [p])
                p.commit(msg=msg)
        cleanup = True
    finally:
        if cleanup:
            shutil.rmtree(tmpdir)
        else:
            print 'Please remove the dir \'%s\' manually' % tmpdir
    r = Request()
    for action in orequest.get_actions():
        new_action = Action.from_xml(action.to_xml())
        r.actions.append(new_action)
        if new_action.type == 'submit':
            new_action.src_package = '%s.%s' % (action.src_package.replace(':', '_'),
                action.src_project.replace(':', '_'))
            new_action.src_project = project
            # do an implicit cleanup
            new_action.opt_sourceupdate = 'cleanup'
    return r

def get_user_projpkgs(apiurl, user, role=None, exclude_projects=[], proj=True, pkg=True, maintained=False, metadata=False):
    """Return all project/packages where user is involved."""
    xpath = 'person/@userid = \'%s\'' % user
    excl_prj = ''
    excl_pkg = ''
    for i in exclude_projects:
        excl_prj = xpath_join(excl_prj, 'not(@name = \'%s\')' % i, op='and')
        excl_pkg = xpath_join(excl_pkg, 'not(@project = \'%s\')' % i, op='and')
    role_filter_xpath = xpath
    if role:
        xpath = xpath_join(xpath, 'person/@role = \'%s\'' % role, inner=True, op='and')
    xpath_pkg = xpath_join(xpath, excl_pkg, op='and')
    xpath_prj = xpath_join(xpath, excl_prj, op='and')

    if maintained:
        xpath_pkg = xpath_join(xpath_pkg, '(project/attribute/@name=\'%(attr)s\' or attribute/@name=\'%(attr)s\')' % {'attr': conf.config['maintained_attribute']}, op='and')

    what = {}
    if pkg:
        if metadata:
            what['package'] = xpath_pkg
        else:
            what['package_id'] = xpath_pkg
    if proj:
        if metadata:
            what['project'] = xpath_prj
        else:
            what['project_id'] = xpath_prj
    try:
        res = search(apiurl, **what)
    except urllib2.HTTPError, e:
        if e.code != 400 or not role_filter_xpath:
            raise e
        # backward compatibility: local role filtering
        what = dict([[kind, role_filter_xpath] for kind in what.keys()])
        if what.has_key('package'):
            what['package'] = xpath_join(role_filter_xpath, excl_pkg, op='and')
        if what.has_key('project'):
            what['project'] = xpath_join(role_filter_xpath, excl_prj, op='and')
        res = search(apiurl, **what)
        filter_role(res, user, role)
    return res

def raw_input(*args):
    import __builtin__
    try:
        return __builtin__.raw_input(*args)
    except EOFError:
        # interpret ctrl-d as user abort
        raise oscerr.UserAbort()

# backward compatibility: local role filtering
def filter_role(meta, user, role):
    """
    remove all project/package nodes if no person node exists
    where @userid=user and @role=role
    """
    for kind, root in meta.iteritems():
        delete = []
        for node in root.findall(kind):
            found = False
            for p in node.findall('person'):
                if p.get('userid') == user and p.get('role') == role:
                    found = True
                    break
            if not found:
                delete.append(node)
        for node in delete:
            root.remove(node)

def find_default_project(apiurl=None, package=None):
    """"
    look though the list of conf.config['getpac_default_project']
    and find the first project where the given package exists in the build service.
    """
    if not len(conf.config['getpac_default_project']):
        return None
    candidates = re.split('[, ]+', conf.config['getpac_default_project'])
    if package is None or len(candidates) == 1:
        return candidates[0]

    # search through the list, where package exists ...
    for prj in candidates:
        try:
            # any fast query will do here.
            show_package_meta(apiurl, prj, package)
            return prj
        except urllib2.HTTPError: 
            pass
    return None



# vim: sw=4 et
