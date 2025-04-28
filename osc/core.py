# and distributed under the terms of the GNU General Public Licence,
# either version 2, or version 3 (at your option).


import codecs
import copy
import csv
import datetime
import difflib
import errno
import fnmatch
import glob
import hashlib
import io
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
import warnings
from functools import cmp_to_key, total_ordering
from http.client import IncompleteRead
from io import StringIO
from pathlib import Path
from typing import Optional, Dict, Union, List, Iterable
from urllib.parse import parse_qs, urlsplit, urlunsplit, urlparse, quote, urlencode, unquote
from urllib.error import HTTPError
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
from . import output
from . import store as osc_store
from .connection import http_request, http_GET, http_POST, http_PUT, http_DELETE
from .obs_scm import File
from .obs_scm import Linkinfo
from .obs_scm import Package
from .obs_scm import Project
from .obs_scm import Serviceinfo
from .obs_scm import Store
from .obs_scm.store import __store_version__
from .obs_scm.store import check_store_version
from .obs_scm.store import delete_storedir
from .obs_scm.store import is_package_dir
from .obs_scm.store import is_project_dir
from .obs_scm.store import read_inconflict
from .obs_scm.store import read_filemeta
from .obs_scm.store import read_sizelimit
from .obs_scm.store import read_tobeadded
from .obs_scm.store import read_tobedeleted
from .obs_scm.store import store
from .obs_scm.store import store_read_apiurl
from .obs_scm.store import store_read_file
from .obs_scm.store import store_read_last_buildroot
from .obs_scm.store import store_readlist
from .obs_scm.store import store_read_package
from .obs_scm.store import store_read_project
from .obs_scm.store import store_read_scmurl
from .obs_scm.store import store_unlink_file
from .obs_scm.store import store_write_apiurl
from .obs_scm.store import store_write_initial_packages
from .obs_scm.store import store_write_last_buildroot
from .obs_scm.store import store_write_project
from .obs_scm.store import store_write_string
from .output import get_default_pager
from .output import run_pager
from .output import sanitize_text
from .util import xdg
from .util.helper import decode_list, decode_it, raw_input, _html_escape
from .util.xml import xml_fromstring
from .util.xml import xml_indent_compat as xmlindent
from .util.xml import xml_parse


ET_ENCODING = "unicode"


def compare(a, b): return cmp(a[1:], b[1:])


def cmp(a, b):
    return (a > b) - (a < b)


DISTURL_RE = re.compile(r"^(?P<bs>.*)://(?P<apiurl>.*?)/(?P<project>.*?)/(?P<repository>.*?)/(?P<revision>.*)-(?P<source>.*)$")
BUILDLOGURL_RE = re.compile(r"^(?P<apiurl>https?://.*?)/build/(?P<project>.*?)/(?P<repository>.*?)/(?P<arch>.*?)/(?P<package>.*?)/_log$")
BUFSIZE = 1024 * 1024

new_project_templ = """\
<project name="%(name)s">

  <title></title> <!-- Short title of NewProject -->
  <description></description>
    <!-- This is for a longer description of the purpose of the project -->

  <!-- Uncomment and specify an URL and branch if your project is managed in git.
  <scmsync>url#branch</scmsync>
  -->

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

  <!-- Uncomment and specify an URL and branch if your package is managed in git.
  <scmsync>url#branch</scmsync>
  -->

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

project_info_templ = """\
Project name: %s
Path: %s
API URL: %s
Source URL: %s
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


