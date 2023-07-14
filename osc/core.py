# Copyright (C) 2006 Novell Inc.  All rights reserved.
# This program is free software; it may be used, copied, modified
# and distributed under the terms of the GNU General Public Licence,
# either version 2, or version 3 (at your option).


# __store_version__ is to be incremented when the format of the working copy
# "store" changes in an incompatible way. Please add any needed migration
# functionality to check_store_version().
__store_version__ = '1.0'


import codecs
import copy
import datetime
import difflib
import errno
import fnmatch
import glob
import hashlib
import locale
import os
import platform
import re
import shlex
import shutil
import subprocess
import sys
import tempfile
import textwrap
import time
from functools import cmp_to_key, total_ordering
from http.client import IncompleteRead
from io import StringIO
from pathlib import Path
from typing import Optional, Dict, Union, List, Iterable
from urllib.parse import urlsplit, urlunsplit, urlparse, quote_plus, urlencode, unquote
from urllib.error import HTTPError
from urllib.request import pathname2url
from xml.etree import ElementTree as ET

try:
    import distro
except ImportError:
    distro = None

from . import __version__
from . import _private
from . import conf
from . import meter
from . import oscerr
from .connection import http_request, http_GET, http_POST, http_PUT, http_DELETE
from .store import Store
from .util.helper import decode_list, decode_it, raw_input, _html_escape


ET_ENCODING = "unicode"


def compare(a, b): return cmp(a[1:], b[1:])


def cmp(a, b):
    return (a > b) - (a < b)


DISTURL_RE = re.compile(r"^(?P<bs>.*)://(?P<apiurl>.*?)/(?P<project>.*?)/(?P<repository>.*?)/(?P<revision>.*)-(?P<source>.*)$")
BUILDLOGURL_RE = re.compile(r"^(?P<apiurl>https?://.*?)/build/(?P<project>.*?)/(?P<repository>.*?)/(?P<arch>.*?)/(?P<package>.*?)/_log$")
BUFSIZE = 1024 * 1024
store = '.osc'

new_project_templ = """\
<project name="%(name)s">

  <title></title> <!-- Short title of NewProject -->
  <description></description>
    <!-- This is for a longer description of the purpose of the project -->

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
    <enable />
  </debuginfo>

<!-- remove this comment to enable one or more build targets

  <repository name="openSUSE_Factory">
    <path project="openSUSE:Factory" repository="snapshot" />
    <arch>x86_64</arch>
    <arch>i586</arch>
  </repository>
  <repository name="openSUSE_13.2">
    <path project="openSUSE:13.2" repository="standard"/>
    <arch>x86_64</arch>
    <arch>i586</arch>
  </repository>
  <repository name="openSUSE_13.1">
    <path project="openSUSE:13.1" repository="standard"/>
    <arch>x86_64</arch>
    <arch>i586</arch>
  </repository>
  <repository name="Fedora_21">
    <path project="Fedora:21" repository="standard" />
    <arch>x86_64</arch>
    <arch>i586</arch>
  </repository>
  <repository name="SLE_12">
    <path project="SUSE:SLE-12:GA" repository="standard" />
    <arch>x86_64</arch>
    <arch>i586</arch>
  </repository>
-->

</project>
"""

new_package_templ = """\
<package name="%(name)s">

  <title></title> <!-- Title of package -->

  <description></description> <!-- for long description -->

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

new_group_template = """\
<group>
  <title>%(group)s</title>
  <person>
    <person userid=""/>
  </person>
</group>
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
<!-- See https://github.com/openSUSE/libzypp/tree/master/zypp/parser/yum/schema/patterns.rng -->

<!--
<pattern xmlns="http://novell.com/package/metadata/suse/pattern"
 xmlns:rpm="http://linux.duke.edu/metadata/rpm">
 <name></name>
 <summary></summary>
 <description></description>
 <uservisible/>
 <category lang="en"></category>
 <rpm:requires>
   <rpm:entry name="must-have-package"/>
 </rpm:requires>
 <rpm:recommends>
   <rpm:entry name="package"/>
 </rpm:recommends>
 <rpm:suggests>
   <rpm:entry name="anotherpackage"/>
 </rpm:suggests>
</pattern>
-->
"""

buildstatus_symbols = {'succeeded': '.',
                       'disabled': ' ',
                       'expansion error': 'U',  # obsolete with OBS 2.0
                       'unresolvable': 'U',
                       'failed': 'F',
                       'broken': 'B',
                       'blocked': 'b',
                       'building': '%',
                       'finished': 'f',
                       'scheduled': 's',
                       'locked': 'L',
                       'excluded': 'x',
                       'dispatching': 'd',
                       'signing': 'S',
                       }


# os.path.samefile is available only under Unix
def os_path_samefile(path1, path2):
    try:
        return os.path.samefile(path1, path2)
    except AttributeError:
        return os.path.realpath(path1) == os.path.realpath(path2)


@total_ordering
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

    def __eq__(self, other):
        if isinstance(other, str):
            return self.name == other
        self_data = (self.name, self.md5, self.size, self.mtime, self.skipped)
        other_data = (other.name, other.md5, other.size, other.mtime, other.skipped)
        return self_data == other_data

    def __lt__(self, other):
        self_data = (self.name, self.md5, self.size, self.mtime, self.skipped)
        other_data = (other.name, other.md5, other.size, other.mtime, other.skipped)
        return self_data < other_data

    @classmethod
    def from_xml_node(cls, node):
        assert node.tag == "entry"
        kwargs = {
            "name": node.get("name"),
            "md5": node.get("md5"),
            "size": int(node.get("size")),
            "mtime": int(node.get("mtime")),
            "skipped": "skipped" in node.attrib,
        }
        return cls(**kwargs)

    def to_xml_node(self, parent_node):
        attributes = {
            "name": self.name,
            "md5": self.md5,
            "size": str(int(self.size)),
            "mtime": str(int(self.mtime)),
        }
        if self.skipped:
            attributes["skipped"] = "true"
        new_node = ET.SubElement(parent_node, "entry", attributes)
        return new_node


class Serviceinfo:
    """Source service content
    """

    def __init__(self):
        """creates an empty serviceinfo instance"""
        self.services = []
        self.apiurl: Optional[str] = None
        self.project: Optional[str] = None
        self.package: Optional[str] = None

    def read(self, serviceinfo_node, append=False):
        """read in the source services ``<services>`` element passed as
        elementtree node.
        """
        def error(msg, xml):
            data = 'invalid service format:\n%s' % ET.tostring(xml, encoding=ET_ENCODING)
            raise ValueError("%s\n\n%s" % (data, msg))

        if serviceinfo_node is None:
            return
        if not append:
            self.services = []
        services = serviceinfo_node.findall('service')

        for service in services:
            name = service.get('name')
            if name is None:
                error("invalid service definition. Attribute name missing.", service)
            if len(name) < 3 or '/' in name:
                error("invalid service name: %s" % name, service)
            mode = service.get('mode', '')
            data = {'name': name, 'mode': mode}
            command = [name]
            for param in service.findall('param'):
                option = param.get('name')
                if option is None:
                    error("%s: a parameter requires a name" % name, service)
                value = ''
                if param.text:
                    value = param.text
                command.append('--' + option)
                # hmm is this reasonable or do we want to allow real
                # options (e.g., "--force" (without an argument)) as well?
                command.append(value)
            data['command'] = command
            self.services.append(data)

    def getProjectGlobalServices(self, apiurl: str, project: str, package: str):
        self.apiurl = apiurl
        # get all project wide services in one file, we don't store it yet
        u = makeurl(apiurl, ['source', project, package], query='cmd=getprojectservices')
        try:
            f = http_POST(u)
            root = ET.parse(f).getroot()
            self.read(root, True)
            self.project = project
            self.package = package
        except HTTPError as e:
            if e.code == 404 and package != '_project':
                self.getProjectGlobalServices(apiurl, project, '_project')
                self.package = package
            elif e.code != 403 and e.code != 400:
                raise e

    def addVerifyFile(self, serviceinfo_node, filename: str):
        f = open(filename, 'rb')
        digest = hashlib.sha256(f.read()).hexdigest()
        f.close()

        r = serviceinfo_node
        s = ET.Element("service", name="verify_file")
        ET.SubElement(s, "param", name="file").text = filename
        ET.SubElement(s, "param", name="verifier").text = "sha256"
        ET.SubElement(s, "param", name="checksum").text = digest

        r.append(s)
        return r

    def addDownloadUrl(self, serviceinfo_node, url_string: str):
        url = urlparse(url_string)
        protocol = url.scheme
        host = url.netloc
        path = url.path

        r = serviceinfo_node
        s = ET.Element("service", name="download_url")
        ET.SubElement(s, "param", name="protocol").text = protocol
        ET.SubElement(s, "param", name="host").text = host
        ET.SubElement(s, "param", name="path").text = path

        r.append(s)
        return r

    def addSetVersion(self, serviceinfo_node):
        r = serviceinfo_node
        s = ET.Element("service", name="set_version", mode="buildtime")
        r.append(s)
        return r

    def addGitUrl(self, serviceinfo_node, url_string: Optional[str]):
        r = serviceinfo_node
        s = ET.Element("service", name="obs_scm")
        ET.SubElement(s, "param", name="url").text = url_string
        ET.SubElement(s, "param", name="scm").text = "git"
        r.append(s)
        return r

    def addTarUp(self, serviceinfo_node):
        r = serviceinfo_node
        s = ET.Element("service", name="tar", mode="buildtime")
        r.append(s)
        return r

    def addRecompressTar(self, serviceinfo_node):
        r = serviceinfo_node
        s = ET.Element("service", name="recompress", mode="buildtime")
        ET.SubElement(s, "param", name="file").text = "*.tar"
        ET.SubElement(s, "param", name="compression").text = "xz"
        r.append(s)
        return r

    def execute(self, dir, callmode: Optional[str] = None, singleservice=None, verbose: Optional[bool] = None):
        old_dir = os.path.join(dir, '.old')

        # if 2 osc instances are executed at a time one, of them fails on .old file existence
        # sleep up to 10 seconds until we can create the directory
        for i in reversed(range(10)):
            try:
                os.mkdir(old_dir)
                break
            except FileExistsError:
                time.sleep(1)

            if i == 0:
                msg = f'"{old_dir}" exists, please remove it'
                raise oscerr.OscIOError(None, msg)

        try:
            result = self._execute(dir, old_dir, callmode, singleservice, verbose)
        finally:
            shutil.rmtree(old_dir)
        return result

    def _execute(
        self, dir, old_dir, callmode: Optional[str] = None, singleservice=None, verbose: Optional[bool] = None
    ):
        # cleanup existing generated files
        for filename in os.listdir(dir):
            if filename.startswith('_service:') or filename.startswith('_service_'):
                os.rename(os.path.join(dir, filename),
                          os.path.join(old_dir, filename))

        allservices = self.services or []
        service_names = [s['name'] for s in allservices]
        if singleservice and singleservice not in service_names:
            # set array to the manual specified singleservice, if it is not part of _service file
            data = {'name': singleservice, 'command': [singleservice], 'mode': callmode}
            allservices = [data]
        elif singleservice:
            allservices = [s for s in allservices if s['name'] == singleservice]
            # set the right called mode or the service would be skipped below
            for s in allservices:
                s['mode'] = callmode

        if not allservices:
            # short-circuit to avoid a potential http request in vc_export_env
            # (if there are no services to execute this http request is
            # useless)
            return 0

        # services can detect that they run via osc this way
        os.putenv("OSC_VERSION", get_osc_version())

        # set environment when using OBS 2.3 or later
        if self.project is not None:
            # These need to be kept in sync with bs_service
            os.putenv("OBS_SERVICE_APIURL", self.apiurl)
            os.putenv("OBS_SERVICE_PROJECT", self.project)
            os.putenv("OBS_SERVICE_PACKAGE", self.package)
            # also export vc env vars (some services (like obs_scm) use them)
            vc_export_env(self.apiurl)

        # recreate files
        ret = 0
        for service in allservices:
            if callmode != "all":
                if service['mode'] == "buildtime":
                    continue
                if service['mode'] == "serveronly" and callmode != "local":
                    continue
                if service['mode'] == "manual" and callmode != "manual":
                    continue
                if service['mode'] != "manual" and callmode == "manual":
                    continue
                if service['mode'] == "disabled" and callmode != "disabled":
                    continue
                if service['mode'] != "disabled" and callmode == "disabled":
                    continue
                if service['mode'] != "trylocal" and service['mode'] != "localonly" and callmode == "trylocal":
                    continue
            temp_dir = None
            try:
                temp_dir = tempfile.mkdtemp(dir=dir, suffix='.%s.service' % service['name'])
                cmd = service['command']
                if not os.path.exists("/usr/lib/obs/service/" + cmd[0]):
                    raise oscerr.PackageNotInstalled("obs-service-%s" % cmd[0])
                cmd[0] = "/usr/lib/obs/service/" + cmd[0]
                cmd = cmd + ["--outdir", temp_dir]
                if conf.config['verbose'] or verbose or conf.config['debug']:
                    print("Run source service:", ' '.join(cmd))
                r = run_external(*cmd)

                if r != 0:
                    print("Aborting: service call failed: ", ' '.join(cmd))
                    # FIXME: addDownloadUrlService calls si.execute after
                    #        updating _services.
                    return r

                if service['mode'] == "manual" or service['mode'] == "disabled" or service['mode'] == "trylocal" or service['mode'] == "localonly" or callmode == "local" or callmode == "trylocal" or callmode == "all":
                    for filename in os.listdir(temp_dir):
                        os.rename(os.path.join(temp_dir, filename), os.path.join(dir, filename))
                else:
                    name = service['name']
                    for filename in os.listdir(temp_dir):
                        os.rename(os.path.join(temp_dir, filename), os.path.join(dir, "_service:" + name + ":" + filename))
            finally:
                if temp_dir is not None:
                    shutil.rmtree(temp_dir)

        return 0


class Linkinfo:
    """linkinfo metadata (which is part of the xml representing a directory)
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
        """read in the linkinfo metadata from the ``<linkinfo>`` element passed as
        elementtree node.
        If the passed element is ``None``, the method does nothing.
        """
        if linkinfo_node is None:
            return
        self.project = linkinfo_node.get('project')
        self.package = linkinfo_node.get('package')
        self.xsrcmd5 = linkinfo_node.get('xsrcmd5')
        self.lsrcmd5 = linkinfo_node.get('lsrcmd5')
        self.srcmd5 = linkinfo_node.get('srcmd5')
        self.error = linkinfo_node.get('error')
        self.rev = linkinfo_node.get('rev')
        self.baserev = linkinfo_node.get('baserev')

    def islink(self):
        """:return: ``True`` if the linkinfo is not empty, otherwise ``False``"""
        if self.xsrcmd5 or self.lsrcmd5 or self.error is not None:
            return True
        return False

    def isexpanded(self):
        """:return: ``True`` if the package is an expanded link"""
        if self.lsrcmd5 and not self.xsrcmd5:
            return True
        return False

    def haserror(self):
        """:return: ``True`` if the link is in error state (could not be applied)"""
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


class DirectoryServiceinfo:
    def __init__(self):
        self.code = None
        self.xsrcmd5 = None
        self.lsrcmd5 = None
        self.error = ''

    def read(self, serviceinfo_node):
        if serviceinfo_node is None:
            return
        self.code = serviceinfo_node.get('code')
        self.xsrcmd5 = serviceinfo_node.get('xsrcmd5')
        self.lsrcmd5 = serviceinfo_node.get('lsrcmd5')
        self.error = serviceinfo_node.find('error')
        if self.error:
            self.error = self.error.text

    def isexpanded(self):
        """
        Returns true, if the directory contains the "expanded"/generated service files
        """
        return self.lsrcmd5 is not None and self.xsrcmd5 is None

    def haserror(self):
        return self.error is not None

# http://effbot.org/zone/element-lib.htm#prettyprint


def xmlindent(elem, level=0):
    i = "\n" + level * "  "
    if isinstance(elem, ET.ElementTree):
        elem = elem.getroot()
    if len(elem):
        if not elem.text or not elem.text.strip():
            elem.text = i + "  "
        for e in elem:
            xmlindent(e, level + 1)
            if not e.tail or not e.tail.strip():
                e.tail = i + "  "
        if not e.tail or not e.tail.strip():
            e.tail = i
    else:
        if level and (not elem.tail or not elem.tail.strip()):
            elem.tail = i


class Project:
    """
    Represent a checked out project directory, holding packages.

    :Attributes:
        ``dir``
            The directory path containing the project.

        ``name``
            The name of the project.

        ``apiurl``
            The endpoint URL of the API server.

        ``pacs_available``
            List of names of packages available server-side.
            This is only populated if ``getPackageList`` is set
            to ``True`` in the constructor.

        ``pacs_have``
            List of names of packages which exist server-side
            and exist in the local project working copy (if
            'do_package_tracking' is disabled).
            If 'do_package_tracking' is enabled it represents the
            list names of packages which are tracked in the project
            working copy (that is it might contain packages which
            exist on the server as well as packages which do not
            exist on the server (for instance if the local package
            was added or if the package was removed on the server-side)).

        ``pacs_excluded``
            List of names of packages in the local project directory
            which are excluded by the `exclude_glob` configuration
            variable.  Only set if `do_package_tracking` is enabled.

        ``pacs_unvers``
            List of names of packages in the local project directory
            which are not tracked. Only set if `do_package_tracking`
            is enabled.

        ``pacs_broken``
            List of names of packages which are tracked but do not
            exist in the local project working copy. Only set if
            `do_package_tracking` is enabled.

        ``pacs_missing``
            List of names of packages which exist server-side but
            are not expected to exist in the local project directory.
    """

    REQ_STOREFILES = ('_project', '_apiurl')

    def __init__(self, dir, getPackageList=True, progress_obj=None, wc_check=True):
        """
        Constructor.

        :Parameters:
            `dir` : str
                The directory path containing the checked out project.

            `getPackageList` : bool
                Set to `False` if you want to skip retrieval from the
                server of the list of packages in the project .

            `wc_check` : bool
        """
        self.dir = Path(dir)
        self.absdir = os.path.abspath(dir)
        self.store = Store(dir)
        self.progress_obj = progress_obj

        self.name = store_read_project(self.dir)
        self.scm_url = self.store.scmurl
        self.apiurl = self.store.apiurl

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
            self.pacs_have = [pac.get('name') for pac in self.pac_root.findall('package')]
            self.pacs_excluded = [i for i in os.listdir(self.dir)
                                  for j in conf.config['exclude_glob']
                                  if fnmatch.fnmatch(i, j)]
            self.pacs_unvers = [i for i in os.listdir(self.dir) if i not in self.pacs_have and i not in self.pacs_excluded]
            # store all broken packages (e.g. packages which where removed by a non-osc cmd)
            # in the self.pacs_broken list
            self.pacs_broken = []
            for p in self.pacs_have:
                if not os.path.isdir(os.path.join(self.absdir, p)):
                    # all states will be replaced with the '!'-state
                    # (except it is already marked as deleted ('D'-state))
                    self.pacs_broken.append(p)
        else:
            self.pacs_have = [i for i in os.listdir(self.dir) if i in self.pacs_available]

        self.pacs_missing = [i for i in self.pacs_available if i not in self.pacs_have]

    def wc_check(self):
        global store
        dirty_files = []
        req_storefiles = Project.REQ_STOREFILES
        if conf.config['do_package_tracking'] and self.scm_url is None:
            req_storefiles += ('_packages',)
        for fname in req_storefiles:
            if not os.path.exists(os.path.join(self.absdir, store, fname)):
                dirty_files.append(fname)
        return dirty_files

    def wc_repair(self, apiurl: Optional[str] = None):
        store = Store(self.dir)
        store.assert_is_project()
        if not store.exists("_apiurl") or apiurl:
            if apiurl is None:
                msg = 'cannot repair wc: the \'_apiurl\' file is missing but ' \
                    'no \'apiurl\' was passed to wc_repair'
                # hmm should we raise oscerr.WrongArgs?
                raise oscerr.WorkingCopyInconsistent(self.name, None, [], msg)
            # sanity check
            conf.parse_apisrv_url(None, apiurl)
            store.apiurl = apiurl
            self.apiurl = apiurl

    def checkout_missing_pacs(self, sinfos, expand_link=False, unexpand_link=False):
        for pac in self.pacs_missing:
            if conf.config['do_package_tracking'] and pac in self.pacs_unvers:
                # pac is not under version control but a local file/dir exists
                msg = 'can\'t add package \'%s\': Object already exists' % pac
                raise oscerr.PackageExists(self.name, pac, msg)

            if not (expand_link or unexpand_link):
                sinfo = sinfos.get(pac)
                if sinfo is None:
                    # should never happen...
                    continue
                linked = sinfo.find('linked')
                if linked is not None and linked.get('project') == self.name:
                    # hmm what about a linkerror (sinfo.get('lsrcmd5') is None)?
                    # Should we skip the package as well or should we it out?
                    # let's skip it for now
                    print('Skipping %s (link to package %s)' % (pac, linked.get('package')))
                    continue

            print('checking out new package %s' % pac)
            checkout_package(self.apiurl, self.name, pac,
                             pathname=getTransActPath(os.path.join(self.dir, pac)),
                             prj_obj=self, prj_dir=self.dir,
                             expand_link=expand_link or not unexpand_link, progress_obj=self.progress_obj)

    def status(self, pac: str):
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
            if st not in exclude_states:
                res.append((st, pac))
        if '?' not in exclude_states:
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
        if node is None:
            self.new_package_entry(pac, state)
        else:
            node.set('state', state)

    def get_package_node(self, pac: str):
        for node in self.pac_root.findall('package'):
            if pac == node.get('name'):
                return node
        return None

    def del_package_node(self, pac):
        for node in self.pac_root.findall('package'):
            if pac == node.get('name'):
                self.pac_root.remove(node)

    def get_state(self, pac: str):
        node = self.get_package_node(pac)
        if node is not None:
            return node.get('state')
        else:
            return None

    def new_package_entry(self, name, state):
        ET.SubElement(self.pac_root, 'package', name=name, state=state)

    def read_packages(self):
        """
        Returns an ``xml.etree.ElementTree`` object representing the
        parsed contents of the project's ``.osc/_packages`` XML file.
        """
        global store

        packages_file = os.path.join(self.absdir, store, '_packages')
        if os.path.isfile(packages_file) and os.path.getsize(packages_file):
            try:
                result = ET.parse(packages_file)
            except:
                msg = 'Cannot read package file \'%s\'. ' % packages_file
                msg += 'You can try to remove it and then run osc repairwc.'
                raise oscerr.OscIOError(None, msg)
            return result
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
        store_write_string(self.absdir, '_packages', ET.tostring(self.pac_root, encoding=ET_ENCODING))

    def addPackage(self, pac):
        for i in conf.config['exclude_glob']:
            if fnmatch.fnmatch(pac, i):
                msg = 'invalid package name: \'%s\' (see \'exclude_glob\' config option)' % pac
                raise oscerr.OscIOError(None, msg)
        state = self.get_state(pac)
        if state is None or state == 'D':
            self.new_package_entry(pac, 'A')
            self.write_packages()
            # sometimes the new pac doesn't exist in the list because
            # it would take too much time to update all data structs regularly
            if pac in self.pacs_unvers:
                self.pacs_unvers.remove(pac)
        else:
            raise oscerr.PackageExists(self.name, pac, 'package \'%s\' is already under version control' % pac)

    def delPackage(self, pac, force=False):
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
                        print(statfrmt('D', getTransActPath(os.path.join(pac.dir, filename))))
                print(statfrmt('D', getTransActPath(os.path.join(pac.dir, os.pardir, pac.name))))
                pac.write_deletelist()
                self.set_state(pac.name, 'D')
                self.write_packages()
            else:
                print('package \'%s\' has local modifications (see osc st for details)' % pac.name)
        elif state == 'A':
            if force:
                delete_dir(pac.absdir)
                self.del_package_node(pac.name)
                self.write_packages()
                print(statfrmt('D', pac.name))
            else:
                print('package \'%s\' has local modifications (see osc st for details)' % pac.name)
        elif state is None:
            print('package is not under version control')
        else:
            print('unsupported state')

    def update(self, pacs=(), expand_link=False, unexpand_link=False, service_files=False):
        if pacs:
            for pac in pacs:
                Package(os.path.join(self.dir, pac), progress_obj=self.progress_obj).update()
        else:
            # we need to make sure that the _packages file will be written (even if an exception
            # occurs)
            try:
                # update complete project
                # packages which no longer exists upstream
                upstream_del = [pac for pac in self.pacs_have if pac not in self.pacs_available and self.get_state(pac) != 'A']
                sinfo_pacs = [pac for pac in self.pacs_have if self.get_state(pac) in (' ', 'D') and pac not in self.pacs_broken]
                sinfo_pacs.extend(self.pacs_missing)
                sinfos = get_project_sourceinfo(self.apiurl, self.name, True, *sinfo_pacs)

                for pac in upstream_del:
                    if self.status(pac) != '!':
                        p = Package(os.path.join(self.dir, pac))
                        self.delPackage(p, force=True)
                        delete_storedir(p.storedir)
                        try:
                            os.rmdir(pac)
                        except:
                            pass
                    self.pac_root.remove(self.get_package_node(pac))
                    self.pacs_have.remove(pac)

                for pac in self.pacs_have:
                    state = self.get_state(pac)
                    if pac in self.pacs_broken:
                        if self.get_state(pac) != 'A':
                            checkout_package(self.apiurl, self.name, pac,
                                             pathname=getTransActPath(os.path.join(self.dir, pac)), prj_obj=self,
                                             prj_dir=self.dir, expand_link=not unexpand_link, progress_obj=self.progress_obj)
                    elif state == ' ':
                        # do a simple update
                        p = Package(os.path.join(self.dir, pac), progress_obj=self.progress_obj)
                        rev = None
                        needs_update = True
                        if p.scm_url is not None:
                            # git managed.
                            print("Skipping git managed package ", pac)
                            continue
                        elif expand_link and p.islink() and not p.isexpanded():
                            if p.haslinkerror():
                                try:
                                    rev = show_upstream_xsrcmd5(p.apiurl, p.prjname, p.name, revision=p.rev)
                                except:
                                    rev = show_upstream_xsrcmd5(p.apiurl, p.prjname, p.name, revision=p.rev, linkrev="base")
                                    p.mark_frozen()
                            else:
                                rev = p.linkinfo.xsrcmd5
                            print('Expanding to rev', rev)
                        elif unexpand_link and p.islink() and p.isexpanded():
                            rev = p.linkinfo.lsrcmd5
                            print('Unexpanding to rev', rev)
                        elif p.islink() and p.isexpanded():
                            needs_update = p.update_needed(sinfos[p.name])
                            if needs_update:
                                rev = p.latest_rev()
                        elif p.hasserviceinfo() and p.serviceinfo.isexpanded() and not service_files:
                            # FIXME: currently, do_update does not propagate the --server-side-source-service-files
                            # option to this method. Consequence: an expanded service is always unexpanded during
                            # an update (TODO: discuss if this is a reasonable behavior (at least this the default
                            # behavior for a while))
                            needs_update = True
                        else:
                            needs_update = p.update_needed(sinfos[p.name])
                        print('Updating %s' % p.name)
                        if needs_update:
                            p.update(rev, service_files)
                        else:
                            print('At revision %s.' % p.rev)
                        if unexpand_link:
                            p.unmark_frozen()
                    elif state == 'D':
                        # pac exists (the non-existent pac case was handled in the first if block)
                        p = Package(os.path.join(self.dir, pac), progress_obj=self.progress_obj)
                        if p.update_needed(sinfos[p.name]):
                            p.update()
                    elif state == 'A' and pac in self.pacs_available:
                        # file/dir called pac already exists and is under version control
                        msg = 'can\'t add package \'%s\': Object already exists' % pac
                        raise oscerr.PackageExists(self.name, pac, msg)
                    elif state == 'A':
                        # do nothing
                        pass
                    else:
                        print('unexpected state.. package \'%s\'' % pac)

                self.checkout_missing_pacs(sinfos, expand_link, unexpand_link)
            finally:
                self.write_packages()

    def commit(self, pacs=(), msg='', files=None, verbose=False, skip_local_service_run=False, can_branch=False, force=False):
        files = files or {}
        if pacs:
            try:
                for pac in pacs:
                    todo = []
                    if pac in files:
                        todo = files[pac]
                    state = self.get_state(pac)
                    if state == 'A':
                        self.commitNewPackage(pac, msg, todo, verbose=verbose, skip_local_service_run=skip_local_service_run)
                    elif state == 'D':
                        self.commitDelPackage(pac, force=force)
                    elif state == ' ':
                        # display the correct dir when sending the changes
                        if os_path_samefile(os.path.join(self.dir, pac), os.getcwd()):
                            p = Package('.')
                        else:
                            p = Package(os.path.join(self.dir, pac))
                        p.todo = todo
                        p.commit(msg, verbose=verbose, skip_local_service_run=skip_local_service_run, can_branch=can_branch, force=force)
                    elif pac in self.pacs_unvers and not is_package_dir(os.path.join(self.dir, pac)):
                        print('osc: \'%s\' is not under version control' % pac)
                    elif pac in self.pacs_broken or not os.path.exists(os.path.join(self.dir, pac)):
                        print('osc: \'%s\' package not found' % pac)
                    elif state is None:
                        self.commitExtPackage(pac, msg, todo, verbose=verbose, skip_local_service_run=skip_local_service_run)
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
                        Package(os.path.join(self.dir, pac)).commit(msg, verbose=verbose, skip_local_service_run=skip_local_service_run)
                    elif state == 'D':
                        self.commitDelPackage(pac, force=force)
                    elif state == 'A':
                        self.commitNewPackage(pac, msg, verbose=verbose, skip_local_service_run=skip_local_service_run)
            finally:
                self.write_packages()

    def commitNewPackage(self, pac, msg='', files=None, verbose=False, skip_local_service_run=False):
        """creates and commits a new package if it does not exist on the server"""
        files = files or []
        if pac in self.pacs_available:
            print('package \'%s\' already exists' % pac)
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
            print(statfrmt('Sending', os.path.normpath(p.dir)))
            p.commit(msg=msg, verbose=verbose, skip_local_service_run=skip_local_service_run)
            self.set_state(pac, ' ')
            os.chdir(olddir)

    def commitDelPackage(self, pac, force=False):
        """deletes a package on the server and in the working copy"""
        try:
            # display the correct dir when sending the changes
            if os_path_samefile(os.path.join(self.dir, pac), os.curdir):
                pac_dir = pac
            else:
                pac_dir = os.path.join(self.dir, pac)
            p = Package(os.path.join(self.dir, pac))
            # print statfrmt('Deleting', os.path.normpath(os.path.join(p.dir, os.pardir, pac)))
            delete_storedir(p.storedir)
            try:
                os.rmdir(p.dir)
            except:
                pass
        except OSError:
            pac_dir = os.path.join(self.dir, pac)
        except (oscerr.NoWorkingCopy, oscerr.WorkingCopyOutdated, oscerr.PackageError):
            pass
        # print statfrmt('Deleting', getTransActPath(os.path.join(self.dir, pac)))
        print(statfrmt('Deleting', getTransActPath(pac_dir)))
        delete_package(self.apiurl, self.name, pac, force=force)
        self.del_package_node(pac)

    def commitExtPackage(self, pac, msg, files=None, verbose=False, skip_local_service_run=False):
        """commits a package from an external project"""
        files = files or []
        if os_path_samefile(os.path.join(self.dir, pac), os.getcwd()):
            pac_path = '.'
        else:
            pac_path = os.path.join(self.dir, pac)

        store = Store(pac_path)
        project = store_read_project(pac_path)
        package = store_read_package(pac_path)
        apiurl = store.apiurl
        if not meta_exists(metatype='pkg',
                           path_args=(quote_plus(project), quote_plus(package)),
                           template_args=None, create_new=False, apiurl=apiurl):
            user = conf.get_apiurl_usr(self.apiurl)
            edit_meta(metatype='pkg',
                      path_args=(quote_plus(project), quote_plus(package)),
                      template_args=({'name': pac, 'user': user}), apiurl=apiurl)
        p = Package(pac_path)
        p.todo = files
        p.commit(msg=msg, verbose=verbose, skip_local_service_run=skip_local_service_run)

    def __str__(self):
        r = []
        r.append('*****************************************************')
        r.append('Project %s (dir=%s, absdir=%s)' % (self.name, self.dir, self.absdir))
        r.append('have pacs:\n%s' % ', '.join(self.pacs_have))
        r.append('missing pacs:\n%s' % ', '.join(self.pacs_missing))
        r.append('*****************************************************')
        return '\n'.join(r)

    @staticmethod
    def init_project(
        apiurl: str,
        dir: Path,
        project,
        package_tracking=True,
        getPackageList=True,
        progress_obj=None,
        wc_check=True,
        scm_url=None,
    ):
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
        Store(dir).apiurl = apiurl
        if scm_url:
            Store(dir).scmurl = scm_url
            package_tracking = None
        if package_tracking:
            store_write_initial_packages(dir, project, [])
        return Project(dir, getPackageList, progress_obj, wc_check)