def revision_is_empty(rev: Union[None, str, int]):
    return rev in (None, "")


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
        self.comment = review_node.findtext("comment", default="").strip()

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
        if history_node.find('description') is not None:
            # OBS 2.6
            self.description = history_node.findtext("description").strip()
        else:
            # OBS 2.5 and before
            self.description = history_node.get("name")
        self.comment = ''
        if history_node.find("comment") is not None:
            self.comment = history_node.findtext("comment").strip()
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
        self.superseded_by = state_node.get("superseded_by", None)
        if state_node.find('description') is None:
            # OBS 2.6 has it always, before it did not exist
            self.description = state_node.get('description')
        self.comment = ''
        if state_node.find('comment') is not None:
            self.comment = state_node.findtext("comment").strip()

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
                 'release': ('src_project', 'src_package', 'src_rev', 'src_repository', 'tgt_project', 'tgt_package', 'person_name',
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
            raise oscerr.WrongArgs(f'invalid action type: \'{type}\'')
        self.type = type
        for i in kwargs.keys():
            if i not in Action.type_args[type]:
                raise oscerr.WrongArgs(f'invalid argument: \'{i}\'')
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
                data = [(f'opt_{opt.tag}', opt.text.strip()) for opt in node if opt.text]
            else:
                data = [(f'{prefix}_{k}', v) for k, v in node.items()]
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
            raise oscerr.APIError(f'invalid request: {ET.tostring(root, encoding=ET_ENCODING)}\n')
        self.reqid = root.get('id')
        if root.get('creator'):
            # OBS 2.8 and later is delivering creator informations
            self.creator = root.get('creator')
        if root.find('state') is None:
            raise oscerr.APIError(f'invalid request (state expected): {ET.tostring(root, encoding=ET_ENCODING)}\n')
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
        if root.findtext("priority"):
            self.priority = root.findtext("priority").strip()
        if root.findtext("accept_at"):
            self.accept_at = root.findtext("accept_at").strip()
        if root.findtext("title"):
            self.title = root.findtext("title").strip()
        if root.findtext("description"):
            self.description = root.findtext("description").strip()

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

        d = {'state': f'{review.state}:'}
        if review.by_package:
            d['by'] = f'{review.by_project}/{review.by_package}'
            d['type'] = 'Package'
        elif review.by_project:
            d['by'] = f'{review.by_project}'
            d['type'] = 'Project'
        elif review.by_group:
            d['by'] = f'{review.by_group}'
            d['type'] = 'Group'
        else:
            d['by'] = f'{review.by_user}'
            d['type'] = 'User'
        if review.who:
            d['by'] += f'({review.who})'
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
                return f'{prj}({repository})'
            return f'{prj}/{pkg}'

        d = {'type': f'{action.type}:'}
        if action.type == 'set_bugowner':
            if action.person_name:
                d['source'] = action.person_name
            if action.group_name:
                d['source'] = f'group:{action.group_name}'
            d['target'] = prj_pkg_join(action.tgt_project, action.tgt_package)
        elif action.type == 'change_devel':
            d['source'] = prj_pkg_join(action.tgt_project, action.tgt_package)
            d['target'] = f'developed in {prj_pkg_join(action.src_project, action.src_package)}'
        elif action.type == 'maintenance_incident':
            d['source'] = f'{action.src_project} ->'
            if action.src_package:
                d['source'] = f'{prj_pkg_join(action.src_project, action.src_package)}'
                if action.src_rev:
                    d['source'] = d['source'] + f'@{action.src_rev}'
                d['source'] = d['source'] + ' ->'
            d['target'] = action.tgt_project
            if action.tgt_releaseproject:
                d['target'] += " (release in " + action.tgt_releaseproject + ")"
            srcupdate = ' '
            if action.opt_sourceupdate and show_srcupdate:
                srcupdate = f'({action.opt_sourceupdate})'
        elif action.type in ('maintenance_release', 'release'):
            d['source'] = f'{prj_pkg_join(action.src_project, action.src_package)}'
            if action.src_rev:
                d['source'] = d['source'] + f'@{action.src_rev}'
            d['source'] = d['source'] + ' ->'
            d['target'] = prj_pkg_join(action.tgt_project, action.tgt_package)
        elif action.type == 'submit':
            d['source'] = f'{prj_pkg_join(action.src_project, action.src_package)}'
            if action.src_rev:
                d['source'] = d['source'] + f'@{action.src_rev}'
            if action.opt_sourceupdate and show_srcupdate:
                d['source'] = d['source'] + f'({action.opt_sourceupdate})'
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
                roles.append(f'person: {action.person_name} as {action.person_role}')
            if action.group_name and action.group_role:
                roles.append(f'group: {action.group_name} as {action.group_role}')
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
            raise oscerr.APIError(f'Unknown action type {action.type}\n')
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
        history = [f'{hist.description}: {hist.who}' for hist in self.statehistory]
        if history:
            lines.append(f"        From: {' -> '.join(history)}")
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
            state_name = self.state.name
            if self.state.superseded_by:
                state_name += f" by {self.state.superseded_by}"
            lines += ["", "State:", f"  {state_name:61} {self.state.when:12} {self.state.who}"]
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
        root = xml_fromstring(f.read())
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


def parse_disturl(disturl: str):
    """Parse a disturl, returns tuple (apiurl, project, source, repository,
    revision), else raises an oscerr.WrongArgs exception
    """

    global DISTURL_RE

    m = DISTURL_RE.match(disturl)
    if not m:
        raise oscerr.WrongArgs(f"`{disturl}' does not look like disturl")

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
        raise oscerr.WrongArgs(f'\'{buildlogurl}\' does not look like url with a build log')

    return (m.group('apiurl'), m.group('project'), m.group('package'), m.group('repository'), m.group('arch'))


def slash_split(args):
    """Split command line arguments like 'foo/bar' into 'foo' 'bar'.
    This is handy to allow copy/paste a project/package combination in this form.

    Leading and trailing slashes are removed before the split, because the split
    could otherwise give additional empty strings.
    """
    result = []
    for arg in args:
        arg = arg.strip("/")
        result += arg.split("/")
    return result


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


def parseargs(list_of_args):
    """Convenience method osc's commandline argument parsing.

    If called with an empty tuple (or list), return a list containing the current directory.
    Otherwise, return a list of the arguments."""
    if list_of_args:
        return list(list_of_args)
    else:
        return [os.curdir]


def statfrmt(statusletter, filename):
    return f'{statusletter}    {filename}'


def pathjoin(a, *p):
    """Join two or more pathname components, inserting '/' as needed. Cut leading ./"""
    path = os.path.join(a, *p)
    if path.startswith('./'):
        path = path[2:]
    return path


class UrlQueryArray(list):
    """
    Passing values wrapped in this object causes ``makeurl()`` to encode the list
    in Ruby on Rails compatible way (adding square brackets to the parameter names):
    {"file": UrlQueryArray(["foo", "bar"])} -> &file[]=foo&file[]=bar
    """
    pass


def makeurl(apiurl: str, path: List[str], query: Optional[dict] = None):
    """
    Construct an URL based on the given arguments.

    :param apiurl: URL to the API server.
    :param path: List of URL path components.
    :param query: Optional dictionary with URL query data.
                  Values can be: ``str``, ``int``, ``bool``, ``[str]``, ``[int]``.
                  Items with value equal to ``None`` will be skipped.
    """
    apiurl_scheme, apiurl_netloc, apiurl_path = urlsplit(apiurl)[0:3]

    path = apiurl_path.split("/") + [i.strip("/") for i in path]
    path = [quote(i, safe="/:") for i in path]
    path_str = "/".join(path)

    # DEPRECATED
    if isinstance(query, (list, tuple)):
        warnings.warn(
            "makeurl() query taking a list or a tuple is deprecated. Use dict instead.",
            DeprecationWarning
        )
        query_str = "&".join(query)
        return urlunsplit((apiurl_scheme, apiurl_netloc, path_str, query_str, ""))

    # DEPRECATED
    if isinstance(query, str):
        warnings.warn(
            "makeurl() query taking a string is deprecated. Use dict instead.",
            DeprecationWarning
        )
        query_str = query
        return urlunsplit((apiurl_scheme, apiurl_netloc, path_str, query_str, ""))

    if query is None:
        query = {}
    query = copy.deepcopy(query)

    for key in list(query):
        value = query[key]

        if value in (None, [], ()):
            # remove items with value equal to None or [] or ()
            del query[key]
        elif isinstance(value, bool):
            # convert boolean values to "0" or "1"
            query[key] = str(int(value))
        elif isinstance(value, UrlQueryArray):
            # encode lists in Ruby on Rails compatible way:
            # {"file": ["foo", "bar"]} -> &file[]=foo&file[]=bar
            del query[key]
            query[f"{key}[]"] = value

    query_str = urlencode(query, doseq=True)
    _private.print_msg("makeurl:", path_str+"?"+query_str, print_to="debug")

    return urlunsplit((apiurl_scheme, apiurl_netloc, path_str, query_str, ""))


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
    root = xml_parse(f).getroot()
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
    if not revision_is_empty(revision):
        query['rev'] = revision
    else:
        query['rev'] = 'latest'

    u = makeurl(apiurl, ['source', prj, package], query=query)
    f = http_GET(u)
    root = xml_parse(f).getroot()

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
    root = xml_parse(f).getroot()
    return sorted(node.get('name') for node in root if node.get('name'))


def show_project_meta(apiurl: str, prj: str, rev=None, blame=None):
    query = {}
    if blame:
        query['view'] = "blame"
    if not revision_is_empty(rev):
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
            e.osc_msg = f'BuildService API error: {error_help}'
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
    if not revision_is_empty(rev):
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
        e.osc_msg = f'Error getting trigger reason for project \'{prj}\' package \'{pac}\''
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
        e.osc_msg = f'Error getting meta for project \'{unquote(prj)}\' package \'{pac}\''
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
    query = {}
    query["with_default"] = with_defaults
    query["with_project"] = with_project
    url = makeurl(apiurl, path, query)
    try:
        f = http_GET(url)
        return f.readlines()
    except HTTPError as e:
        e.osc_msg = f'Error getting meta for project \'{prj}\' package \'{pac}\''
        raise


def clean_assets(directory):
    return run_external(conf.config['download-assets-cmd'], '--clean', directory)


def download_assets(directory):
    return run_external(conf.config['download-assets-cmd'], '--unpack', '--noassetdir', directory)


def show_scmsync(apiurl, prj, pac=None):
    from . import obs_api

    if pac:
        package_obj = obs_api.Package.from_api(apiurl, prj, pac)
        return package_obj.scmsync

    project_obj = obs_api.Project.from_api(apiurl, prj)
    return project_obj.scmsync


def show_devel_project(apiurl, prj, pac):
    from . import obs_api

    package_obj = obs_api.Package.from_api(apiurl, prj, pac)
    if package_obj.devel is None:
        return None, None

    # mute a false-positive: Instance of 'dict' has no 'project' member (no-member)
    # pylint: disable=no-member
    return package_obj.devel.project, package_obj.devel.package


def set_devel_project(apiurl, prj, pac, devprj=None, devpac=None, print_to="debug"):
    from . import obs_api

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
    output.print_msg(msg, print_to=print_to)

    package_obj = obs_api.Package.from_api(apiurl, prj, pac)

    if devprj is None:
        package_obj.devel = None
    else:
        package_obj.devel = {"project": devprj, "package": devpac}

    if package_obj.has_changed():
        return package_obj.to_api(apiurl)

    # TODO: debug log that we have skipped the API call
    return None


def show_package_disabled_repos(apiurl: str, prj: str, pac: str):
    from . import obs_api

    # FIXME: don't work if all repos of a project are disabled and only some are enabled since <disable/> is empty
    package_obj = obs_api.Package.from_api(apiurl, prj, pac)
    result = []
    for i in package_obj.build_list or []:
        if i.flag == "disable":  # pylint: disable=no-member
            result.append({"repo": i.repository, "arch": i.arch})  # pylint: disable=no-member
    return result


def show_pattern_metalist(apiurl: str, prj: str):
    url = makeurl(apiurl, ['source', prj, '_pattern'])
    try:
        f = http_GET(url)
        tree = xml_parse(f)
    except HTTPError as e:
        e.osc_msg = f'show_pattern_metalist: Error getting pattern list for project \'{prj}\''
        raise
    r = sorted(node.get('name') for node in tree.getroot())
    return r


def show_pattern_meta(apiurl: str, prj: str, pattern: str):
    url = makeurl(apiurl, ['source', prj, '_pattern', pattern])
    try:
        f = http_GET(url)
        return f.readlines()
    except HTTPError as e:
        e.osc_msg = f'show_pattern_meta: Error getting pattern \'{pattern}\' for project \'{prj}\''
        raise


def show_configuration(apiurl):
    u = makeurl(apiurl, ['configuration'])
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

    def __init__(self, url, input, change_is_required=False, file_ext='.xml', method=None):
        if isinstance(url, self._URLFactory):
            self._url_factory = url
        else:
            delegate = lambda **kwargs: url
            # force is not supported for a raw url
            self._url_factory = self._URLFactory(delegate, False)
        self.url = self._url_factory()
        self.change_is_required = change_is_required
        (fd, self.filename) = tempfile.mkstemp(prefix='osc_metafile.', suffix=file_ext)
        self._method = method

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
        if self._method == "POST":
            http_POST(self.url, file=self.filename)
        else:
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
                    root = xml_fromstring(e.read())
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
            print(f'discarding {self.filename}')
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
             'attribute': {'path': 'source/%s/_attribute/%s',
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
        raise AttributeError(f'make_meta_url(): Unknown meta type \'{metatype}\'')
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
    method: Optional[str] = None,
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
        orgprj = xml_fromstring(parse_meta_to_string(data)).get('project')

        if orgprj is not None and unquote(project) != orgprj:
            print('The package is linked from a different project.')
            print('If you want to edit the meta of the package create first a branch.')
            print(f'  osc branch {orgprj} {package} {unquote(project)}')
            print(f'  osc meta pkg {unquote(project)} {package} -e')
            return

    def delegate(force=force):
        return make_meta_url(metatype, path_args, apiurl, force, remove_linking_repositories, msg)

    url_factory = metafile._URLFactory(delegate)
    f = metafile(url_factory, data, change_is_required, metatypes[metatype]['file_ext'], method=method)

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
    if not revision_is_empty(revision):
        query['rev'] = revision
    else:
        query['rev'] = 'latest'
    if not revision_is_empty(linkrev):
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
    et = xml_fromstring(m)
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
    et = xml_fromstring(m)
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


def show_project_sourceinfo(apiurl: str, project: str, nofilename: bool, *packages) -> bytes:
    query = {}
    query["view"] = "info"
    query["nofilename"] = nofilename

    def to_chunks(lst, size):
        import itertools

        pos = 0
        while True:
            chunk = list(itertools.islice(lst, pos, pos + size))
            if not chunk:
                break
            yield chunk
            pos += size

    # sometimes the number of packages exceeds reasonable size of a GET query
    # that's why we make multiple requests and join the results
    max_packages = 100

    if packages:
        packages_chunks = to_chunks(packages, max_packages)
    else:
        packages_chunks = [None]

    sourceinfolist = ET.Element("sourceinfolist")
    for packages_chunk in packages_chunks:
        query["package"] = packages_chunk
        url = makeurl(apiurl, ['source', project], query=query)
        f = http_GET(url)
        root = xml_parse(f).getroot()
        assert root.tag == "sourceinfolist"
        assert root.attrib == {}
        sourceinfolist.extend(root[:])
    return ET.tostring(sourceinfolist)


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
            raise oscerr.APIError(f'package name too long: {packages[0]}')
        n = int(len(packages) / 2)
        pkgs = packages[:n]
        res = get_project_sourceinfo(apiurl, project, nofilename, *pkgs)
        pkgs = packages[n:]
        res.update(get_project_sourceinfo(apiurl, project, nofilename, *pkgs))
        return res
    root = xml_fromstring(si)
    res = {}
    for sinfo in root.findall('sourceinfo'):
        res[sinfo.get('package')] = sinfo
    return res


def show_upstream_rev_vrev(apiurl: str, prj, pac, revision=None, expand=False, meta=False):
    m = show_files_meta(apiurl, prj, pac, revision=revision, expand=expand, meta=meta)
    et = xml_fromstring(m)
    rev = et.get("rev") or None
    vrev = et.get("vrev") or None
    return rev, vrev


def show_upstream_rev(
    apiurl: str, prj, pac, revision=None, expand=False, linkrev=None, meta=False, include_service_files=False
):
    m = show_files_meta(apiurl, prj, pac, revision=revision, expand=expand, linkrev=linkrev, meta=meta)
    et = xml_fromstring(m)
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
        raise oscerr.OscIOError(None, f'\'{specfile}\' is not a regular file')

    rpmspec_path = shutil.which("rpmspec")
    if rpmspec_path:
        result = {}
        for arg in args:
            # convert tag to lower case and remove the leading '%'
            tag = arg.lower().lstrip("%")
            cmd = [rpmspec_path, "-q", specfile, "--srpm", "--qf", "%{" + tag + "}"]
            value = subprocess.check_output(cmd, encoding="utf-8")
            if value == "(none)":
                value = ""
            result[arg] = value
        return result

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
        if m is None:
            spec_data[section] = ""
            continue
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


def format_diff_line(line):
    # highlight trailing whitespaces
    match = re.search(rb"(\s+)$", line)
    if match and not re.match(rb"^[+\- ]*$", line):
        line = line[:match.start(1)] + b"\x1b[41m" + line[match.start(1):] + b"\x1b[0m"

    if line.startswith(b"+++ ") or line.startswith(b"--- ") or line.startswith(b"Index:"):
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
                editor.extend(['-c', f':r {f.name}', filename])
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

        cache_dir = os.path.expanduser(os.path.join(xdg.XDG_CACHE_HOME, "osc", "edited-messages"))
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
            file_changed = False
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
                ri = raw_input(f'{reason}\na)bort, c)ontinue, e)dit: ')
                if ri in 'aA':
                    raise oscerr.UserAbort()
                elif ri in 'cC':
                    break
                elif ri in 'eE':
                    ri_err = False
                else:
                    print(f"{ri} is not a valid option.")
                    ri_err = True
    finally:
        os.unlink(filename)
    return msg


def clone_request(apiurl: str, reqid, msg=None):
    query = {'cmd': 'branch', 'request': reqid}
    url = makeurl(apiurl, ['source'], query)
    r = http_POST(url, data=msg)
    root = xml_fromstring(r.read())
    project = None
    for i in root.findall('data'):
        if i.get('name') == 'targetproject':
            project = i.text.strip()
    if not project:
        raise oscerr.APIError(f'invalid data from clone request:\n{ET.tostring(root, encoding=ET_ENCODING)}\n')
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
    message: str = "",
    orev: Optional[str] = None,
    src_update: Optional[str] = None,
    dst_updatelink: Optional[bool] = None,
):
    from . import obs_api

    req = obs_api.Request(
        action_list=[
            {
                "type": "submit",
                "source": {
                    "project": src_project,
                    "package": src_package,
                    "rev": orev or show_upstream_rev(apiurl, src_project, src_package),
                },
                "target": {
                    "project": dst_project,
                    "package": dst_package,
                },
                "options": {
                    "sourceupdate": src_update,
                    "updatelink": "true" if dst_updatelink else None,
                }
            },
        ],
        description=message,
    )

    try:
        new_req = req.cmd_create(apiurl)
    except HTTPError as e:
        if e.hdrs.get('X-Opensuse-Errorcode') == "submit_request_rejected":
            print('WARNING: As the project is in maintenance, a maintenance incident request is')
            print('WARNING: being created (instead of a regular submit request). If this is not your')
            print('WARNING: intention please revoke it to avoid unnecessary work for all involved parties.')
            xpath = f"maintenance/maintains/@project = '{dst_project}' and attribute/@name = '{conf.config['maintenance_attribute']}'"
            res = search(apiurl, project_id=xpath)
            root = res['project_id']
            project = root.find('project')
            if project is None:
                print(f"WARNING: This project is not maintained in the maintenance project specified by '{conf.config['maintenance_attribute']}', looking elsewhere")
                xpath = f'maintenance/maintains/@project = \'{dst_project}\''
                res = search(apiurl, project_id=xpath)
                root = res['project_id']
                project = root.find('project')
            if project is None:
                raise oscerr.APIError("Server did not define a default maintenance project, can't submit.")
            tproject = project.get('name')
            r = create_maintenance_request(apiurl, src_project, [src_package], tproject, dst_project, src_update, message, rev=orev)
            return r.reqid
        else:
            raise

    return new_req.id


def get_request(apiurl: str, reqid):
    u = makeurl(apiurl, ['request', reqid], {'withfullhistory': '1'})
    f = http_GET(u)
    root = xml_parse(f).getroot()

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
    root = xml_parse(f).getroot()
    return root.get('code')


def change_request_state(apiurl: str, reqid, newstate, message="", supersed=None, force=False, keep_packages_locked=False):
    query = {"cmd": "changestate", "newstate": newstate}
    if supersed:
        query['superseded_by'] = supersed
    if force:
        query['force'] = "1"
    if keep_packages_locked:
        query['keep_packages_locked'] = "1"
    u = makeurl(apiurl,
                ['request', reqid], query=query)
    f = http_POST(u, data=message)

    root = xml_parse(f).getroot()
    return root.get('code', 'unknown')


def change_request_state_template(req, newstate):
    if not req.actions:
        return ''
    action = req.actions[0]
    tmpl_name = f'{action.type}request_{newstate}_template'
    tmpl = conf.config.get(tmpl_name, "") or ""
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
        print(f'error: cannot interpolate \'{e.args[0]}\' in \'{tmpl_name}\'', file=sys.stderr)
        return ''


def get_review_list(
    apiurl: str, project="", package="", byuser="", bygroup="", byproject="", bypackage="", states=(), req_type="", req_states=("review",)
):
    # this is so ugly...
    def build_by(xpath, val):
        if 'all' in states:
            return xpath_join(xpath, f'review/{val}', op='and')
        elif states:
            s_xp = ''
            for state in states:
                s_xp = xpath_join(s_xp, f'@state=\'{state}\'', inner=True)
            val = val.strip('[').strip(']')
            return xpath_join(xpath, f'review[{val} and ({s_xp})]', op='and')
        else:
            # default case
            return xpath_join(xpath, f'review[{val} and @state=\'new\']', op='and')
        return ''

    xpath = ''

    # By default we're interested only in reviews of requests that are in state review.
    for req_state in req_states:
        xpath = xpath_join(xpath, f"state/@name='{req_state}'", inner=True)

    xpath = f"({xpath})"

    if states == ():
        xpath = xpath_join(xpath, 'review/@state=\'new\'', op='and')
    if byuser:
        xpath = build_by(xpath, f'@by_user=\'{byuser}\'')
    if bygroup:
        xpath = build_by(xpath, f'@by_group=\'{bygroup}\'')
    if bypackage:
        xpath = build_by(xpath, f'@by_project=\'{byproject}\' and @by_package=\'{bypackage}\'')
    elif byproject:
        xpath = build_by(xpath, f'@by_project=\'{byproject}\'')

    if req_type:
        xpath = xpath_join(xpath, f'action/@type=\'{req_type}\'', op='and')

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

    output.print_msg(f"[ {xpath} ]", print_to="debug")
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
    types: Optional[List[str]] = None,
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
    res = xml_parse(f).getroot()

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
            xpath = xpath_join(xpath, f'state/@name=\'{state}\'', op='or', inner=True)
        xpath = f'({xpath})'
    if req_who:
        xpath = xpath_join(xpath, '(state/@who=\'%(who)s\' or history/@who=\'%(who)s\')' % {'who': req_who}, op='and')

    xpath += f" and action[source/@project='{src_project}'"
    if src_package:
        xpath += f" and source/@package='{src_package}'"
    xpath += f" and target/@project='{dst_project}'"
    if dst_package:
        xpath += f" and target/@package='{dst_package}'"
    xpath += "]"
    if req_type:
        xpath += f" and action/@type='{req_type}'"

    output.print_msg(f"[ {xpath} ]", print_to="debug")

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
            xpath = xpath_join(xpath, f'action/target/@project=\'{prj}\'', inner=True)
        else:
            xp = ''
            for p in pacs:
                xp = xpath_join(xp, f'action/target/@package=\'{p}\'', inner=True)
            xp = xpath_join(xp, f'action/target/@project=\'{prj}\'', op='and')
            xpath = xpath_join(xpath, xp, inner=True)
    if req_type:
        xpath = xpath_join(xpath, f'action/@type=\'{req_type}\'', op='and')
    if 'all' not in req_state:
        xp = ''
        for state in req_state:
            xp = xpath_join(xp, f'state/@name=\'{state}\'', inner=True)
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
        print(f"{open_request_string} {' '.join([i.reqid for i in reqs])}")
        repl = raw_input(f'{supersede_request_string} (y/n/c) ')
        while repl.lower() not in ['c', 'y', 'n']:
            print(f'{repl} is not a valid option.')
            repl = raw_input(f'{supersede_request_string} (y/n/c) ')
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
        print(f"{open_request_string} {', '.join([i.reqid for i in reqs])}.")
        repl = raw_input(f'{supersede_request_string} (y/n/c) ')
        while repl.lower() not in ['c', 'y', 'n']:
            print(f'{repl} is not a valid option.')
            repl = raw_input(f'{supersede_request_string} (y/n/c) ')
        if repl.lower() == 'c':
            print('Aborting', file=sys.stderr)
            raise oscerr.UserAbort()
    return repl == 'y', reqs

# old function for compat reasons. Some plugins may call this function.
# and we do not want to break the plugins.


def get_group(apiurl: str, group: str):
    return get_group_meta(apiurl, group)


def get_group_meta(apiurl: str, group: str):
    u = makeurl(apiurl, ['group', group])
    try:
        f = http_GET(u)
        return b''.join(f.readlines())
    except HTTPError:
        print(f'group \'{group}\' not found')
        return None


def get_user_meta(apiurl: str, user: str):
    u = makeurl(apiurl, ['person', user])
    try:
        f = http_GET(u)
        return b''.join(f.readlines())
    except HTTPError:
        print(f'user \'{user}\' not found')
        return None


def _get_xml_data(meta, *tags):
    data = []
    if meta is not None:
        root = xml_fromstring(meta)
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
            for buf in streamfile(url, http_GET, BUFSIZE, progress_obj=progress_obj, text=filename):
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
    if not revision_is_empty(revision):
        query['rev'] = revision
    u = makeurl(
        apiurl,
        ["source", prj, package, filename],
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


def binary(data: bytes):
    """
    Return ``True`` if ``data`` is binary data.

    We're using heuristics according to OBS: src/backend/BSSrcServer/filediff - look for "diff binary detection"
    """
    if b"\0" in data:
        return True
    binary_chars = re.findall(b"[\x00-\x07\x0e-\x1f]", data)
    return len(binary_chars) * 40 > len(data)


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
        olddir = os.path.join(dir, store, "sources")

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
    files: Optional[list] = None,
):
    query: Dict[str, Union[str, int]] = {"cmd": "diff"}
    if expand:
        query['expand'] = 1
    if old_project:
        query['oproject'] = old_project
    if old_package:
        query['opackage'] = old_package
    if not revision_is_empty(old_revision):
        query['orev'] = old_revision
    if not revision_is_empty(new_revision):
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
        query["file"] = UrlQueryArray(files)

    u = makeurl(apiurl, ['source', new_project, new_package], query=query)
    f = http_POST(u)
    if onlyissues and not xml:
        del_issue_list = []
        add_issue_list = []
        chn_issue_list = []
        root = xml_fromstring(f.read())
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
    files: Optional[list] = None,
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
                elm = xml_fromstring(body).find('summary')
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
    request_tree = xml_parse(f).getroot()
    issue_list = []
    for elem in request_tree.iterfind('action/sourcediff/issues/issue'):
        issue_id = elem.get('name')
        encode_search = f'@name=\'{issue_id}\''
        u = makeurl(apiurl, ['search/issue'], query={'match': encode_search})
        f = http_GET(u)
        collection = xml_parse(f).getroot()
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
                root = xml_fromstring(e.read())
                return b'error: \'%s\' does not exist' % root.findtext("summary").encode()
        elif e.code == 404:
            root = xml_fromstring(e.read())
            return b'error: \'%s\' does not exist' % root.findtext("summary").encode()
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


def run_obs_scm_bridge(url: str, target_dir: str):
    if not os.path.isfile(conf.config.obs_scm_bridge_cmd):
        raise oscerr.OscIOError(None, "Install the obs-scm-bridge package to work on packages managed in scm (git)!")
    env = os.environ.copy()
    env["OSC_VERSION"] = get_osc_version()
    run_external([conf.config.obs_scm_bridge_cmd, "--outdir", target_dir, "--url", url], env=env)


def checkout_package(
    apiurl: str,
    project: str,
    package: str,
    revision=None,
    pathname=None,
    prj_obj=None,
    expand_link=False,
    prj_dir: Optional[Path] = None,
    server_service_files=None,
    service_files=None,
    native_obs_package=False,
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
    oldproj = None
    if conf.config['checkout_rooted']:
        if prj_dir.stem == '/':
            output.print_msg(f"checkout_rooted ignored for {prj_dir}", print_to="verbose")
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
        output.print_msg(f"{prj_dir} is project dir of {oldproj}. Root found at {os.path.abspath(root_dots)}", print_to="verbose")
        prj_dir = root_dots / prj_dir

    if not pathname:
        pathname = getTransActPath(os.path.join(prj_dir, package))

    # before we create directories and stuff, check if the package actually
    # exists
    meta_data = b''.join(show_package_meta(apiurl, project, package))
    root = xml_fromstring(meta_data)
    scmsync_element = root.find("scmsync")
    if not native_obs_package and scmsync_element is not None and scmsync_element.text is not None:
        directory = make_dir(apiurl, project, package, pathname, prj_dir, conf.config['do_package_tracking'], outdir)

        scm_url = scmsync_element.text
        fetch_obsinfo = "noobsinfo" not in parse_qs(urlparse(scm_url).query)

        if revision is not None and fetch_obsinfo:
            # search for the git sha sum based on the OBS DISTURL package source revision
            # we need also take into account that the url was different at that point of time
            from .obs_api.scmsync_obsinfo import ScmsyncObsinfo
            scmsync_obsinfo = ScmsyncObsinfo.from_api(apiurl, project, package, rev=revision)
            scm_url = scmsync_obsinfo.scm_url

        run_obs_scm_bridge(url=scm_url, target_dir=directory)

        # this will fail if the git repo contains .osc directory added by mistake
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
    keep_lock: bool = False, keep_scmsync: bool = True,
):
    """
    update pkgmeta with new new_name and new_prj and set calling user as the
    only maintainer (unless keep_maintainers is set). Additionally remove the
    develproject entry (<devel />) unless keep_develproject is true.
    """
    root = xml_fromstring(b''.join(pkgmeta))
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
    if not keep_scmsync:
        for node in root.findall("scmsync"):
            root.remove(node)
    return ET.tostring(root, encoding=ET_ENCODING)


def link_to_branch(apiurl: str, project: str, package: str):
    """
     convert a package with a _link + project.diff to a branch
    """

    if '_link' in meta_get_filelist(apiurl, project, package):
        u = makeurl(apiurl, ["source", project, package], {"cmd": "linktobranch"})
        http_POST(u)
    else:
        raise oscerr.OscIOError(None, f'no _link file inside project \'{project}\' package \'{package}\'')


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
    from . import obs_api

    if src_project == dst_project and src_package == dst_package:
        raise oscerr.OscValueError("Cannot link package. Source and target are the same.")

    if not revision_is_empty(rev) and not checkRevision(src_project, src_package, rev):
        raise oscerr.OscValueError(f"Revision doesn't exist: {rev}")

    apiurl = conf.config["apiurl"]

    create_dst_package = False
    src_package_obj = obs_api.Package.from_api(apiurl, src_project, src_package)
    try:
        dst_package_obj = obs_api.Package.from_api(apiurl, dst_project, dst_package)
        if dst_package_obj.project != dst_project:
            # If the target package doesn't exist and the target project contains a project link,
            # the package meta from the linked project is returned instead!
            # We need to detect it and create the target package based on source package meta.
            create_dst_package = True
    except HTTPError as e:
        if e.code != 404:
            raise
        create_dst_package = True

    if create_dst_package:
        if missing_target:
            # we start with empty values because we want has_changed() to return True
            dst_package_obj = obs_api.Package(project="", name="")
        else:
            dst_package_obj = copy.deepcopy(src_package_obj)

            # purging unwanted fields; see also replace_pkg_meta()
            # TODO: create Package.clone() or .copy() method instead of this
            dst_package_obj.devel = None
            dst_package_obj.group_list = []
            dst_package_obj.lock = None
            dst_package_obj.person_list = []
            dst_package_obj.releasename = None
            dst_package_obj.scmsync = None

        dst_package_obj.project = dst_project
        dst_package_obj.name = dst_package

    if disable_build:
        dst_package_obj.build_list = [{"flag": "disable"}]

    if disable_publish:
        dst_package_obj.publish_list = [{"flag": "disable"}]

    dst_package_obj.scmsync = None

    if dst_package_obj.has_changed():
        dst_package_obj.to_api(apiurl)

    # create the _link file
    # but first, make sure not to overwrite an existing one
    if '_link' in meta_get_filelist(apiurl, dst_project, dst_package):
        if force:
            print('forced overwrite of existing _link file', file=sys.stderr)
        else:
            print(file=sys.stderr)
            print('_link file already exists...! Aborting', file=sys.stderr)
            sys.exit(1)

    if not revision_is_empty(rev):
        rev = f' rev="{rev}"'
    else:
        rev = ''

    if vrev:
        vrev = f' vrev="{vrev}"'
    else:
        vrev = ''

    missingok = ''
    if missing_target:
        missingok = ' missingok="true"'

    if cicount:
        cicount = f' cicount="{cicount}"'
    else:
        cicount = ''

    print('Creating _link...', end=' ')

    project = ''
    if src_project != dst_project:
        project = f'project="{src_project}"'

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
                               path_args=(dst_project, dst_package_meta),
                               template_args=None,
                               create_new=False, apiurl=apiurl)
        root = xml_fromstring(parse_meta_to_string(dst_meta))
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
        root = xml_fromstring(''.join(dst_meta))
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
    aggregate_template = f"""<aggregatelist>
  <aggregate project="{src_project}">
"""

    aggregate_template += f"""    <package>{src_package}</package>
"""

    if nosources:
        aggregate_template += """\
    <nosources />
"""
    for src, tgt in repo_map.items():
        aggregate_template += f"""    <repository target="{tgt}" source="{src}" />
"""

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
        root = xml_fromstring(e.read())
        summary = root.find('summary')
        if summary is not None and summary.text is not None:
            raise oscerr.APIError(summary.text)
        msg = f'unexpected response: {ET.tostring(root, encoding=ET_ENCODING)}'
        raise oscerr.APIError(msg)

    r = None

    root = xml_fromstring(f.read())
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

    # BEGIN: Error out on branching scmsync packages; this should be properly handled in the API

    # read src_package meta
    try:
        m = b"".join(show_package_meta(apiurl, src_project, src_package))
        root = xml_fromstring(m)
    except HTTPError as e:
        if e.code == 404 and missingok:
            root = None
        else:
            raise

    devel_project = None
    devel_package = None
    if root is not None and not nodevelproject:
        devel_node = root.find("devel")
        if devel_node is not None:
            devel_project = devel_node.get("project")
            devel_package = devel_node.get("package", src_package)
        if devel_project:
            # replace src_package meta with devel_package meta because we're about branch from devel
            m = b"".join(show_package_meta(apiurl, devel_project, devel_package))
            root = xml_fromstring(m)

    # error out if we're branching a scmsync package (we'd end up with garbage anyway)
    if root is not None and root.find("scmsync") is not None:
        msg = ("osc cannot branch packages with <scmsync>, i.e. externally "
              "managed sources. Often, the URL for cloning is also the URL "
              "for a collaborative web interface where you can fork (branch). "
              "The scmsync URL was: " + root.find("scmsync").text)
        if devel_project:
            raise oscerr.PackageError(devel_project, devel_package, msg)
        raise oscerr.PackageError(src_project, src_package, msg)

    # END: Error out on branching scmsync packages; this should be properly handled in the API

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
    if not revision_is_empty(rev):
        query['rev'] = rev
    if not revision_is_empty(linkrev):
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
        root = xml_fromstring(e.read())
        if missingok:
            if root and root.get('code') == "not_missing":
                raise oscerr.NotMissing("Package exists already via project link, but link will point to given project")
        summary = root.find('summary')
        if summary is None:
            raise oscerr.APIError(f'unexpected response:\n{ET.tostring(root, encoding=ET_ENCODING)}')
        if not return_existing:
            raise oscerr.APIError(f'failed to branch: {summary.text}')
        m = re.match(r"branch target package already exists: (\S+)/(\S+)", summary.text)
        if not m:
            e.msg += '\n' + summary.text
            raise
        return (True, m.group(1), m.group(2), None, None)

    root = xml_fromstring(f.read())
    if conf.config['http_debug']:
        print(ET.tostring(root, encoding=ET_ENCODING), file=sys.stderr)
    data = {}
    for i in root.findall('data'):
        data[i.get('name')] = i.text

    if disable_build:
        target_meta = show_package_meta(apiurl, data["targetproject"], data["targetpackage"])
        root = xml_fromstring(b''.join(target_meta))

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

    meta = None
    if not (src_apiurl == dst_apiurl and src_project == dst_project
            and src_package == dst_package):
        src_meta = show_package_meta(src_apiurl, src_project, src_package)
        dst_userid = conf.get_apiurl_usr(dst_apiurl)
        meta = replace_pkg_meta(src_meta, dst_package, dst_project, keep_maintainers,
                                dst_userid, keep_develproject, keep_scmsync=(not client_side_copy))

        url = make_meta_url('pkg', (dst_project, dst_package), dst_apiurl)
        found = None
        try:
            found = http_GET(url).readlines()
        except HTTPError as e:
            pass
        if force_meta_update or not found:
            print('Sending meta data...')
            u = makeurl(dst_apiurl, ['source', dst_project, dst_package, '_meta'])
            http_PUT(u, data=meta)

    if meta is None:
        meta = show_files_meta(dst_apiurl, dst_project, dst_package)

    root = xml_fromstring(meta)
    if root.find("scmsync") is not None:
        print("Note: package source is managed via SCM")
        return

    print('Copying files...')
    if not client_side_copy:
        query = {'cmd': 'copy', 'oproject': src_project, 'opackage': src_package}
        if expand or keep_link:
            query['expand'] = '1'
        if keep_link:
            query['keeplink'] = '1'
        if not revision_is_empty(revision):
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
        filelist = xml_fromstring(xml)
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
                path = ['source', dst_project, dst_package, filename]
                u = makeurl(dst_apiurl, path, query={'rev': 'repository'})
                http_PUT(u, file=f.name)
        tfilelist = Package.commit_filelist(dst_apiurl, dst_project, dst_package,
                                            filelist, msg=comment)
        todo = Package.commit_get_missing(tfilelist)
        if todo:
            raise oscerr.APIError(f"failed to copy: {', '.join(todo)}")
        return 'Done.'


def lock(apiurl: str, project: str, package: str, msg: Optional[str] = None):
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
        u = makeurl(apiurl, ['source', prj, pac, filename], query={'comment': f'removed {filename}'})
        http_DELETE(u)


# old compat lib call
def get_platforms(apiurl: str):
    return get_repositories(apiurl)


def get_repositories(apiurl: str):
    f = http_GET(makeurl(apiurl, ['platform']))
    tree = xml_parse(f)
    r = sorted(node.get('name') for node in tree.getroot())
    return r


def get_distributions(apiurl: str):
    """Returns list of dicts with headers
      'distribution', 'project', 'repository', 'reponame'"""

    f = http_GET(makeurl(apiurl, ['distributions']))
    root = xml_fromstring(b''.join(f))

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
    from . import obs_api

    project_obj = obs_api.Project.from_api(apiurl, prj)
    return [i.name for i in project_obj.repository_list or []]


class Repo:
    repo_line_templ = '%-15s %-10s'

    def __init__(self, name: str, arch: str):
        self.name = name
        self.arch = arch

    def __str__(self):
        return self.repo_line_templ % (self.name, self.arch)

    def __repr__(self):
        return f'Repo({self.name} {self.arch})'

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
                f.write(f'{repo.name} {repo.arch}\n')