@total_ordering
class Package:
    """represent a package (its directory) and read/keep/write its metadata"""

    # should _meta be a required file?
    REQ_STOREFILES = ('_project', '_package', '_apiurl', '_files', '_osclib_version')
    OPT_STOREFILES = ('_to_be_added', '_to_be_deleted', '_in_conflict', '_in_update',
                      '_in_commit', '_meta', '_meta_mode', '_frozenlink', '_pulled', '_linkrepair',
                      '_size_limit', '_commit_msg', '_last_buildroot')

    def __init__(self, workingdir, progress_obj=None, size_limit=None, wc_check=True):
        global store

        self.todo = []
        if os.path.isfile(workingdir) or not os.path.exists(workingdir):
            # workingdir is a file
            # workingdir doesn't exist -> it points to a non-existing file in a working dir (e.g. during mv)
            workingdir, todo_entry = os.path.split(workingdir)
            self.todo.append(todo_entry)

        self.dir = workingdir or "."
        self.absdir = os.path.abspath(self.dir)
        self.store = Store(self.dir)
        self.storedir = os.path.join(self.absdir, store)
        self.progress_obj = progress_obj
        self.size_limit = size_limit
        self.scm_url = self.store.scmurl
        if size_limit and size_limit == 0:
            self.size_limit = None

        check_store_version(self.dir)

        self.prjname = store_read_project(self.dir)
        self.name = store_read_package(self.dir)
        self.apiurl = self.store.apiurl

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

    def __repr__(self):
        return super().__repr__() + f"({self.prjname}/{self.name})"

    def __hash__(self):
        return hash((self.name, self.prjname, self.apiurl))

    def __eq__(self, other):
        return (self.name, self.prjname, self.apiurl) == (other.name, other.prjname, other.apiurl)

    def __lt__(self, other):
        return (self.name, self.prjname, self.apiurl) < (other.name, other.prjname, other.apiurl)

    @classmethod
    def from_paths(cls, paths, progress_obj=None):
        """
        Return a list of Package objects from working copies in given paths.
        """
        packages = []
        for path in paths:
            package = cls(path, progress_obj)
            seen_package = None
            try:
                # re-use an existing package
                seen_package_index = packages.index(package)
                seen_package = packages[seen_package_index]
            except ValueError:
                pass

            if seen_package:
                # merge package into seen_package
                if seen_package.absdir != package.absdir:
                    raise oscerr.PackageExists(package.prjname, package.name, "Duplicate package")
                seen_package.merge(package)
            else:
                # use the new package instance
                packages.append(package)

        return packages

    @classmethod
    def from_paths_nofail(cls, paths, progress_obj=None):
        """
        Return a list of Package objects from working copies in given paths
        and a list of strings with paths that do not contain Package working copies.
        """
        packages = []
        failed_to_load = []
        for path in paths:
            try:
                package = cls(path, progress_obj)
            except oscerr.NoWorkingCopy:
                failed_to_load.append(path)
                continue

            # the following code is identical to from_paths()
            seen_package = None
            try:
                # re-use an existing package
                seen_package_index = packages.index(package)
                seen_package = packages[seen_package_index]
            except ValueError:
                pass

            if seen_package:
                # merge package into seen_package
                if seen_package.absdir != package.absdir:
                    raise oscerr.PackageExists(package.prjname, package.name, "Duplicate package")
                seen_package.merge(package)
            else:
                # use the new package instance
                packages.append(package)

        return packages, failed_to_load

    def wc_check(self):
        dirty_files = []
        if self.scm_url:
            return dirty_files
        for fname in self.filenamelist:
            if not os.path.exists(os.path.join(self.storedir, fname)) and fname not in self.skipped:
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
            elif fname not in self.filenamelist:
                dirty_files.append(fname)
        for fname in self.to_be_deleted[:]:
            if fname not in self.filenamelist:
                dirty_files.append(fname)
        for fname in self.in_conflict[:]:
            if fname not in self.filenamelist:
                dirty_files.append(fname)
        return dirty_files

    def wc_repair(self, apiurl: Optional[str] = None):
        store = Store(self.dir)
        store.assert_is_package()
        if not store.exists("_apiurl") or apiurl:
            if apiurl is None:
                msg = 'cannot repair wc: the \'_apiurl\' file is missing but ' \
                    'no \'apiurl\' was passed to wc_repair'
                # hmm should we raise oscerr.WrongArgs?
                raise oscerr.WorkingCopyInconsistent(self.prjname, self.name, [], msg)
            # sanity check
            conf.parse_apisrv_url(None, apiurl)
            store.apiurl = apiurl
            self.apiurl = apiurl

        # all files which are present in the filelist have to exist in the storedir
        for f in self.filelist:
            # XXX: should we also check the md5?
            if not os.path.exists(os.path.join(self.storedir, f.name)) and f.name not in self.skipped:
                # if get_source_file fails we're screwed up...
                get_source_file(self.apiurl, self.prjname, self.name, f.name,
                                targetfilename=os.path.join(self.storedir, f.name), revision=self.rev,
                                mtime=f.mtime)

        for fname in store:
            if fname in Package.REQ_STOREFILES or fname in Package.OPT_STOREFILES or \
                    fname.startswith('_build'):
                continue
            elif fname not in self.filenamelist or fname in self.skipped:
                # this file does not belong to the storedir so remove it
                store.unlink(fname)

        for fname in self.to_be_deleted[:]:
            if fname not in self.filenamelist:
                self.to_be_deleted.remove(fname)
                self.write_deletelist()

        for fname in self.in_conflict[:]:
            if fname not in self.filenamelist:
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
        print(statfrmt('A', pathname))

    def delete_file(self, n, force=False):
        """deletes a file if possible and marks the file as deleted"""
        state = '?'
        try:
            state = self.status(n)
        except OSError as ioe:
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
            # don't remove "merge files" (*.mine, *.new...)
            # that's why we don't use clear_from_conflictlist
            self.in_conflict.remove(n)
            self.write_conflictlist()
        if state not in ('A', '?') and not (state == '!' and was_added):
            self.put_on_deletelist(n)
            self.write_deletelist()
        return (True, state)

    def delete_storefile(self, n):
        try:
            os.unlink(os.path.join(self.storedir, n))
        except:
            pass

    def delete_localfile(self, n):
        try:
            os.unlink(os.path.join(self.dir, n))
        except:
            pass

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
            upfilename = os.path.join(self.dir, n + '.new')

            try:
                os.unlink(myfilename)
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

    def put_source_file(self, n, tdir, copy_only=False):
        query = 'rev=repository'
        tfilename = os.path.join(tdir, n)
        shutil.copyfile(os.path.join(self.dir, n), tfilename)
        # escaping '+' in the URL path (note: not in the URL query string) is
        # only a workaround for ruby on rails, which swallows it otherwise
        if not copy_only:
            u = makeurl(self.apiurl, ['source', self.prjname, self.name, pathname2url(n)], query=query)
            http_PUT(u, file=tfilename)
        if n in self.to_be_added:
            self.to_be_added.remove(n)

    def __commit_update_store(self, tdir):
        """move files from transaction directory into the store"""
        for filename in os.listdir(tdir):
            os.rename(os.path.join(tdir, filename), os.path.join(self.storedir, filename))

    def __generate_commitlist(self, todo_send):
        root = ET.Element('directory')
        for i in sorted(todo_send.keys()):
            ET.SubElement(root, 'entry', name=i, md5=todo_send[i])
        return root

    @staticmethod
    def commit_filelist(apiurl: str, project: str, package: str, filelist, msg="", user=None, **query):
        """send the commitlog and the local filelist to the server"""
        if user is None:
            user = conf.get_apiurl_usr(apiurl)
        query.update({'cmd': 'commitfilelist', 'user': user, 'comment': msg})
        u = makeurl(apiurl, ['source', project, package], query=query)
        f = http_POST(u, data=ET.tostring(filelist, encoding=ET_ENCODING))
        root = ET.parse(f).getroot()
        return root

    @staticmethod
    def commit_get_missing(filelist):
        """returns list of missing files (filelist is the result of commit_filelist)"""
        error = filelist.get('error')
        if error is None:
            return []
        elif error != 'missing':
            raise oscerr.APIError('commit_get_missing_files: '
                                  'unexpected \'error\' attr: \'%s\'' % error)
        todo = []
        for n in filelist.findall('entry'):
            name = n.get('name')
            if name is None:
                raise oscerr.APIError('missing \'name\' attribute:\n%s\n'
                                      % ET.tostring(filelist, encoding=ET_ENCODING))
            todo.append(n.get('name'))
        return todo

    def __send_commitlog(self, msg, local_filelist, validate=False):
        """send the commitlog and the local filelist to the server"""
        query = {}
        if self.islink() and self.isexpanded():
            query['keeplink'] = '1'
            if conf.config['linkcontrol'] or self.isfrozen():
                query['linkrev'] = self.linkinfo.srcmd5
            if self.ispulled():
                query['repairlink'] = '1'
                query['linkrev'] = self.get_pulled_srcmd5()
        if self.islinkrepair():
            query['repairlink'] = '1'
        if validate:
            query['withvalidate'] = '1'
        return self.commit_filelist(self.apiurl, self.prjname, self.name,
                                    local_filelist, msg, **query)

    def commit(self, msg='', verbose=False, skip_local_service_run=False, can_branch=False, force=False):
        # commit only if the upstream revision is the same as the working copy's
        upstream_rev = self.latest_rev()
        if self.rev != upstream_rev:
            raise oscerr.WorkingCopyOutdated((self.absdir, self.rev, upstream_rev))

        if not skip_local_service_run:
            r = self.run_source_services(mode="trylocal", verbose=verbose)
            if r != 0:
                # FIXME: it is better to raise this in Serviceinfo.execute with more
                # information (like which service/command failed)
                raise oscerr.ServiceRuntimeError('A service failed with error: %d' % r)

        # check if it is a link, if so, branch the package
        if self.is_link_to_different_project():
            if can_branch:
                orgprj = self.get_local_origin_project()
                print(f"Branching {self.name} from {orgprj} to {self.prjname}")
                exists, targetprj, targetpkg, srcprj, srcpkg = branch_pkg(
                    self.apiurl, orgprj, self.name, target_project=self.prjname)
                # update _meta and _files to sychronize the local package
                # to the new branched one in OBS
                self.update_local_pacmeta()
                self.update_local_filesmeta()
            else:
                print(f"{self.name} Not commited because is link to a different project")
                return 1

        if not self.todo:
            self.todo = [i for i in self.to_be_added if i not in self.filenamelist] + self.filenamelist

        pathn = getTransActPath(self.dir)

        todo_send = {}
        todo_delete = []
        real_send = []
        sha256sums = {}
        for filename in self.filenamelist + [i for i in self.to_be_added if i not in self.filenamelist]:
            if filename.startswith('_service:') or filename.startswith('_service_'):
                continue
            st = self.status(filename)
            if st == 'C':
                print('Please resolve all conflicts before committing using "osc resolved FILE"!')
                return 1
            elif filename in self.todo:
                if st in ('A', 'R', 'M'):
                    todo_send[filename] = dgst(os.path.join(self.absdir, filename))
                    sha256sums[filename] = sha256_dgst(os.path.join(self.absdir, filename))
                    real_send.append(filename)
                    print(statfrmt('Sending', os.path.join(pathn, filename)))
                elif st in (' ', '!', 'S'):
                    if st == '!' and filename in self.to_be_added:
                        print('file \'%s\' is marked as \'A\' but does not exist' % filename)
                        return 1
                    f = self.findfilebyname(filename)
                    if f is None:
                        raise oscerr.PackageInternalError(self.prjname, self.name,
                                                          'error: file \'%s\' with state \'%s\' is not known by meta'
                                                          % (filename, st))
                    todo_send[filename] = f.md5
                elif st == 'D':
                    todo_delete.append(filename)
                    print(statfrmt('Deleting', os.path.join(pathn, filename)))
            elif st in ('R', 'M', 'D', ' ', '!', 'S'):
                # ignore missing new file (it's not part of the current commit)
                if st == '!' and filename in self.to_be_added:
                    continue
                f = self.findfilebyname(filename)
                if f is None:
                    raise oscerr.PackageInternalError(self.prjname, self.name,
                                                      'error: file \'%s\' with state \'%s\' is not known by meta'
                                                      % (filename, st))
                todo_send[filename] = f.md5
            if ((self.ispulled() or self.islinkrepair() or self.isfrozen())
                    and st != 'A' and filename not in sha256sums):
                # Ignore files with state 'A': if we should consider it,
                # it would have been in pac.todo, which implies that it is
                # in sha256sums.
                # The storefile is guaranteed to exist (since we have a
                # pulled/linkrepair wc, the file cannot have state 'S')
                storefile = os.path.join(self.storedir, filename)
                sha256sums[filename] = sha256_dgst(storefile)

        if not force and not real_send and not todo_delete and not self.islinkrepair() and not self.ispulled():
            print('nothing to do for package %s' % self.name)
            return 1

        print('Transmitting file data', end=' ')
        filelist = self.__generate_commitlist(todo_send)
        sfilelist = self.__send_commitlog(msg, filelist, validate=True)
        hash_entries = [e for e in sfilelist.findall('entry') if e.get('hash') is not None]
        if sfilelist.get('error') and hash_entries:
            name2elem = {e.get('name'): e for e in filelist.findall('entry')}
            for entry in hash_entries:
                filename = entry.get('name')
                fileelem = name2elem.get(filename)
                if filename not in sha256sums:
                    msg = 'There is no sha256 sum for file %s.\n' \
                          'This could be due to an outdated working copy.\n' \
                          'Please update your working copy with osc update and\n' \
                          'commit again afterwards.'
                    print(msg % filename)
                    return 1
                fileelem.set('hash', 'sha256:%s' % sha256sums[filename])
            sfilelist = self.__send_commitlog(msg, filelist)
        send = self.commit_get_missing(sfilelist)
        real_send = [i for i in real_send if i not in send]
        # abort after 3 tries
        tries = 3
        tdir = None
        try:
            tdir = os.path.join(self.storedir, '_in_commit')
            if os.path.isdir(tdir):
                shutil.rmtree(tdir)
            os.mkdir(tdir)
            while send and tries:
                for filename in send[:]:
                    sys.stdout.write('.')
                    sys.stdout.flush()
                    self.put_source_file(filename, tdir)
                    send.remove(filename)
                tries -= 1
                sfilelist = self.__send_commitlog(msg, filelist)
                send = self.commit_get_missing(sfilelist)
            if send:
                raise oscerr.PackageInternalError(self.prjname, self.name,
                                                  'server does not accept filelist:\n%s\nmissing:\n%s\n'
                                                  % (ET.tostring(filelist, encoding=ET_ENCODING), ET.tostring(sfilelist, encoding=ET_ENCODING)))
            # these files already exist on the server
            for filename in real_send:
                self.put_source_file(filename, tdir, copy_only=True)
            # update store with the committed files
            self.__commit_update_store(tdir)
        finally:
            if tdir is not None and os.path.isdir(tdir):
                shutil.rmtree(tdir)
        self.rev = sfilelist.get('rev')
        print()
        print('Committed revision %s.' % self.rev)

        if self.ispulled():
            os.unlink(os.path.join(self.storedir, '_pulled'))
        if self.islinkrepair():
            os.unlink(os.path.join(self.storedir, '_linkrepair'))
            self.linkrepair = False
            # XXX: mark package as invalid?
            print('The source link has been repaired. This directory can now be removed.')

        if self.islink() and self.isexpanded():
            li = Linkinfo()
            li.read(sfilelist.find('linkinfo'))
            if li.xsrcmd5 is None:
                raise oscerr.APIError('linkinfo has no xsrcmd5 attr:\n%s\n' % ET.tostring(sfilelist, encoding=ET_ENCODING))
            sfilelist = ET.fromstring(self.get_files_meta(revision=li.xsrcmd5))
        for i in sfilelist.findall('entry'):
            if i.get('name') in self.skipped:
                i.set('skipped', 'true')
        store_write_string(self.absdir, '_files', ET.tostring(sfilelist, encoding=ET_ENCODING) + '\n')
        for filename in todo_delete:
            self.to_be_deleted.remove(filename)
            self.delete_storefile(filename)
        self.write_deletelist()
        self.write_addlist()
        self.update_datastructs()

        print_request_list(self.apiurl, self.prjname, self.name)

        # FIXME: add testcases for this codepath
        sinfo = sfilelist.find('serviceinfo')
        if sinfo is not None:
            print('Waiting for server side source service run')
            u = makeurl(self.apiurl, ['source', self.prjname, self.name])
            while sinfo is not None and sinfo.get('code') == 'running':
                sys.stdout.write('.')
                sys.stdout.flush()
                # does it make sense to add some delay?
                sfilelist = ET.fromstring(http_GET(u).read())
                # if sinfo is None another commit might have occured in the "meantime"
                sinfo = sfilelist.find('serviceinfo')
            print('')
            rev = self.latest_rev()
            self.update(rev=rev)
        elif self.get_local_meta() is None:
            # if this was a newly added package there is no _meta
            # file
            self.update_local_pacmeta()

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
        if mtime:
            utime(filename, (-1, mtime))
        if origfile is not None:
            os.unlink(origfile)

    def mergefile(self, n, revision, mtime=None):
        filename = os.path.join(self.dir, n)
        storefilename = os.path.join(self.storedir, n)
        myfilename = os.path.join(self.dir, n + '.mine')
        upfilename = os.path.join(self.dir, n + '.new')
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
            ret = -1
            with open(filename, 'w') as f:
                args = ('-m', '-E', myfilename, storefilename, upfilename)
                ret = run_external('diff3', *args, stdout=f)

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
                merge_cmd = 'diff3 ' + ' '.join(args)
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
        return ET.tostring(root, encoding=ET_ENCODING)

    def get_local_meta(self):
        """Get the local _meta file for the package."""
        meta = store_read_file(self.absdir, '_meta')
        return meta

    def get_local_origin_project(self):
        """Get the originproject from the _meta file."""
        # if the wc was checked out via some old osc version
        # there might be no meta file: in this case we assume
        # that the origin project is equal to the wc's project
        meta = self.get_local_meta()
        if meta is None:
            return self.prjname
        root = ET.fromstring(meta)
        return root.get('project')

    def is_link_to_different_project(self):
        """Check if the package is a link to a different project."""
        if self.name == "_project":
            return False
        orgprj = self.get_local_origin_project()
        return self.prjname != orgprj

    def update_datastructs(self):
        """
        Update the internal data structures if the local _files
        file has changed (e.g. update_local_filesmeta() has been
        called).
        """
        if self.scm_url:
            self.filenamelist = []
            self.filelist = []
            self.skipped = []
            self.to_be_added = []
            self.to_be_deleted = []
            self.in_conflict = []
            self.linkrepair = None
            self.rev = None
            self.srcmd5 = None
            self.linkinfo = Linkinfo()
            self.serviceinfo = DirectoryServiceinfo()
            self.size_limit = None
            self.meta = None
            self.excluded = []
            self.filenamelist_unvers = []
            return

        files_tree = read_filemeta(self.dir)
        files_tree_root = files_tree.getroot()

        self.rev = files_tree_root.get('rev')
        self.srcmd5 = files_tree_root.get('srcmd5')

        self.linkinfo = Linkinfo()
        self.linkinfo.read(files_tree_root.find('linkinfo'))
        self.serviceinfo = DirectoryServiceinfo()
        self.serviceinfo.read(files_tree_root.find('serviceinfo'))
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
        self.filenamelist_unvers = [i for i in os.listdir(self.dir)
                                    if i not in self.excluded
                                    if i not in self.filenamelist]

    def islink(self):
        """tells us if the package is a link (has 'linkinfo').
        A package with linkinfo is a package which links to another package.
        Returns ``True`` if the package is a link, otherwise ``False``."""
        return self.linkinfo.islink()

    def isexpanded(self):
        """tells us if the package is a link which is expanded.
        Returns ``True`` if the package is expanded, otherwise ``False``."""
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
        for line in open(os.path.join(self.storedir, '_pulled')):
            pulledrev = line.strip()
        return pulledrev

    def haslinkerror(self):
        """
        Returns ``True`` if the link is broken otherwise ``False``.
        If the package is not a link it returns ``False``.
        """
        return self.linkinfo.haserror()

    def linkerror(self):
        """
        Returns an error message if the link is broken otherwise ``None``.
        If the package is not a link it returns ``None``.
        """
        return self.linkinfo.error

    def hasserviceinfo(self):
        """
        Returns ``True``, if this package contains services.
        """
        return self.serviceinfo.lsrcmd5 is not None or self.serviceinfo.xsrcmd5 is not None

    def update_local_pacmeta(self):
        """
        Update the local _meta file in the store.
        It is replaced with the version pulled from upstream.
        """
        meta = show_package_meta(self.apiurl, self.prjname, self.name)
        if meta != "":
            # is empty for _project for example
            meta = b''.join(meta)
            store_write_string(self.absdir, '_meta', meta + b'\n')

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
            if st not in exclude_states:
                res.append((st, fname))
        return res

    def status(self, n):
        """
        status can be::

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
        localfile = os.path.join(self.absdir, n)
        if n in self.filenamelist:
            known_by_meta = True
        if os.path.exists(localfile):
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
            filemeta = self.findfilebyname(n)
            state = ' '
            if conf.config['status_mtime_heuristic']:
                if os.path.getmtime(localfile) != filemeta.mtime and dgst(localfile) != filemeta.md5:
                    state = 'M'
            elif dgst(localfile) != filemeta.md5:
                state = 'M'
        elif n in self.to_be_added and not exists:
            state = '!'
        elif not exists and exists_in_store and known_by_meta and n not in self.to_be_deleted:
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
        elif os.path.islink(localfile):
            # dangling symlink, whose name is _not_ tracked: treat it
            # as unversioned
            state = '?'
        else:
            # this case shouldn't happen (except there was a typo in the filename etc.)
            raise oscerr.OscIOError(None, 'osc: \'%s\' is not under version control' % n)

        return state

    def get_diff(self, revision=None, ignoreUnversioned=False):
        diff_hdr = b'Index: %s\n'
        diff_hdr += b'===================================================================\n'
        kept = []
        added = []
        deleted = []

        def diff_add_delete(fname, add, revision):
            diff = []
            diff.append(diff_hdr % fname.encode())
            origname = fname
            if add:
                diff.append(b'--- %s\t(revision 0)\n' % fname.encode())
                rev = 'revision 0'
                if revision and fname not in self.to_be_added:
                    rev = 'working copy'
                diff.append(b'+++ %s\t(%s)\n' % (fname.encode(), rev.encode()))
                fname = os.path.join(self.absdir, fname)
                if not os.path.isfile(fname):
                    raise oscerr.OscIOError(None, 'file \'%s\' is marked as \'A\' but does not exist\n'
                                            '(either add the missing file or revert it)' % fname)
            else:
                if revision:
                    b_revision = str(revision).encode()
                else:
                    b_revision = self.rev.encode()
                diff.append(b'--- %s\t(revision %s)\n' % (fname.encode(), b_revision))
                diff.append(b'+++ %s\t(working copy)\n' % fname.encode())
                fname = os.path.join(self.storedir, fname)

            fd = None
            tmpfile = None
            try:
                if revision is not None and not add:
                    (fd, tmpfile) = tempfile.mkstemp(prefix='osc_diff')
                    get_source_file(self.apiurl, self.prjname, self.name, origname, tmpfile, revision)
                    fname = tmpfile
                if binary_file(fname):
                    what = b'added'
                    if not add:
                        what = b'deleted'
                    diff = diff[:1]
                    diff.append(b'Binary file \'%s\' %s.\n' % (origname.encode(), what))
                    return diff
                tmpl = b'+%s'
                ltmpl = b'@@ -0,0 +1,%d @@\n'
                if not add:
                    tmpl = b'-%s'
                    ltmpl = b'@@ -1,%d +0,0 @@\n'
                with open(fname, 'rb') as f:
                    lines = [tmpl % i for i in f.readlines()]
                if len(lines):
                    diff.append(ltmpl % len(lines))
                    if not lines[-1].endswith(b'\n'):
                        lines.append(b'\n\\ No newline at end of file\n')
                diff.extend(lines)
            finally:
                if fd is not None:
                    os.close(fd)
                if tmpfile is not None and os.path.exists(tmpfile):
                    os.unlink(tmpfile)
            return diff

        if revision is None:
            todo = self.todo or [i for i in self.filenamelist if i not in self.to_be_added] + self.to_be_added
            for fname in todo:
                if fname in self.to_be_added and self.status(fname) == 'A':
                    added.append(fname)
                elif fname in self.to_be_deleted:
                    deleted.append(fname)
                elif fname in self.filenamelist:
                    kept.append(self.findfilebyname(fname))
                elif fname in self.to_be_added and self.status(fname) == '!':
                    raise oscerr.OscIOError(None, 'file \'%s\' is marked as \'A\' but does not exist\n'
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
            added.extend([f for f in self.to_be_added if f not in kept])
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
            yield [diff_hdr % f.name.encode()]
            if revision is None:
                yield get_source_file_diff(self.absdir, f.name, self.rev)
            else:
                fd = None
                tmpfile = None
                diff = []
                try:
                    (fd, tmpfile) = tempfile.mkstemp(prefix='osc_diff')
                    get_source_file(self.apiurl, self.prjname, self.name, f.name, tmpfile, revision)
                    diff = get_source_file_diff(self.absdir, f.name, revision,
                                                os.path.basename(tmpfile), os.path.dirname(tmpfile), f.name)
                finally:
                    if fd is not None:
                        os.close(fd)
                    if tmpfile is not None and os.path.exists(tmpfile):
                        os.unlink(tmpfile)
                yield diff

        for f in added:
            yield diff_add_delete(f, True, revision)
        for f in deleted:
            yield diff_add_delete(f, False, revision)

    def merge(self, otherpac):
        for todo_entry in otherpac.todo:
            if todo_entry not in self.todo:
                self.todo.append(todo_entry)

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

    def read_meta_from_spec(self, spec=None):
        if spec:
            specfile = spec
        else:
            # scan for spec files
            speclist = glob.glob(os.path.join(self.dir, '*.spec'))
            if len(speclist) == 1:
                specfile = speclist[0]
            elif len(speclist) > 1:
                print('the following specfiles were found:')
                for filename in speclist:
                    print(filename)
                print('please specify one with --specfile')
                sys.exit(1)
            else:
                print('no specfile was found - please specify one '
                      'with --specfile')
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

        m = b''.join(show_package_meta(self.apiurl, self.prjname, self.name))

        root = ET.fromstring(m)
        root.find('title').text = self.summary
        root.find('description').text = ''.join(self.descr)
        url = root.find('url')
        if url is None:
            url = ET.SubElement(root, 'url')
        url.text = self.url

        def delegate(force=False): return make_meta_url('pkg',
                                                        (self.prjname, self.name),
                                                        self.apiurl, force=force)
        url_factory = metafile._URLFactory(delegate)
        mf = metafile(url_factory, ET.tostring(root, encoding=ET_ENCODING))

        if not force:
            print('*' * 36, 'old', '*' * 36)
            print(decode_it(m))
            print('*' * 36, 'new', '*' * 36)
            print(ET.tostring(root, encoding=ET_ENCODING))
            print('*' * 72)
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
        print()
        print("The link in this package (\"%s\") is currently broken. Checking" % self.name)
        print("out the last working version instead; please use 'osc pull'")
        print("to merge the conflicts.")
        print()

    def unmark_frozen(self):
        if os.path.exists(os.path.join(self.storedir, '_frozenlink')):
            os.unlink(os.path.join(self.storedir, '_frozenlink'))

    def latest_rev(self, include_service_files=False, expand=False):
        # if expand is True the xsrcmd5 will be returned (even if the wc is unexpanded)
        if self.islinkrepair():
            upstream_rev = show_upstream_xsrcmd5(self.apiurl, self.prjname, self.name, linkrepair=1, meta=self.meta, include_service_files=include_service_files)
        elif self.islink() and (self.isexpanded() or expand):
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
        elif not self.islink() and expand:
            upstream_rev = show_upstream_xsrcmd5(self.apiurl, self.prjname, self.name, meta=self.meta, include_service_files=include_service_files)
        else:
            upstream_rev = show_upstream_rev(self.apiurl, self.prjname, self.name, meta=self.meta, include_service_files=include_service_files)
        return upstream_rev

    def __get_files(self, fmeta_root):
        f = []
        if fmeta_root.get('rev') is None and len(fmeta_root.findall('entry')) > 0:
            raise oscerr.APIError('missing rev attribute in _files:\n%s' % ''.join(ET.tostring(fmeta_root, encoding=ET_ENCODING)))
        for i in fmeta_root.findall('entry'):
            error = i.get('error')
            if error is not None:
                raise oscerr.APIError('broken files meta: %s' % error)
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
            if f.name in self.filenamelist and f.name not in self.skipped:
                kept.append(f)
            else:
                added.append(f)
        for f in self.filelist:
            if f.name not in revfilenames:
                deleted.append(f)

        return kept, added, deleted, services

    def update_needed(self, sinfo):
        # this method might return a false-positive (that is a True is returned,
        # even though no update is needed) (for details, see comments below)
        if self.islink():
            if self.isexpanded():
                # check if both revs point to the same expanded sources
                # Note: if the package contains a _service file, sinfo.srcmd5's lsrcmd5
                # points to the "expanded" services (xservicemd5) => chances
                # for a false-positive are high, because osc usually works on the
                # "unexpanded" services.
                # Once the srcserver supports something like noservice=1, we can get rid of
                # this false-positives (patch was already sent to the ml) (but this also
                # requires some slight changes in osc)
                return sinfo.get('srcmd5') != self.srcmd5
            elif self.hasserviceinfo():
                # check if we have expanded or unexpanded services
                if self.serviceinfo.isexpanded():
                    return sinfo.get('lsrcmd5') != self.srcmd5
                else:
                    # again, we might have a false-positive here, because
                    # a mismatch of the "xservicemd5"s does not neccessarily
                    # imply a change in the "unexpanded" services.
                    return sinfo.get('lsrcmd5') != self.serviceinfo.xsrcmd5
            # simple case: unexpanded sources and no services
            # self.srcmd5 should also work
            return sinfo.get('lsrcmd5') != self.linkinfo.lsrcmd5
        elif self.hasserviceinfo():
            if self.serviceinfo.isexpanded():
                return sinfo.get('srcmd5') != self.srcmd5
            else:
                # cannot handle this case, because the sourceinfo does not contain
                # information about the lservicemd5. Once the srcserver supports
                # a noservice=1 query parameter, we can handle this case.
                return True
        return sinfo.get('srcmd5') != self.srcmd5

    def update(self, rev=None, service_files=False, size_limit=None):
        rfiles = []
        # size_limit is only temporary for this update
        old_size_limit = self.size_limit
        if size_limit is not None:
            self.size_limit = int(size_limit)
        if os.path.isfile(os.path.join(self.storedir, '_in_update', '_files')):
            print('resuming broken update...')
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
                    (fd, tmpfile) = tempfile.mkstemp(dir=self.absdir, prefix=broken_file[0] + '.')
                    os.close(fd)
                    os.rename(wcfile, tmpfile)
                    os.rename(origfile, wcfile)
                    print('warning: it seems you modified \'%s\' after the broken '
                          'update. Restored original file and saved modified version '
                          'to \'%s\'.' % (wcfile, tmpfile))
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
            self.__update(kept, added, deleted, services, ET.tostring(root, encoding=ET_ENCODING), root.get('rev'))
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
            print(statfrmt('A', os.path.join(pathn, f.name)))
        for f in deleted:
            # if the storefile doesn't exist we're resuming an aborted update:
            # the file was already deleted but we cannot know this
            # OR we're processing a _service: file (simply keep the file)
            if os.path.isfile(os.path.join(self.storedir, f.name)) and self.status(f.name) not in ('M', 'C'):
                # if self.status(f.name) != 'M':
                self.delete_localfile(f.name)
            self.delete_storefile(f.name)
            print(statfrmt('D', os.path.join(pathn, f.name)))
            if f.name in self.to_be_deleted:
                self.to_be_deleted.remove(f.name)
                self.write_deletelist()
            elif f.name in self.in_conflict:
                self.in_conflict.remove(f.name)
                self.write_conflictlist()

        for f in kept:
            state = self.status(f.name)
#            print f.name, state
            if state == 'M' and self.findfilebyname(f.name).md5 == f.md5:
                # remote file didn't change
                pass
            elif state == 'M':
                # try to merge changes
                merge_status = self.mergefile(f.name, rev, f.mtime)
                print(statfrmt(merge_status, os.path.join(pathn, f.name)))
            elif state == '!':
                self.updatefile(f.name, rev, f.mtime)
                print('Restored \'%s\'' % os.path.join(pathn, f.name))
            elif state == 'C':
                get_source_file(self.apiurl, self.prjname, self.name, f.name,
                                targetfilename=os.path.join(self.storedir, f.name), revision=rev,
                                progress_obj=self.progress_obj, mtime=f.mtime, meta=self.meta)
                print('skipping \'%s\' (this is due to conflicts)' % f.name)
            elif state == 'D' and self.findfilebyname(f.name).md5 != f.md5:
                # XXX: in the worst case we might end up with f.name being
                # in _to_be_deleted and in _in_conflict... this needs to be checked
                if os.path.exists(os.path.join(self.absdir, f.name)):
                    merge_status = self.mergefile(f.name, rev, f.mtime)
                    print(statfrmt(merge_status, os.path.join(pathn, f.name)))
                    if merge_status == 'C':
                        # state changes from delete to conflict
                        self.to_be_deleted.remove(f.name)
                        self.write_deletelist()
                else:
                    # XXX: we cannot recover this case because we've no file
                    # to backup
                    self.updatefile(f.name, rev, f.mtime)
                    print(statfrmt('U', os.path.join(pathn, f.name)))
            elif state == ' ' and self.findfilebyname(f.name).md5 != f.md5:
                self.updatefile(f.name, rev, f.mtime)
                print(statfrmt('U', os.path.join(pathn, f.name)))

        # checkout service files
        for f in services:
            get_source_file(self.apiurl, self.prjname, self.name, f.name,
                            targetfilename=os.path.join(self.absdir, f.name), revision=rev,
                            progress_obj=self.progress_obj, mtime=f.mtime, meta=self.meta)
            print(statfrmt('A', os.path.join(pathn, f.name)))
        store_write_string(self.absdir, '_files', fm + '\n')
        if not self.meta:
            self.update_local_pacmeta()
        self.update_datastructs()

        print('At revision %s.' % self.rev)

    def run_source_services(self, mode=None, singleservice=None, verbose=None):
        if self.name.startswith("_"):
            return 0
        curdir = os.getcwd()
        os.chdir(self.absdir)  # e.g. /usr/lib/obs/service/verify_file fails if not inside the project dir.
        si = Serviceinfo()
        if os.path.exists('_service'):
            try:
                service = ET.parse(os.path.join(self.absdir, '_service')).getroot()
            except ET.ParseError as v:
                line, column = v.position
                print('XML error in _service file on line %s, column %s' % (line, column))
                sys.exit(1)
            si.read(service)
        si.getProjectGlobalServices(self.apiurl, self.prjname, self.name)
        r = si.execute(self.absdir, mode, singleservice, verbose)
        os.chdir(curdir)
        return r

    def revert(self, filename):
        if filename not in self.filenamelist and filename not in self.to_be_added:
            raise oscerr.OscIOError(None, 'file \'%s\' is not under version control' % filename)
        elif filename in self.skipped:
            raise oscerr.OscIOError(None, 'file \'%s\' is marked as skipped and cannot be reverted' % filename)
        if filename in self.filenamelist and not os.path.exists(os.path.join(self.storedir, filename)):
            msg = f"file '{filename}' is listed in filenamelist but no storefile exists"
            raise oscerr.PackageInternalError(self.prjname, self.name, msg)
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
    def init_package(apiurl: str, project, package, dir, size_limit=None, meta=False, progress_obj=None, scm_url=None):
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
        Store(dir).apiurl = apiurl
        if meta:
            store_write_string(dir, '_meta_mode', '')
        if size_limit:
            store_write_string(dir, '_size_limit', str(size_limit) + '\n')
        if scm_url:
            Store(dir).scmurl = scm_url
        else:
            store_write_string(dir, '_files', '<directory />' + '\n')
        store_write_string(dir, '_osclib_version', __store_version__ + '\n')
        return Package(dir, progress_obj=progress_obj, size_limit=size_limit)


class AbstractState:
    """
    Base class which represents state-like objects (``<review />``, ``<state />``).
    """

    def __init__(self, tag):
        self.__tag = tag

    def get_node_attrs(self):
        """:return: attributes for the tag/element"""
        raise NotImplementedError()

    def get_node_name(self):
        """:return: tag/element name"""
        return self.__tag

    def get_comment(self):
        """:return: data from ``<comment />`` tag"""
        raise NotImplementedError()

    def get_description(self):
        """:return: data from ``<description />`` tag"""
        raise NotImplementedError()

    def to_xml(self):
        """:return: object serialized to XML"""
        root = ET.Element(self.get_node_name())
        for attr in self.get_node_attrs():
            val = getattr(self, attr)
            if val is not None:
                root.set(attr, val)
        if self.get_description():
            ET.SubElement(root, 'description').text = self.get_description()
        if self.get_comment():
            ET.SubElement(root, 'comment').text = self.get_comment()
        return root

    def to_str(self):
        """:return: object serialized to pretty-printed XML"""
        root = self.to_xml()
        xmlindent(root)
        return ET.tostring(root, encoding=ET_ENCODING)


class ReviewState(AbstractState):
    """Represents the review state in a request"""

    def __init__(self, review_node):
        if not review_node.get('state'):
            raise oscerr.APIError('invalid review node (state attr expected): %s' %
                                  ET.tostring(review_node, encoding=ET_ENCODING))
        super().__init__(review_node.tag)
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

    def __repr__(self):
        result = super().__repr__()
        result += "("
        result += f"{self.state}"

        if self.who:
            result += f" by {self.who}"

        for by in ("user", "group", "project", "package"):
            by_value = getattr(self, f"by_{by}", None)
            if by_value:
                result += f" [{by} {by_value}])"
                break

        result += ")"
        return result

    def get_node_attrs(self):
        return ('state', 'by_user', 'by_group', 'by_project', 'by_package', 'who', 'when')

    def get_comment(self):
        return self.comment

    def get_description(self):
        return None


class RequestHistory(AbstractState):
    """Represents a history element of a request"""
    re_name = re.compile(r'^Request (?:got )?([^\s]+)$')

    def __init__(self, history_node):
        super().__init__(history_node.tag)
        self.who = history_node.get('who')
        self.when = history_node.get('when')
        if not history_node.find('description') is None and \
                history_node.find('description').text:
            # OBS 2.6
            self.description = history_node.find('description').text.strip()
        else:
            # OBS 2.5 and before
            self.description = history_node.get('name')
        self.comment = ''
        if not history_node.find('comment') is None and \
                history_node.find('comment').text:
            self.comment = history_node.find('comment').text.strip()
        self.name = self._parse_name(history_node)

    def _parse_name(self, history_node):
        name = history_node.get('name', None)
        if name is not None:
            # OBS 2.5 and before
            return name
        mo = self.re_name.search(self.description)
        if mo is not None:
            return mo.group(1)
        return self.description

    def get_node_attrs(self):
        return ('who', 'when')

    def get_description(self):
        return self.description

    def get_comment(self):
        return self.comment


class RequestState(AbstractState):
    """Represents the state of a request"""

    def __init__(self, state_node):
        if not state_node.get('name'):
            raise oscerr.APIError('invalid request state node (name attr expected): %s' %
                                  ET.tostring(state_node, encoding=ET_ENCODING))
        super().__init__(state_node.tag)
        self.name = state_node.get('name')
        self.who = state_node.get('who')
        self.when = state_node.get('when')
        self.approver = state_node.get('approver')
        if state_node.find('description') is None:
            # OBS 2.6 has it always, before it did not exist
            self.description = state_node.get('description')
        self.comment = ''
        if not state_node.find('comment') is None and \
                state_node.find('comment').text:
            self.comment = state_node.find('comment').text.strip()

    def get_node_attrs(self):
        return ('name', 'who', 'when', 'approver')

    def get_comment(self):
        return self.comment

    def get_description(self):
        return None


class Action:
    """
    Represents an ``<action />`` element of a Request.
    This class is quite common so that it can be used for all different
    action types.

    .. note::
        Instances only provide attributes for their specific type.

    Examples::

      r = Action('set_bugowner', tgt_project='foo', person_name='buguser')
      # available attributes: r.type (== 'set_bugowner'), r.tgt_project (== 'foo'), r.tgt_package (is None)
      r.to_str() ->
      <action type="set_bugowner">
        <target project="foo" />
        <person name="buguser" />
      </action>

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
                            'acceptinfo_oxsrcmd5', 'opt_updatelink', 'opt_makeoriginolder'),
                 'add_role': ('tgt_project', 'tgt_package', 'person_name', 'person_role', 'group_name', 'group_role'),
                 'set_bugowner': ('tgt_project', 'tgt_package', 'person_name', 'group_name'),
                 'maintenance_release': ('src_project', 'src_package', 'src_rev', 'tgt_project', 'tgt_package', 'person_name',
                                         'acceptinfo_rev', 'acceptinfo_srcmd5', 'acceptinfo_xsrcmd5', 'acceptinfo_osrcmd5',
                                         'acceptinfo_oxsrcmd5', 'acceptinfo_oproject', 'acceptinfo_opackage'),
                 'release': ('src_project', 'src_package', 'src_rev', 'tgt_project', 'tgt_package', 'person_name',
                             'acceptinfo_rev', 'acceptinfo_srcmd5', 'acceptinfo_xsrcmd5', 'acceptinfo_osrcmd5',
                             'acceptinfo_oxsrcmd5', 'acceptinfo_oproject', 'acceptinfo_opackage', 'tgt_repository'),
                 'maintenance_incident': ('src_project', 'src_package', 'src_rev', 'tgt_project', 'tgt_package', 'tgt_releaseproject', 'person_name', 'opt_sourceupdate', 'opt_makeoriginolder',
                                          'acceptinfo_rev', 'acceptinfo_srcmd5', 'acceptinfo_xsrcmd5', 'acceptinfo_osrcmd5',
                                          'acceptinfo_oxsrcmd5'),
                 'delete': ('tgt_project', 'tgt_package', 'tgt_repository'),
                 'change_devel': ('src_project', 'src_package', 'tgt_project', 'tgt_package'),
                 'group': ('grouped_id', )}
    # attribute prefix to element name map (only needed for abbreviated attributes)
    prefix_to_elm = {'src': 'source', 'tgt': 'target', 'opt': 'options'}

    def __init__(self, type, **kwargs):
        self.apiurl = kwargs.pop("apiurl", None)
        self._src_pkg_object = None
        self._tgt_pkg_object = None
        if type not in Action.type_args.keys():
            raise oscerr.WrongArgs('invalid action type: \'%s\'' % type)
        self.type = type
        for i in kwargs.keys():
            if i not in Action.type_args[type]:
                raise oscerr.WrongArgs('invalid argument: \'%s\'' % i)
        # set all type specific attributes
        for i in Action.type_args[type]:
            setattr(self, i, kwargs.get(i))

    def __repr__(self):
        result = super().__repr__()
        result += "("
        result += f"type={self.type}"

        src_pkg = self.src_pkg_object
        if src_pkg:
            result += f" source={src_pkg.project}/{src_pkg.name}"
        elif getattr(self, "src_project", None):
            result += f" source={self.src_project}"

        tgt_pkg = self.tgt_pkg_object
        if tgt_pkg:
            result += f" target={tgt_pkg.project}/{tgt_pkg.name}"
        elif getattr(self, "tgt_project", None):
            result += f" target={self.tgt_project}"

        result += ")"
        return result

    @property
    def src_pkg_object(self):
        if not getattr(self, "src_project", None) or not getattr(self, "src_package", None):
            return None
        if not self._src_pkg_object:
            src_rev = getattr(self, "src_rev", None)
            self._src_pkg_object = _private.ApiPackage(self.apiurl, self.src_project, self.src_package, src_rev)
        return self._src_pkg_object

    @property
    def tgt_pkg_object(self):
        if not self._tgt_pkg_object:
            if self.type == "maintenance_incident":
                # the target project for maintenance incidents is virtual and cannot be queried
                # the actual target project is in the "releaseproject" attribute
                #
                # tgt_releaseproject is always set for a maintenance_incident
                # pylint: disable=no-member
                tgt_project = self.tgt_releaseproject

                # the target package is not specified
                # we need to extract it from source package's _meta
                src_package_meta_releasename = self.src_pkg_object.get_meta_value("releasename")
                tgt_package = src_package_meta_releasename.split(".")[0]
            else:
                if not getattr(self, "tgt_project", None) or not getattr(self, "tgt_package", None):
                    return None
                # tgt_project and tgt_package are checked above
                # pylint: disable=no-member
                tgt_project = self.tgt_project
                tgt_package = self.tgt_package
            self._tgt_pkg_object = _private.ApiPackage(self.apiurl, tgt_project, tgt_package)
        return self._tgt_pkg_object

    def to_xml(self):
        """
        Serialize object to XML.
        The xml tag names and attributes are constructed from the instance's attributes.

        :return: object serialized to XML

        Example::

          self.group_name  -> tag name is "group", attribute name is "name"
          self.src_project -> tag name is "source" (translated via prefix_to_elm dict),
                              attribute name is "project"

        Attributes prefixed with ``opt_`` need a special handling, the resulting xml should
        look like this: ``opt_updatelink`` -> ``<options><updatelink>value</updatelink></options>``.
        Attributes which are ``None`` will be skipped.
        """
        root = ET.Element('action', type=self.type)
        for i in Action.type_args[self.type]:
            prefix, attr = i.split('_', 1)
            vals = getattr(self, i)
            # single, plain elements are _not_ stored in a list
            plain = False
            if vals is None:
                continue
            elif not hasattr(vals, 'append'):
                vals = [vals]
                plain = True
            for val in vals:
                elm = root.find(Action.prefix_to_elm.get(prefix, prefix))
                if elm is None or not plain:
                    elm = ET.Element(Action.prefix_to_elm.get(prefix, prefix))
                    root.append(elm)
                if prefix == 'opt':
                    ET.SubElement(elm, attr).text = val
                else:
                    elm.set(attr, val)
        return root

    def to_str(self):
        """:return: object serialized to pretty-printed XML"""
        root = self.to_xml()
        xmlindent(root)
        return ET.tostring(root, encoding=ET_ENCODING)

    @staticmethod
    def from_xml(action_node, apiurl=None):
        """create action from XML"""
        if action_node is None or \
                action_node.get('type') not in Action.type_args.keys() or \
                action_node.tag not in ('action', 'submit'):
            raise oscerr.WrongArgs('invalid argument')
        elm_to_prefix = {i[1]: i[0] for i in Action.prefix_to_elm.items()}
        kwargs = {}
        for node in action_node:
            prefix = elm_to_prefix.get(node.tag, node.tag)
            if prefix == 'opt':
                data = [('opt_%s' % opt.tag, opt.text.strip()) for opt in node if opt.text]
            else:
                data = [('%s_%s' % (prefix, k), v) for k, v in node.items()]
            # it would be easier to store everything in a list but in
            # this case we would lose some "structure" (see to_xml)
            for k, v in data:
                if k in kwargs:
                    l = kwargs[k]
                    if not hasattr(l, 'append'):
                        l = [l]
                        kwargs[k] = l
                    l.append(v)
                else:
                    kwargs[k] = v
        kwargs["apiurl"] = apiurl
        return Action(action_node.get('type'), **kwargs)