def get_repos_of_project(apiurl: str, prj: str):
    from . import obs_api

    project_obj = obs_api.Project.from_api(apiurl, prj)
    for repo in project_obj.repository_list or []:
        for arch in repo.arch_list or []:
            yield Repo(repo.name, arch)


def get_binarylist(
    apiurl: str, prj: str, repo: str, arch: str, package: Optional[str] = None, verbose=False, withccache=False
):
    what = package or '_repository'
    query = {}
    if withccache:
        query['withccache'] = 1
    u = makeurl(apiurl, ['build', prj, repo, arch, what], query=query)
    f = http_GET(u)
    tree = xml_parse(f)
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
    tree = xml_parse(f)
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
    multibuild: Optional[bool] = None,
    locallink: Optional[bool] = None,
    code: Optional[str] = None,
):
    repository = repository or []
    arch = arch or []
    query = {}
    query["package"] = package
    query["oldstate"] = oldstate
    query["lastbuild"] = lastbuild
    query["multibuild"] = multibuild
    query["locallink"] = locallink
    query["code"] = code
    query["repository"] = repository
    query["arch"] = arch
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
    root = xml_fromstring(xml)
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


def get_results(
    apiurl: str,
    project: str,
    package: str,
    verbose=False,
    printJoin="",
    out: Optional[dict] = None,
    *args,
    **kwargs
):
    """returns list of/or prints a human readable status for the specified package"""
    # hmm the function name is a bit too generic - something like
    # get_package_results_human would be better, but this would break the existing
    # api (unless we keep get_results around as well)...
    format = kwargs.pop('format', None)
    if format is None:
        format = '%(rep)-20s %(arch)-10s %(pkg)-30s %(status)s'
    r = []
    printed = False
    failed = False
    multibuild_packages = kwargs.pop('multibuild_packages', [])
    show_excluded = kwargs.pop('showexcl', False)
    code_filter = kwargs.get('code', None)
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
                    res['status'] += f": {res['details']}"
            elif res['code'] in ('scheduled', ) and res['details']:
                # highlight scheduled jobs with possible dispatch problems
                res['status'] += '*'
            if res['dirty']:
                if verbose:
                    res['status'] = f"outdated (was: {res['status']})"
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
                r.append(format % res)

            if res['code'] in ('failed', 'broken', 'unresolvable'):
                failed = True

        if printJoin:
            if printed:
                # will print a newline if already a result was printed (improves readability)
                print()
            print(printJoin.join(r))
            printed = True

    if out is None:
        out = {}

    out["failed"] = failed

    return r


def get_package_results(apiurl: str, project: str, package: Optional[str] = None, wait=False, multibuild_packages: Optional[List[str]] = None, *args, **kwargs):
    """generator that returns a the package results as an xml structure"""
    xml = b''
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
            root = xml_fromstring(e.read())
            if e.code == 400 and kwargs.get('multibuild') and re.search('multibuild', getattr(root.find('summary'), 'text', '')):
                kwargs['multibuild'] = None
                kwargs['locallink'] = None
                continue
            raise
        root = xml_fromstring(xml)
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

        # filter the result according to the specified multibuild_packages (flavors)
        if multibuild_packages:
            for result in list(root):
                for status in list(result):
                    package = status.attrib["package"]
                    package_flavor = package.rsplit(":", 1)

                    # package has flavor, check if the flavor is in multibuild_packages
                    flavor_match = len(package_flavor) == 2 and package_flavor[1] in multibuild_packages

                    # package nas no flavor, check if "" is in multibuild_packages
                    no_flavor_match = len(package_flavor) == 1 and "" in multibuild_packages

                    if not flavor_match and not no_flavor_match:
                        # package doesn't match multibuild_packages, remove the corresponding <status> from <result>
                        result.remove(status)

                # remove empty <result> from <resultlist>
                if len(result) == 0:
                    root.remove(result)

            if len(root) == 0:
                break

            xmlindent(root)
            xml = ET.tostring(root)

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
    root = xml_fromstring(b''.join(f))

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
        for node in results.findall('status'):
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
                r.append(f'{pac} {repo[0]} {repo[1]} {state}')
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
                            print(f'osc: warn: unknown status \'{status[pac][tg]}\'...')
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
                        print(f'osc: warn: unknown status \'{status[pac][tg]}\'...')
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
            raise oscerr.OscIOError(None, f'Content-Length is empty for {url}, protocol violation')
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
    output_buffer=None,
):
    """prints out the buildlog on stdout"""

    output_buffer = output_buffer or sys.stdout.buffer

    def print_data(data, strip_time=False):
        if strip_time:
            data = buildlog_strip_time(data)
        # to protect us against control characters (CVE-2012-1095)
        output_buffer.write(sanitize_text(data))

    query = {'nostream': '1', 'start': f'{offset}'}
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
    query = {}
    query["package"] = packages

    if reverse:
        query["view"] = "revpkgnames"
    else:
        query["view"] = "pkgnames"

    u = makeurl(apiurl, ['build', project, repository, arch, '_builddepinfo'], query=query)
    f = http_GET(u)
    return f.read()