@total_ordering
class Request:
    """Represents a request (``<request />``)"""

    @classmethod
    def from_api(cls, apiurl: str, req_id: int):
        # TODO: deprecate get_request() or move its content here
        req_id = str(req_id)
        return get_request(apiurl, req_id)

    def __init__(self):
        self._init_attributes()

    def _init_attributes(self):
        """initialize attributes with default values"""
        self.reqid = None
        self.creator = ''
        self.title = ''
        self.description = ''
        self.priority = None
        self.state = None
        self.accept_at = None
        self.actions = []
        self.statehistory = []
        self.reviews = []
        self._issues = None

    def __eq__(self, other):
        return int(self.reqid) == int(other.reqid)

    def __lt__(self, other):
        return int(self.reqid) < int(other.reqid)

    @property
    def id(self):
        return self.reqid

    @property
    def issues(self):
        if self._issues is None:
            self._issues = get_request_issues(self.apiurl, self.id)
        return self._issues

    def read(self, root, apiurl=None):
        """read in a request"""
        self._init_attributes()
        self.apiurl = apiurl
        if not root.get('id'):
            raise oscerr.APIError('invalid request: %s\n' % ET.tostring(root, encoding=ET_ENCODING))
        self.reqid = root.get('id')
        if root.get('creator'):
            # OBS 2.8 and later is delivering creator informations
            self.creator = root.get('creator')
        if root.find('state') is None:
            raise oscerr.APIError('invalid request (state expected): %s\n' % ET.tostring(root, encoding=ET_ENCODING))
        self.state = RequestState(root.find('state'))
        action_nodes = root.findall('action')
        if not action_nodes:
            # check for old-style requests
            for i in root.findall('submit'):
                i.set('type', 'submit')
                action_nodes.append(i)
        for action in action_nodes:
            self.actions.append(Action.from_xml(action, self.apiurl))
        for review in root.findall('review'):
            self.reviews.append(ReviewState(review))
        for history_element in root.findall('history'):
            self.statehistory.append(RequestHistory(history_element))
        if not root.find('priority') is None and root.find('priority').text:
            self.priority = root.find('priority').text.strip()
        if not root.find('accept_at') is None and root.find('accept_at').text:
            self.accept_at = root.find('accept_at').text.strip()
        if not root.find('title') is None:
            self.title = root.find('title').text.strip()
        if not root.find('description') is None and root.find('description').text:
            self.description = root.find('description').text.strip()

    def add_action(self, type, **kwargs):
        """add a new action to the request"""
        self.actions.append(Action(type, **kwargs))

    def get_actions(self, *types) -> List[Action]:
        """
        get all actions with a specific type
        (if types is empty return all actions)
        """
        if not types:
            return self.actions
        return [i for i in self.actions if i.type in types]

    def to_xml(self):
        """:return: object serialized to XML"""
        root = ET.Element('request')
        if self.reqid is not None:
            root.set('id', self.reqid)
        if self.creator:
            root.set('creator', self.creator)
        for action in self.actions:
            root.append(action.to_xml())
        if self.state is not None:
            root.append(self.state.to_xml())
        for review in self.reviews:
            root.append(review.to_xml())
        for hist in self.statehistory:
            root.append(hist.to_xml())
        if self.title:
            ET.SubElement(root, 'title').text = self.title
        if self.description:
            ET.SubElement(root, 'description').text = self.description
        if self.accept_at:
            ET.SubElement(root, 'accept_at').text = self.accept_at
        if self.priority:
            ET.SubElement(root, 'priority').text = self.priority
        return root

    def to_str(self):
        """:return: object serialized to pretty-printed XML"""
        root = self.to_xml()
        xmlindent(root)
        return ET.tostring(root, encoding=ET_ENCODING)

    def accept_at_in_hours(self, hours):
        """set auto accept_at time"""
        now = datetime.datetime.utcnow()
        now = now + datetime.timedelta(hours=hours)
        self.accept_at = now.isoformat() + '+00:00'

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

    def format_action(self, action: Action, show_srcupdate=False):
        """
        format an action depending on the action's type.
        A dict which contains the formatted str's is returned.
        """
        def prj_pkg_join(prj, pkg, repository=None):
            if not pkg:
                if not repository:
                    return prj or ''
                return '%s(%s)' % (prj, repository)
            return '%s/%s' % (prj, pkg)

        d = {'type': '%s:' % action.type}
        if action.type == 'set_bugowner':
            if action.person_name:
                d['source'] = action.person_name
            if action.group_name:
                d['source'] = 'group:%s' % action.group_name
            d['target'] = prj_pkg_join(action.tgt_project, action.tgt_package)
        elif action.type == 'change_devel':
            d['source'] = prj_pkg_join(action.tgt_project, action.tgt_package)
            d['target'] = 'developed in %s' % prj_pkg_join(action.src_project, action.src_package)
        elif action.type == 'maintenance_incident':
            d['source'] = '%s ->' % action.src_project
            if action.src_package:
                d['source'] = '%s' % prj_pkg_join(action.src_project, action.src_package)
                if action.src_rev:
                    d['source'] = d['source'] + '@%s' % action.src_rev
                d['source'] = d['source'] + ' ->'
            d['target'] = action.tgt_project
            if action.tgt_releaseproject:
                d['target'] += " (release in " + action.tgt_releaseproject + ")"
            srcupdate = ' '
            if action.opt_sourceupdate and show_srcupdate:
                srcupdate = '(%s)' % action.opt_sourceupdate
        elif action.type in ('maintenance_release', 'release'):
            d['source'] = '%s' % prj_pkg_join(action.src_project, action.src_package)
            if action.src_rev:
                d['source'] = d['source'] + '@%s' % action.src_rev
            d['source'] = d['source'] + ' ->'
            d['target'] = prj_pkg_join(action.tgt_project, action.tgt_package)
        elif action.type == 'submit':
            d['source'] = '%s' % prj_pkg_join(action.src_project, action.src_package)
            if action.src_rev:
                d['source'] = d['source'] + '@%s' % action.src_rev
            if action.opt_sourceupdate and show_srcupdate:
                d['source'] = d['source'] + '(%s)' % action.opt_sourceupdate
            d['source'] = d['source'] + ' ->'
            tgt_package = action.tgt_package
            if action.src_package == action.tgt_package:
                tgt_package = ''
            d['target'] = prj_pkg_join(action.tgt_project, tgt_package)
            if action.opt_makeoriginolder:
                d['target'] = d['target'] + ' ***make origin older***'
            if action.opt_updatelink:
                d['target'] = d['target'] + ' ***update link***'
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
            d['target'] = prj_pkg_join(action.tgt_project, action.tgt_package, action.tgt_repository)
        elif action.type == 'group':
            l = action.grouped_id
            if l is None:
                # there may be no requests in a group action
                l = ''
            if not hasattr(l, 'append'):
                l = [l]
            d['source'] = ', '.join(l) + ' ->'
            d['target'] = self.reqid
        else:
            raise oscerr.APIError('Unknown action type %s\n' % action.type)
        return d

    def list_view(self):
        """return "list view" format"""
        status = self.state.name
        if self.state.name == 'review' and self.state.approver:
            status += "(approved)"
        lines = ['%6s  State:%-10s By:%-12s When:%-19s' % (self.reqid, status, self.state.who, self.state.when)]
        lines += [f"        Created by: {self.creator}"]
        tmpl = '        %(type)-16s %(source)-50s %(target)s'
        for action in self.actions:
            lines.append(tmpl % self.format_action(action))
        tmpl = '        Review by %(type)-10s is %(state)-10s %(by)-50s'
        for review in self.reviews:
            lines.append(tmpl % Request.format_review(review))
        history = ['%s: %s' % (hist.description, hist.who) for hist in self.statehistory]
        if history:
            lines.append('        From: %s' % ' -> '.join(history))
        if self.description:
            lines.append(textwrap.fill(self.description, width=80, initial_indent='        Descr: ',
                                       subsequent_indent='               '))
        lines.append(textwrap.fill(self.state.comment, width=80, initial_indent='        Comment: ',
                                   subsequent_indent='               '))
        return '\n'.join(lines)

    def __str__(self):
        """return "detailed" format"""
        lines = [
            f"Request:    {self.reqid}",
            f"Created by: {self.creator}",
        ]

        if self.accept_at and self.state.name in ['new', 'review']:
            lines.append('    *** This request will get automatically accepted after ' + self.accept_at + ' ! ***\n')

        if self.priority in ['critical', 'important'] and self.state.name in ['new', 'review']:
            lines.append('    *** This request has classified as ' + self.priority + ' ! ***\n')

        if self.state and self.state.approver and self.state.name == 'review':
            lines.append('    *** This request got approved by ' + self.state.approver + '. It will get automatically accepted after last review got accepted! ***\n')

        lines += ["", "Actions:"]
        for action in self.actions:
            fmt_action = self.format_action(action, show_srcupdate=True)
            if action.type == 'delete':
                lines += [f"  {fmt_action['type']:13} {fmt_action['target']}"]
            else:
                lines += [f"  {fmt_action['type']:13} {fmt_action['source']} {fmt_action['target']}"]

        lines += ["", "Message:", textwrap.indent(self.description or "<no message>", prefix="  ")]

        if self.state:
            lines += ["", "State:", f"  {self.state.name:61} {self.state.when:12} {self.state.who}"]
            if self.state.comment:
                lines += [textwrap.indent(self.state.comment, prefix="    | ", predicate=lambda line: True)]

        if self.reviews:
            lines += [""]
            lines += ["Review:"]
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
                lines += [f"  {d['state']:10} {d['by']:50} {d['when']:12} {d['who']}"]
                if review.comment:
                    lines += [textwrap.indent(review.comment, prefix="    | ", predicate=lambda line: True)]

        if self.statehistory:
            lines += ["", "History:"]
            for hist in reversed(self.statehistory):
                lines += [f"  {hist.when:10} {hist.who:30} {hist.description}"]

        return '\n'.join(lines)

    def create(self, apiurl: str, addrevision=False, enforce_branching=False):
        """create a new request"""
        query = {'cmd': 'create'}
        if addrevision:
            query['addrevision'] = "1"
        if enforce_branching:
            query['enforce_branching'] = "1"
        u = makeurl(apiurl, ['request'], query=query)
        f = http_POST(u, data=self.to_str())
        root = ET.fromstring(f.read())
        self.read(root)