def get_buildinfo(
    apiurl: str, prj: str, package: str, repository: str, arch: str, specfile=None, addlist=None, debug=None
):
    query = {}
    query["add"] = addlist
    query["debug"] = debug

    u = makeurl(apiurl, ['build', prj, repository, arch, package, '_buildinfo'], query=query)

    if specfile:
        f = http_POST(u, data=specfile)
    else:
        f = http_GET(u)
    return f.read()


def get_buildconfig(apiurl: str, prj: str, repository: str, path=None):
    query = {}
    query["path"] = path
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
    pb = xml_fromstring('<pbuild></pbuild>')
    tree = ET.ElementTree(pb)
    preset = ET.SubElement(pb, 'preset', name=repository, default="")  # default should be empty, but ET crashes
    bi_text = decode_it(get_buildinfo(apiurl, project, '_repository', repository, arch, specfile="Name: dummy"))
    root = xml_fromstring(bi_text)

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
    root = xml_fromstring(b''.join(f))
    return [node.get('name') for node in root.findall('entry')]


def get_source_rev(apiurl: str, project: str, package: str, revision=None):
    # API supports ?deleted=1&meta=1&rev=4
    # but not rev=current,rev=latest,rev=top, or anything like this.
    # CAUTION: We have to loop through all rev and find the highest one, if none given.

    if not revision_is_empty(revision):
        url = makeurl(apiurl, ['source', project, package, '_history'], {'rev': revision})
    else:
        url = makeurl(apiurl, ['source', project, package, '_history'])
    f = http_GET(url)
    xml = xml_parse(f)
    ent = None
    for new in xml.findall('revision'):
        # remember the newest one.
        if not ent:
            ent = new
        elif ent.findtext("time") < new.findtext("time"):
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
    root = xml_parse(f).getroot()

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
            print(f'{endtime}|{package}|{reason}|{code}|{waitbuild}|{worker}')
        else:
            print('%s  %-50s %-16s %-16s %-16s %-16s' % (endtime, package[0:49], reason[0:15], code[0:15], waitbuild, worker))


def get_commitlog(
    apiurl: str,
    prj: str,
    package: str,
    revision: Optional[str],
    format: str = "text",
    meta: Optional[bool] = None,
    deleted: Optional[bool] = None,
    revision_upper: Optional[str] = None,
    patch: Optional[bool] = None,
):
    if package is None:
        package = "_project"

    from . import obs_api
    revision_list = obs_api.Package.get_revision_list(apiurl, prj, package, deleted=deleted, meta=meta)

    # TODO: consider moving the following block to Package.get_revision_list()
    # keep only entries matching the specified revision
    if not revision_is_empty(revision):
        if isinstance(revision, str) and len(revision) == 32:
            # revision is srcmd5
            revision_list = [i for i in revision_list if i.srcmd5 == revision]
        else:
            revision = int(revision)
            if revision_is_empty(revision_upper):
                revision_list = [i for i in revision_list if i.rev == revision]
            else:
                revision_upper = int(revision_upper)
                revision_list = [i for i in revision_list if i.rev <= revision_upper and i.rev >= revision]

    if format == "csv":
        f = io.StringIO()
        writer = csv.writer(f, dialect="unix")
        for revision in reversed(revision_list):
            writer.writerow(
                (
                    revision.rev,
                    revision.user,
                    revision.get_time_str(),
                    revision.srcmd5,
                    revision.comment,
                    revision.requestid,
                )
            )
        f.seek(0)
        yield from f.read().splitlines()
        return

    if format == "xml":
        root = ET.Element("log")
        for revision in reversed(revision_list):
            entry = ET.SubElement(root, "logentry")
            entry.attrib["revision"] = str(revision.rev)
            entry.attrib["srcmd5"] = revision.srcmd5
            ET.SubElement(entry, "author").text = revision.user
            ET.SubElement(entry, "date").text = revision.get_time_str()
            ET.SubElement(entry, "requestid").text = str(revision.requestid) if revision.requestid else ""
            ET.SubElement(entry, "msg").text = revision.comment or ""
        xmlindent(root)
        yield from ET.tostring(root, encoding="utf-8").decode("utf-8").splitlines()
        return

    if format == "text":
        for revision in reversed(revision_list):
            entry = (
                f"r{revision.rev}",
                revision.user,
                revision.get_time_str(),
                revision.srcmd5,
                revision.version,
                f"rq{revision.requestid}" if revision.requestid else ""
            )
            yield 76 * "-"
            yield " | ".join(entry)
            yield ""
            yield revision.comment or "<no message>"
            yield ""
            if patch:
                rdiff = server_diff_noex(
                    apiurl,
                    prj,
                    package,
                    revision.rev - 1,
                    prj,
                    package,
                    revision.rev,
                    meta=meta,
                )
                yield highlight_diff(rdiff).decode("utf-8", errors="replace")
        return

    raise ValueError(f"Invalid format: {format}")


def runservice(apiurl: str, prj: str, package: str):
    u = makeurl(apiurl, ['source', prj, package], query={'cmd': 'runservice'})

    try:
        f = http_POST(u)
    except HTTPError as e:
        e.osc_msg = f'could not trigger service run for project \'{prj}\' package \'{package}\''
        raise

    root = xml_parse(f).getroot()
    return root.get('code')


def waitservice(apiurl: str, prj: str, package: str):
    u = makeurl(apiurl, ['source', prj, package], query={'cmd': 'waitservice'})

    try:
        f = http_POST(u)
    except HTTPError as e:
        e.osc_msg = f'The service for project \'{prj}\' package \'{package}\' failed'
        raise

    root = xml_parse(f).getroot()
    return root.get('code')


def mergeservice(apiurl: str, prj: str, package: str):
    # first waiting that the service finishes and that it did not fail
    waitservice(apiurl, prj, package)

    # real merge
    u = makeurl(apiurl, ['source', prj, package], query={'cmd': 'mergeservice'})

    try:
        f = http_POST(u)
    except HTTPError as e:
        e.osc_msg = f'could not merge service files in project \'{prj}\' package \'{package}\''
        raise

    root = xml_parse(f).getroot()
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
        e.osc_msg = f'could not trigger rebuild for project \'{prj}\' package \'{package}\''
        raise

    root = xml_parse(f).getroot()
    return root.get('code')


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
        e.osc_msg = f'{cmd} command failed for project {project}'
        if package:
            e.osc_msg += f' package {package}'
        if arch:
            e.osc_msg += f' arch {arch}'
        if repo:
            e.osc_msg += f' repository {repo}'
        if code:
            e.osc_msg += f' code={code}'
        if sysrq:
            e.osc_msg += f' sysrq={code}'
        raise

    root = xml_parse(f).getroot()
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
        expr = f'({expr})'
    if nexpr_parentheses:
        new_expr = f'({new_expr})'
    return f'{expr} {op} {new_expr}'


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
        res[urlpath] = xml_parse(f).getroot()
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
        res = xml_parse(f).getroot()
    except HTTPError as e:
        # old server not supporting this search
        pass
    return res

def set_link_rev(
    apiurl: str,
    project: str,
    package: str,
    revision="",
    expand=False,
    msg: Optional[str] = None,
    vrev: Optional[str] = None,
):
    url = makeurl(apiurl, ["source", project, package, "_link"])
    try:
        f = http_GET(url)
        root = xml_parse(f).getroot()
    except HTTPError as e:
        e.osc_msg = f'Unable to get _link file in package \'{package}\' for project \'{project}\''
        raise
    revision = _set_link_rev(apiurl, project, package, root, revision, expand=expand, setvrev=vrev)
    l = ET.tostring(root, encoding=ET_ENCODING)

    if not msg:
        if revision:
            msg = f"Set link revision to {revision}"
        else:
            msg = "Unset link revision"
    url = makeurl(apiurl, ["source", project, package, "_link"], {"comment": msg})
    http_PUT(url, data=l)
    return revision


def _set_link_rev(
    apiurl: str, project: str, package: str, root, revision="", expand=False, setvrev: Optional[str] = None
):
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
    if setvrev:
        root.set('vrev', setvrev)
    elif not revision_is_empty(vrev) and not revision_is_empty(revision) and len(revision) >= 32:
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


def unpack_srcrpm(srpm, dir, *files):
    """
    This method unpacks the passed srpm into the
    passed dir. If arguments are passed to the \'files\' tuple
    only this files will be unpacked.
    """
    if not is_srcrpm(srpm):
        print(f'error - \'{srpm}\' is not a source rpm.', file=sys.stderr)
        sys.exit(1)
    curdir = os.getcwd()
    if os.path.isdir(dir):
        os.chdir(dir)
    ret = -1
    with open(srpm) as fsrpm:
        with open(os.devnull, 'w') as devnull:
            rpm2cpio_proc = subprocess.Popen(['rpm2cpio'], stdin=fsrpm,
                                             stdout=subprocess.PIPE)
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
        print(f'error \'{ret}\' - cannot extract \'{srpm}\'', file=sys.stderr)
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
    path = (prj, )
    kind = 'prj'
    if pac:
        path = path + (pac ,)
        kind = 'pkg'
    data = meta_exists(metatype=kind,
                       path_args=path,
                       template_args=None,
                       create_new=False)

    if data and get_user_meta(apiurl, user) is not None:
        root = xml_fromstring(parse_meta_to_string(data))
        found = False
        for person in root.iter('person'):
            if person.get('userid') == user and person.get('role') == role:
                found = True
                print("user already exists")
                break
        if not found:
            # the xml has a fixed structure
            root.insert(2, ET.Element('person', role=role, userid=user))
            print(f'user \'{user}\' added to \'{pac or prj}\'')
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
    path = (prj, )
    kind = 'prj'
    if pac:
        path = path + (pac, )
        kind = 'pkg'
    data = meta_exists(metatype=kind,
                       path_args=path,
                       template_args=None,
                       create_new=False)
    if data and get_user_meta(apiurl, user) is not None:
        root = xml_fromstring(parse_meta_to_string(data))
        found = False
        for person in root.iter('person'):
            if person.get('userid') == user and person.get('role') == role:
                root.remove(person)
                found = True
                print(f"user '{user}' removed")
        if found:
            edit_meta(metatype=kind,
                      path_args=path,
                      data=ET.tostring(root, encoding=ET_ENCODING))
        else:
            print(f"user '{user}' not found in '{pac or prj}'")
    else:
        print("an error occured")