def shorttime(t):
    """format time as Apr 02 18:19
    or                Apr 02  2005
    depending on whether it is in the current year
    """
    if time.gmtime()[0] == time.gmtime(t)[0]:
        # same year
        return time.strftime('%b %d %H:%M', time.gmtime(t))
    else:
        return time.strftime('%b %d  %Y', time.gmtime(t))


def is_project_dir(d):
    global store

    return os.path.exists(os.path.join(d, store, '_project')) and not \
        os.path.exists(os.path.join(d, store, '_package'))


def is_package_dir(d):
    global store

    return os.path.exists(os.path.join(d, store, '_project')) and \
        os.path.exists(os.path.join(d, store, '_package'))


def parse_disturl(disturl: str):
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


def parse_buildlogurl(buildlogurl: str):
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
    using the current directory, or none of them if not possible.
    If howmany is 0, proj is expanded if possible, then, if there
    is no idx+1 element in args (or args[idx+1] == '.'), pack is also
    expanded, if possible.
    If howmany is 1, only proj is expanded if possible.

    If args[idx] does not exist, an implicit '.' is assumed.
    If not enough elements up to idx exist, an error is raised.

    See also parseargs(args), slash_split(args), Package.from_paths(args)
    All these need unification, somehow.
    """

    # print args,idx,howmany

    if len(args) < idx:
        raise oscerr.WrongArgs('not enough argument, expected at least %d' % idx)

    if len(args) == idx:
        args += '.'
    if args[idx + 0] == '.':
        if howmany == 0 and len(args) > idx + 1:
            if args[idx + 1] == '.':
                # we have two dots.
                # remove one dot and make sure to expand both proj and pack
                args.pop(idx + 1)
                howmany = 2
            else:
                howmany = 1
        # print args,idx,howmany

        args[idx + 0] = store_read_project('.')
        if howmany == 0:
            try:
                package = store_read_package('.')
                args.insert(idx + 1, package)
            except:
                pass
        elif howmany == 2:
            package = store_read_package('.')
            args.insert(idx + 1, package)
    return args


def findpacs(files, progress_obj=None, fatal=True):
    """collect Package objects belonging to the given files
    and make sure each Package is returned only once"""
    import warnings
    warnings.warn(
        "osc.core.findpacs() is deprecated. "
        "Use osc.core.Package.from_paths() or osc.core.Package.from_paths_nofail() instead.",
        DeprecationWarning
    )
    if fatal:
        return Package.from_paths(files, progress_obj)
    return Package.from_paths_nofail(files, progress_obj)


def read_filemeta(dir):
    global store

    msg = '\'%s\' is not a valid working copy.' % dir
    filesmeta = os.path.join(dir, store, '_files')
    if not is_package_dir(dir):
        raise oscerr.NoWorkingCopy(msg)
    if os.path.isfile(os.path.join(dir, store, '_scm')):
        raise oscerr.NoWorkingCopy("Is managed via scm")
    if not os.path.isfile(filesmeta):
        raise oscerr.NoWorkingCopy('%s (%s does not exist)' % (msg, filesmeta))

    try:
        r = ET.parse(filesmeta)
    except SyntaxError as e:
        raise oscerr.NoWorkingCopy('%s\nWhen parsing .osc/_files, the following error was encountered:\n%s' % (msg, e))
    return r


def store_readlist(dir, name):
    global store

    r = []
    if os.path.exists(os.path.join(dir, store, name)):
        with open(os.path.join(dir, store, name)) as f:
            r = [line.rstrip('\n') for line in f]
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
        with open(fname) as f:
            r = f.readline().strip()

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


def osc_urlencode(data):
    """
    An urlencode wrapper that encodes dictionaries in OBS compatible way:
    {"file": ["foo", "bar"]} -> &file[]=foo&file[]=bar
    """
    data = copy.deepcopy(data)
    if isinstance(data, dict):
        for key, value in list(data.items()):
            if isinstance(value, list):
                del data[key]
                data[f"{key}[]"] = value

    return urlencode(data, doseq=True)


def makeurl(baseurl: str, l, query=None):
    """Given a list of path compoments, construct a complete URL.

    Optional parameters for a query string can be given as a list, as a
    dictionary, or as an already assembled string.
    In case of a dictionary, the parameters will be urlencoded by this
    function. In case of a list not -- this is to be backwards compatible.
    """
    query = query or []
    if conf.config['debug']:
        print('makeurl:', baseurl, l, query)

    if isinstance(query, list):
        query = '&'.join(query)
    elif isinstance(query, dict):
        query = osc_urlencode(query)

    scheme, netloc, path = urlsplit(baseurl)[0:3]
    return urlunsplit((scheme, netloc, '/'.join([path] + list(l)), query, ''))


def check_store_version(dir):
    global store

    versionfile = os.path.join(dir, store, '_osclib_version')
    try:
        with open(versionfile) as f:
            v = f.read().strip()
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
        raise oscerr.WorkingCopyWrongVersion(msg)


def meta_get_packagelist(apiurl: str, prj, deleted=None, expand=False):

    query = {}
    if deleted:
        query['deleted'] = 1
    elif deleted in (False, 0):
        # HACK: Omitted 'deleted' and 'deleted=0' produce different results.
        # By explicit 'deleted=0', we also get multibuild packages listed.
        # See: https://github.com/openSUSE/open-build-service/issues/9715
        query['deleted'] = 0
    if expand:
        query['expand'] = 1

    u = makeurl(apiurl, ['source', prj], query)
    f = http_GET(u)
    root = ET.parse(f).getroot()
    return [node.get('name') for node in root.findall('entry')]


def meta_get_filelist(
    apiurl: str, prj: str, package: str, verbose=False, expand=False, revision=None, meta=False, deleted=False
):
    """return a list of file names,
    or a list File() instances if verbose=True"""

    query: Dict[str, Union[str, int]] = {}
    if deleted:
        query['deleted'] = 1
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
        return [node.get('name') for node in root.findall('entry')]

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


def meta_get_project_list(apiurl: str, deleted=False):
    query = {}
    if deleted:
        query['deleted'] = 1

    u = makeurl(apiurl, ['source'], query)
    f = http_GET(u)
    root = ET.parse(f).getroot()
    return sorted(node.get('name') for node in root if node.get('name'))


def show_project_meta(apiurl: str, prj: str, rev=None, blame=None):
    query = {}
    if blame:
        query['view'] = "blame"
    if rev:
        query['rev'] = rev
        url = makeurl(apiurl, ['source', prj, '_project', '_meta'], query)
        try:
            f = http_GET(url)
        except HTTPError as e:
            error_help = "%d" % e.code
            os_err = e.hdrs.get('X-Opensuse-Errorcode')
            if os_err:
                error_help = "%s (%d) project: %s" % (os_err, e.code, prj)
            if e.code == 404 and os_err == 'unknown_package':
                error_help = 'option -r|--revision is not supported by this OBS version'
            e.osc_msg = 'BuildService API error: %s' % error_help
            raise
    else:
        if blame:
            url = makeurl(apiurl, ['source', prj, '_project', '_meta'], query)
        else:
            url = makeurl(apiurl, ['source', prj, '_meta'])
        f = http_GET(url)
    return f.readlines()


def show_project_conf(apiurl: str, prj: str, rev=None, blame=None):
    query = {}
    url = None
    if rev:
        query['rev'] = rev
    if blame:
        query['view'] = "blame"
        url = makeurl(apiurl, ['source', prj, '_project', '_config'], query=query)
    else:
        url = makeurl(apiurl, ['source', prj, '_config'], query=query)
    f = http_GET(url)
    return f.readlines()


def show_package_trigger_reason(apiurl: str, prj: str, pac: str, repo: str, arch: str):
    url = makeurl(apiurl, ['build', prj, repo, arch, pac, '_reason'])
    try:
        f = http_GET(url)
        return f.read()
    except HTTPError as e:
        e.osc_msg = 'Error getting trigger reason for project \'%s\' package \'%s\'' % (prj, pac)
        raise


def show_package_meta(apiurl: str, prj: str, pac: str, meta=False, blame=None):
    query: Dict[str, Union[str, int]] = {}
    if meta:
        query['meta'] = 1
    if blame:
        query['view'] = "blame"
        query['meta'] = 1

    url = makeurl(apiurl, ['source', prj, pac, '_meta'], query)
    try:
        f = http_GET(url)
        return f.readlines()
    except HTTPError as e:
        e.osc_msg = 'Error getting meta for project \'%s\' package \'%s\'' % (unquote(prj), pac)
        raise


def show_attribute_meta(apiurl: str, prj: str, pac, subpac, attribute, with_defaults, with_project):
    path = []
    path.append('source')
    path.append(prj)
    if pac:
        path.append(pac)
    if pac and subpac:
        path.append(subpac)
    path.append('_attribute')
    if attribute:
        path.append(attribute)
    query = []
    if with_defaults:
        query.append("with_default=1")
    if with_project:
        query.append("with_project=1")
    url = makeurl(apiurl, path, query)
    try:
        f = http_GET(url)
        return f.readlines()
    except HTTPError as e:
        e.osc_msg = 'Error getting meta for project \'%s\' package \'%s\'' % (prj, pac)
        raise


def clean_assets(directory):
    return run_external(conf.config['download-assets-cmd'], '--clean', directory)


def download_assets(directory):
    return run_external(conf.config['download-assets-cmd'], '--unpack', '--noassetdir', directory)


def show_scmsync(apiurl, prj, pac=None):
    if pac:
        m = show_package_meta(apiurl, prj, pac)
    else:
        m = show_project_meta(apiurl, prj)
    node = ET.fromstring(b''.join(m)).find('scmsync')
    if node is None:
        return None
    else:
        return node.text


def show_devel_project(apiurl, prj, pac):
    m = show_package_meta(apiurl, prj, pac)
    node = ET.fromstring(b''.join(m)).find('devel')
    if node is None:
        return None, None
    else:
        return node.get('project'), node.get('package', None)


def set_devel_project(apiurl, prj, pac, devprj=None, devpac=None, print_to="debug"):
    if devprj:
        msg = "Setting devel project of"
    else:
        msg = "Unsetting devel project from"

    msg = _private.format_msg_project_package_options(
        msg,
        prj,
        pac,
        devprj,
        devpac,
    )
    _private.print_msg(msg, print_to=print_to)

    meta = show_package_meta(apiurl, prj, pac)
    root = ET.fromstring(b''.join(meta))
    node = root.find('devel')
    if node is None:
        if devprj is None:
            return
        node = ET.Element('devel')
        root.append(node)
    else:
        if devprj is None:
            root.remove(node)
        else:
            node.clear()
    if devprj:
        node.set('project', devprj)
        if devpac:
            node.set('package', devpac)
    url = makeurl(apiurl, ['source', prj, pac, '_meta'])
    mf = metafile(url, ET.tostring(root, encoding=ET_ENCODING))
    mf.sync()


def show_package_disabled_repos(apiurl: str, prj: str, pac: str):
    m = show_package_meta(apiurl, prj, pac)
    # FIXME: don't work if all repos of a project are disabled and only some are enabled since <disable/> is empty
    try:
        root = ET.fromstring(''.join(m))
        elm = root.find('build')
        r = []
        for node in elm.findall('disable'):
            repo = node.get('repository')
            arch = node.get('arch')
            dis_r = {'repo': repo, 'arch': arch}
            r.append(dis_r)
        return r
    except:
        return None


def show_pattern_metalist(apiurl: str, prj: str):
    url = makeurl(apiurl, ['source', prj, '_pattern'])
    try:
        f = http_GET(url)
        tree = ET.parse(f)
    except HTTPError as e:
        e.osc_msg = 'show_pattern_metalist: Error getting pattern list for project \'%s\'' % prj
        raise
    r = sorted(node.get('name') for node in tree.getroot())
    return r


def show_pattern_meta(apiurl: str, prj: str, pattern: str):
    url = makeurl(apiurl, ['source', prj, '_pattern', pattern])
    try:
        f = http_GET(url)
        return f.readlines()
    except HTTPError as e:
        e.osc_msg = 'show_pattern_meta: Error getting pattern \'%s\' for project \'%s\'' % (pattern, prj)
        raise


def show_configuration(apiurl):
    u = makeurl(apiurl, ['public', 'configuration'])
    f = http_GET(u)
    return f.readlines()


class metafile:
    """metafile that can be manipulated and is stored back after manipulation."""

    class _URLFactory:
        # private class which might go away again...
        def __init__(self, delegate, force_supported=True):
            self._delegate = delegate
            self._force_supported = force_supported

        def is_force_supported(self):
            return self._force_supported

        def __call__(self, **kwargs):
            return self._delegate(**kwargs)

    def __init__(self, url, input, change_is_required=False, file_ext='.xml'):
        if isinstance(url, self._URLFactory):
            self._url_factory = url
        else:
            delegate = lambda **kwargs: url
            # force is not supported for a raw url
            self._url_factory = self._URLFactory(delegate, False)
        self.url = self._url_factory()
        self.change_is_required = change_is_required
        (fd, self.filename) = tempfile.mkstemp(prefix='osc_metafile.', suffix=file_ext)

        open_mode = 'w'
        input_as_str = None

        if not isinstance(input, list):
            input = [input]
        if input and isinstance(input[0], str):
            input_as_str = ''.join(input)
        else:
            open_mode = 'wb'
            input_as_str = b''.join(input)
        f = os.fdopen(fd, open_mode)
        f.write(input_as_str)
        f.close()
        self.hash_orig = dgst(self.filename)

    def sync(self):
        if self.change_is_required and self.hash_orig == dgst(self.filename):
            print('File unchanged. Not saving.')
            os.unlink(self.filename)
            return

        print('Sending meta data...')
        # don't do any exception handling... it's up to the caller what to do in case
        # of an exception
        http_PUT(self.url, file=self.filename)
        os.unlink(self.filename)
        print('Done.')

    def edit(self):
        try:
            try_force = False
            while True:
                if not try_force:
                    run_editor(self.filename)
                try_force = False
                try:
                    self.sync()
                    break
                except HTTPError as e:
                    error_help = "%d" % e.code
                    if e.hdrs.get('X-Opensuse-Errorcode'):
                        error_help = "%s (%d)" % (e.hdrs.get('X-Opensuse-Errorcode'), e.code)

                    print('BuildService API error:', error_help, file=sys.stderr)
                    # examine the error - we can't raise an exception because we might want
                    # to try again
                    root = ET.fromstring(e.read())
                    summary = root.find('summary')
                    if summary is not None:
                        print(summary.text, file=sys.stderr)
                    if self._url_factory.is_force_supported():
                        prompt = 'Try again? ([y/N/f]): '
                    else:
                        prompt = 'Try again? ([y/N): '

                    ri = raw_input(prompt)
                    if ri in ('y', 'Y'):
                        self.url = self._url_factory()
                    elif ri in ('f', 'F') and self._url_factory.is_force_supported():
                        self.url = self._url_factory(force='1')
                        try_force = True
                    else:
                        break
        finally:
            self.discard()

    def discard(self):
        if os.path.exists(self.filename):
            print('discarding %s' % self.filename)
            os.unlink(self.filename)


# different types of metadata
metatypes = {'prj': {'path': 'source/%s/_meta',
                     'template': new_project_templ,
                     'file_ext': '.xml'
                     },
             'pkg': {'path': 'source/%s/%s/_meta',
                     'template': new_package_templ,
                     'file_ext': '.xml'
                     },
             'attribute': {'path': 'source/%s/%s/_meta',
                           'template': new_attribute_templ,
                           'file_ext': '.xml'
                           },
             'prjconf': {'path': 'source/%s/_config',
                         'template': '',
                         'file_ext': '.txt'
                         },
             'user': {'path': 'person/%s',
                      'template': new_user_template,
                      'file_ext': '.xml'
                      },
             'group': {'path': 'group/%s',
                       'template': new_group_template,
                       'file_ext': '.xml'
                       },
             'pattern': {'path': 'source/%s/_pattern/%s',
                         'template': new_pattern_template,
                         'file_ext': '.xml'
                         },
             }


def meta_exists(metatype: str, path_args=None, template_args=None, create_new=True, apiurl=None):

    global metatypes

    if not apiurl:
        apiurl = conf.config['apiurl']
    url = make_meta_url(metatype, path_args, apiurl)
    try:
        data = http_GET(url).readlines()
    except HTTPError as e:
        if e.code == 404 and create_new:
            data = metatypes[metatype]['template']
            if template_args:
                data = StringIO(data % template_args).readlines()
        else:
            raise e

    return data


def make_meta_url(
    metatype: str,
    path_args=None,
    apiurl: Optional[str] = None,
    force=False,
    remove_linking_repositories=False,
    msg=None,
):
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
        query = {'force': '1'}
    if remove_linking_repositories:
        query['remove_linking_repositories'] = '1'
    if msg:
        query['comment'] = msg

    return makeurl(apiurl, [path], query)


def parse_meta_to_string(data: Union[bytes, list, Iterable]) -> str:
    """
    Converts the output of meta_exists into a string value
    """
    # data can be a bytes object, a list with strings, a list with bytes, just a string.
    # So we need the following even if it is ugly.
    if isinstance(data, bytes):
        data = decode_it(data)
    elif isinstance(data, list):
        data = decode_list(data)
    return ''.join(data)


def edit_meta(
    metatype,
    path_args=None,
    data: Optional[List[str]] = None,
    template_args=None,
    edit=False,
    force=False,
    remove_linking_repositories=False,
    change_is_required=False,
    apiurl: Optional[str] = None,
    msg=None,
):

    global metatypes

    if not apiurl:
        apiurl = conf.config['apiurl']
    if not data:
        data = meta_exists(metatype,
                           path_args,
                           template_args,
                           create_new=metatype != 'prjconf',  # prjconf always exists, 404 => unknown prj
                           apiurl=apiurl)

    if edit:
        change_is_required = True

    if metatype == 'pkg':
        # check if the package is a link to a different project
        project, package = path_args
        orgprj = ET.fromstring(parse_meta_to_string(data)).get('project')

        if orgprj is not None and unquote(project) != orgprj:
            print('The package is linked from a different project.')
            print('If you want to edit the meta of the package create first a branch.')
            print('  osc branch %s %s %s' % (orgprj, package, unquote(project)))
            print('  osc meta pkg %s %s -e' % (unquote(project), package))
            return

    def delegate(force=force):
        return make_meta_url(metatype, path_args, apiurl, force, remove_linking_repositories, msg)

    url_factory = metafile._URLFactory(delegate)
    f = metafile(url_factory, data, change_is_required, metatypes[metatype]['file_ext'])

    if edit:
        f.edit()
    else:
        f.sync()


def show_files_meta(
    apiurl: str,
    prj: str,
    pac: str,
    revision=None,
    expand=False,
    linkrev=None,
    linkrepair=False,
    meta=False,
    deleted=False,
):
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
    if deleted:
        query['deleted'] = 1
    if expand:
        query['expand'] = 1
    if linkrepair:
        query['emptylink'] = 1
    f = http_GET(makeurl(apiurl, ['source', prj, pac], query=query))
    return f.read()


def show_upstream_srcmd5(
    apiurl: str, prj: str, pac: str, expand=False, revision=None, meta=False, include_service_files=False, deleted=False
):
    m = show_files_meta(apiurl, prj, pac, expand=expand, revision=revision, meta=meta, deleted=deleted)
    et = ET.fromstring(m)
    if include_service_files:
        try:
            sinfo = et.find('serviceinfo')
            if sinfo is not None and sinfo.get('xsrcmd5') and not sinfo.get('error'):
                return sinfo.get('xsrcmd5')
        except:
            pass
    return et.get('srcmd5')


def show_upstream_xsrcmd5(
    apiurl: str, prj, pac, revision=None, linkrev=None, linkrepair=False, meta=False, include_service_files=False
):
    m = show_files_meta(
        apiurl,
        prj,
        pac,
        revision=revision,
        linkrev=linkrev,
        linkrepair=linkrepair,
        meta=meta,
        expand=include_service_files,
    )
    et = ET.fromstring(m)
    if include_service_files:
        return et.get('srcmd5')

    li_node = et.find('linkinfo')
    if li_node is None:
        return None

    li = Linkinfo()
    li.read(li_node)

    if li.haserror():
        raise oscerr.LinkExpandError(prj, pac, li.error)
    return li.xsrcmd5


def show_project_sourceinfo(apiurl: str, project: str, nofilename: bool, *packages):
    query = ['view=info']
    if packages:
        query.extend(['package=%s' % quote_plus(p) for p in packages])
    if nofilename:
        query.append('nofilename=1')
    f = http_GET(makeurl(apiurl, ['source', project], query=query))
    return f.read()


def get_project_sourceinfo(apiurl: str, project: str, nofilename: bool, *packages):
    try:
        si = show_project_sourceinfo(apiurl, project, nofilename, *packages)
    except HTTPError as e:
        # old API servers (e.g. 2.3.5) do not know the 'nofilename' parameter, so retry without
        if e.code == 400 and nofilename:
            return get_project_sourceinfo(apiurl, project, False, *packages)
        # an uri too long error is sometimes handled as status 500
        # (depending, e.g., on the apache2 configuration)
        if e.code not in (414, 500):
            raise
        if len(packages) == 1:
            raise oscerr.APIError('package name too long: %s' % packages[0])
        n = int(len(packages) / 2)
        pkgs = packages[:n]
        res = get_project_sourceinfo(apiurl, project, nofilename, *pkgs)
        pkgs = packages[n:]
        res.update(get_project_sourceinfo(apiurl, project, nofilename, *pkgs))
        return res
    root = ET.fromstring(si)
    res = {}
    for sinfo in root.findall('sourceinfo'):
        res[sinfo.get('package')] = sinfo
    return res


def show_upstream_rev_vrev(apiurl: str, prj, pac, revision=None, expand=False, meta=False):
    m = show_files_meta(apiurl, prj, pac, revision=revision, expand=expand, meta=meta)
    et = ET.fromstring(m)
    return et.get('rev'), et.get('vrev')


def show_upstream_rev(
    apiurl: str, prj, pac, revision=None, expand=False, linkrev=None, meta=False, include_service_files=False
):
    m = show_files_meta(apiurl, prj, pac, revision=revision, expand=expand, linkrev=linkrev, meta=meta)
    et = ET.fromstring(m)
    if include_service_files:
        try:
            sinfo = et.find('serviceinfo')
            if sinfo is not None and sinfo.get('xsrcmd5') and not sinfo.get('error'):
                return sinfo.get('xsrcmd5')
        except:
            pass
    return et.get('rev')


def read_meta_from_spec(specfile, *args):
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

    tag_pat = r'(?P<tag>^%s)\s*:\s*(?P<val>.*)'
    for tag in tags:
        m = re.compile(tag_pat % tag, re.I | re.M).search(''.join(lines))
        if m and m.group('val'):
            spec_data[tag] = m.group('val').strip()

    section_pat = r'^%s\s*?$'
    for section in sections:
        m = re.compile(section_pat % section, re.I | re.M).search(''.join(lines))
        if m:
            start = lines.index(m.group() + '\n') + 1
        data = []
        for line in lines[start:]:
            if line.startswith('%'):
                break
            data.append(line)
        spec_data[section] = data

    return spec_data


def _get_linux_distro():
    if distro is not None:
        return distro.id()
    return None


def get_default_editor():
    system = platform.system()
    if system == 'Linux':
        dist = _get_linux_distro()
        if dist == 'debian':
            return 'editor'
        elif dist == 'fedora':
            return 'vi'
        return 'vim'
    return 'vi'


def get_default_pager():
    system = platform.system()
    if system == 'Linux':
        dist = _get_linux_distro()
        if dist == 'debian':
            return 'pager'
        return 'less'
    return 'more'


def format_diff_line(line):
    if line.startswith(b"+++") or line.startswith(b"---") or line.startswith(b"Index:"):
        line = b"\x1b[1m" + line + b"\x1b[0m"
    elif line.startswith(b"+"):
        line = b"\x1b[32m" + line + b"\x1b[0m"
    elif line.startswith(b"-"):
        line = b"\x1b[31m" + line + b"\x1b[0m"
    elif line.startswith(b"@"):
        line = b"\x1b[96m" + line + b"\x1b[0m"
    return line


def highlight_diff(diff):
    if sys.stdout.isatty():
        diff = b"\n".join((format_diff_line(line) for line in diff.split(b"\n")))
    return diff


def run_pager(message, tmp_suffix=''):
    if not message:
        return

    if not sys.stdout.isatty():
        if isinstance(message, str):
            print(message)
        else:
            sys.stdout.buffer.write(message)
    else:
        tmpfile = tempfile.NamedTemporaryFile(suffix=tmp_suffix)
        if isinstance(message, str):
            tmpfile.write(bytes(message, 'utf-8'))
        else:
            tmpfile.write(message)
        tmpfile.flush()
        pager = os.getenv("PAGER", default="").strip()
        pager = pager or get_default_pager()
        cmd = shlex.split(pager) + [tmpfile.name]
        try:
            run_external(*cmd)
        finally:
            tmpfile.close()


def run_editor(filename):
    cmd = _editor_command()
    cmd.append(filename)
    return run_external(cmd[0], *cmd[1:])


def _editor_command():
    editor = os.getenv("EDITOR", default="").strip()
    editor = editor or get_default_editor()
    try:
        cmd = shlex.split(editor)
    except SyntaxError:
        cmd = editor.split()
    return cmd


# list of files with message backups
# we'll show this list when osc errors out
MESSAGE_BACKUPS = []


def _edit_message_open_editor(filename, data, orig_mtime):
    editor = _editor_command()
    mtime = os.stat(filename).st_mtime
    if isinstance(data, str):
        data = bytes(data, 'utf-8')
    if mtime == orig_mtime:
        # prepare file for editors
        if editor[0] in ('vi', 'vim'):
            with tempfile.NamedTemporaryFile() as f:
                f.write(data)
                f.flush()
                editor.extend(['-c', ':r %s' % f.name, filename])
                run_external(editor[0], *editor[1:])
        else:
            with open(filename, 'wb') as f:
                f.write(data)
            orig_mtime = os.stat(filename).st_mtime
            run_editor(filename)
    else:
        run_editor(filename)

    if os.stat(filename).st_mtime != orig_mtime:
        # file has changed

        cache_dir = os.path.expanduser("~/.cache/osc/edited-messages")
        try:
            os.makedirs(cache_dir, mode=0o700)
        except FileExistsError:
            pass

        # remove any stored messages older than 1 day
        now = datetime.datetime.now()
        epoch = datetime.datetime.timestamp(now - datetime.timedelta(days=1))
        for fn in os.listdir(cache_dir):
            path = os.path.join(cache_dir, fn)
            if not os.path.isfile(path):
                continue
            mtime = os.path.getmtime(path)
            if mtime < epoch:
                os.unlink(path)

        # store the current message's backup to the cache dir
        message_backup_path = os.path.join(cache_dir, str(now).replace(" ", "_"))
        shutil.copyfile(filename, message_backup_path)
        MESSAGE_BACKUPS.append(message_backup_path)
        return True

    return False


def edit_message(footer='', template='', templatelen=30):
    delim = '--This line, and those below, will be ignored--\n'
    data = ''
    if template != '':
        if templatelen is not None:
            lines = template.splitlines()
            data = '\n'.join(lines[:templatelen])
            if lines[templatelen:]:
                footer = '%s\n\n%s' % ('\n'.join(lines[templatelen:]), footer)
    data += '\n' + delim + '\n' + footer
    return edit_text(data, delim, suffix='.diff', template=template)


def edit_text(data='', delim=None, suffix='.txt', template=''):
    try:
        (fd, filename) = tempfile.mkstemp(prefix='osc-editor', suffix=suffix)
        os.close(fd)
        mtime = os.stat(filename).st_mtime
        ri_err = False
        while True:
            if not ri_err:
                file_changed = _edit_message_open_editor(filename, data, mtime)
                msg = open(filename).read()
            if delim:
                msg = msg.split(delim)[0].rstrip()
            if msg and file_changed:
                break
            else:
                reason = 'Log message not specified'
                if template == msg:
                    reason = 'Default log message was not changed. Press \'c\' to continue.'
                ri = raw_input('%s\na)bort, c)ontinue, e)dit: ' % reason)
                if ri in 'aA':
                    raise oscerr.UserAbort()
                elif ri in 'cC':
                    break
                elif ri in 'eE':
                    ri_err = False
                else:
                    print("%s is not a valid option." % ri)
                    ri_err = True
    finally:
        os.unlink(filename)
    return msg


def clone_request(apiurl: str, reqid, msg=None):
    query = {'cmd': 'branch', 'request': reqid}
    url = makeurl(apiurl, ['source'], query)
    r = http_POST(url, data=msg)
    root = ET.fromstring(r.read())
    project = None
    for i in root.findall('data'):
        if i.get('name') == 'targetproject':
            project = i.text.strip()
    if not project:
        raise oscerr.APIError('invalid data from clone request:\n%s\n' % ET.tostring(root, encoding=ET_ENCODING))
    return project

# create a maintenance release request


def create_release_request(apiurl: str, src_project, message=""):
    r = Request()
    # api will complete the request
    r.add_action('maintenance_release', src_project=src_project)
    r.description = message
    r.create(apiurl)
    return r

# create a maintenance incident per request


def create_maintenance_request(
    apiurl: str,
    src_project,
    src_packages,
    tgt_project,
    tgt_releaseproject,
    opt_sourceupdate,
    message="",
    enforce_branching=False,
    rev=None,
):
    r = Request()
    if src_packages:
        for p in src_packages:
            r.add_action('maintenance_incident', src_project=src_project, src_package=p, src_rev=rev, tgt_project=tgt_project, tgt_releaseproject=tgt_releaseproject, opt_sourceupdate=opt_sourceupdate)
    else:
        r.add_action('maintenance_incident', src_project=src_project, tgt_project=tgt_project, tgt_releaseproject=tgt_releaseproject, opt_sourceupdate=opt_sourceupdate)
    r.description = message
    r.create(apiurl, addrevision=True, enforce_branching=enforce_branching)
    return r


def create_submit_request(
    apiurl: str,
    src_project: str,
    src_package: Optional[str] = None,
    dst_project: Optional[str] = None,
    dst_package: Optional[str] = None,
    message="",
    orev=None,
    src_update=None,
    dst_updatelink=None,
):
    options_block = ""
    package = ""
    if src_package:
        package = """package="%s" """ % (src_package)
    options_block = "<options>"
    if src_update:
        options_block += """<sourceupdate>%s</sourceupdate>""" % (src_update)
    if dst_updatelink:
        options_block += """<updatelink>true</updatelink>"""
    options_block += "</options>"

    # Yes, this kind of xml construction is horrible
    targetxml = ""
    if dst_project:
        packagexml = ""
        if dst_package:
            packagexml = """package="%s" """ % (dst_package)
        targetxml = """<target project="%s" %s /> """ % (dst_project, packagexml)
    # XXX: keep the old template for now in order to work with old obs instances
    xml = """\
<request>
    <action type="submit">
        <source project="%s" %s rev="%s"/>
        %s
        %s
    </action>
    <state name="new"/>
    <description>%s</description>
</request>
""" % (src_project,
       package,
       orev or show_upstream_rev(apiurl, src_project, src_package),
       targetxml,
       options_block,
       _html_escape(message))

    u = makeurl(apiurl, ['request'], query='cmd=create')
    r = None
    try:
        f = http_POST(u, data=xml)
        root = ET.parse(f).getroot()
        r = root.get('id')
    except HTTPError as e:
        if e.hdrs.get('X-Opensuse-Errorcode') == "submit_request_rejected":
            print('WARNING: As the project is in maintenance, a maintenance incident request is')
            print('WARNING: being created (instead of a regular submit request). If this is not your')
            print('WARNING: intention please revoke it to avoid unnecessary work for all involved parties.')
            xpath = 'maintenance/maintains/@project = \'%s\' and attribute/@name = \'%s\'' % (dst_project, conf.config['maintenance_attribute'])
            res = search(apiurl, project_id=xpath)
            root = res['project_id']
            project = root.find('project')
            if project is None:
                print("WARNING: This project is not maintained in the maintenance project specified by '%s', looking elsewhere" % conf.config['maintenance_attribute'])
                xpath = 'maintenance/maintains/@project = \'%s\'' % dst_project
                res = search(apiurl, project_id=xpath)
                root = res['project_id']
                project = root.find('project')
            if project is None:
                raise oscerr.APIError("Server did not define a default maintenance project, can't submit.")
            tproject = project.get('name')
            r = create_maintenance_request(apiurl, src_project, [src_package], tproject, dst_project, src_update, message, rev=orev)
            r = r.reqid
        else:
            raise

    return r


def get_request(apiurl: str, reqid):
    u = makeurl(apiurl, ['request', reqid], {'withfullhistory': '1'})
    f = http_GET(u)
    root = ET.parse(f).getroot()

    r = Request()
    r.read(root, apiurl=apiurl)
    return r


def change_review_state(
    apiurl: str, reqid, newstate, by_user="", by_group="", by_project="", by_package="", message="", supersed=None
):
    query = {"cmd": "changereviewstate", "newstate": newstate}
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


def change_request_state(apiurl: str, reqid, newstate, message="", supersed=None, force=False):
    query = {"cmd": "changestate", "newstate": newstate}
    if supersed:
        query['superseded_by'] = supersed
    if force:
        query['force'] = "1"
    u = makeurl(apiurl,
                ['request', reqid], query=query)
    f = http_POST(u, data=message)

    root = ET.parse(f).getroot()
    return root.get('code', 'unknown')


def change_request_state_template(req, newstate):
    if not req.actions:
        return ''
    action = req.actions[0]
    tmpl_name = '%srequest_%s_template' % (action.type, newstate)
    tmpl = conf.config.get(tmpl_name, '')
    tmpl = tmpl.replace('\\t', '\t').replace('\\n', '\n')
    data = {'reqid': req.reqid, 'type': action.type, 'who': req.creator}
    if req.actions[0].type == 'submit':
        data.update({'src_project': action.src_project,
                     'src_package': action.src_package, 'src_rev': action.src_rev,
                     'dst_project': action.tgt_project, 'dst_package': action.tgt_package,
                     'tgt_project': action.tgt_project, 'tgt_package': action.tgt_package})
    try:
        return tmpl % data
    except KeyError as e:
        print('error: cannot interpolate \'%s\' in \'%s\'' % (e.args[0], tmpl_name), file=sys.stderr)
        return ''


def get_review_list(
    apiurl: str, project="", package="", byuser="", bygroup="", byproject="", bypackage="", states=(), req_type="", req_states=("review",)
):
    # this is so ugly...
    def build_by(xpath, val):
        if 'all' in states:
            return xpath_join(xpath, 'review/%s' % val, op='and')
        elif states:
            s_xp = ''
            for state in states:
                s_xp = xpath_join(s_xp, '@state=\'%s\'' % state, inner=True)
            val = val.strip('[').strip(']')
            return xpath_join(xpath, 'review[%s and (%s)]' % (val, s_xp), op='and')
        else:
            # default case
            return xpath_join(xpath, 'review[%s and @state=\'new\']' % val, op='and')
        return ''

    xpath = ''

    # By default we're interested only in reviews of requests that are in state review.
    for req_state in req_states:
        xpath = xpath_join(xpath, "state/@name='%s'" % req_state, inner=True)

    xpath = "(%s)" % xpath

    if states == ():
        xpath = xpath_join(xpath, 'review/@state=\'new\'', op='and')
    if byuser:
        xpath = build_by(xpath, '@by_user=\'%s\'' % byuser)
    if bygroup:
        xpath = build_by(xpath, '@by_group=\'%s\'' % bygroup)
    if bypackage:
        xpath = build_by(xpath, '@by_project=\'%s\' and @by_package=\'%s\'' % (byproject, bypackage))
    elif byproject:
        xpath = build_by(xpath, '@by_project=\'%s\'' % byproject)

    if req_type:
        xpath = xpath_join(xpath, 'action/@type=\'%s\'' % req_type, op='and')

    # XXX: we cannot use the '|' in the xpath expression because it is not supported
    #      in the backend
    todo = {}
    if project:
        todo['project'] = project
    if package:
        todo['package'] = package
    for kind, val in todo.items():
        xpath_base = 'action/target/@%(kind)s=\'%(val)s\''

        if conf.config['include_request_from_project']:
            xpath_base = xpath_join(xpath_base, 'action/source/@%(kind)s=\'%(val)s\'', op='or', inner=True)
        xpath = xpath_join(xpath, xpath_base % {'kind': kind, 'val': val}, op='and', nexpr_parentheses=True)

    if conf.config['debug']:
        print('[ %s ]' % xpath)
    res = search(apiurl, request=xpath)
    collection = res['request']
    requests = []
    for root in collection.findall('request'):
        r = Request()
        r.read(root)
        requests.append(r)
    return requests


# this function uses the logic in the api which is faster and more exact then the xpath search
def get_request_collection(
    apiurl: str,
    user=None,
    group=None,
    roles=None,
    project=None,
    package=None,
    states=None,
    review_states=None,
    types: List[str] = None,
    ids=None,
    withfullhistory=False
):

    # We don't want to overload server by requesting everything.
    # Let's enforce specifying at least some search criteria.
    if not any([user, group, project, package, ids]):
        raise oscerr.OscValueError("Please specify search criteria")

    query = {"view": "collection"}

    if user:
        query["user"] = user

    if group:
        query["group"] = group

    if roles:
        query["roles"] = ",".join(roles)

    if project:
        query["project"] = project

    if package:
        if not project:
            raise ValueError("Project must be set to query a package; see https://github.com/openSUSE/open-build-service/issues/13075")
        query["package"] = package

    states = states or ("new", "review", "declined")
    if states:
        if "all" not in states:
            query["states"] = ",".join(states)

    if review_states:
        if "all" not in review_states:
            query["review_states"] = ",".join(review_states)

    if types:
        assert not isinstance(types, str)
        query["types"] = ",".join(types)

    if ids:
        query["ids"] = ",".join(ids)

    if withfullhistory:
        query["withfullhistory"] = "1"

    u = makeurl(apiurl, ['request'], query)
    f = http_GET(u)
    res = ET.parse(f).getroot()

    requests = []
    for root in res.findall('request'):
        r = Request()
        r.read(root)

        # post-process results until we switch back to the /search/request
        # which seems to be more suitable for such queries
        exclude = False
        for action in r.actions:
            src_project = getattr(action, "src_project", None)
            src_package = getattr(action, "src_package", None)
            tgt_project = getattr(action, "tgt_project", None)
            tgt_package = getattr(action, "tgt_package", None)

            # skip if neither of source and target project matches
            if "project" in query and query["project"] not in (src_project, tgt_project):
                exclude = True
                break

            # skip if neither of source and target package matches
            if "package" in query and query["package"] not in (src_package, tgt_package):
                exclude = True
                break

            if not conf.config["include_request_from_project"]:
                if "project" in query and "package" in query:
                    if (src_project, src_package) == (query["project"], query["package"]):
                        exclude = True
                        break
                elif "project" in query:
                    if src_project == query["project"]:
                        exclude = True
                        break
        if exclude:
            continue

        requests.append(r)
    return requests


def get_exact_request_list(
    apiurl: str,
    src_project: str,
    dst_project: str,
    src_package: Optional[str] = None,
    dst_package: Optional[str] = None,
    req_who: Optional[str] = None,
    req_state=("new", "review", "declined"),
    req_type: Optional[str] = None,
):
    xpath = ""
    if "all" not in req_state:
        for state in req_state:
            xpath = xpath_join(xpath, 'state/@name=\'%s\'' % state, op='or', inner=True)
        xpath = '(%s)' % xpath
    if req_who:
        xpath = xpath_join(xpath, '(state/@who=\'%(who)s\' or history/@who=\'%(who)s\')' % {'who': req_who}, op='and')

    xpath += " and action[source/@project='%s'" % src_project
    if src_package:
        xpath += " and source/@package='%s'" % src_package
    xpath += " and target/@project='%s'" % dst_project
    if dst_package:
        xpath += " and target/@package='%s'" % dst_package
    xpath += "]"
    if req_type:
        xpath += " and action/@type=\'%s\'" % req_type

    if conf.config['debug']:
        print('[ %s ]' % xpath)

    res = search(apiurl, request=xpath)
    collection = res['request']
    requests = []
    for root in collection.findall('request'):
        r = Request()
        r.read(root)
        requests.append(r)
    return requests


def get_request_list(
    apiurl: str,
    project="",
    package="",
    req_who="",
    req_state=("new", "review", "declined"),
    req_type=None,
    exclude_target_projects=None,
    withfullhistory=False,
    roles=None,
):
    kwargs = {
        "apiurl": apiurl,
        "user": req_who,
        "roles": roles,
        "project": project,
        "package": package,
        "states": req_state,
        "withfullhistory": withfullhistory,
    }

    if req_type is not None:
        kwargs["types"] = [req_type]

    assert not exclude_target_projects, "unsupported"

    return get_request_collection(**kwargs)


# old style search, this is to be removed
def get_user_projpkgs_request_list(
    apiurl: str,
    user,
    req_state=(
        "new",
        "review",
        "declined",
    ),
    req_type=None,
    exclude_projects=None,
    projpkgs=None,
):
    """OBSOLETE: user involved request search is supported by OBS 2.2 server side in a better way
       Return all running requests for all projects/packages where is user is involved"""
    exclude_projects = exclude_projects or []
    projpkgs = projpkgs or {}
    if not projpkgs:
        res = get_user_projpkgs(apiurl, user, exclude_projects=exclude_projects)
        projects = []
        for i in res['project_id'].findall('project'):
            projpkgs[i.get('name')] = []
            projects.append(i.get('name'))
        for i in res['package_id'].findall('package'):
            if not i.get('project') in projects:
                projpkgs.setdefault(i.get('project'), []).append(i.get('name'))
        if not projpkgs:
            return []
    xpath = ''
    for prj, pacs in projpkgs.items():
        if not pacs:
            xpath = xpath_join(xpath, 'action/target/@project=\'%s\'' % prj, inner=True)
        else:
            xp = ''
            for p in pacs:
                xp = xpath_join(xp, 'action/target/@package=\'%s\'' % p, inner=True)
            xp = xpath_join(xp, 'action/target/@project=\'%s\'' % prj, op='and')
            xpath = xpath_join(xpath, xp, inner=True)
    if req_type:
        xpath = xpath_join(xpath, 'action/@type=\'%s\'' % req_type, op='and')
    if 'all' not in req_state:
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


def get_request_log(apiurl: str, reqid):
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
    for state in [r.state] + r.statehistory:
        s = frmt % (state.name, state.who, state.when, str(state.comment))
        data.append(s)
    return data


def check_existing_requests(
    apiurl: str, src_project: str, src_package: str, dst_project: str, dst_package: str, ask=True
):
    reqs = get_exact_request_list(
        apiurl,
        src_project,
        dst_project,
        src_package,
        dst_package,
        req_type="submit",
        req_state=["new", "review", "declined"],
    )
    if not ask:
        return True, reqs
    repl = ''
    if reqs:
        open_request_string = "The following submit request is already open:"
        supersede_request_string = "Supersede the old request?"
        if len(reqs) > 1:
            open_request_string = "The following submit requests are already open:"
            supersede_request_string = "Supersede the old requests?"
        print('%s %s.' %
              (open_request_string, ', '.join([i.reqid for i in reqs])))
        repl = raw_input('%s (y/n/c) ' % supersede_request_string)
        while repl.lower() not in ['c', 'y', 'n']:
            print('%s is not a valid option.' % repl)
            repl = raw_input('%s (y/n/c) ' % supersede_request_string)
        if repl.lower() == 'c':
            print('Aborting', file=sys.stderr)
            raise oscerr.UserAbort()
    return repl == 'y', reqs


def check_existing_maintenance_requests(
    apiurl: str, src_project: str, src_packages: List[str], dst_project: str, release_project, ask=True
):
    reqs = []
    for src_package in src_packages:
        reqs += get_exact_request_list(
            apiurl,
            src_project,
            dst_project,
            src_package,
            None,
            req_type="maintenance_incident",
            req_state=["new", "review", "declined"],
        )
    if not ask:
        return True, reqs
    repl = ''
    if reqs:
        open_request_string = "The following maintenance incident request is already open:"
        supersede_request_string = "Supersede the old request?"
        if len(reqs) > 1:
            open_request_string = "The following maintenance incident requests are already open:"
            supersede_request_string = "Supersede the old requests?"
        print('%s %s.' %
              (open_request_string, ', '.join([i.reqid for i in reqs])))
        repl = raw_input('%s (y/n/c) ' % supersede_request_string)
        while repl.lower() not in ['c', 'y', 'n']:
            print('%s is not a valid option.' % repl)
            repl = raw_input('%s (y/n/c) ' % supersede_request_string)
        if repl.lower() == 'c':
            print('Aborting', file=sys.stderr)
            raise oscerr.UserAbort()
    return repl == 'y', reqs

# old function for compat reasons. Some plugins may call this function.
# and we do not want to break the plugins.


def get_group(apiurl: str, group: str):
    return get_group_meta(apiurl, group)


def get_group_meta(apiurl: str, group: str):
    u = makeurl(apiurl, ['group', quote_plus(group)])
    try:
        f = http_GET(u)
        return b''.join(f.readlines())
    except HTTPError:
        print('group \'%s\' not found' % group)
        return None


def get_user_meta(apiurl: str, user: str):
    u = makeurl(apiurl, ['person', quote_plus(user)])
    try:
        f = http_GET(u)
        return b''.join(f.readlines())
    except HTTPError:
        print('user \'%s\' not found' % user)
        return None


def _get_xml_data(meta, *tags):
    data = []
    if meta is not None:
        root = ET.fromstring(meta)
        for tag in tags:
            elm = root.find(tag)
            if elm is None or elm.text is None:
                data.append('-')
            else:
                data.append(elm.text)
    return data


def get_user_data(apiurl: str, user: str, *tags):
    """get specified tags from the user meta"""
    meta = get_user_meta(apiurl, user)
    return _get_xml_data(meta, *tags)


def get_group_data(apiurl: str, group: str, *tags):
    meta = get_group_meta(apiurl, group)
    return _get_xml_data(meta, *tags)


def download(url: str, filename, progress_obj=None, mtime=None):
    global BUFSIZE

    o = None
    try:
        prefix = os.path.basename(filename)
        path = os.path.dirname(filename)
        (fd, tmpfile) = tempfile.mkstemp(dir=path, prefix=prefix, suffix='.osctmp')
        os.fchmod(fd, 0o644)
        try:
            o = os.fdopen(fd, 'wb')
            for buf in streamfile(url, http_GET, BUFSIZE, progress_obj=progress_obj):
                if isinstance(buf, str):
                    o.write(bytes(buf, "utf-8"))
                else:
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
        utime(filename, (-1, mtime))


def get_source_file(
    apiurl: str,
    prj: str,
    package: str,
    filename,
    targetfilename=None,
    revision=None,
    progress_obj=None,
    mtime=None,
    meta=False,
):
    targetfilename = targetfilename or filename
    query = {}
    if meta:
        query['meta'] = 1
    if revision:
        query['rev'] = revision
    u = makeurl(
        apiurl,
        ["source", prj, package, pathname2url(filename.encode(locale.getpreferredencoding(), "replace"))],
        query=query,
    )
    download(u, targetfilename, progress_obj, mtime)


def get_binary_file(
    apiurl: str,
    prj: str,
    repo: str,
    arch: str,
    filename,
    package: Optional[str] = None,
    target_filename=None,
    target_mtime=None,
    progress_meter=False,
):
    progress_obj = None
    if progress_meter:
        progress_obj = meter.create_text_meter()

    target_filename = target_filename or filename

    # create target directory if it doesn't exist
    target_dir = os.path.dirname(target_filename)
    if target_dir:
        try:
            os.makedirs(target_dir, 0o755)
        except OSError as e:
            if e.errno != errno.EEXIST:
                raise

    where = package or '_repository'
    u = makeurl(apiurl, ['build', prj, repo, arch, where, filename])
    download(u, target_filename, progress_obj, target_mtime)
    if target_filename.endswith('.AppImage'):
        os.chmod(target_filename, 0o755)


def dgst(file):

    # if not os.path.exists(file):
    # return None

    global BUFSIZE
    s = hashlib.md5()
    f = open(file, 'rb')
    while True:
        buf = f.read(BUFSIZE)
        if not buf:
            break
        s.update(buf)
    f.close()
    return s.hexdigest()


def sha256_dgst(file):

    global BUFSIZE

    f = open(file, 'rb')
    s = hashlib.sha256()
    while True:
        buf = f.read(BUFSIZE)
        if not buf:
            break
        s.update(buf)
    f.close()
    return s.hexdigest()


def binary(s):
    """return ``True`` if a string is binary data using diff's heuristic"""
    if s and bytes('\0', "utf-8") in s[:4096]:
        return True
    return False


def binary_file(fn):
    """read 4096 bytes from a file named fn, and call binary() on the data"""
    with open(fn, 'rb') as f:
        return binary(f.read(4096))


def get_source_file_diff(dir, filename, rev, oldfilename=None, olddir=None, origfilename=None):
    """
    This methods diffs oldfilename against filename (so filename will
    be shown as the new file).
    The variable origfilename is used if filename and oldfilename differ
    in their names (for instance if a tempfile is used for filename etc.)
    """
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
        return [b'Binary file \'%s\' has changed.\n' % origfilename.encode()]

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

    from_file = b'%s\t(revision %s)' % (origfilename.encode(), str(rev).encode())
    to_file = b'%s\t(working copy)' % origfilename.encode()

    d = difflib.diff_bytes(difflib.unified_diff, s1, s2,
                           fromfile=from_file,
                           tofile=to_file)
    d = list(d)
    # python2.7's difflib slightly changed the format
    # adapt old format to the new format
    if len(d) > 1:
        d[0] = d[0].replace(b' \n', b'\n')
        d[1] = d[1].replace(b' \n', b'\n')

    # if file doesn't end with newline, we need to append one in the diff result
    for i, line in enumerate(d):
        if not line.endswith(b'\n'):
            d[i] += b'\n\\ No newline at end of file'
            if i + 1 != len(d):
                d[i] += b'\n'
    return d


def server_diff(
    apiurl: str,
    old_project: str,
    old_package: str,
    old_revision: str,
    new_project: str,
    new_package: str,
    new_revision: str,
    unified=False,
    missingok=False,
    meta=False,
    expand=True,
    onlyissues=False,
    full=True,
    xml=False,
    files: list = None,
):
    query: Dict[str, Union[str, int]] = {"cmd": "diff"}
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
    if full:
        query['filelimit'] = 0
        query['tarlimit'] = 0
    if onlyissues:
        query['onlyissues'] = 1
        query['view'] = 'xml'
        query['unified'] = 0
    if files:
        query["file"] = files

    u = makeurl(apiurl, ['source', new_project, new_package], query=query)
    f = http_POST(u, retry_on_400=False)
    if onlyissues and not xml:
        del_issue_list = []
        add_issue_list = []
        chn_issue_list = []
        root = ET.fromstring(f.read())
        node = root.find('issues')
        for issuenode in node.findall('issue'):
            if issuenode.get('state') == 'deleted':
                del_issue_list.append(issuenode.get('label'))
            elif issuenode.get('state') == 'added':
                add_issue_list.append(issuenode.get('label'))
            else:
                chn_issue_list.append(issuenode.get('label'))
        string = 'added:\n----------\n' + '\n'.join(add_issue_list) + \
            '\n\nchanged:\n----------\n' + '\n'.join(chn_issue_list) + \
            '\n\ndeleted:\n----------\n' + '\n'.join(del_issue_list)
        return string
    return f.read()


def server_diff_noex(
    apiurl: str,
    old_project: str,
    old_package: str,
    old_revision: str,
    new_project: str,
    new_package: str,
    new_revision: str,
    unified=False,
    missingok=False,
    meta=False,
    expand=True,
    onlyissues=False,
    xml=False,
    files: list = None,
):
    try:
        return server_diff(apiurl,
                           old_project, old_package, old_revision,
                           new_project, new_package, new_revision,
                           unified, missingok, meta, expand, onlyissues, True, xml, files=files)
    except HTTPError as e:
        msg = None
        body = None
        try:
            body = e.read()
            if b'bad link' not in body:
                return b'# diff failed: ' + body
        except:
            return b'# diff failed with unknown error'

        if expand:
            rdiff = b"## diff on expanded link not possible, showing unexpanded version\n"
            try:
                rdiff += server_diff_noex(apiurl,
                                          old_project, old_package, old_revision,
                                          new_project, new_package, new_revision,
                                          unified, missingok, meta, False, files=files)
            except:
                elm = ET.fromstring(body).find('summary')
                summary = ''
                if elm is not None and elm.text is not None:
                    summary = elm.text
                return b'error: diffing failed: %s' % summary.encode()
            return rdiff


def request_diff(apiurl: str, reqid, superseded_reqid=None):
    query = {'cmd': 'diff'}
    if superseded_reqid:
        query['diff_to_superseded'] = superseded_reqid
    u = makeurl(apiurl, ['request', reqid], query)

    f = http_POST(u)
    return f.read()


def get_request_issues(apiurl: str, reqid):
    """
    gets a request xml with the issues for the request inside and creates
    a list 'issue_list' with a dict of the relevant information for the issues.
    This only works with bugtrackers we can access, like buzilla.o.o
    """
    u = makeurl(apiurl, ['request', reqid], query={'cmd': 'diff', 'view': 'xml', 'withissues': '1'})
    f = http_POST(u)
    request_tree = ET.parse(f).getroot()
    issue_list = []
    for elem in request_tree.iterfind('action/sourcediff/issues/issue'):
        issue_id = elem.get('name')
        encode_search = '@name=\'%s\'' % issue_id
        u = makeurl(apiurl, ['search/issue'], query={'match': encode_search})
        f = http_GET(u)
        collection = ET.parse(f).getroot()
        for cissue in collection:
            issue = {}
            for issue_detail in cissue.iter():
                if issue_detail.text:
                    issue[issue_detail.tag] = issue_detail.text.strip()
            issue_list.append(issue)
    return issue_list


def submit_action_diff(apiurl: str, action: Action):
    """diff a single submit action"""
    # backward compatiblity: only a recent api/backend supports the missingok parameter
    try:
        return server_diff(apiurl, action.tgt_project, action.tgt_package, None,
                           action.src_project, action.src_package, action.src_rev, True, True)
    except HTTPError as e:
        if e.code == 400:
            try:
                return server_diff(apiurl, action.tgt_project, action.tgt_package, None,
                                   action.src_project, action.src_package, action.src_rev, True, False)
            except HTTPError as e:
                if e.code != 404:
                    raise e
                root = ET.fromstring(e.read())
                return b'error: \'%s\' does not exist' % root.find('summary').text.encode()
        elif e.code == 404:
            root = ET.fromstring(e.read())
            return b'error: \'%s\' does not exist' % root.find('summary').text.encode()
        raise e


def make_dir(
    apiurl: str, project: str, package: str, pathname=None, prj_dir=None, package_tracking=True, pkg_path=None
):
    """
    creates the plain directory structure for a package dir.
    The 'apiurl' parameter is needed for the project dir initialization.
    The 'project' and 'package' parameters specify the name of the
    project and the package. The optional 'pathname' parameter is used
    for printing out the message that a new dir was created (default: 'prj_dir/package').
    The optional 'prj_dir' parameter specifies the path to the project dir (default: 'project').
    If pkg_path is not None store the package's content in pkg_path (no project structure is created)
    """
    prj_dir = prj_dir or project

    # FIXME: carefully test each patch component of prj_dir,
    # if we have a .osc/_files entry at that level.
    #   -> if so, we have a package/project clash,
    #      and should rename this path component by appending '.proj'
    #      and give user a warning message, to discourage such clashes

    if pkg_path is None:
        pathname = pathname or getTransActPath(os.path.join(prj_dir, package))
        pkg_path = os.path.join(prj_dir, package)
        if is_package_dir(prj_dir):
            # we want this to become a project directory,
            # but it already is a package directory.
            raise oscerr.OscIOError(None, 'checkout_package: package/project clash. Moving myself away not implemented')

        if not is_project_dir(prj_dir):
            # this directory could exist as a parent direory for one of our earlier
            # checked out sub-projects. in this case, we still need to initialize it.
            print(statfrmt('A', prj_dir))
            Project.init_project(apiurl, prj_dir, project, package_tracking)

        if is_project_dir(os.path.join(prj_dir, package)):
            # the thing exists, but is a project directory and not a package directory
            # FIXME: this should be a warning message to discourage package/project clashes
            raise oscerr.OscIOError(None, 'checkout_package: package/project clash. Moving project away not implemented')
    else:
        pathname = pkg_path

    if not os.path.exists(pkg_path):
        print(statfrmt('A', pathname))
        os.mkdir(os.path.join(pkg_path))
#        os.mkdir(os.path.join(prj_dir, package, store))

    return pkg_path


def checkout_package(
    apiurl: str,
    project: str,
    package: str,
    revision=None,
    pathname=None,
    prj_obj=None,
    expand_link=False,
    prj_dir: Path=None,
    server_service_files=None,
    service_files=None,
    progress_obj=None,
    size_limit=None,
    meta=False,
    outdir=None,
):
    try:
        # the project we're in might be deleted.
        # that'll throw an error then.
        olddir = Path.cwd()
    except FileNotFoundError:
        olddir = Path(os.environ.get("PWD"))

    if not prj_dir:
        prj_dir = olddir
    else:
        sep = "/" if conf.config['checkout_no_colon'] else conf.config['project_separator']
        prj_dir = Path(str(prj_dir).replace(':', sep))

    root_dots = Path('.')
    if conf.config['checkout_rooted']:
        if prj_dir.stem == '/':
            if conf.config['verbose']:
                print("checkout_rooted ignored for %s" % prj_dir)
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
                root_dots = Path("../")
            elif is_project_dir("../.."):
                # testing two levels is better than one.
                # May happen in case of checkout_no_colon, or
                # if project roots were previously inconsistent
                root_dots = Path("../../")
            if is_project_dir(root_dots):
                oldproj = store_read_project(root_dots)
                if conf.config['checkout_no_colon']:
                    n = len(oldproj.split(':'))
                else:
                    n = 1
                root_dots = root_dots / ("../" * n)

    if str(root_dots) != '.':
        if conf.config['verbose']:
            print("%s is project dir of %s. Root found at %s" %
                  (prj_dir, oldproj, os.path.abspath(root_dots)))
        prj_dir = root_dots / prj_dir

    if not pathname:
        pathname = getTransActPath(os.path.join(prj_dir, package))

    # before we create directories and stuff, check if the package actually
    # exists
    meta_data = b''.join(show_package_meta(apiurl, quote_plus(project), quote_plus(package)))
    root = ET.fromstring(meta_data)
    scmsync_element = root.find("scmsync")
    if scmsync_element is not None and scmsync_element.text is not None:
        if not os.path.isfile('/usr/lib/obs/service/obs_scm_bridge'):
            raise oscerr.OscIOError(None, 'Install the obs-scm-bridge package to work on packages managed in scm (git)!')
        scm_url = scmsync_element.text
        directory = make_dir(apiurl, project, package, pathname, prj_dir, conf.config['do_package_tracking'], outdir)
        os.putenv("OSC_VERSION", get_osc_version())
        run_external(['/usr/lib/obs/service/obs_scm_bridge', '--outdir', directory, '--url', scm_url])
        Package.init_package(apiurl, project, package, directory, size_limit, meta, progress_obj, scm_url)

        # add package to <prj>/.obs/_packages
        if not prj_obj:
            prj_obj = Project(prj_dir)
        prj_obj.set_state(package, ' ')
        prj_obj.write_packages()

        return

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
    directory = make_dir(apiurl, project, package, pathname, prj_dir, conf.config['do_package_tracking'], outdir)
    p = Package.init_package(apiurl, project, package, directory, size_limit, meta, progress_obj)
    if isfrozen:
        p.mark_frozen()
    # no project structure is wanted when outdir is used
    if conf.config['do_package_tracking'] and outdir is None:
        # check if we can re-use an existing project object
        if prj_obj is None:
            prj_obj = Project(prj_dir)
        prj_obj.set_state(p.name, ' ')
        prj_obj.write_packages()
    p.update(revision, server_service_files, size_limit)
    if service_files:
        print('Running all source services local')
        p.run_source_services()