def setBugowner(apiurl: str, prj: str, pac: str, user=None, group=None):
    """ delete all bugowners (user and group entries) and set one new one in a package or project """
    path = (prj, )
    kind = 'prj'
    if pac:
        path = path + (pac, )
        kind = 'pkg'
    data = meta_exists(metatype=kind,
                       path_args=path,
                       template_args=None,
                       create_new=False)
    if user.startswith('group:'):
        group = user.replace('group:', '')
        user = None
    if data:
        root = xml_fromstring(parse_meta_to_string(data))
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
            raise oscerr.OscIOError(None, f'file or directory \'{pathname}\' already exists')
    else:
        msg = f'\'{prj_dir}\' is not a working copy'
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
        services = xml_parse(os.path.join(os.getcwd(), '_service')).getroot()
    else:
        services = xml_fromstring("<services />")
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
        services = xml_parse(os.path.join(os.getcwd(), '_service')).getroot()
    else:
        services = xml_fromstring("<services />")
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
            raise oscerr.OscIOError(None, f'file \'{filename}\' does not exist')

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
            print(f'osc: warning: \'{filename}\' is already under version control')
            pacs.remove(filename)
        elif os.path.isdir(filename) and is_project_dir(prj_dir):
            raise oscerr.WrongArgs('osc: cannot add a directory to a project unless '
                                   '\'do_package_tracking\' is enabled in the configuration file')

    pacs, no_pacs = Package.from_paths_nofail(pacs)
    for filename in no_pacs:
        filename = os.path.normpath(filename)
        directory = os.path.join(filename, os.pardir)
        if not is_package_dir(directory):
            print(f'osc: warning: \'{filename}\' cannot be associated to a package')
            continue
        resp = raw_input(f"{filename} is a directory, do you want to archive it for submission? (y/n) ")
        if resp not in ('y', 'Y'):
            continue
        archive = f"{filename}.obscpio"
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
                        print(f'skipping directory \'{os.path.join(pac.dir, filename)}\'')
                    else:
                        pac.todo.append(filename)
            elif pac.name in prj.pacs_have:
                print(f'osc: warning: \'{pac.name}\' is already under version control')
        for filename in pac.todo:
            if filename in pac.skipped:
                continue
            if filename in pac.excluded and not force:
                print(f'osc: warning: \'{filename}\' is excluded from a working copy', file=sys.stderr)
                continue
            try:
                pac.addfile(filename)
            except oscerr.PackageFileConflict as e:
                fname = os.path.join(getTransActPath(pac.dir), filename)
                print(f'osc: warning: \'{fname}\' is already under version control')


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
            footer.append(f'\nDiff for working copy: {p.dir}')
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
        print(msg % ('package', f"{project}/{package}", len(requests)))
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
            root = xml_fromstring(e.read())
            summary = root.find('summary')
            if summary is not None:
                print(summary.text, file=sys.stderr)
            print('Try -f to force the state change', file=sys.stderr)
        return False

    def get_repos(src_actions):
        """
        Translate src_actions to [{"proj": ..., "pkg": ..., "repo": ..., "arch": ...}]
        """
        result = []
        for action in src_actions:
            disabled = show_package_disabled_repos(apiurl, action.src_project, action.src_package)
            for repo in get_repos_of_project(apiurl, action.src_project):
                if (disabled is None) or (repo.name not in [d["repo"] for d in disabled]):
                    entry = {
                        "proj": action.src_project,
                        "pkg": action.src_package,
                        "repo": repo.name,
                        "arch": repo.arch
                    }
                    result.append(entry)
        return result

    def select_repo(src_actions):
        """
        Prompt user to select a repo from a list.
        """
        repos = get_repos(src_actions)

        for num, entry in enumerate(repos):
            print(f"({num}) {entry['proj']}/{entry['pkg']}/{entry['repo']}/{entry['arch']}")

        if not repos:
            print('No repos')
            return None

        while True:
            try:
                reply = raw_input(f"Number of repo to examine (0 - {len(repos)-1}): ").strip()
                if not reply:
                    return None
                reply_num = int(reply)
                return repos[reply_num]
            except (ValueError, IndexError):
                print(f"Invalid index. Please choose between 0 and {len(repos)-1}")

    def safe_get_rpmlint_log(src_actions):
        repo = select_repo(src_actions)
        if not repo:
            return
        try:
            run_pager(get_rpmlint_log(apiurl, **repo))
        except HTTPError as e:
            if e.code == 404:
                print(f"No rpmlint log for {repo['repo']}/{repo['arch']}")
            else:
                raise

    def get_build_log(src_actions):
        repo = select_repo(src_actions)
        if not repo:
            return
        try:
            buffer = io.BytesIO()
            print_buildlog(apiurl, repo["proj"], repo["pkg"], repo["repo"], repo["arch"], output_buffer=buffer)
            buffer.seek(0)
            run_pager(buffer.read())
        except HTTPError as e:
            if e.code == 404:
                print(f"No build log for {repo['repo']}/{repo['arch']}")
            else:
                raise

    def print_request(request):
        print(request)

    def print_source_buildstatus(src_actions, newline=False):
        if newline:
            print()
        for action in src_actions:
            print(f'{action.src_project}/{action.src_package}:')
            try:
                print('\n'.join(get_results(apiurl, action.src_project, action.src_package)))
            except HTTPError as e:
                if e.code != 404:
                    raise
                print(f'unable to retrieve the buildstatus: {e}')

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
            prompt = 'd(i)ff/(a)ccept/(d)ecline/(r)evoke/(b)uildstatus/(bl)buildlog/rpm(li)ntlog/c(l)one/(e)dit/co(m)ment/(s)kip/(c)ancel > '
        elif src_actions:
            # no edit for maintenance release requests
            prompt = 'd(i)ff/(a)ccept/(d)ecline/(r)evoke/(b)uildstatus/(bl)buildlog/rpm(li)ntlog/c(l)one/co(m)ment/(s)kip/(c)ancel > '
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
            accept = repl == "a" or repl.startswith("a ")

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
                print(f'skipping: #{request.reqid}', file=sys.stderr)
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
            elif repl == 'bl' and src_actions:
                get_build_log(src_actions)
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
                    print(f'invalid choice: \'{repl}\'', file=sys.stderr)
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
                                                  f'superseded by {request.reqid}', request.reqid, force=force)
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
                            print(f'\'{num}\' is not a number.')
                            continue
                        if num < 0 or num >= len(reviews):
                            print(f'number \'{num}\' out of range.')
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
            print('(%i)' % i, f"{fmt['source']}  {fmt['target']}")
        num = raw_input('> ')
        try:
            num = int(num)
        except ValueError:
            raise oscerr.WrongArgs(f'\'{num}\' is not a number.')
        if num < 0 or num >= len(orequest.actions):
            raise oscerr.WrongArgs(f'number \'{num}\' out of range.')

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
            print(f'Please remove the dir \'{tmpdir}\' manually')
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
    xpath = f'person/@userid = \'{user}\''
    excl_prj = ''
    excl_pkg = ''
    for i in exclude_projects:
        excl_prj = xpath_join(excl_prj, f'not(@name = \'{i}\')', op='and')
        excl_pkg = xpath_join(excl_pkg, f'not(@project = \'{i}\')', op='and')
    role_filter_xpath = xpath
    if role:
        xpath = xpath_join(xpath, f'person/@role = \'{role}\'', inner=True, op='and')
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
    url = makeurl(apiurl, ["comments", kind] + list(args))
    f = http_GET(url)
    return xml_parse(f).getroot()


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
    query["parent_id"] = kwargs.get("parent", None)
    u = makeurl(apiurl, ["comments", kind] + list(args), query=query)
    f = http_POST(u, data=comment)
    ret = xml_fromstring(f.read()).find('summary')
    if ret is None:
        return None
    return ret.text


def delete_comment(apiurl: str, cid: str) -> Optional[str]:
    u = makeurl(apiurl, ['comment', cid])
    f = http_DELETE(u)
    ret = xml_fromstring(f.read()).find('summary')
    if ret is None:
        return None
    return ret.text


def get_rpmlint_log(apiurl: str, proj: str, pkg: str, repo: str, arch: str):
    u = makeurl(apiurl, ['build', proj, repo, arch, pkg, 'rpmlint.log'])
    f = http_GET(u)
    return f.read()


def checkout_deleted_package(apiurl: str, proj: str, pkg: str, dst, *, revision: Optional[str] = None):
    pl = meta_get_filelist(apiurl, proj, pkg, revision=revision, deleted=True)
    query = {}
    query['deleted'] = 1
    query['rev'] = revision

    if os.path.isdir(dst):
        print(f'Restoring in existing directory {dst}')
    else:
        print(f'Creating {dst}')
        os.makedirs(dst)

    for filename in pl:
        print(f'Restoring {filename} to {dst}')
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
        config_present = bool(conf.config['api_host_options'][apiurl].get(tag, None))
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
                    msg = f'Try env {tag2envs[tag][0]}=...'
                    print(msg, file=sys.stderr)

    for (tag, val) in tag2val.items():
        for env in tag2envs[tag]:
            if val:
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

        root = xml_fromstring(s)
        for node in root.findall("flavor"):
            result.add(node.text)
        # <package> is deprecated according to OBS Multibuild.pm, but it is widely used
        for node in root.findall("package"):
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

            # always add an empty flavor which is implicit
            all_flavors.add("")

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