def replace_pkg_meta(
    pkgmeta, new_name: str, new_prj: str, keep_maintainers=False, dst_userid=None, keep_develproject=False,
    keep_lock: bool = False,
):
    """
    update pkgmeta with new new_name and new_prj and set calling user as the
    only maintainer (unless keep_maintainers is set). Additionally remove the
    develproject entry (<devel />) unless keep_develproject is true.
    """
    root = ET.fromstring(b''.join(pkgmeta))
    root.set('name', new_name)
    root.set('project', new_prj)
    # never take releasename, it needs to be explicit
    for releasename in root.findall('releasename'):
        root.remove(releasename)
    if not keep_maintainers:
        for person in root.findall('person'):
            root.remove(person)
        for group in root.findall('group'):
            root.remove(group)
    if not keep_develproject:
        for dp in root.findall('devel'):
            root.remove(dp)
    if not keep_lock:
        for node in root.findall("lock"):
            root.remove(node)
    return ET.tostring(root, encoding=ET_ENCODING)


def link_to_branch(apiurl: str, project: str, package: str):
    """
     convert a package with a _link + project.diff to a branch
    """

    if '_link' in meta_get_filelist(apiurl, project, package):
        u = makeurl(apiurl, ['source', project, package], 'cmd=linktobranch')
        http_POST(u)
    else:
        raise oscerr.OscIOError(None, 'no _link file inside project \'%s\' package \'%s\'' % (project, package))


def link_pac(
    src_project: str,
    src_package: str,
    dst_project: str,
    dst_package: str,
    force: bool,
    rev=None,
    cicount=None,
    disable_publish=False,
    missing_target=False,
    vrev=None,
    disable_build=False,
):
    """
    create a linked package
     - "src" is the original package
     - "dst" is the "link" package that we are creating here
    """
    if src_project == dst_project and src_package == dst_package:
        raise oscerr.OscValueError("Cannot link package. Source and target are the same.")

    if rev and not checkRevision(src_project, src_package, rev):
        raise oscerr.OscValueError(f"Revision doesn't exist: {rev}")

    meta_change = False
    dst_meta = ''
    apiurl = conf.config['apiurl']
    try:
        dst_meta = meta_exists(metatype='pkg',
                               path_args=(quote_plus(dst_project), quote_plus(dst_package)),
                               template_args=None,
                               create_new=False, apiurl=apiurl)
        root = ET.fromstring(parse_meta_to_string(dst_meta))
        if root.get('project') != dst_project:
            # The source comes from a different project via a project link, we need to create this instance
            meta_change = True
    except HTTPError as e:
        if e.code != 404:
            raise
        meta_change = True
    if meta_change:
        if missing_target:
            dst_meta = '<package name="%s"><title/><description/></package>' % dst_package
        else:
            src_meta = show_package_meta(apiurl, src_project, src_package)
            dst_meta = replace_pkg_meta(src_meta, dst_package, dst_project)

    if disable_build or disable_publish:
        meta_change = True
        root = ET.fromstring(''.join(dst_meta))

        if disable_build:
            elm = root.find('build')
            if not elm:
                elm = ET.SubElement(root, 'build')
            elm.clear()
            ET.SubElement(elm, 'disable')

        if disable_publish:
            elm = root.find('publish')
            if not elm:
                elm = ET.SubElement(root, 'publish')
            elm.clear()
            ET.SubElement(elm, 'disable')

        dst_meta = ET.tostring(root, encoding=ET_ENCODING)

    if meta_change:
        edit_meta('pkg',
                  path_args=(dst_project, dst_package),
                  data=dst_meta)
    # create the _link file
    # but first, make sure not to overwrite an existing one
    if '_link' in meta_get_filelist(apiurl, dst_project, dst_package):
        if force:
            print('forced overwrite of existing _link file', file=sys.stderr)
        else:
            print(file=sys.stderr)
            print('_link file already exists...! Aborting', file=sys.stderr)
            sys.exit(1)

    if rev:
        rev = ' rev="%s"' % rev
    else:
        rev = ''

    if vrev:
        vrev = ' vrev="%s"' % vrev
    else:
        vrev = ''

    missingok = ''
    if missing_target:
        missingok = ' missingok="true"'

    if cicount:
        cicount = ' cicount="%s"' % cicount
    else:
        cicount = ''

    print('Creating _link...', end=' ')

    project = ''
    if src_project != dst_project:
        project = 'project="%s"' % src_project

    link_template = """\
<link %s package="%s"%s%s%s%s>
<patches>
  <!-- <branch /> for a full copy, default case  -->
  <!-- <apply name="patch" /> apply a patch on the source directory  -->
  <!-- <topadd>%%define build_with_feature_x 1</topadd> add a line on the top (spec file only) -->
  <!-- <add name="file.patch" /> add a patch to be applied after %%setup (spec file only) -->
  <!-- <add name="file.patch" />
        Add a patch to be applied after %%setup (spec file only).
        Patch path prefix stipping can be controlled with the "popt" attribute,
        for example ``popt="1"`` that translates to %%patch -p1.
  -->
  <!-- <delete name="filename" /> delete a file -->
</patches>
</link>
""" % (project, src_package, missingok, rev, vrev, cicount)

    u = makeurl(apiurl, ['source', dst_project, dst_package, '_link'])
    http_PUT(u, data=link_template)
    print('Done.')


def aggregate_pac(
    src_project: str,
    src_package: str,
    dst_project: str,
    dst_package: str,
    repo_map: Optional[dict] = None,
    disable_publish=False,
    nosources=False,
    repo_check=True,
):
    """
    aggregate package
     - "src" is the original package
     - "dst" is the "aggregate" package that we are creating here
     - "map" is a dictionary SRC => TARGET repository mappings
     - "repo_check" determines if presence of repos in the source and destination repos is checked
    """
    if (src_project, src_package) == (dst_project, dst_package):
        raise oscerr.OscValueError("Cannot aggregate package. Source and target are the same.")

    meta_change = False
    dst_meta = ''
    apiurl = conf.config['apiurl']
    repo_map = repo_map or {}

    # we need to remove :flavor from the package names when accessing meta
    src_package_meta = src_package.split(":")[0]
    dst_package_meta = dst_package.split(":")[0]

    try:
        dst_meta = meta_exists(metatype='pkg',
                               path_args=(quote_plus(dst_project), quote_plus(dst_package_meta)),
                               template_args=None,
                               create_new=False, apiurl=apiurl)
        root = ET.fromstring(parse_meta_to_string(dst_meta))
        if root.get('project') != dst_project:
            # The source comes from a different project via a project link, we need to create this instance
            meta_change = True
    except HTTPError as e:
        if e.code != 404:
            raise
        meta_change = True

    if repo_check:
        src_repos = set(get_repositories_of_project(apiurl, src_project))
        dst_repos = set(get_repositories_of_project(apiurl, dst_project))

        if repo_map:
            map_from = set(repo_map.keys())
            map_to = set(repo_map.values())

            # only repos that do not exist in src/dst remain
            delta_from = map_from - src_repos
            delta_to = map_to - dst_repos

            if delta_from or delta_to:
                msg = ["The following repos in repo map do not exist"]
                if delta_from:
                    msg += ["  Source repos: " + ", ".join(sorted(delta_from))]
                if delta_to:
                    msg += ["  Destination repos: " + ", ".join(sorted(delta_to))]
                raise oscerr.OscBaseError("\n".join(msg))
        else:
            # no overlap between src and dst repos leads to the 'broken: missing repositories: <src_project>' message
            if not src_repos & dst_repos:
                msg = [
                    "The source and the destination project do not have any repository names in common.",
                    "Use repo map to specify actual repository mapping.",
                ]
                raise oscerr.OscBaseError("\n".join(msg))

    if meta_change:
        src_meta = show_package_meta(apiurl, src_project, src_package_meta)
        dst_meta = replace_pkg_meta(src_meta, dst_package_meta, dst_project)
        meta_change = True

    if disable_publish:
        meta_change = True
        root = ET.fromstring(''.join(dst_meta))
        elm = root.find('publish')
        if not elm:
            elm = ET.SubElement(root, 'publish')
        elm.clear()
        ET.SubElement(elm, 'disable')
        dst_meta = ET.tostring(root, encoding=ET_ENCODING)
    if meta_change:
        edit_meta('pkg',
                  path_args=(dst_project, dst_package_meta),
                  data=dst_meta)

    # create the _aggregate file
    # but first, make sure not to overwrite an existing one
    if '_aggregate' in meta_get_filelist(apiurl, dst_project, dst_package_meta):
        print(file=sys.stderr)
        print('_aggregate file already exists...! Aborting', file=sys.stderr)
        sys.exit(1)

    print('Creating _aggregate...', end=' ')
    aggregate_template = """\
<aggregatelist>
  <aggregate project="%s">
""" % (src_project)

    aggregate_template += """\
    <package>%s</package>
""" % (src_package)

    if nosources:
        aggregate_template += """\
    <nosources />
"""
    for src, tgt in repo_map.items():
        aggregate_template += """\
    <repository target="%s" source="%s" />
""" % (tgt, src)

    aggregate_template += """\
  </aggregate>
</aggregatelist>
"""

    u = makeurl(apiurl, ['source', dst_project, dst_package_meta, '_aggregate'])
    http_PUT(u, data=aggregate_template)
    print('Done.')


def attribute_branch_pkg(
    apiurl: str,
    attribute: str,
    maintained_update_project_attribute,
    package: str,
    targetproject: str,
    return_existing=False,
    force=False,
    noaccess=False,
    add_repositories=False,
    dryrun=False,
    nodevelproject=False,
    maintenance=False,
):
    """
    Branch packages defined via attributes (via API call)
    """
    query = {'cmd': 'branch'}
    query['attribute'] = attribute
    if targetproject:
        query['target_project'] = targetproject
    if dryrun:
        query['dryrun'] = "1"
    if force:
        query['force'] = "1"
    if noaccess:
        query['noaccess'] = "1"
    if nodevelproject:
        query['ignoredevel'] = '1'
    if add_repositories:
        query['add_repositories'] = "1"
    if maintenance:
        query['maintenance'] = "1"
    if package:
        query['package'] = package
    if maintained_update_project_attribute:
        query['update_project_attribute'] = maintained_update_project_attribute

    u = makeurl(apiurl, ['source'], query=query)
    f = None
    try:
        f = http_POST(u)
    except HTTPError as e:
        root = ET.fromstring(e.read())
        summary = root.find('summary')
        if summary is not None and summary.text is not None:
            raise oscerr.APIError(summary.text)
        msg = 'unexpected response: %s' % ET.tostring(root, encoding=ET_ENCODING)
        raise oscerr.APIError(msg)

    r = None

    root = ET.fromstring(f.read())
    if dryrun:
        return root
    # TODO: change api here and return parsed XML as class
    if conf.config['http_debug']:
        print(ET.tostring(root, encoding=ET_ENCODING), file=sys.stderr)
    for node in root.findall('data'):
        r = node.get('name')
        if r and r == 'targetproject':
            return node.text

    return r


def branch_pkg(
    apiurl: str,
    src_project: str,
    src_package: str,
    nodevelproject=False,
    rev=None,
    linkrev=None,
    target_project: Optional[str] = None,
    target_package=None,
    return_existing=False,
    msg="",
    force=False,
    noaccess=False,
    add_repositories=False,
    add_repositories_block=None,
    add_repositories_rebuild=None,
    extend_package_names=False,
    missingok=False,
    maintenance=False,
    newinstance=False,
    disable_build=False,
):
    """
    Branch a package (via API call)
    """
    query = {'cmd': 'branch'}
    if nodevelproject:
        query['ignoredevel'] = '1'
    if force:
        query['force'] = '1'
    if noaccess:
        query['noaccess'] = '1'
    if add_repositories:
        query['add_repositories'] = "1"
    if add_repositories_block:
        query['add_repositories_block'] = add_repositories_block
    if add_repositories_rebuild:
        query['add_repositories_rebuild'] = add_repositories_rebuild
    if maintenance:
        query['maintenance'] = "1"
    if missingok:
        query['missingok'] = "1"
    if newinstance:
        query['newinstance'] = "1"
    if extend_package_names:
        query['extend_package_names'] = "1"
    if rev:
        query['rev'] = rev
    if linkrev:
        query['linkrev'] = linkrev
    if target_project:
        query['target_project'] = target_project
    if target_package:
        query['target_package'] = target_package
    if msg:
        query['comment'] = msg
    u = makeurl(apiurl, ['source', src_project, src_package], query=query)
    try:
        f = http_POST(u)
    except HTTPError as e:
        root = ET.fromstring(e.read())
        if missingok:
            if root and root.get('code') == "not_missing":
                raise oscerr.NotMissing("Package exists already via project link, but link will point to given project")
        summary = root.find('summary')
        if summary is None:
            raise oscerr.APIError('unexpected response:\n%s' % ET.tostring(root, encoding=ET_ENCODING))
        if not return_existing:
            raise oscerr.APIError('failed to branch: %s' % summary.text)
        m = re.match(r"branch target package already exists: (\S+)/(\S+)", summary.text)
        if not m:
            e.msg += '\n' + summary.text
            raise
        return (True, m.group(1), m.group(2), None, None)

    root = ET.fromstring(f.read())
    if conf.config['http_debug']:
        print(ET.tostring(root, encoding=ET_ENCODING), file=sys.stderr)
    data = {}
    for i in root.findall('data'):
        data[i.get('name')] = i.text

    if disable_build:
        target_meta = show_package_meta(apiurl, data["targetproject"], data["targetpackage"])
        root = ET.fromstring(b''.join(target_meta))

        elm = root.find('build')
        if not elm:
            elm = ET.SubElement(root, 'build')
        elm.clear()
        ET.SubElement(elm, 'disable')

        target_meta = ET.tostring(root, encoding=ET_ENCODING)
        edit_meta('pkg', path_args=(data["targetproject"], data["targetpackage"]), data=target_meta)

    return (False, data.get('targetproject', None), data.get('targetpackage', None),
            data.get('sourceproject', None), data.get('sourcepackage', None))


def copy_pac(
    src_apiurl: str,
    src_project: str,
    src_package: str,
    dst_apiurl: str,
    dst_project: str,
    dst_package: str,
    client_side_copy=False,
    keep_maintainers=False,
    keep_develproject=False,
    expand=False,
    revision=None,
    comment=None,
    force_meta_update=None,
    keep_link=None,
):
    """
    Create a copy of a package.

    Copying can be done by downloading the files from one package and commit
    them into the other by uploading them (client-side copy) --
    or by the server, in a single api call.
    """
    if (src_apiurl, src_project, src_package) == (dst_apiurl, dst_project, dst_package):
        # special cases when source and target can be the same:
        # * expanding sources
        # * downgrading package to an old revision
        if not any([expand, revision]):
            raise oscerr.OscValueError("Cannot copy package. Source and target are the same.")

    if not (src_apiurl == dst_apiurl and src_project == dst_project
            and src_package == dst_package):
        src_meta = show_package_meta(src_apiurl, src_project, src_package)
        dst_userid = conf.get_apiurl_usr(dst_apiurl)
        src_meta = replace_pkg_meta(src_meta, dst_package, dst_project, keep_maintainers,
                                    dst_userid, keep_develproject)

        url = make_meta_url('pkg', (quote_plus(dst_project),) + (quote_plus(dst_package),), dst_apiurl)
        found = None
        try:
            found = http_GET(url).readlines()
        except HTTPError as e:
            pass
        if force_meta_update or not found:
            print('Sending meta data...')
            u = makeurl(dst_apiurl, ['source', dst_project, dst_package, '_meta'])
            http_PUT(u, data=src_meta)

    print('Copying files...')
    if not client_side_copy:
        query = {'cmd': 'copy', 'oproject': src_project, 'opackage': src_package}
        if expand or keep_link:
            query['expand'] = '1'
        if keep_link:
            query['keeplink'] = '1'
        if revision:
            query['orev'] = revision
        if comment:
            query['comment'] = comment
        u = makeurl(dst_apiurl, ['source', dst_project, dst_package], query=query)
        f = http_POST(u)
        return f.read()

    else:
        # copy one file after the other
        query = {'rev': 'upload'}
        xml = show_files_meta(src_apiurl, src_project, src_package,
                              expand=expand, revision=revision)
        filelist = ET.fromstring(xml)
        revision = filelist.get('srcmd5')
        # filter out _service: files
        for entry in filelist.findall('entry'):
            # hmm the old code also checked for _service_ (but this is
            # probably a relict from former times (if at all))
            if entry.get('name').startswith('_service:'):
                filelist.remove(entry)
        tfilelist = Package.commit_filelist(dst_apiurl, dst_project,
                                            dst_package, filelist, msg=comment)
        todo = Package.commit_get_missing(tfilelist)
        for filename in todo:
            print(' ', filename)
            # hmm ideally, we would pass a file-like (that delegates to
            # streamfile) to http_PUT...
            with tempfile.NamedTemporaryFile(prefix='osc-copypac') as f:
                get_source_file(src_apiurl, src_project, src_package, filename,
                                targetfilename=f.name, revision=revision)
                path = ['source', dst_project, dst_package, pathname2url(filename)]
                u = makeurl(dst_apiurl, path, query={'rev': 'repository'})
                http_PUT(u, file=f.name)
        tfilelist = Package.commit_filelist(dst_apiurl, dst_project, dst_package,
                                            filelist, msg=comment)
        todo = Package.commit_get_missing(tfilelist)
        if todo:
            raise oscerr.APIError('failed to copy: %s' % ', '.join(todo))
        return 'Done.'


def lock(apiurl: str, project: str, package: str, msg: str = None):
    url_path = ["source", project]
    if package:
        url_path += [package]

    url_query = {
        "cmd": "set_flag",
        "flag": "lock",
        "status": "enable",
    }

    if msg:
        url_query["comment"] = msg

    _private.api.post(apiurl, url_path, url_query)


def unlock_package(apiurl: str, prj: str, pac: str, msg):
    query = {'cmd': 'unlock', 'comment': msg}
    u = makeurl(apiurl, ['source', prj, pac], query)
    http_POST(u)


def unlock_project(apiurl: str, prj: str, msg=None):
    query = {'cmd': 'unlock', 'comment': msg}
    u = makeurl(apiurl, ['source', prj], query)
    http_POST(u)


def undelete_package(apiurl: str, prj: str, pac: str, msg=None):
    query = {'cmd': 'undelete'}
    if msg:
        query['comment'] = msg
    else:
        query['comment'] = 'undeleted via osc'
    u = makeurl(apiurl, ['source', prj, pac], query)
    http_POST(u)


def undelete_project(apiurl: str, prj: str, msg=None):
    query = {'cmd': 'undelete'}
    if msg:
        query['comment'] = msg
    else:
        query['comment'] = 'undeleted via osc'
    u = makeurl(apiurl, ['source', prj], query)
    http_POST(u)


def delete_package(apiurl: str, prj: str, pac: str, force=False, msg=None):
    if not force:
        requests = get_request_collection(apiurl, project=prj, package=pac)
        if requests:
            error_msg = \
                "Package has pending requests. Deleting the package will break them. " \
                "They should be accepted/declined/revoked before deleting the package. " \
                "Or just use the 'force' option"
            raise oscerr.PackageError(prj, pac, error_msg)

    query = {}
    if force:
        query['force'] = "1"
    if msg:
        query['comment'] = msg
    u = makeurl(apiurl, ['source', prj, pac], query)
    http_DELETE(u)


def delete_project(apiurl: str, prj: str, force=False, msg=None, recursive=False):
    if not recursive:
        packages = meta_get_packagelist(apiurl, prj)
        if packages:
            error_msg = \
                "Project contains packages. It must be empty before deleting it. " \
                "If you are sure that you want to remove this project and all its " \
                "packages use the 'recursive' option."
            raise oscerr.ProjectError(prj, error_msg)

    query = {}
    if force:
        query['force'] = "1"
    if msg:
        query['comment'] = msg
    u = makeurl(apiurl, ['source', prj], query)
    http_DELETE(u)


def delete_files(apiurl: str, prj: str, pac: str, files):
    for filename in files:
        u = makeurl(apiurl, ['source', prj, pac, filename], query={'comment': 'removed %s' % (filename, )})
        http_DELETE(u)


# old compat lib call
def get_platforms(apiurl: str):
    return get_repositories(apiurl)


def get_repositories(apiurl: str):
    f = http_GET(makeurl(apiurl, ['platform']))
    tree = ET.parse(f)
    r = sorted(node.get('name') for node in tree.getroot())
    return r


def get_distributions(apiurl: str):
    """Returns list of dicts with headers
      'distribution', 'project', 'repository', 'reponame'"""

    f = http_GET(makeurl(apiurl, ['distributions']))
    root = ET.fromstring(b''.join(f))

    distlist = []
    for node in root.findall('distribution'):
        dmap = {}
        for child in node:
            if child.tag == 'name':
                dmap['distribution'] = child.text
            elif child.tag in ('project', 'repository', 'reponame'):
                dmap[child.tag] = child.text
        distlist.append(dmap)
    return distlist


# old compat lib call
def get_platforms_of_project(apiurl: str, prj: str):
    return get_repositories_of_project(apiurl, prj)


def get_repositories_of_project(apiurl: str, prj: str):
    f = show_project_meta(apiurl, prj)
    root = ET.fromstring(b''.join(f))

    r = [node.get('name') for node in root.findall('repository')]
    return r


class Repo:
    repo_line_templ = '%-15s %-10s'

    def __init__(self, name: str, arch: str):
        self.name = name
        self.arch = arch

    def __str__(self):
        return self.repo_line_templ % (self.name, self.arch)

    def __repr__(self):
        return 'Repo(%s %s)' % (self.name, self.arch)

    @staticmethod
    def fromfile(filename):
        if not os.path.exists(filename):
            return []
        repos = []
        lines = open(filename).readlines()
        for line in lines:
            data = line.split()
            if len(data) == 2:
                repos.append(Repo(data[0], data[1]))
            elif len(data) == 1:
                # only for backward compatibility
                repos.append(Repo(data[0], ''))
        return repos

    @staticmethod
    def tofile(filename, repos):
        with open(filename, 'w') as f:
            for repo in repos:
                f.write('%s %s\n' % (repo.name, repo.arch))


def get_repos_of_project(apiurl, prj):
    f = show_project_meta(apiurl, prj)
    root = ET.fromstring(b''.join(f))

    for node in root.findall('repository'):
        for node2 in node.findall('arch'):
            yield Repo(node.get('name'), node2.text)


def get_binarylist(
    apiurl: str, prj: str, repo: str, arch: str, package: Optional[str] = None, verbose=False, withccache=False
):
    what = package or '_repository'
    query = {}
    if withccache:
        query['withccache'] = 1
    u = makeurl(apiurl, ['build', prj, repo, arch, what], query=query)
    f = http_GET(u)
    tree = ET.parse(f)
    if not verbose:
        return [node.get('filename') for node in tree.findall('binary')]
    else:
        l = []
        for node in tree.findall('binary'):
            f = File(node.get('filename'),
                     None,
                     int(node.get('size') or 0) or None,
                     int(node.get('mtime') or 0) or None)
            l.append(f)
        return l


def get_binarylist_published(apiurl: str, prj: str, repo: str, arch: str):
    u = makeurl(apiurl, ['published', prj, repo, arch])
    f = http_GET(u)
    tree = ET.parse(f)
    r = [node.get('name') for node in tree.findall('entry')]
    return r


def show_results_meta(
    apiurl: str,
    prj: str,
    package: Optional[str] = None,
    lastbuild: Optional[str] = None,
    repository: Optional[List[str]] = None,
    arch: Optional[List[str]] = None,
    oldstate: Optional[str] = None,
    multibuild=False,
    locallink=False,
    code: Optional[str] = None,
):
    repository = repository or []
    arch = arch or []
    query = []
    if package:
        query.append('package=%s' % quote_plus(package))
    if oldstate:
        query.append('oldstate=%s' % quote_plus(oldstate))
    if lastbuild:
        query.append('lastbuild=1')
    if multibuild:
        query.append('multibuild=1')
    if locallink:
        query.append('locallink=1')
    if code:
        query.append('code=%s' % quote_plus(code))
    for repo in repository:
        query.append('repository=%s' % quote_plus(repo))
    for a in arch:
        query.append('arch=%s' % quote_plus(a))
    u = makeurl(apiurl, ['build', prj, '_result'], query=query)
    f = http_GET(u)
    return f.readlines()


def show_prj_results_meta(
    apiurl: str, prj: str, repositories: Optional[List[str]] = None, arches: Optional[List[str]] = None
):
    # this function is only needed for backward/api compatibility
    if repositories is None:
        repositories = []
    if arches is None:
        arches = []
    return show_results_meta(apiurl, prj, repository=repositories, arch=arches)


def result_xml_to_dicts(xml):
    # assumption: xml contains at most one status element (maybe we should
    # generalize this to arbitrary status element)
    root = ET.fromstring(xml)
    for node in root.findall('result'):
        rmap = {}
        rmap['project'] = rmap['prj'] = node.get('project')
        rmap['repository'] = rmap['repo'] = rmap['rep'] = node.get('repository')
        rmap['arch'] = node.get('arch')
        rmap['state'] = node.get('state')
        rmap['dirty'] = node.get('dirty') == 'true' or node.get('code') == 'blocked'
        rmap['repostate'] = node.get('code')
        rmap['pkg'] = rmap['package'] = rmap['pac'] = ''
        rmap['code'] = node.get('code')
        rmap['details'] = node.get('details')
        # the way we currently use this function, there should be
        # always a status element
        snodes = node.findall('status')
        is_multi = len(snodes) > 1
        if len(snodes) < 1:
            # the repository setup is broken
            smap = dict(rmap)
            smap['pkg'] = "_repository"
            smap['code'] = rmap['repostate']
            smap['details'] = node.get('details')
            yield smap, is_multi
            continue

        for statusnode in snodes:
            smap = dict(rmap)
            smap['pkg'] = smap['package'] = smap['pac'] = statusnode.get('package')
            smap['code'] = statusnode.get('code', '')
            details = statusnode.find('details')
            if details is not None:
                smap['details'] = details.text
            if rmap['code'] == 'broken':
                # real error just becomes visible in details/verbose
                smap['code'] = rmap['code']
                smap['details'] = "repository: " + rmap['details']
            yield smap, is_multi


def format_results(results, format):
    """apply selected format on each dict in results and return it as a list of strings"""
    return [format % r for r in results]


def get_results(apiurl: str, project: str, package: str, verbose=False, printJoin="", *args, **kwargs):
    """returns list of/or prints a human readable status for the specified package"""
    # hmm the function name is a bit too generic - something like
    # get_package_results_human would be better, but this would break the existing
    # api (unless we keep get_results around as well)...
    result_line_templ = '%(rep)-20s %(arch)-10s %(status)s'
    result_line_mb_templ = '%(rep)-20s %(arch)-10s %(pkg)-30s %(status)s'
    r = []
    printed = False
    multibuild_packages = kwargs.pop('multibuild_packages', [])
    show_excluded = kwargs.pop('showexcl', False)
    code_filter = kwargs.get('code')
    for results in get_package_results(apiurl, project, package, **kwargs):
        r = []
        for res, is_multi in result_xml_to_dicts(results):
            if not show_excluded and res['code'] == 'excluded':
                continue
            if '_oldstate' in res:
                oldstate = res['_oldstate']
                continue
            if multibuild_packages:
                l = res['pkg'].rsplit(':', 1)
                if (len(l) != 2 or l[1] not in multibuild_packages) and not (len(l) == 1 and "" in multibuild_packages):
                    # special case: packages without flavor when multibuild_packages contains an empty string
                    continue
            res['status'] = res['code']
            if verbose and res['details'] is not None:
                if res['code'] in ('unresolvable', 'expansion error'):
                    lines = res['details'].split(',')
                    res['status'] += ': \n      ' + '\n     '.join(lines)
                else:
                    res['status'] += ': %s' % res['details']
            elif res['code'] in ('scheduled', ) and res['details']:
                # highlight scheduled jobs with possible dispatch problems
                res['status'] += '*'
            if res['dirty']:
                if verbose:
                    res['status'] = 'outdated (was: %s)' % res['status']
                else:
                    res['status'] += '*'
            elif res['code'] in ('succeeded', ) and res['repostate'] != "published":
                if verbose:
                    res['status'] += '(unpublished)'
                else:
                    res['status'] += '*'
            # we need to do the code filtering again, because result_xml_to_dicts returns the code
            # of the repository if the result is already prefiltered by the backend. So we need
            # to filter out the repository states.
            if code_filter is None or code_filter == res['code']:
                if is_multi:
                    r.append(result_line_mb_templ % res)
                else:
                    r.append(result_line_templ % res)

        if printJoin:
            if printed:
                # will print a newline if already a result was printed (improves readability)
                print()
            print(printJoin.join(r))
            printed = True
    return r


def get_package_results(apiurl: str, project: str, package: Optional[str] = None, wait=False, *args, **kwargs):
    """generator that returns a the package results as an xml structure"""
    xml = ''
    waiting_states = ('blocked', 'scheduled', 'dispatching', 'building',
                      'signing', 'finished')
    while True:
        waiting = False
        try:
            xml = b''.join(show_results_meta(apiurl, project, package, *args, **kwargs))
        except HTTPError as e:
            # check for simple timeout error and fetch again
            if e.code == 502 or e.code == 504:
                # re-try result request
                continue
            root = ET.fromstring(e.read())
            if e.code == 400 and kwargs.get('multibuild') and re.search('multibuild', getattr(root.find('summary'), 'text', '')):
                kwargs['multibuild'] = None
                kwargs['locallink'] = None
                continue
            raise
        root = ET.fromstring(xml)
        kwargs['oldstate'] = root.get('state')
        for result in root.findall('result'):
            if result.get('dirty') is not None:
                waiting = True
                break
            elif result.get('code') in waiting_states:
                waiting = True
                break
            else:
                pkg = result.find('status')
                if pkg is not None and pkg.get('code') in waiting_states:
                    waiting = True
                    break

        if not wait or not waiting:
            break
        else:
            yield xml
    yield xml


def get_prj_results(
    apiurl: str,
    prj: str,
    hide_legend=False,
    csv=False,
    status_filter=None,
    name_filter=None,
    arch=None,
    repo=None,
    vertical=None,
    show_excluded=None,
    brief=False,
):
    # print '----------------------------------------'
    global buildstatus_symbols

    r = []

    f = show_prj_results_meta(apiurl, prj)
    root = ET.fromstring(b''.join(f))

    if name_filter is not None:
        name_filter = re.compile(name_filter)

    pacs = []
    # sequence of (repo,arch) tuples
    targets = []
    # {package: {(repo,arch): status}}
    status = {}
    if root.find('result') is None:
        return []
    for results in root.findall('result'):
        for node in results:
            pacs.append(node.get('package'))
    pacs = sorted(list(set(pacs)))
    for node in root.findall('result'):
        # filter architecture and repository
        if arch and node.get('arch') not in arch:
            continue
        if repo and node.get('repository') not in repo:
            continue
        if node.get('dirty') == "true":
            state = "outdated"
        else:
            state = node.get('state')
        if node.get('details'):
            state += ' details: ' + node.get('details')
        tg = (node.get('repository'), node.get('arch'), state)
        targets.append(tg)
        for pacnode in node.findall('status'):
            pac = pacnode.get('package')
            if pac not in status:
                status[pac] = {}
            status[pac][tg] = pacnode.get('code')
    targets.sort()

    # filter option
    filters = []
    if status_filter or name_filter or not show_excluded:
        pacs_to_show = []
        targets_to_show = []

        # filtering for Package Status
        if status_filter:
            if status_filter in buildstatus_symbols.values():
                # a list is needed because if status_filter == "U"
                # we have to filter either an "expansion error" (obsolete)
                # or an "unresolvable" state
                for txt, sym in buildstatus_symbols.items():
                    if sym == status_filter:
                        filters.append(txt)
            else:
                filters.append(status_filter)
            for filt_txt in filters:
                for pkg in status.keys():
                    for repo in status[pkg].keys():
                        if status[pkg][repo] == filt_txt:
                            if not name_filter:
                                pacs_to_show.append(pkg)
                                targets_to_show.append(repo)
                            elif name_filter.search(pkg) is not None:
                                pacs_to_show.append(pkg)
        # filtering for Package Name
        elif name_filter:
            for pkg in pacs:
                if name_filter.search(pkg) is not None:
                    pacs_to_show.append(pkg)

        # filter non building states
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

        pacs = [i for i in pacs if i in pacs_to_show]
        if targets_to_show:
            targets = [i for i in targets if i in targets_to_show]

    # csv output
    if csv:
        # TODO: option to disable the table header
        row = ['_'] + ['/'.join(tg) for tg in targets]
        r.append(';'.join(row))
        for pac in pacs:
            row = [pac] + [status[pac][tg] for tg in targets if tg in status[pac]]
            r.append(';'.join(row))
        return r

    if brief:
        for pac, repo_states in status.items():
            for repo, state in repo_states.items():
                if filters and state not in filters:
                    continue
                r.append('%s %s %s %s' % (pac, repo[0], repo[1], state))
        return r

    if not vertical:
        # human readable output
        max_pacs = 40
        for startpac in range(0, len(pacs), max_pacs):
            offset = 0
            for pac in pacs[startpac:startpac + max_pacs]:
                r.append(' |' * offset + ' ' + pac)
                offset += 1

            for tg in targets:
                line = []
                line.append(' ')
                for pac in pacs[startpac:startpac + max_pacs]:
                    st = ''
                    if pac not in status or tg not in status[pac]:
                        # for newly added packages, status may be missing
                        st = '?'
                    else:
                        try:
                            st = buildstatus_symbols[status[pac][tg]]
                        except:
                            print('osc: warn: unknown status \'%s\'...' % status[pac][tg])
                            print('please edit osc/core.py, and extend the buildstatus_symbols dictionary.')
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
            r.append('| ' * offset + '%s %s (%s)' % tg)
            offset += 1

        for pac in pacs:
            line = []
            for tg in targets:
                st = ''
                if pac not in status or tg not in status[pac]:
                    # for newly added packages, status may be missing
                    st = '?'
                else:
                    try:
                        st = buildstatus_symbols[status[pac][tg]]
                    except:
                        print('osc: warn: unknown status \'%s\'...' % status[pac][tg])
                        print('please edit osc/core.py, and extend the buildstatus_symbols dictionary.')
                        st = '?'
                        buildstatus_symbols[status[pac][tg]] = '?'
                line.append(st)
            line.append(' ' + pac)
            r.append(' '.join(line))

        line = []
        for i in range(0, len(targets)):
            line.append(str(i % 10))
        r.append(' '.join(line))

        r.append('')

    if not hide_legend and len(pacs):
        r.append(' Legend:')
        legend = []
        for i, j in buildstatus_symbols.items():
            if i == "expansion error":
                continue
            legend.append('%3s %-20s' % (j, i))
        legend.append('  ? buildstatus not available (only new packages)')

        if vertical:
            for i in range(0, len(targets)):
                s = '%1d %s %s (%s)' % (i % 10, targets[i][0], targets[i][1], targets[i][2])
                if i < len(legend):
                    legend[i] += s
                else:
                    legend.append(' ' * 24 + s)

        r += legend

    return r


def streamfile(url: str, http_meth=http_GET, bufsize=8192, data=None, progress_obj=None, text=None):
    """
    performs http_meth on url and read bufsize bytes from the response
    until EOF is reached. After each read bufsize bytes are yielded to the
    caller. A spezial usage is bufsize="line" to read line by line (text).
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
            print('\n\nRetry %d --' % (retries - 1), url, file=sys.stderr)
        f = http_meth.__call__(url, data=data)
        cl = f.info().get('Content-Length')

    if cl is not None:
        # sometimes the proxy adds the same header again
        # which yields in value like '3495, 3495'
        # use the first of these values (should be all the same)
        cl = cl.split(',')[0]
        cl = int(cl)

    if progress_obj:
        if not text:
            basename = os.path.basename(urlsplit(url)[2])
        else:
            basename = text
        progress_obj.start(basename, cl)

    if bufsize == "line":
        bufsize = 8192
        xread = f.readline
    else:
        xread = f.read

    read = 0
    while True:
        data = xread(bufsize)
        if not data:
            break
        read += len(data)
        if progress_obj:
            progress_obj.update(read)
        yield data

    if progress_obj:
        progress_obj.end()
    f.close()

    if cl is not None and read != cl:
        raise oscerr.OscIOError(None, 'Content-Length is not matching file size for %s: %i vs %i file size' % (url, cl, read))


def buildlog_strip_time(data):
    """Strips the leading build time from the log"""
    if isinstance(data, str):
        time_regex = re.compile(r'^\[[^\]]*\] ', re.M)
        return time_regex.sub('', data)
    else:
        time_regex = re.compile(br'^\[[^\]]*\] ', re.M)
        return time_regex.sub(b'', data)


def print_buildlog(
    apiurl: str,
    prj: str,
    package: str,
    repository: str,
    arch: str,
    offset=0,
    strip_time=False,
    last=False,
    lastsucceeded=False,
):
    """prints out the buildlog on stdout"""

    def print_data(data, strip_time=False):
        if strip_time:
            data = buildlog_strip_time(data)
        sys.stdout.buffer.write(data)

    query = {'nostream': '1', 'start': '%s' % offset}
    if last:
        query['last'] = 1
    if lastsucceeded:
        query['lastsucceeded'] = 1
    retry_count = 0
    while True:
        query['start'] = offset
        start_offset = offset
        u = makeurl(apiurl, ['build', prj, repository, arch, package, '_log'], query=query)
        try:
            for data in streamfile(u):
                offset += len(data)
                print_data(data, strip_time)
        except IncompleteRead as e:
            if retry_count >= 3:
                raise e
            retry_count += 1
            data = e.partial
            if len(data):
                offset += len(data)
                print_data(data, strip_time)
            continue
        if start_offset == offset:
            break


def get_dependson(apiurl: str, project: str, repository: str, arch: str, packages=None, reverse=None):
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


def get_buildinfo(
    apiurl: str, prj: str, package: str, repository: str, arch: str, specfile=None, addlist=None, debug=None
):
    query = []
    if addlist:
        for i in addlist:
            query.append('add=%s' % quote_plus(i))
    if debug:
        query.append('debug=1')

    u = makeurl(apiurl, ['build', prj, repository, arch, package, '_buildinfo'], query=query)

    if specfile:
        f = http_POST(u, data=specfile)
    else:
        f = http_GET(u)
    return f.read()


def get_buildconfig(apiurl: str, prj: str, repository: str, path=None):
    query = []
    if path:
        for prp in path:
            query.append('path=%s' % quote_plus(prp))
    u = makeurl(apiurl, ['build', prj, repository, '_buildconfig'], query=query)
    f = http_GET(u)
    return f.read()


def create_pbuild_config(apiurl: str, project: str, repository: str, arch: str, project_dir):
    """
    This is always replacing a possible exiting config for now
    we could extend the _pbuild file easily, but what should we do with multiple instances of the _config?
    """
    # get expanded buildconfig for given project and repository
    bc = get_buildconfig(apiurl, project, repository)
    if not bc:
        msg = "Failed to get build config for project '{project}', repository '{repository}'"
        raise oscerr.NotFoundAPIError(msg)

    with open(os.path.join(project_dir, '_config'), "w") as f:
        f.write(decode_it(bc))

    # create the _pbuild file based on expanded repository path informations
    pb = ET.fromstring('<pbuild></pbuild>')
    tree = ET.ElementTree(pb)
    preset = ET.SubElement(pb, 'preset', name=repository, default="")  # default should be empty, but ET crashes
    bi_text = decode_it(get_buildinfo(apiurl, project, '_repository', repository, arch, specfile="Name: dummy"))
    root = ET.fromstring(bi_text)

# cross compile setups are not yet supported
#    for path in root.findall('hostsystem'):
#        ET.SubElement(preset, 'hostrepo').text = path.get('url')

    for path in root.findall('path'):
        ET.SubElement(preset, 'repo').text = path.get('url')

    ET.SubElement(preset, 'arch').text = arch
    xmlindent(tree)
    tree.write(os.path.join(project_dir,'_pbuild'), encoding="utf-8", xml_declaration=True)


def get_worker_info(apiurl: str, worker: str):
    u = makeurl(apiurl, ['worker', worker])
    f = http_GET(u)

    return decode_it(f.read())


def check_constraints(apiurl: str, prj: str, repository: str, arch: str, package: str, constraintsfile=None):
    query = {"cmd": "checkconstraints", "project": prj, "package": package, "repository": repository, "arch": arch}
    u = makeurl(apiurl, ["worker"], query)
    f = http_POST(u, data=constraintsfile)
    root = ET.fromstring(b''.join(f))
    return [node.get('name') for node in root.findall('entry')]


def get_source_rev(apiurl: str, project: str, package: str, revision=None):
    # API supports ?deleted=1&meta=1&rev=4
    # but not rev=current,rev=latest,rev=top, or anything like this.
    # CAUTION: We have to loop through all rev and find the highest one, if none given.

    if revision:
        url = makeurl(apiurl, ['source', project, package, '_history'], {'rev': revision})
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
        return {'version': None, 'error': 'empty revisionlist: no such package?'}
    e = {}
    for k in ent.keys():
        e[k] = ent.get(k)
    for k in list(ent):
        e[k.tag] = k.text
    return e


def print_jobhistory(apiurl: str, prj: str, current_package: str, repository: str, arch: str, format="text", limit=20):
    query = {}
    if current_package:
        query['package'] = current_package
    if limit is not None and int(limit) > 0:
        query['limit'] = int(limit)
    u = makeurl(apiurl, ['build', prj, repository, arch, '_jobhistory'], query)
    f = http_GET(u)
    root = ET.parse(f).getroot()

    if format == 'text':
        print("time                 package                                            reason           code              build time      worker")
    for node in root.findall('jobhist'):
        package = node.get('package')
        worker = node.get('workerid')
        reason = node.get('reason')
        if not reason:
            reason = "unknown"
        code = node.get('code')
        st = int(node.get('starttime'))
        et = int(node.get('endtime'))
        endtime = time.strftime('%Y-%m-%d %H:%M:%S', time.gmtime(et))
        waittm = et - st
        if waittm > 24 * 60 * 60:
            waitbuild = "%1dd %2dh %2dm %2ds" % (waittm / (24 * 60 * 60), (waittm / (60 * 60)) % 24, (waittm / 60) % 60, waittm % 60)
        elif waittm > 60 * 60:
            waitbuild = "   %2dh %2dm %2ds" % (waittm / (60 * 60), (waittm / 60) % 60, waittm % 60)
        else:
            waitbuild = "       %2dm %2ds" % (waittm / 60, waittm % 60)

        if format == 'csv':
            print('%s|%s|%s|%s|%s|%s' % (endtime, package, reason, code, waitbuild, worker))
        else:
            print('%s  %-50s %-16s %-16s %-16s %-16s' % (endtime, package[0:49], reason[0:15], code[0:15], waitbuild, worker))


def get_commitlog(
    apiurl: str, prj: str, package: str, revision, format="text", meta=False, deleted=False, revision_upper=None
):
    if package is None:
        package = "_project"

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
            # vrev = int(node.get('vrev')) # what is the meaning of vrev?
            try:
                if revision is not None and revision_upper is not None:
                    if rev > int(revision_upper) or rev < int(revision):
                        continue
                elif revision is not None and rev != int(revision):
                    continue
            except ValueError:
                if revision != srcmd5:
                    continue
        except ValueError:
            # this part should _never_ be reached but...
            return ['an unexpected error occured - please file a bug']
        version = node.find('version').text
        user = node.find('user').text
        try:
            comment = node.find('comment').text.encode(locale.getpreferredencoding(), 'replace')
        except:
            comment = b'<no message>'
        try:
            requestid = node.find('requestid').text.encode(locale.getpreferredencoding(), 'replace')
        except:
            requestid = ""
        t = time.gmtime(int(node.find('time').text))
        t = time.strftime('%Y-%m-%d %H:%M:%S', t)

        if format == 'csv':
            s = '%s|%s|%s|%s|%s|%s|%s' % (rev, user, t, srcmd5, version,
                                          decode_it(comment).replace('\\', '\\\\').replace('\n', '\\n').replace('|', '\\|'), requestid)
            r.append(s)
        elif format == 'xml':
            r.append('<logentry')
            r.append('   revision="%s" srcmd5="%s">' % (rev, srcmd5))
            r.append('<author>%s</author>' % user)
            r.append('<date>%s</date>' % t)
            r.append('<requestid>%s</requestid>' % requestid)
            r.append('<msg>%s</msg>' % _private.api.xml_escape(decode_it(comment)))
            r.append('</logentry>')
        else:
            if requestid:
                requestid = decode_it(b"rq" + requestid)
            s = '-' * 76 + \
                '\nr%s | %s | %s | %s | %s | %s\n' % (rev, user, t, srcmd5, version, requestid) + \
                '\n' + decode_it(comment)
            r.append(s)

    if format not in ['csv', 'xml']:
        r.append('-' * 76)
    if format == 'xml':
        r.append('</log>')
    return r


def runservice(apiurl: str, prj: str, package: str):
    u = makeurl(apiurl, ['source', prj, package], query={'cmd': 'runservice'})

    try:
        f = http_POST(u)
    except HTTPError as e:
        e.osc_msg = 'could not trigger service run for project \'%s\' package \'%s\'' % (prj, package)
        raise

    root = ET.parse(f).getroot()
    return root.get('code')


def waitservice(apiurl: str, prj: str, package: str):
    u = makeurl(apiurl, ['source', prj, package], query={'cmd': 'waitservice'})

    try:
        f = http_POST(u)
    except HTTPError as e:
        e.osc_msg = 'The service for project \'%s\' package \'%s\' failed' % (prj, package)
        raise

    root = ET.parse(f).getroot()
    return root.get('code')


def mergeservice(apiurl: str, prj: str, package: str):
    # first waiting that the service finishes and that it did not fail
    waitservice(apiurl, prj, package)

    # real merge
    u = makeurl(apiurl, ['source', prj, package], query={'cmd': 'mergeservice'})

    try:
        f = http_POST(u)
    except HTTPError as e:
        e.osc_msg = 'could not merge service files in project \'%s\' package \'%s\'' % (prj, package)
        raise

    root = ET.parse(f).getroot()
    return root.get('code')


def rebuild(apiurl: str, prj: str, package: str, repo: str, arch: str, code=None):
    query = {'cmd': 'rebuild'}
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
    except HTTPError as e:
        e.osc_msg = 'could not trigger rebuild for project \'%s\' package \'%s\'' % (prj, package)
        raise

    root = ET.parse(f).getroot()
    return root.get('code')


def store_read_project(dir):
    global store

    try:
        with open(os.path.join(dir, store, '_project')) as f:
            p = f.readline().strip()
    except OSError:
        msg = 'Error: \'%s\' is not an osc project dir or working copy' % os.path.abspath(dir)
        if os.path.exists(os.path.join(dir, '.svn')):
            msg += '\nTry svn instead of osc.'
        raise oscerr.NoWorkingCopy(msg)
    return p


def store_read_package(dir):
    global store

    try:
        with open(os.path.join(dir, store, '_package')) as f:
            p = f.readline().strip()
    except OSError:
        msg = 'Error: \'%s\' is not an osc package working copy' % os.path.abspath(dir)
        if os.path.exists(os.path.join(dir, '.svn')):
            msg += '\nTry svn instead of osc.'
        raise oscerr.NoWorkingCopy(msg)
    return p


def store_read_scmurl(dir):
    import warnings
    warnings.warn(
        "osc.core.store_read_scmurl() is deprecated. "
        "You should be using high-level classes such as Store, Project or Package instead.",
        DeprecationWarning
    )
    return Store(dir).scmurl


def store_read_apiurl(dir, defaulturl=True):
    import warnings
    warnings.warn(
        "osc.core.store_read_apiurl() is deprecated. "
        "You should be using high-level classes such as Store, Project or Package instead.",
        DeprecationWarning
    )
    return Store(dir).apiurl


def store_read_last_buildroot(dir):
    global store

    fname = os.path.join(dir, store, '_last_buildroot')
    if os.path.exists(fname):
        lines = open(fname).read().splitlines()
        if len(lines) == 3:
            return lines

    return


def store_write_string(dir, file, string, subdir=''):
    global store

    if subdir and not os.path.isdir(os.path.join(dir, store, subdir)):
        os.mkdir(os.path.join(dir, store, subdir))
    fname = os.path.join(dir, store, subdir, file)
    try:
        f = open(fname + '.new', 'w')
        if not isinstance(string, str):
            string = decode_it(string)
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
    import warnings
    warnings.warn(
        "osc.core.store_write_apiurl() is deprecated. "
        "You should be using high-level classes such as Store, Project or Package instead.",
        DeprecationWarning
    )
    Store(dir).apiurl = apiurl


def store_write_last_buildroot(dir, repo, arch, vm_type):
    store_write_string(dir, '_last_buildroot', repo + '\n' + arch + '\n' + vm_type + '\n')


def store_unlink_file(dir, file):
    global store

    try:
        os.unlink(os.path.join(dir, store, file))
    except:
        pass


def store_read_file(dir, file):
    global store

    try:
        with open(os.path.join(dir, store, file)) as f:
            return f.read()
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


def abortbuild(apiurl: str, project: str, package=None, arch=None, repo=None):
    return cmdbuild(apiurl, 'abortbuild', project, package, arch, repo)


def restartbuild(apiurl: str, project: str, package=None, arch=None, repo=None):
    return cmdbuild(apiurl, 'restartbuild', project, package, arch, repo)


def unpublish(apiurl: str, project: str, package: Optional[str] = None, arch=None, repo=None, code=None):
    return cmdbuild(apiurl, "unpublish", project, package, arch, repo, code)


def wipebinaries(apiurl: str, project: str, package: Optional[str] = None, arch=None, repo=None, code=None):
    return cmdbuild(apiurl, "wipe", project, package, arch, repo, code)


def cmdbuild(
    apiurl: str, cmd: str, project: str, package: Optional[str] = None, arch=None, repo=None, code=None, sysrq=None
):
    query = {"cmd": cmd}
    if package:
        query['package'] = package
    if arch:
        query['arch'] = arch
    if repo:
        query['repository'] = repo
    if code:
        query['code'] = code
    if sysrq:
        query['sysrq'] = sysrq

    u = makeurl(apiurl, ['build', project], query)
    try:
        f = http_POST(u)
    except HTTPError as e:
        e.osc_msg = '%s command failed for project %s' % (cmd, project)
        if package:
            e.osc_msg += ' package %s' % package
        if arch:
            e.osc_msg += ' arch %s' % arch
        if repo:
            e.osc_msg += ' repository %s' % repo
        if code:
            e.osc_msg += ' code=%s' % code
        if sysrq:
            e.osc_msg += ' sysrq=%s' % code
        raise

    root = ET.parse(f).getroot()
    return root.get('code')


def parseRevisionOption(string, allow_md5=True):
    """
    returns a tuple which contains the revisions
    """

    revisions = [None, None]
    if string:
        parts = string.split(':')

        if len(parts) > 2:
            raise oscerr.OscInvalidRevision(string)

        for i, revision in enumerate(parts, 0):
            if revision.isdigit() or (allow_md5 and revision.isalnum() and len(revision) == 32):
                revisions[i] = revision
            elif revision != '' and revision != 'latest':
                raise oscerr.OscInvalidRevision(string)

    return tuple(revisions)


def checkRevision(prj: str, pac: str, revision, apiurl: Optional[str] = None, meta=False):
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
        if int(revision) > int(show_upstream_rev(apiurl, prj, pac, meta=meta)) \
           or int(revision) <= 0:
            return False
        else:
            return True
    except (ValueError, TypeError):
        return False


def build_table(col_num, data=None, headline=None, width=1, csv=False):
    """
    This method builds a simple table.

    Example::

        build_table(2, ['foo', 'bar', 'suse', 'osc'], ['col1', 'col2'], 2)

        col1  col2
        foo   bar
        suse  osc
    """
    data = data or []
    headline = headline or []

    longest_col = []
    for i in range(col_num):
        longest_col.append(0)
    if headline and not csv:
        data[0:0] = headline

    data = [str(i) for i in data]

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
        if i == col_num - 1 or csv:
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


def search(apiurl: str, queries=None, **kwargs):
    """
    Perform a search request. The requests are constructed as follows:
    kwargs = {'kind1' => xpath1, 'kind2' => xpath2, ..., 'kindN' => xpathN}
    GET /search/kind1?match=xpath1
    ...
    GET /search/kindN?match=xpathN

    queries is a dict of optional http query parameters, which are passed
    to the makeurl call, of the form
    {kindI1: dict_or_list, ..., kindIL: dict_or_list},
    where kind_i1 to kind_iL are keys of kwargs.
    """
    if queries is None:
        queries = {}
    res = {}
    for urlpath, xpath in kwargs.items():
        path = ['search']
        path += urlpath.split('_')  # FIXME: take underscores as path seperators. I see no other way atm to fix OBS api calls and not breaking osc api
        query = queries.get(urlpath, {})
        query['match'] = xpath
        u = makeurl(apiurl, path, query)
        f = http_GET(u)
        res[urlpath] = ET.parse(f).getroot()
    return res


def owner(
    apiurl: str,
    search_term=None,
    mode="binary",
    attribute=None,
    project=None,
    usefilter=None,
    devel=None,
    limit=None,
    binary=None,
):
    """
    Perform a binary package owner search. This is supported since OBS 2.4.
    """

    # binary is just for API backward compatibility
    if not (search_term is None) ^ (binary is None):
        raise ValueError('Either specify search_term or binary')
    elif binary is not None:
        search_term = binary

    # find default project, if not specified
    # mode can be "binary" or "package" atm
    query = {mode: search_term}
    if attribute:
        query['attribute'] = attribute
    if project:
        query['project'] = project
    if devel:
        query['devel'] = devel
    if limit is not None:
        query['limit'] = limit
    if usefilter is not None:
        query['filter'] = ",".join(usefilter)
    u = makeurl(apiurl, ['search', 'owner'], query)
    res = None
    try:
        f = http_GET(u)
        res = ET.parse(f).getroot()
    except HTTPError as e:
        # old server not supporting this search
        pass
    return res


def set_link_rev(apiurl: str, project: str, package: str, revision="", expand=False, msg: str=None):
    url = makeurl(apiurl, ["source", project, package, "_link"])
    try:
        f = http_GET(url)
        root = ET.parse(f).getroot()
    except HTTPError as e:
        e.osc_msg = 'Unable to get _link file in package \'%s\' for project \'%s\'' % (package, project)
        raise
    revision = _set_link_rev(apiurl, project, package, root, revision, expand=expand)
    l = ET.tostring(root, encoding=ET_ENCODING)

    if not msg:
        if revision:
            msg = f"Set link revision to {revision}"
        else:
            msg = "Unset link revision"
    url = makeurl(apiurl, ["source", project, package, "_link"], {"comment": msg})
    http_PUT(url, data=l)
    return revision


def _set_link_rev(apiurl: str, project: str, package: str, root, revision="", expand=False):
    """
    Updates the rev attribute of the _link xml. If revision is set to None
    the rev and vrev attributes are removed from the _link xml.
    updates the rev attribute of the _link xml. If revision is the empty
    string the latest rev of the link's source package is used (or the
    xsrcmd5 if expand is True). If revision is neither None nor the empty
    string the _link's rev attribute is set to this revision (or to the
    xsrcmd5 if expand is True).
    """
    src_project = root.get('project', project)
    src_package = root.get('package', package)
    vrev = None
    if revision is None:
        if 'rev' in root.keys():
            del root.attrib['rev']
        if 'vrev' in root.keys():
            del root.attrib['vrev']
    elif not revision or expand:
        revision, vrev = show_upstream_rev_vrev(apiurl, src_project, src_package, revision=revision, expand=expand)

    if revision:
        root.set('rev', revision)
    # add vrev when revision is a srcmd5
    if vrev is not None and revision is not None and len(revision) >= 32:
        root.set('vrev', vrev)
    return revision


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
        print('error - \'%s\' is not a source rpm.' % srpm, file=sys.stderr)
        sys.exit(1)
    curdir = os.getcwd()
    if os.path.isdir(dir):
        os.chdir(dir)
    ret = -1
    with open(srpm) as fsrpm:
        with open(os.devnull, 'w') as devnull:
            rpm2cpio_proc = subprocess.Popen(['rpm2cpio'], stdin=fsrpm,
                                             stdout=subprocess.PIPE)
            # XXX: shell injection is possible via the files parameter, but the
            #      current osc code does not use the files parameter.
            cpio_proc = subprocess.Popen(['cpio', '-i'] + list(files),
                                         stdin=rpm2cpio_proc.stdout,
                                         stderr=devnull)
            rpm2cpio_proc.stdout.close()
            cpio_proc.communicate()
            rpm2cpio_proc.wait()
            ret = rpm2cpio_proc.returncode
            if not ret:
                ret = cpio_proc.returncode
    if ret != 0:
        print('error \'%s\' - cannot extract \'%s\'' % (ret, srpm), file=sys.stderr)
        sys.exit(1)
    os.chdir(curdir)


def is_rpm(f):
    """check if the named file is an RPM package"""
    try:
        h = open(f, 'rb').read(4)
    except:
        return False

    if isinstance(h, str):
        isrpmstr = '\xed\xab\xee\xdb'
    else:
        isrpmstr = b'\xed\xab\xee\xdb'
    if h == isrpmstr:
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

    issrcrpm = bytes(bytearray([h[7]])).decode('utf-8')
    if issrcrpm == '\x01':
        return True
    else:
        return False


def addMaintainer(apiurl: str, prj: str, pac: str, user: str):
    # for backward compatibility only
    addPerson(apiurl, prj, pac, user)


def addPerson(apiurl: str, prj: str, pac: str, user: str, role="maintainer"):
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

    if data and get_user_meta(apiurl, user) is not None:
        root = ET.fromstring(parse_meta_to_string(data))
        found = False
        for person in root.iter('person'):
            if person.get('userid') == user and person.get('role') == role:
                found = True
                print("user already exists")
                break
        if not found:
            # the xml has a fixed structure
            root.insert(2, ET.Element('person', role=role, userid=user))
            print('user \'%s\' added to \'%s\'' % (user, pac or prj))
            edit_meta(metatype=kind,
                      path_args=path,
                      data=ET.tostring(root, encoding=ET_ENCODING))
    else:
        print("osc: an error occured")


def delMaintainer(apiurl: str, prj: str, pac: str, user: str):
    # for backward compatibility only
    delPerson(apiurl, prj, pac, user)


def delPerson(apiurl: str, prj: str, pac: str, user: str, role="maintainer"):
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
    if data and get_user_meta(apiurl, user) is not None:
        root = ET.fromstring(parse_meta_to_string(data))
        found = False
        for person in root.iter('person'):
            if person.get('userid') == user and person.get('role') == role:
                root.remove(person)
                found = True
                print("user \'%s\' removed" % user)
        if found:
            edit_meta(metatype=kind,
                      path_args=path,
                      data=ET.tostring(root, encoding=ET_ENCODING))
        else:
            print("user \'%s\' not found in \'%s\'" % (user, pac or prj))
    else:
        print("an error occured")


def setBugowner(apiurl: str, prj: str, pac: str, user=None, group=None):
    """ delete all bugowners (user and group entries) and set one new one in a package or project """
    path = quote_plus(prj),
    kind = 'prj'
    if pac:
        path = path + (quote_plus(pac), )
        kind = 'pkg'
    data = meta_exists(metatype=kind,
                       path_args=path,
                       template_args=None,
                       create_new=False)
    if user.startswith('group:'):
        group = user.replace('group:', '')
        user = None
    if data:
        root = ET.fromstring(parse_meta_to_string(data))
        for group_element in root.iter('group'):
            if group_element.get('role') == "bugowner":
                root.remove(group_element)
        for person_element in root.iter('person'):
            if person_element.get('role') == "bugowner":
                root.remove(person_element)
        if user:
            root.insert(2, ET.Element('person', role='bugowner', userid=user))
        elif group:
            root.insert(2, ET.Element('group', role='bugowner', groupid=group))
        else:
            print("Neither user nor group is specified")
        edit_meta(metatype=kind,
                  path_args=path,
                  data=ET.tostring(root, encoding=ET_ENCODING))


def setDevelProject(apiurl, prj, pac, dprj, dpkg=None):
    """ set the <devel project="..."> element to package metadata"""
    path = (quote_plus(prj),) + (quote_plus(pac),)
    data = meta_exists(metatype='pkg',
                       path_args=path,
                       template_args=None,
                       create_new=False)

    if data and show_project_meta(apiurl, dprj) is not None:
        root = ET.fromstring(parse_meta_to_string(data))
        if not root.find('devel') is not None:
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
                  data=ET.tostring(root, encoding=ET_ENCODING))
    else:
        print("osc: an error occured")


def createPackageDir(pathname, prj_obj=None):
    """
    create and initialize a new package dir in the given project.
    prj_obj can be a Project() instance.
    """
    prj_dir, pac_dir = getPrjPacPaths(pathname)
    if is_project_dir(prj_dir):
        global store
        if not os.path.exists(os.path.join(pathname, store)):
            prj = prj_obj or Project(prj_dir, False)
            Package.init_package(prj.apiurl, prj.name, pac_dir, pathname)
            prj.addPackage(pac_dir)
            print(statfrmt('A', os.path.normpath(pathname)))
        else:
            raise oscerr.OscIOError(None, 'file or directory \'%s\' already exists' % pathname)
    else:
        msg = '\'%s\' is not a working copy' % prj_dir
        if os.path.exists(os.path.join(prj_dir, '.svn')):
            msg += '\ntry svn instead of osc.'
        raise oscerr.NoWorkingCopy(msg)


def stripETxml(node):
    node.tail = None
    if node.text is not None:
        node.text = node.text.replace(" ", "").replace("\n", "")
    for child in node:
        stripETxml(child)


def addGitSource(url):
    service_file = os.path.join(os.getcwd(), '_service')
    addfile = False
    if os.path.exists(service_file):
        services = ET.parse(os.path.join(os.getcwd(), '_service')).getroot()
    else:
        services = ET.fromstring("<services />")
        addfile = True
    stripETxml(services)
    si = Serviceinfo()
    s = si.addGitUrl(services, url)
    s = si.addTarUp(services)
    s = si.addRecompressTar(services)
    s = si.addSetVersion(services)
    si.read(s)

    # for pretty output
    xmlindent(s)
    f = open(service_file, 'w')
    f.write(ET.tostring(s, encoding=ET_ENCODING))
    f.close()
    if addfile:
        addFiles(['_service'])


def addDownloadUrlService(url):
    service_file = os.path.join(os.getcwd(), '_service')
    addfile = False
    if os.path.exists(service_file):
        services = ET.parse(os.path.join(os.getcwd(), '_service')).getroot()
    else:
        services = ET.fromstring("<services />")
        addfile = True
    stripETxml(services)
    si = Serviceinfo()
    s = si.addDownloadUrl(services, url)
    si.read(s)

    # for pretty output
    xmlindent(s)
    f = open(service_file, 'w')
    f.write(ET.tostring(s, encoding=ET_ENCODING))
    f.close()
    if addfile:
        addFiles(['_service'])

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
    f = open(service_file, 'w')
    f.write(ET.tostring(s, encoding=ET_ENCODING))
    f.close()


def addFiles(filenames, prj_obj=None, force=False):
    for filename in filenames:
        if not os.path.exists(filename):
            raise oscerr.OscIOError(None, 'file \'%s\' does not exist' % filename)

    # TODO: this function needs improvement
    #       it should check if we're in a project or a package working copy and behave accordingly

    # init a package dir if we have a normal dir in the "filenames"-list
    # so that it will be find by Package.from_paths_nofail() later
    pacs = list(filenames)
    for filename in filenames:
        prj_dir, pac_dir = getPrjPacPaths(filename)
        if not is_package_dir(filename) and os.path.isdir(filename) and is_project_dir(prj_dir) \
           and conf.config['do_package_tracking']:
            store = Store(prj_dir)
            prj_name = store_read_project(prj_dir)
            prj_apiurl = store.apiurl
            Package.init_package(prj_apiurl, prj_name, pac_dir, filename)
        elif is_package_dir(filename) and conf.config['do_package_tracking']:
            print('osc: warning: \'%s\' is already under version control' % filename)
            pacs.remove(filename)
        elif os.path.isdir(filename) and is_project_dir(prj_dir):
            raise oscerr.WrongArgs('osc: cannot add a directory to a project unless '
                                   '\'do_package_tracking\' is enabled in the configuration file')

    pacs, no_pacs = Package.from_paths_nofail(pacs)
    for filename in no_pacs:
        filename = os.path.normpath(filename)
        directory = os.path.join(filename, os.pardir)
        if not is_package_dir(directory):
            print('osc: warning: \'%s\' cannot be associated to a package' % filename)
            continue
        resp = raw_input("%s is a directory, do you want to archive it for submission? (y/n) " % (filename))
        if resp not in ('y', 'Y'):
            continue
        archive = "%s.obscpio" % filename
        todo = [os.path.join(p, elm)
                for p, dirnames, fnames in os.walk(filename, followlinks=False)
                for elm in dirnames + fnames]
        enc_todo = [b'%s' % elem.encode() for elem in todo]
        with open(archive, 'w') as f:
            cpio_proc = subprocess.Popen(['cpio', '-o', '-H', 'newc', '-0'],
                                         stdin=subprocess.PIPE, stdout=f)
            cpio_proc.communicate(b'\0'.join(enc_todo))
        pacs.extend(Package.from_paths([archive]))

    for pac in pacs:
        if conf.config['do_package_tracking'] and not pac.todo:
            prj = prj_obj or Project(os.path.dirname(pac.absdir), False)
            if pac.name in prj.pacs_unvers:
                prj.addPackage(pac.name)
                print(statfrmt('A', getTransActPath(os.path.join(pac.dir, os.pardir, pac.name))))
                for filename in pac.filenamelist_unvers:
                    if os.path.isdir(os.path.join(pac.dir, filename)):
                        print('skipping directory \'%s\'' % os.path.join(pac.dir, filename))
                    else:
                        pac.todo.append(filename)
            elif pac.name in prj.pacs_have:
                print('osc: warning: \'%s\' is already under version control' % pac.name)
        for filename in pac.todo:
            if filename in pac.skipped:
                continue
            if filename in pac.excluded and not force:
                print('osc: warning: \'%s\' is excluded from a working copy' % filename, file=sys.stderr)
                continue
            try:
                pac.addfile(filename)
            except oscerr.PackageFileConflict as e:
                fname = os.path.join(getTransActPath(pac.dir), filename)
                print('osc: warning: \'%s\' is already under version control' % fname)


def getPrjPacPaths(path):
    """
    returns the path for a project and a package
    from path. This is needed if you try to add
    or delete packages:

    Examples::

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
    path = str(Path(pac_dir))  # accept str and Path as pac_dir
    return '' if path == '.' else path


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
            with open(os.path.join(pac.absdir, filename), 'rb') as f:
                diff.extend(b'+' + line for line in f)

    if diff:
        template = parse_diff_for_commit_message(''.join(decode_list(diff)))

    return template


def parse_diff_for_commit_message(diff, template=None):
    template = template or []
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
        states = sorted(p.get_status(False, ' ', '?'), key=cmp_to_key(compare))
        changed = [statfrmt(st, os.path.normpath(os.path.join(p.dir, filename))) for st, filename in states]
        if changed:
            footer += changed
            footer.append('\nDiff for working copy: %s' % p.dir)
            footer.extend([''.join(decode_list(i)) for i in p.get_diff(ignoreUnversioned=True)])
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


def print_request_list(apiurl, project, package=None, states=("new", "review"), force=False):
    """
    prints list of pending requests for the specified project/package if "check_for_request_on_action"
    is enabled in the config or if "force" is set to True
    """
    if not conf.config['check_for_request_on_action'] and not force:
        return
    requests = get_request_collection(apiurl, project=project, package=package, states=states)
    msg = '\nPending requests for %s: %s (%s)'
    if sys.stdout.isatty():
        msg = f'\033[1m{msg}\033[0m'
    if package is None and requests:
        print(msg % ('project', project, len(requests)))
    elif requests:
        print(msg % ('package', '/'.join([project, package]), len(requests)))
    for r in requests:
        print(r.list_view(), '\n')


def request_interactive_review(apiurl, request, initial_cmd='', group=None,
                               ignore_reviews=False, source_buildstatus=False):
    """review the request interactively"""
    tmpfile = None

    def safe_change_request_state(*args, **kwargs):
        try:
            change_request_state(*args, **kwargs)
            return True
        except HTTPError as e:
            print('Server returned an error:', e, file=sys.stderr)
            details = e.hdrs.get('X-Opensuse-Errorcode')
            if details:
                print(details, file=sys.stderr)
            root = ET.fromstring(e.read())
            summary = root.find('summary')
            if summary is not None:
                print(summary.text, file=sys.stderr)
            print('Try -f to force the state change', file=sys.stderr)
        return False

    def safe_get_rpmlint_log(src_actions):
        lintlogs = []
        for action in src_actions:
            print('Type %s:' % action.type)
            disabled = show_package_disabled_repos(apiurl, action.src_project, action.src_package)
            for repo in get_repos_of_project(apiurl, action.src_project):
                if (disabled is None) or (repo.name not in [d['repo'] for d in disabled]):
                    lintlog_entry = {
                        'proj': action.src_project,
                        'pkg': action.src_package,
                        'repo': repo.name,
                        'arch': repo.arch
                    }
                    lintlogs.append(lintlog_entry)
                    print('(%i) %s/%s/%s/%s' % ((len(lintlogs) - 1), action.src_project, action.src_package, repo.name, repo.arch))
        if not lintlogs:
            print('No possible rpmlintlogs found')
            return False
        while True:
            try:
                lint_n = int(raw_input('Number of rpmlint log to examine (0 - %i): ' % (len(lintlogs) - 1)))
                lintlogs[lint_n]
                break
            except (ValueError, IndexError):
                print('Invalid rpmlintlog index. Please choose between 0 and %i' % (len(lintlogs) - 1))
        try:
            print(decode_it(get_rpmlint_log(apiurl, **lintlogs[lint_n])))
        except HTTPError as e:
            if e.code == 404:
                print('No rpmlintlog for %s %s' % (lintlogs[lint_n]['repo'],
                      lintlogs[lint_n]['arch']))
            else:
                raise e

    def print_request(request):
        print(request)

    def print_source_buildstatus(src_actions, newline=False):
        if newline:
            print()
        for action in src_actions:
            print('%s/%s:' % (action.src_project, action.src_package))
            try:
                print('\n'.join(get_results(apiurl, action.src_project, action.src_package)))
            except HTTPError as e:
                if e.code != 404:
                    raise
                print('unable to retrieve the buildstatus: %s' % e)

    def get_formatted_issues(apiurl, reqid):
        """get issue_list and return a printable string"""
        issue_list = get_request_issues(apiurl, reqid)
        issues = ""
        issues_nodetails = ""
        # the check_list is needed to make sure that every issue is just listed
        # once. Sometimes the API returns the same issue twice or more. See:
        # https://github.com/openSUSE/open-build-service/issues/4044
        # Once this is fixed this can be changed.
        check_list = []
        for issue in issue_list:
            if issue['label'] in check_list:
                continue
            if 'summary' in issue:
                issues += ("## BUG# " + issue['label'] + ": "
                           + issue.get('summary') + " : "
                           + issue.get('state', 'unknown state') + '\n')
            else:
                issues_nodetails += issue['label'] + ' '
            check_list.append(issue['label'])
        if issues_nodetails:
            issues += '## No details for the issue(s): ' + issues_nodetails + '\n'
        return issues

    print_request(request)
    print_comments(apiurl, 'request', request.reqid)
    try:
        prompt = '(a)ccept/(d)ecline/(r)evoke/c(l)one/co(m)ment/(s)kip/(c)ancel > '
        editable_actions = request.get_actions('submit', 'maintenance_incident')
        # actions which have sources + buildresults
        src_actions = editable_actions + request.get_actions('maintenance_release')
        if editable_actions:
            prompt = 'd(i)ff/(a)ccept/(d)ecline/(r)evoke/(b)uildstatus/rpm(li)ntlog/c(l)one/(e)dit/co(m)ment/(s)kip/(c)ancel > '
        elif src_actions:
            # no edit for maintenance release requests
            prompt = 'd(i)ff/(a)ccept/(d)ecline/(r)evoke/(b)uildstatus/rpm(li)ntlog/c(l)one/co(m)ment/(s)kip/(c)ancel > '
        editprj = ''
        orequest = None
        if source_buildstatus and src_actions:
            print_source_buildstatus(src_actions, newline=True)
        while True:
            if initial_cmd:
                repl = initial_cmd
                initial_cmd = ''
            else:
                repl = raw_input(prompt).strip()

            # remember if we're accepting so we can decide whether to forward request to the parent project later on
            accept = repl == "a"

            if repl == 'i' and src_actions:
                req_summary = str(request) + '\n'
                issues = '\n\n' + get_formatted_issues(apiurl, request.reqid)
                if orequest is not None and tmpfile:
                    tmpfile.close()
                    tmpfile = None
                if tmpfile is None:
                    tmpfile = tempfile.NamedTemporaryFile(suffix='.diff', mode='rb+')
                    tmpfile.write(req_summary.encode())
                    tmpfile.write(issues.encode())
                    try:
                        diff = request_diff(apiurl, request.reqid)
                        tmpfile.write(diff)
                    except HTTPError as e:
                        if e.code != 400:
                            raise
                        # backward compatible diff for old apis
                        for action in src_actions:
                            diff = b'old: %s/%s\nnew: %s/%s\n' % (action.src_project.encode(), action.src_package.encode(),
                                                                  action.tgt_project.encode(), action.tgt_package.encode())
                            diff += submit_action_diff(apiurl, action)
                            diff += b'\n\n'
                            tmpfile.write(diff)
                    tmpfile.flush()
                run_editor(tmpfile.name)
                print_request(request)
                print_comments(apiurl, 'request', request.reqid)
            elif repl == 's':
                print('skipping: #%s' % request.reqid, file=sys.stderr)
                break
            elif repl == 'c':
                print('Aborting', file=sys.stderr)
                raise oscerr.UserAbort()
            elif repl == 'm':
                if tmpfile is not None:
                    tmpfile.seek(0)
                    comment = edit_message(footer=decode_it(tmpfile.read()))
                else:
                    comment = edit_text()
                create_comment(apiurl, 'request', comment, request.reqid)
            elif repl == 'b' and src_actions:
                print_source_buildstatus(src_actions)
            elif repl == 'li' and src_actions:
                safe_get_rpmlint_log(src_actions)
            elif repl == 'e' and editable_actions:
                # this is only for editable actions
                if not editprj:
                    editprj = clone_request(apiurl, request.reqid, 'osc editrequest')
                    orequest = request
                request = edit_submitrequest(apiurl, editprj, orequest, request)
                src_actions = editable_actions = request.get_actions('submit', 'maintenance_incident')
                print_request(request)
                prompt = 'd(i)ff/(a)ccept/(b)uildstatus/(e)dit/(s)kip/(c)ancel > '
            else:
                state_map = {'a': 'accepted', 'd': 'declined', 'r': 'revoked'}
                mo = re.search(r'^([adrl])(?:\s+(-f)?\s*-m\s+(.*))?$', repl)
                if mo is None or orequest and mo.group(1) != 'a':
                    print('invalid choice: \'%s\'' % repl, file=sys.stderr)
                    continue
                state = state_map.get(mo.group(1))
                force = mo.group(2) is not None
                msg = mo.group(3)
                footer = ''
                msg_template = ''
                if not (state is None or request.state is None):
                    footer = 'changing request from state \'%s\' to \'%s\'\n\n' \
                        % (request.state.name, state)
                    msg_template = change_request_state_template(request, state)
                if tmpfile is None:
                    footer += str(request)
                if tmpfile is not None:
                    tmpfile.seek(0)
                    # the read bytes probably have a moderate size so the str won't be too large
                    footer += '\n\n' + decode_it(tmpfile.read())
                if msg is None:
                    try:
                        msg = edit_message(footer=footer, template=msg_template)
                    except oscerr.UserAbort:
                        # do not abort (show prompt again)
                        continue
                else:
                    msg = msg.strip('\'').strip('"')
                if orequest is not None:
                    request.create(apiurl)
                    if not safe_change_request_state(apiurl, request.reqid, 'accepted', msg, force=force):
                        # an error occured
                        continue
                    repl = raw_input('Supersede original request? (y|N) ')
                    if repl in ('y', 'Y'):
                        safe_change_request_state(apiurl, orequest.reqid, 'superseded',
                                                  'superseded by %s' % request.reqid, request.reqid, force=force)
                elif state is None:
                    clone_request(apiurl, request.reqid, msg)
                else:
                    reviews = [r for r in request.reviews if r.state == 'new']
                    if not reviews or ignore_reviews:
                        if safe_change_request_state(apiurl, request.reqid, state, msg, force=force):
                            if accept:
                                from . import _private
                                _private.forward_request(apiurl, request, interactive=True)
                            break
                        else:
                            # an error occured
                            continue
                    group_reviews = [r for r in reviews if (r.by_group is not None
                                                            and r.by_group == group)]
                    if len(group_reviews) == 1 and conf.config['review_inherit_group']:
                        review = group_reviews[0]
                    else:
                        print('Please chose one of the following reviews:')
                        for i in range(len(reviews)):
                            fmt = Request.format_review(reviews[i])
                            print('(%i)' % i, 'by %(type)-10s %(by)s' % fmt)
                        num = raw_input('> ')
                        try:
                            num = int(num)
                        except ValueError:
                            print('\'%s\' is not a number.' % num)
                            continue
                        if num < 0 or num >= len(reviews):
                            print('number \'%s\' out of range.' % num)
                            continue
                        review = reviews[num]
                    change_review_state(apiurl, request.reqid, state, by_user=review.by_user,
                                        by_group=review.by_group, by_project=review.by_project,
                                        by_package=review.by_package, message=msg)
                break
    finally:
        if tmpfile is not None:
            tmpfile.close()


def edit_submitrequest(apiurl, project, orequest, new_request=None):
    """edit a submit action from orequest/new_request"""
    actions = orequest.get_actions('submit')
    oactions = actions
    if new_request is not None:
        actions = new_request.get_actions('submit')
    num = 0
    if len(actions) > 1:
        print('Please chose one of the following submit actions:')
        for i in range(len(actions)):
            # it is safe to use orequest because currently the formatting
            # of a submit action does not need instance specific data
            fmt = orequest.format_action(actions[i])
            print('(%i)' % i, '%(source)s  %(target)s' % fmt)
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
        print('Checked out package \'%s\' to %s. Started a new shell (%s).\n'
              'Please fix the package and close the shell afterwards.' % (package, tmpdir, shell))
        run_external(shell)
        # the pkg might have uncommitted changes...
        cleanup = False
        os.chdir(olddir)
        # reread data
        p = Package(tmpdir)
        modified = p.get_status(False, ' ', '?', 'S')
        if modified:
            print('Your working copy has the following modifications:')
            print('\n'.join([statfrmt(st, filename) for st, filename in modified]))
            repl = raw_input('Do you want to commit the local changes first? (y|N) ')
            if repl in ('y', 'Y'):
                msg = get_commit_msg(p.absdir, [p])
                p.commit(msg=msg)
        cleanup = True
    finally:
        if cleanup:
            shutil.rmtree(tmpdir)
        else:
            print('Please remove the dir \'%s\' manually' % tmpdir)
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


def get_user_projpkgs(apiurl, user, role=None, exclude_projects=None, proj=True, pkg=True, maintained=False, metadata=False):
    """Return all project/packages where user is involved."""
    exclude_projects = exclude_projects or []
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
    except HTTPError as e:
        if e.code != 400 or not role_filter_xpath:
            raise e
        # backward compatibility: local role filtering
        what = {kind: role_filter_xpath for kind in what.keys()}
        if 'package' in what:
            what['package'] = xpath_join(role_filter_xpath, excl_pkg, op='and')
        if 'project' in what:
            what['project'] = xpath_join(role_filter_xpath, excl_prj, op='and')
        res = search(apiurl, **what)
        filter_role(res, user, role)
    return res


def run_external(filename, *args, **kwargs):
    """Executes the program filename via subprocess.call.

    *args are additional arguments which are passed to the
    program filename. **kwargs specify additional arguments for
    the subprocess.call function.
    if no args are specified the plain filename is passed
    to subprocess.call (this can be used to execute a shell
    command). Otherwise [filename] + list(args) is passed
    to the subprocess.call function.

    """
    # unless explicitly specified use shell=False
    kwargs.setdefault('shell', False)
    if args:
        cmd = [filename] + list(args)
    else:
        cmd = filename
    try:
        return subprocess.call(cmd, **kwargs)
    except OSError as e:
        if e.errno != errno.ENOENT:
            raise
        raise oscerr.ExtRuntimeError(e.strerror, filename)


def return_external(filename, *args, **kwargs):
    """Executes the program filename via subprocess.check_output.

    ``*args`` are additional arguments which are passed to the
    program filename. ``**kwargs`` specify additional arguments for
    the subprocess.check_output function.
    if no args are specified the plain filename is passed
    to subprocess.check_output (this can be used to execute a shell
    command). Otherwise [filename] + list(args) is passed
    to the subprocess.check_output function.

    Returns the output of the command.
    """
    if args:
        cmd = [filename] + list(args)
    else:
        cmd = filename

    try:
        # backward compatibility for python 2.6
        if 'check_output' not in dir(subprocess):
            process = subprocess.Popen(cmd, stdout=subprocess.PIPE)
            output, errstr = process.communicate()
            retcode = process.poll()
            if retcode:
                error = subprocess.CalledProcessError(retcode, cmd)
                error.output = output
                raise error
            return output
        return subprocess.check_output(cmd, **kwargs)
    except OSError as e:
        if e.errno != errno.ENOENT:
            raise
        raise oscerr.ExtRuntimeError(e.strerror, filename)

# backward compatibility: local role filtering


def filter_role(meta, user, role):
    """
    remove all project/package nodes if no person node exists
    where @userid=user and @role=role
    """
    for kind, root in meta.items():
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


def find_default_project(apiurl: Optional[str] = None, package: Optional[str] = None):
    """
    look though the list of conf.config['getpac_default_project']
    and find the first project where the given package exists in the build service.
    """
    if not conf.config['getpac_default_project']:
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
        except HTTPError:
            pass
    return None


def utime(filename, arg, ignore_einval=True):
    """wrapper around os.utime which ignore errno EINVAL by default"""
    try:
        # workaround for bnc#857610): if filename resides on a nfs share
        # os.utime might raise EINVAL
        os.utime(filename, arg)
    except OSError as e:
        if e.errno == errno.EINVAL and ignore_einval:
            return
        raise


def which(name: str):
    """Searches "name" in PATH."""
    name = os.path.expanduser(name)
    if os.path.isabs(name):
        if os.path.exists(name):
            return name
        return None
    for directory in os.environ.get('PATH', '').split(':'):
        path = os.path.join(directory, name)
        if os.path.exists(path):
            return path
    return None


def get_comments(apiurl: str, kind, *args):
    url = makeurl(apiurl, ('comments', kind) + args)
    f = http_GET(url)
    return ET.parse(f).getroot()


def print_comments(apiurl: str, kind, *args):
    def print_rec(comments, indent=''):
        for comment in comments:
            print(indent, end='')
            print('(', comment.get('id'), ')', 'On', comment.get('when'), comment.get('who'), 'wrote:')
            text = indent + comment.text.replace('\r\n', ' \n')
            print(('\n' + indent).join(text.split('\n')))
            print()
            print_rec([c for c in root if c.get('parent') == comment.get('id')], indent + '  ')
    root = get_comments(apiurl, kind, *args)
    comments = [c for c in root if c.get('parent') is None]
    if comments:
        print('\nComments:')
        print_rec(comments)


def create_comment(apiurl: str, kind, comment, *args, **kwargs) -> Optional[str]:
    query = {}
    if kwargs.get('parent') is not None:
        query = {'parent_id': kwargs['parent']}
    u = makeurl(apiurl, ('comments', kind) + args, query=query)
    f = http_POST(u, data=comment)
    ret = ET.fromstring(f.read()).find('summary')
    if ret is None:
        return None
    return ret.text


def delete_comment(apiurl: str, cid: str) -> Optional[str]:
    u = makeurl(apiurl, ['comment', cid])
    f = http_DELETE(u)
    ret = ET.fromstring(f.read()).find('summary')
    if ret is None:
        return None
    return ret.text


def get_rpmlint_log(apiurl: str, proj: str, pkg: str, repo: str, arch: str):
    u = makeurl(apiurl, ['build', proj, repo, arch, pkg, 'rpmlint.log'])
    f = http_GET(u)
    return f.read()


def checkout_deleted_package(apiurl: str, proj: str, pkg: str, dst):
    pl = meta_get_filelist(apiurl, proj, pkg, deleted=True)
    query = {}
    query['deleted'] = 1

    if os.path.isdir(dst):
        print('Restoring in existing directory %s' % dst)
    else:
        print('Creating %s' % dst)
        os.makedirs(dst)

    for filename in pl:
        print('Restoring %s to %s' % (filename, dst))
        full_file_path = os.path.join(dst, filename)
        u = makeurl(apiurl, ['source', proj, pkg, filename], query=query)
        with open(full_file_path, 'wb') as f:
            for data in streamfile(u):
                f.write(data)
    print('done.')


def vc_export_env(apiurl: str, quiet=False):
    # try to set the env variables for the user's realname and email
    # (the variables are used by the "vc" script or some source service)
    tag2envs = {'realname': ['VC_REALNAME'],
                'email': ['VC_MAILADDR', 'mailaddr']}
    tag2val = {}
    missing_tags = []

    for (tag, envs) in tag2envs.items():
        env_present = [env for env in envs if env in os.environ]
        config_present = tag in conf.config['api_host_options'][apiurl]
        if not env_present and not config_present:
            missing_tags.append(tag)
        elif config_present:
            tag2val[tag] = conf.config['api_host_options'][apiurl][tag]

    if missing_tags:
        user = conf.get_apiurl_usr(apiurl)
        data = get_user_data(apiurl, user, *missing_tags)
        if data:
            for tag in missing_tags:
                val = data.pop(0)
                if val != '-':
                    tag2val[tag] = val
                elif not quiet:
                    msg = 'Try env %s=...' % tag2envs[tag][0]
                    print(msg, file=sys.stderr)

    for (tag, val) in tag2val.items():
        for env in tag2envs[tag]:
            os.environ[env] = val


class MultibuildFlavorResolver:
    def __init__(self, apiurl: str, project: str, package: str, use_local=False):
        self.apiurl = apiurl
        self.project = project
        self.package = package
        # whether to use local _multibuild file or download it from server
        self.use_local = use_local

    def get_multibuild_data(self):
        """
        Retrieve contents of _multibuild file from given project/package.
        Return None if the file doesn't exist.
        """

        # use local _multibuild file
        if self.use_local:
            try:
                with open("_multibuild") as f:
                    return f.read()
            except OSError as e:
                if e.errno != errno.EEXIST:
                    raise
            return None

        # use _multibuild file from server
        query = {}
        query['expand'] = 1
        u = makeurl(self.apiurl, ['source', self.project, self.package, '_multibuild'], query=query)

        try:
            f = http_GET(u)
        except HTTPError as e:
            if e.code == 404:
                return None
            raise
        return f.read()

    @staticmethod
    def parse_multibuild_data(s: str):
        """
        Return set of flavors from a string with multibuild xml.
        """
        result = set()

        # handle empty string and None
        if not s:
            return result

        root = ET.fromstring(s)
        for node in root.findall("flavor"):
            result.add(node.text)
        return result

    def resolve(self, patterns: List[str]):
        """
        Return list of flavors based on given flavor `patterns`.
        If `patterns` contain a glob, it's resolved according to _multibuild file,
        values without globs are passed through.
        """

        # determine if we're using globs
        #   yes: contact server and do glob matching
        #   no: use the specified values directly
        use_globs = False
        for pattern in patterns:
            if '*' in pattern:
                use_globs = True
                break

        if use_globs:
            multibuild_xml = self.get_multibuild_data()
            all_flavors = self.parse_multibuild_data(multibuild_xml)
            flavors = set()
            for pattern in patterns:
                # not a glob, use it as it is
                if '*' not in pattern:
                    flavors.add(pattern)
                    continue

                # match the globs with flavors from server
                for flavor in all_flavors:
                    if fnmatch.fnmatch(flavor, pattern):
                        flavors.add(flavor)

        else:
            flavors = patterns

        return sorted(flavors)

    def resolve_as_packages(self, patterns: List[str]):
        """
        Return list of package:flavor based on given flavor `patterns`.
        If a value from `patterns` contains a glob, it is resolved according to the _multibuild
        file. Values without globs are passed through. If a value is empty string, package
        without flavor is returned.
        """

        flavors = self.resolve(patterns)

        packages = []
        for flavor in flavors:
            if flavor:
                packages.append(self.package + ':' + flavor)
            else:
                # special case: no flavor
                packages.append(self.package)
        return packages


# vim: sw=4 et
