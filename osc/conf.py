# Copyright (C) 2006-2009 Novell Inc.  All rights reserved.
# This program is free software; it may be used, copied, modified
# and distributed under the terms of the GNU General Public Licence,
# either version 2, or version 3 (at your option).

from __future__ import print_function

"""Read osc configuration and store it in a dictionary

This module reads and parses oscrc. The resulting configuration is stored
for later usage in a dictionary named 'config'.
The oscrc is kept mode 0600, so that it is not publically readable.
This gives no real security for storing passwords.
If in doubt, use your favourite keyring.
Password is stored on ~/.config/osc/oscrc as bz2 compressed and base64 encoded, so that is fairly
large and not to be recognized or remembered easily by an occasional spectator.

If information is missing, it asks the user questions.

After reading the config, urllib2 is initialized.

The configuration dictionary could look like this:

{'apisrv': 'https://api.opensuse.org/',
 'user': 'joe',
 'api_host_options': {'api.opensuse.org': {'user': 'joe', 'pass': 'secret'},
                      'apitest.opensuse.org': {'user': 'joe', 'pass': 'secret',
                                               'http_headers':(('Host','api.suse.de'),
                                                               ('User','faye'))},
                      'foo.opensuse.org': {'user': 'foo', 'pass': 'foo'}},
 'build-cmd': '/usr/bin/build',
 'build-root': '/abuild/oscbuild-%(repo)s-%(arch)s',
 'packagecachedir': '/var/cache/osbuild',
 'su-wrapper': 'sudo',
 }

"""

import bz2
import base64
import os
import re
import sys
import ssl
import warnings
import getpass

try:
    from http.cookiejar import LWPCookieJar, CookieJar
    from http.client import HTTPConnection, HTTPResponse
    from io import StringIO
    from urllib.parse import urlsplit
    from urllib.error import URLError
    from urllib.request import HTTPBasicAuthHandler, HTTPCookieProcessor, HTTPPasswordMgrWithDefaultRealm, ProxyHandler
    from urllib.request import AbstractHTTPHandler, build_opener, proxy_bypass, HTTPSHandler
except ImportError:
    #python 2.x
    from cookielib import LWPCookieJar, CookieJar
    from httplib import HTTPConnection, HTTPResponse
    from StringIO import StringIO
    from urlparse import urlsplit
    from urllib2 import URLError, HTTPBasicAuthHandler, HTTPCookieProcessor, HTTPPasswordMgrWithDefaultRealm, ProxyHandler, AbstractBasicAuthHandler
    from urllib2 import AbstractHTTPHandler, build_opener, proxy_bypass, HTTPSHandler

from . import OscConfigParser
from osc import oscerr
from osc.util.helper import raw_input
from .oscsslexcp import NoSecureSSLError
from osc import credentials

GENERIC_KEYRING = False
GNOME_KEYRING = False

try:
    import keyring
    GENERIC_KEYRING = True
except:
    try:
        import gobject
        gobject.set_application_name('osc')
        import gnomekeyring
        GNOME_KEYRING = gnomekeyring.is_available()
    except:
        pass


def _get_processors():
    """
    get number of processors (online) based on
    SC_NPROCESSORS_ONLN (returns 1 if config name does not exist).
    """
    try:
        return os.sysconf('SC_NPROCESSORS_ONLN')
    except ValueError as e:
        return 1

DEFAULTS = {'apiurl': 'https://api.opensuse.org',
            'user': None,
            'pass': None,
            'passx': None,
            'packagecachedir': '/var/tmp/osbuild-packagecache',
            'su-wrapper': 'sudo',

            # build type settings
            'build-cmd': '/usr/bin/build',
            'build-type': '',                   # may be empty for chroot, kvm or xen
            'build-root': '/var/tmp/build-root/%(repo)s-%(arch)s',
            'build-uid': '',                    # use the default provided by build
            'build-device': '',                 # required for VM builds
            'build-memory': '',                 # required for VM builds
            'build-swap': '',                   # optional for VM builds
            'build-vmdisk-rootsize': '',        # optional for VM builds
            'build-vmdisk-swapsize': '',        # optional for VM builds
            'build-vmdisk-filesystem': '',        # optional for VM builds
            'build-vm-user': '',                # optional for VM builds
            'build-kernel': '',                 # optional for VM builds
            'build-initrd': '',                 # optional for VM builds

            'build-jobs': str(_get_processors()),
            'builtin_signature_check': '1',     # by default use builtin check for verify pkgs
            'icecream': '0',

            'buildlog_strip_time': '0',  # strips the build time from the build log

            'debug': '0',
            'http_debug': '0',
            'http_full_debug': '0',
            'http_retries': '3',
            'verbose': '1',
            'no_preinstallimage': '0',
            'traceback': '0',
            'post_mortem': '0',
            'use_keyring': '0',
            'gnome_keyring': '0',
            'cookiejar': '~/.osc_cookiejar',
            # fallback for osc build option --no-verify
            'no_verify': '0',
            # enable project tracking by default
            'do_package_tracking': '1',
            # default for osc build
            'extra-pkgs': '',
            # default repository
            'build_repository': 'openSUSE_Factory',
            # default project for branch or bco
            'getpac_default_project': 'openSUSE:Factory',
            # alternate filesystem layout: have multiple subdirs, where colons were.
            'checkout_no_colon': '0',
            # change filesystem layout: avoid checkout from within a proj or package dir.
            'checkout_rooted': '0',
            # local files to ignore with status, addremove, ....
            'exclude_glob': '.osc CVS .svn .* _linkerror *~ #*# *.orig *.bak *.changes.vctmp.*',
            # whether to keep passwords in plaintext (deprecated (see creds manager)).
            'plaintext_passwd': '0',
            # whether to print Web UI links to directly insert in browser (where possible)
            'print_web_links': '0',
            # limit the age of requests shown with 'osc req list'.
            # this is a default only, can be overridden by 'osc req list -D NNN'
            # Use 0 for unlimted.
            'request_list_days': 0,
            # check for unversioned/removed files before commit
            'check_filelist': '1',
            # check for pending requests after executing an action (e.g. checkout, update, commit)
            'check_for_request_on_action': '1',
            # what to do with the source package if the submitrequest has been accepted
            'submitrequest_on_accept_action': '',
            'request_show_interactive': '0',
            'request_show_source_buildstatus': '0',
            # if a review is accepted in interactive mode and a group
            # was specified the review will be accepted for this group
            'review_inherit_group': '0',
            'submitrequest_accepted_template': '',
            'submitrequest_declined_template': '',
            'linkcontrol': '0',
            'include_request_from_project': '1',
            'local_service_run': '1',

            # Maintenance defaults to OBS instance defaults
            'maintained_attribute': 'OBS:Maintained',
            'maintenance_attribute': 'OBS:MaintenanceProject',
            'maintained_update_project_attribute': 'OBS:UpdateProject',
            'show_download_progress': '0',
            # path to the vc script
            'vc-cmd': '/usr/lib/build/vc',

            # heuristic to speedup Package.status
            'status_mtime_heuristic': '0'
}

# some distros like Debian rename and move build to obs-build
if not os.path.isfile('/usr/bin/build') and os.path.isfile('/usr/bin/obs-build'):
    DEFAULTS['build-cmd'] = '/usr/bin/obs-build'
if not os.path.isfile('/usr/lib/build/vc') and os.path.isfile('/usr/lib/obs-build/vc'):
    DEFAULTS['vc-cmd'] = '/usr/lib/obs-build/vc'

# being global to this module, this dict can be accessed from outside
# it will hold the parsed configuration
config = DEFAULTS.copy()

boolean_opts = ['debug', 'do_package_tracking', 'http_debug', 'post_mortem', 'traceback', 'check_filelist', 'plaintext_passwd',
    'checkout_no_colon', 'checkout_rooted', 'check_for_request_on_action', 'linkcontrol', 'show_download_progress', 'request_show_interactive',
    'request_show_source_buildstatus', 'review_inherit_group', 'use_keyring', 'gnome_keyring', 'no_verify', 'builtin_signature_check',
    'http_full_debug', 'include_request_from_project', 'local_service_run', 'buildlog_strip_time', 'no_preinstallimage',
    'status_mtime_heuristic', 'print_web_links']
integer_opts = ['build-jobs']

api_host_options = ['user', 'pass', 'passx', 'aliases', 'http_headers', 'realname', 'email', 'sslcertck', 'cafile', 'capath', 'trusted_prj']

new_conf_template = """
[general]

# URL to access API server, e.g. %(apiurl)s
# you also need a section [%(apiurl)s] with the credentials
apiurl = %(apiurl)s

# Downloaded packages are cached here. Must be writable by you.
#packagecachedir = %(packagecachedir)s

# Wrapper to call build as root (sudo, su -, ...)
#su-wrapper = %(su-wrapper)s

# rootdir to setup the chroot environment
# can contain %%(repo)s, %%(arch)s, %%(project)s, %%(package)s and %%(apihost)s (apihost is the hostname
# extracted from currently used apiurl) for replacement, e.g.
# /srv/oscbuild/%%(repo)s-%%(arch)s or
# /srv/oscbuild/%%(repo)s-%%(arch)s-%%(project)s-%%(package)s
#build-root = %(build-root)s

# compile with N jobs (default: "getconf _NPROCESSORS_ONLN")
#build-jobs = N

# build-type to use - values can be (depending on the capabilities of the 'build' script)
# empty    -  chroot build
# kvm      -  kvm VM build  (needs build-device, build-swap, build-memory)
# xen      -  xen VM build  (needs build-device, build-swap, build-memory)
#   experimental:
#     qemu -  qemu VM build
#     lxc  -  lxc build
#build-type =

# build-device is the disk-image file to use as root for VM builds
# e.g. /var/tmp/FILE.root
#build-device = /var/tmp/FILE.root

# build-swap is the disk-image to use as swap for VM builds
# e.g. /var/tmp/FILE.swap
#build-swap = /var/tmp/FILE.swap

# build-kernel is the boot kernel used for VM builds
#build-kernel = /boot/vmlinuz

# build-initrd is the boot initrd used for VM builds
#build-initrd = /boot/initrd

# build-memory is the amount of memory used in the VM
# value in MB - e.g. 512
#build-memory = 512

# build-vmdisk-rootsize is the size of the disk-image used as root in a VM build
# values in MB - e.g. 4096
#build-vmdisk-rootsize = 4096

# build-vmdisk-swapsize is the size of the disk-image used as swap in a VM build
# values in MB - e.g. 1024
#build-vmdisk-swapsize = 1024

# build-vmdisk-filesystem is the file system type of the disk-image used in a VM build
# values are ext3(default) ext4 xfs reiserfs btrfs
#build-vmdisk-filesystem = ext4

# Numeric uid:gid to assign to the "abuild" user in the build-root
# or "caller" to use the current users uid:gid
# This is convenient when sharing the buildroot with ordinary userids
# on the host.
# This should not be 0
# build-uid =

# strip leading build time information from the build log
# buildlog_strip_time = 1

# extra packages to install when building packages locally (osc build)
# this corresponds to osc build's -x option and can be overridden with that
# -x '' can also be given on the command line to override this setting, or
# you can have an empty setting here. This global setting may leads to 
# dependency problems when the base distro is not providing the package.
# => using server side definition via cli_debug_packages substitute rule is
#    recommended therefore.
#extra-pkgs = 

# build platform is used if the platform argument is omitted to osc build
#build_repository = %(build_repository)s

# default project for getpac or bco
#getpac_default_project = %(getpac_default_project)s

# alternate filesystem layout: have multiple subdirs, where colons were.
#checkout_no_colon = %(checkout_no_colon)s

# change filesystem layout: avoid checkout within a project or package dir.
#checkout_rooted = %(checkout_rooted)s

# local files to ignore with status, addremove, ....
#exclude_glob = %(exclude_glob)s

# limit the age of requests shown with 'osc req list'.
# this is a default only, can be overridden by 'osc req list -D NNN'
# Use 0 for unlimted.
#request_list_days = %(request_list_days)s

# show info useful for debugging
#debug = 1

# show HTTP traffic useful for debugging
#http_debug = 1

# number of retries on HTTP transfer
#http_retries = 3

# Skip signature verification of packages used for build.
#no_verify = 1

# jump into the debugger in case of errors
#post_mortem = 1

# print call traces in case of errors
#traceback = 1

# check for unversioned/removed files before commit
#check_filelist = 1

# check for pending requests after executing an action (e.g. checkout, update, commit)
#check_for_request_on_action = 1

# what to do with the source package if the submitrequest has been accepted. If
# nothing is specified the API default is used
#submitrequest_on_accept_action = cleanup|update|noupdate

# template for an accepted submitrequest
#submitrequest_accepted_template = Hi %%(who)s,\\n
# thanks for working on:\\t%%(tgt_project)s/%%(tgt_package)s.
# SR %%(reqid)s has been accepted.\\n\\nYour maintainers

# template for a declined submitrequest
#submitrequest_declined_template = Hi %%(who)s,\\n
# sorry your SR %%(reqid)s (request type: %%(type)s) for
# %%(tgt_project)s/%%(tgt_package)s has been declined because...

#review requests interactively (default: off)
#request_show_review = 1

# if a review is accepted in interactive mode and a group
# was specified the review will be accepted for this group (default: off)
#review_inherit_group = 1

[%(apiurl)s]
# set aliases for this apiurl
# aliases = foo, bar
# real name used in .changes, unless the one from osc meta prj <user> will be used
# realname =
# email used in .changes, unless the one from osc meta prj <user> will be used
# email =
# additional headers to pass to a request, e.g. for special authentication
#http_headers = Host: foofoobar,
#       User: mumblegack
# Plain text password
#pass =
"""


account_not_configured_text = """
Your user account / password are not configured yet.
You will be asked for them below, and they will be stored in
%s for future use.
"""

config_incomplete_text = """

Your configuration file %s is not complete.
Make sure that it has a [general] section.
(You can copy&paste the below. Some commented defaults are shown.)

"""

config_missing_apiurl_text = """
the apiurl \'%s\' does not exist in the config file. Please enter
your credentials for this apiurl.
"""

cookiejar = None


def parse_apisrv_url(scheme, apisrv):
    if apisrv.startswith('http://') or apisrv.startswith('https://'):
        url = apisrv
    elif scheme != None:
        url = scheme + apisrv
    else:
        msg = 'invalid apiurl \'%s\' (specify the protocol (http:// or https://))' % apisrv
        raise URLError(msg)
    scheme, url, path = urlsplit(url)[0:3]
    return scheme, url, path.rstrip('/')


def urljoin(scheme, apisrv, path=''):
    return '://'.join([scheme, apisrv]) + path


def is_known_apiurl(url):
    """returns true if url is a known apiurl"""
    apiurl = urljoin(*parse_apisrv_url(None, url))
    return apiurl in config['api_host_options']


def extract_known_apiurl(url):
    """
    Return longest prefix of given url that is known apiurl,
    None if there is no known apiurl that is prefix of given url.
    """
    scheme, host, path = parse_apisrv_url(None, url)
    p = path.split('/')
    while p:
        apiurl = urljoin(scheme, host, '/'.join(p))
        if apiurl in config['api_host_options']:
            return apiurl
        p.pop()
    return None


def get_apiurl_api_host_options(apiurl):
    """
    Returns all apihost specific options for the given apiurl, None if
    no such specific optiosn exist.
    """
    # FIXME: in A Better World (tm) there was a config object which
    # knows this instead of having to extract it from a url where it
    # had been mingled into before.  But this works fine for now.

    apiurl = urljoin(*parse_apisrv_url(None, apiurl))
    if is_known_apiurl(apiurl):
        return config['api_host_options'][apiurl]
    raise oscerr.ConfigMissingApiurl('missing credentials for apiurl: \'%s\'' % apiurl,
                                     '', apiurl)


def get_apiurl_usr(apiurl):
    """
    returns the user for this host - if this host does not exist in the
    internal api_host_options the default user is returned.
    """
    # FIXME: maybe there should be defaults not just for the user but
    # for all apihost specific options.  The ConfigParser class
    # actually even does this but for some reason we don't use it
    # (yet?).

    try:
        return get_apiurl_api_host_options(apiurl)['user']
    except KeyError:
        print('no specific section found in config file for host of [\'%s\'] - using default user: \'%s\'' \
            % (apiurl, config['user']), file=sys.stderr)
        return config['user']


# workaround m2crypto issue:
# if multiple SSL.Context objects are created
# m2crypto only uses the last object which was created.
# So we need to build a new opener everytime we switch the
# apiurl (because different apiurls may have different
# cafile/capath locations)
def _build_opener(apiurl):
    from osc.core import __version__
    global config
    if 'last_opener' not in _build_opener.__dict__:
        _build_opener.last_opener = (None, None)
    if apiurl == _build_opener.last_opener[0]:
        return _build_opener.last_opener[1]

    # respect no_proxy env variable
    if proxy_bypass(apiurl):
        # initialize with empty dict
        proxyhandler = ProxyHandler({})
    else:
        # read proxies from env
        proxyhandler = ProxyHandler()

    # workaround for http://bugs.python.org/issue9639
    authhandler_class = HTTPBasicAuthHandler
    if sys.version_info >= (2, 6, 6) and sys.version_info < (2, 7, 9):
        class OscHTTPBasicAuthHandler(HTTPBasicAuthHandler):
            # The following two functions were backported from upstream 2.7.
            def http_error_auth_reqed(self, authreq, host, req, headers):
                authreq = headers.get(authreq, None)

                if authreq:
                    mo = AbstractBasicAuthHandler.rx.search(authreq)
                    if mo:
                        scheme, quote, realm = mo.groups()
                        if quote not in ['"', "'"]:
                            warnings.warn("Basic Auth Realm was unquoted",
                                          UserWarning, 2)
                        if scheme.lower() == 'basic':
                            return self.retry_http_basic_auth(host, req, realm)

            def retry_http_basic_auth(self, host, req, realm):
                user, pw = self.passwd.find_user_password(realm, host)
                if pw is not None:
                    raw = "%s:%s" % (user, pw)
                    auth = 'Basic %s' % base64.b64encode(raw).strip()
                    if req.get_header(self.auth_header, None) == auth:
                        return None
                    req.add_unredirected_header(self.auth_header, auth)
                    return self.parent.open(req, timeout=req.timeout)
                else:
                    return None

        authhandler_class = OscHTTPBasicAuthHandler

    options = config['api_host_options'][apiurl]
    # with None as first argument, it will always use this username/password
    # combination for urls for which arg2 (apisrv) is a super-url
    authhandler = authhandler_class( \
        HTTPPasswordMgrWithDefaultRealm())
    authhandler.add_password(None, apiurl, options['user'], options['pass'])

    if options['sslcertck']:
        try:
            from . import oscssl
            from M2Crypto import m2urllib2
        except ImportError as e:
            print(e)
            raise NoSecureSSLError('M2Crypto is needed to access %s in a secure way.\nPlease install python-m2crypto.' % apiurl)

        cafile = options.get('cafile', None)
        capath = options.get('capath', None)
        if not cafile and not capath:
            for i in ['/etc/pki/tls/cert.pem', '/etc/ssl/certs']:
                if os.path.isfile(i):
                    cafile = i
                    break
                elif os.path.isdir(i):
                    capath = i
                    break
        if not cafile and not capath:
            raise oscerr.OscIOError(None, 'No CA certificates found. (You may want to install ca-certificates-mozilla package)')
        ctx = oscssl.mySSLContext()
        if ctx.load_verify_locations(capath=capath, cafile=cafile) != 1:
            raise oscerr.OscIOError(None, 'No CA certificates found. (You may want to install ca-certificates-mozilla package)')
        opener = m2urllib2.build_opener(ctx, oscssl.myHTTPSHandler(ssl_context=ctx, appname='osc'), HTTPCookieProcessor(cookiejar), authhandler, proxyhandler)
    else:
        handlers = [HTTPCookieProcessor(cookiejar), authhandler, proxyhandler]
        try:
            # disable ssl cert check in python >= 2.7.9
            ctx = ssl._create_unverified_context()
            handlers.append(HTTPSHandler(context=ctx))
        except AttributeError:
            pass
        print("WARNING: SSL certificate checks disabled. Connection is insecure!\n", file=sys.stderr)
        opener = build_opener(*handlers)
    opener.addheaders = [('User-agent', 'osc/%s' % __version__)]
    _build_opener.last_opener = (apiurl, opener)
    return opener


def init_basicauth(config, config_mtime):
    """initialize urllib2 with the credentials for Basic Authentication"""

    def filterhdrs(meth, ishdr, *hdrs):
        # this is so ugly but httplib doesn't use
        # a logger object or such
        def new_method(self, *args, **kwargs):
            # check if this is a recursive call (note: we do not
            # have to care about thread safety)
            is_rec_call = getattr(self, '_orig_stdout', None) is not None
            try:
                if not is_rec_call:
                    self._orig_stdout = sys.stdout
                    sys.stdout = StringIO()
                meth(self, *args, **kwargs)
                hdr = sys.stdout.getvalue()
            finally:
                # restore original stdout
                if not is_rec_call:
                    sys.stdout = self._orig_stdout
                    del self._orig_stdout
            for i in hdrs:
                if ishdr:
                    hdr = re.sub(r'%s:[^\\r]*\\r\\n' % i, '', hdr)
                else:
                    hdr = re.sub(i, '', hdr)
            sys.stdout.write(hdr)
        new_method.__name__ = meth.__name__
        return new_method

    if config['http_debug'] and not config['http_full_debug']:
        HTTPConnection.send = filterhdrs(HTTPConnection.send, True, 'Cookie', 'Authorization')
        HTTPResponse.begin = filterhdrs(HTTPResponse.begin, False, 'header: Set-Cookie.*\n')

    if sys.version_info < (2, 6):
        # HTTPS proxy is not supported in old urllib2. It only leads to an error
        # or, at best, a warning.
        if 'https_proxy' in os.environ:
            del os.environ['https_proxy']
        if 'HTTPS_PROXY' in os.environ:
            del os.environ['HTTPS_PROXY']

    if config['http_debug']:
        # brute force
        def urllib2_debug_init(self, debuglevel=0):
            self._debuglevel = 1
        AbstractHTTPHandler.__init__ = urllib2_debug_init

    cookie_file = os.path.expanduser(config['cookiejar'])
    global cookiejar
    cookiejar = LWPCookieJar(cookie_file)
    try:
        cookiejar.load(ignore_discard=True)
        if int(round(config_mtime)) > int(os.stat(cookie_file).st_mtime):
            cookiejar.clear()
            cookiejar.save()
    except IOError:
        try:
            fd = os.open(cookie_file, os.O_CREAT | os.O_WRONLY | os.O_TRUNC, 0o600)
            os.close(fd)
        except IOError:
            # hmm is any good reason why we should catch the IOError?
            #print 'Unable to create cookiejar file: \'%s\'. Using RAM-based cookies.' % cookie_file
            cookiejar = CookieJar()


def get_configParser(conffile=None, force_read=False):
    """
    Returns an ConfigParser() object. After its first invocation the
    ConfigParser object is stored in a method attribute and this attribute
    is returned unless you pass force_read=True.
    """
    if not conffile:
        conffile = identify_conf()

    conffile = os.path.expanduser(conffile)
    if 'conffile' not in get_configParser.__dict__:
        get_configParser.conffile = conffile
    if force_read or 'cp' not in get_configParser.__dict__ or conffile != get_configParser.conffile:
        get_configParser.cp = OscConfigParser.OscConfigParser(DEFAULTS)
        get_configParser.cp.read(conffile)
        get_configParser.conffile = conffile
    return get_configParser.cp


def write_config(fname, cp):
    """write new configfile in a safe way"""
    if os.path.exists(fname) and not os.path.isfile(fname):
        # only write to a regular file
        return
    if not os.path.exists(os.path.dirname(fname)):
        os.makedirs(os.path.dirname(fname), mode=0o700)
    with open(fname + '.new', 'w') as f:
        cp.write(f, comments=True)
    try:
        os.rename(fname + '.new', fname)
        os.chmod(fname, 0o600)
    except:
        if os.path.exists(fname + '.new'):
            os.unlink(fname + '.new')
        raise


def config_set_option(section, opt, val=None, delete=False, update=True, creds_mgr_descr=None, **kwargs):
    """
    Sets a config option. If val is not specified the current/default value is
    returned. If val is specified, opt is set to val and the new value is returned.
    If an option was modified get_config is called with **kwargs unless update is set
    to False (override_conffile defaults to config['conffile']).
    If val is not specified and delete is True then the option is removed from the
    config/reset to the default value.
    """
    cp = get_configParser(config['conffile'])
    # don't allow "internal" options
    general_opts = [i for i in DEFAULTS.keys() if not i in ['user', 'pass', 'passx']]
    if section != 'general':
        section = config['apiurl_aliases'].get(section, section)
        scheme, host, path = \
            parse_apisrv_url(config.get('scheme', 'https'), section)
        section = urljoin(scheme, host, path)

    sections = {}
    for url in cp.sections():
        if url == 'general':
            sections[url] = url
        else:
            scheme, host, path = \
                parse_apisrv_url(config.get('scheme', 'https'), url)
            apiurl = urljoin(scheme, host, path)
            sections[apiurl] = url

    section = sections.get(section.rstrip('/'), section)
    if not section in cp.sections():
        raise oscerr.ConfigError('unknown section \'%s\'' % section, config['conffile'])
    if section == 'general' and not opt in general_opts or \
       section != 'general' and not opt in api_host_options:
        raise oscerr.ConfigError('unknown config option \'%s\'' % opt, config['conffile'])
    run = False
    if val:
        if opt == 'pass':
            creds_mgr = _get_credentials_manager(section, cp)
            user = _extract_user_compat(cp, section, creds_mgr)
            old_pw = creds_mgr.get_password(section, user, defer=False)
            try:
                creds_mgr.delete_password(section, user)
                if creds_mgr_descr:
                    creds_mgr_new = creds_mgr_descr.create(cp)
                else:
                    creds_mgr_new = creds_mgr
                creds_mgr_new.set_password(section, user, val)
                write_config(config['conffile'], cp)
                opt = credentials.AbstractCredentialsManager.config_entry
                old_pw = None
            finally:
                if old_pw is not None:
                    creds_mgr.set_password(section, user, old_pw)
                    # not nice, but needed if the Credentials Manager will change
                    # something in cp
                    write_config(config['conffile'], cp)
        else:
            cp.set(section, opt, val)
            write_config(config['conffile'], cp)
        run = True
    elif delete and (cp.has_option(section, opt) or opt == 'pass'):
        if opt == 'pass':
            creds_mgr = _get_credentials_manager(section, cp)
            user = _extract_user_compar(cp, section, creds_mgr)
            creds_mgr.delete_password(section, user)
        else:
            cp.remove_option(section, opt)
        write_config(config['conffile'], cp)
        run = True
    if run and update:
        kw = {'override_conffile': config['conffile'],
              'override_no_keyring': config['use_keyring'],
              'override_no_gnome_keyring': config['gnome_keyring']}
        kw.update(kwargs)
        get_config(**kw)
    if cp.has_option(section, opt):
        return (opt, cp.get(section, opt, raw=True))
    return (opt, None)

def _extract_user_compat(cp, section, creds_mgr):
    """
    This extracts the user either from the ConfigParser or
    the creds_mgr. Only needed for deprecated Gnome Keyring
    """
    user = cp.get(section, 'user')
    if user is None and hasattr(creds_mgr, 'get_user'):
        user = creds_mgr.get_user(section)
    return user

def write_initial_config(conffile, entries, custom_template='', creds_mgr_descriptor=None):
    """
    write osc's intial configuration file. entries is a dict which contains values
    for the config file (e.g. { 'user' : 'username', 'pass' : 'password' } ).
    custom_template is an optional configuration template.
    """
    conf_template = custom_template or new_conf_template
    config = DEFAULTS.copy()
    config.update(entries)
    sio = StringIO(conf_template.strip() % config)
    cp = OscConfigParser.OscConfigParser(DEFAULTS)
    cp.readfp(sio)
    cp.set(config['apiurl'], 'user', config['user'])
    if creds_mgr_descriptor:
        creds_mgr = creds_mgr_descriptor.create(cp)
    else:
        creds_mgr = _get_credentials_manager(config['apiurl'], cp)
    creds_mgr.set_password(config['apiurl'], config['user'], config['pass'])
    write_config(conffile, cp)


def add_section(filename, url, user, passwd, creds_mgr_descriptor=None):
    """
    Add a section to config file for new api url.
    """
    global config
    cp = get_configParser(filename)
    try:
        cp.add_section(url)
    except OscConfigParser.configparser.DuplicateSectionError:
        # Section might have existed, but was empty
        pass
    cp.set(url, 'user', user)
    if creds_mgr_descriptor:
        creds_mgr = creds_mgr_descriptor.create(cp)
    else:
        creds_mgr = _get_credentials_manager(url, cp)
    creds_mgr.set_password(url, user, passwd)
    write_config(filename, cp)


def _get_credentials_manager(url, cp):
    if cp.has_option(url, credentials.AbstractCredentialsManager.config_entry):
        creds_mgr = credentials.create_credentials_manager(url, cp)
        if creds_mgr is None:
            msg = 'Unable to instantiate creds mgr (section: %s)' % url
            conffile = get_configParser.conffile
            raise oscerr.ConfigMissingCredentialsError(msg, conffile, url)
        return creds_mgr
    if config['use_keyring'] and GENERIC_KEYRING:
        return credentials.get_keyring_credentials_manager(cp)
    elif config['gnome_keyring'] and GNOME_KEYRING:
        protocol, host, path = parse_apisrv_url(None, url)
        return credentials.GnomeKeyringCredentialsManager(cp, None)
    elif cp.get(url, 'passx') is not None:
        return credentials.ObfuscatedConfigFileCredentialsManager(cp, None)
    return credentials.PlaintextConfigFileCredentialsManager(cp, None)


class APIHostOptionsEntry(dict):
    def __getitem__(self, key, *args, **kwargs):
        value = super(self.__class__, self).__getitem__(key, *args, **kwargs)
        if key == 'pass' and callable(value):
            value = value()
        return value


def get_config(override_conffile=None,
               override_apiurl=None,
               override_debug=None,
               override_http_debug=None,
               override_http_full_debug=None,
               override_traceback=None,
               override_post_mortem=None,
               override_no_keyring=None,
               override_no_gnome_keyring=None,
               override_verbose=None):
    """do the actual work (see module documentation)"""
    global config

    if not override_conffile:
        conffile = identify_conf()
    else:
        conffile = override_conffile

    conffile = os.path.expanduser(conffile)
    if not os.path.exists(conffile):
        raise oscerr.NoConfigfile(conffile, \
                                  account_not_configured_text % conffile)

    # okay, we made sure that oscrc exists

    # make sure it is not world readable, it may contain a password.
    os.chmod(conffile, 0o600)

    cp = get_configParser(conffile)

    if not cp.has_section('general'):
        # FIXME: it might be sufficient to just assume defaults?
        msg = config_incomplete_text % conffile
        msg += new_conf_template % DEFAULTS
        raise oscerr.ConfigError(msg, conffile)

    config = dict(cp.items('general', raw=1))
    config['conffile'] = conffile

    typed_opts = ((boolean_opts, cp.getboolean), (integer_opts, cp.getint))
    for opts, meth in typed_opts:
        for opt in opts:
            try:
                config[opt] = meth('general', opt)
            except ValueError as e:
                msg = 'cannot parse \'%s\' setting: %s' % (opt, str(e))
                raise oscerr.ConfigError(msg, conffile)

    config['packagecachedir'] = os.path.expanduser(config['packagecachedir'])
    config['exclude_glob'] = config['exclude_glob'].split()

    re_clist = re.compile('[, ]+')
    config['extra-pkgs'] = [i.strip() for i in re_clist.split(config['extra-pkgs'].strip()) if i]

    # collect the usernames, passwords and additional options for each api host
    api_host_options = {}

    # Regexp to split extra http headers into a dictionary
    # the text to be matched looks essentially looks this:
    # "Attribute1: value1, Attribute2: value2, ..."
    # there may be arbitray leading and intermitting whitespace.
    # the following regexp does _not_ support quoted commas within the value.
    http_header_regexp = re.compile(r"\s*(.*?)\s*:\s*(.*?)\s*(?:,\s*|\Z)")

    # override values which we were called with
    # This needs to be done before processing API sections as it might be already used there
    if override_no_keyring:
        config['use_keyring'] = False
    if override_no_gnome_keyring:
        config['gnome_keyring'] = False

    aliases = {}
    for url in [x for x in cp.sections() if x != 'general']:
        # backward compatiblity
        scheme, host, path = parse_apisrv_url(config.get('scheme', 'https'), url)
        apiurl = urljoin(scheme, host, path)
        creds_mgr = _get_credentials_manager(url, cp)
        # if the deprecated gnomekeyring is used we should use the apiurl instead of url
        # (that's what the old code did), but this makes things more complex
        # (also, it is very unlikely that url and apiurl differ)
        user = _extract_user_compat(cp, url, creds_mgr)
        if user is None:
            raise oscerr.ConfigMissingCredentialsError('No user found in section %s' % url, conffile, url)
        password = creds_mgr.get_password(url, user)
        if password is None:
            raise oscerr.ConfigMissingCredentialsError('No password found in section %s' % url, conffile, url)

        if cp.has_option(url, 'http_headers'):
            http_headers = cp.get(url, 'http_headers')
            http_headers = http_header_regexp.findall(http_headers)
        else:
            http_headers = []
        if cp.has_option(url, 'aliases'):
            for i in cp.get(url, 'aliases').split(','):
                key = i.strip()
                if key == '':
                    continue
                if key in aliases:
                    msg = 'duplicate alias entry: \'%s\' is already used for another apiurl' % key
                    raise oscerr.ConfigError(msg, conffile)
                aliases[key] = url

        entry = {'user': user,
                 'pass': password,
                 'http_headers': http_headers}
        api_host_options[apiurl] = APIHostOptionsEntry(entry)

        optional = ('realname', 'email', 'sslcertck', 'cafile', 'capath')
        for key in optional:
            if cp.has_option(url, key):
                if key == 'sslcertck':
                    api_host_options[apiurl][key] = cp.getboolean(url, key)
                else:
                    api_host_options[apiurl][key] = cp.get(url, key)
        if cp.has_option(url, 'build-root', proper=True):
            api_host_options[apiurl]['build-root'] = cp.get(url, 'build-root', raw=True)

        if not 'sslcertck' in api_host_options[apiurl]:
            api_host_options[apiurl]['sslcertck'] = True

        if scheme == 'http':
            api_host_options[apiurl]['sslcertck'] = False

        if cp.has_option(url, 'trusted_prj'):
            api_host_options[apiurl]['trusted_prj'] = cp.get(url, 'trusted_prj').split(' ')
        else:
            api_host_options[apiurl]['trusted_prj'] = []

    # add the auth data we collected to the config dict
    config['api_host_options'] = api_host_options
    config['apiurl_aliases'] = aliases

    apiurl = aliases.get(config['apiurl'], config['apiurl'])
    config['apiurl'] = urljoin(*parse_apisrv_url(None, apiurl))
    # backward compatibility
    if 'apisrv' in config:
        apisrv = config['apisrv'].lstrip('http://')
        apisrv = apisrv.lstrip('https://')
        scheme = config.get('scheme', 'https')
        config['apiurl'] = urljoin(scheme, apisrv)
    if 'apisrc' in config or 'scheme' in config:
        print('Warning: Use of the \'scheme\' or \'apisrv\' in oscrc is deprecated!\n' \
                            'Warning: See README for migration details.', file=sys.stderr)
    if 'build_platform' in config:
        print('Warning: Use of \'build_platform\' config option is deprecated! (use \'build_repository\' instead)', file=sys.stderr)
        config['build_repository'] = config['build_platform']
    if config['plaintext_passwd']:
        print('The \'plaintext_passwd\' option is deprecated and will be ignored', file=sys.stderr)

    config['verbose'] = int(config['verbose'])
    # override values which we were called with
    if override_verbose:
        config['verbose'] = override_verbose + 1

    if override_debug:
        config['debug'] = override_debug
    if override_http_debug:
        config['http_debug'] = override_http_debug
    if override_http_full_debug:
        config['http_debug'] = override_http_full_debug or config['http_debug']
        config['http_full_debug'] = override_http_full_debug
    if override_traceback:
        config['traceback'] = override_traceback
    if override_post_mortem:
        config['post_mortem'] = override_post_mortem
    if override_apiurl:
        apiurl = aliases.get(override_apiurl, override_apiurl)
        # check if apiurl is a valid url
        config['apiurl'] = urljoin(*parse_apisrv_url(None, apiurl))

    # XXX unless config['user'] goes away (and is replaced with a handy function, or
    # config becomes an object, even better), set the global 'user' here as well,
    # provided that there _are_ credentials for the chosen apiurl:
    try:
        config['user'] = get_apiurl_usr(config['apiurl'])
    except oscerr.ConfigMissingApiurl as e:
        e.msg = config_missing_apiurl_text % config['apiurl']
        e.file = conffile
        raise e

    # finally, initialize urllib2 for to use the credentials for Basic Authentication
    init_basicauth(config, os.stat(conffile).st_mtime)

def identify_conf():
    # needed for compat reasons(users may have their oscrc still in ~
    if 'OSC_CONFIG' in os.environ:
        return os.environ.get('OSC_CONFIG')
    if os.path.exists(os.path.expanduser('~/.oscrc')):
        conffile = '~/.oscrc'
    else:
        conffile = os.environ.get('XDG_CONFIG_HOME', '~/.config') + '/osc/oscrc'

    return conffile

def interactive_config_setup(conffile, apiurl, initial=True):
    user = raw_input('Username: ')
    passwd = getpass.getpass()
    creds_mgr_descr = select_credentials_manager_descr()
    if initial:
        config = {'user': user, 'pass': passwd}
        if apiurl:
            config['apiurl'] = apiurl
        write_initial_config(conffile, config, creds_mgr_descriptor=creds_mgr_descr)
    else:
        add_section(conffile, apiurl, user, passwd, creds_mgr_descriptor=creds_mgr_descr)

def select_credentials_manager_descr():
    if not credentials.has_keyring_support():
        print('To use keyrings please install python-keyring.')
    creds_mgr_descriptors = credentials.get_credentials_manager_descriptors()
    for i, creds_mgr_descr in enumerate(creds_mgr_descriptors, 1):
        print('%d) %s (%s)' % (i, creds_mgr_descr.name(), creds_mgr_descr.description()))#
    i = raw_input('Select credentials manager: ')
    if not i.isdigit():
        sys.exit('Invalid selection')
    i = int(i) - 1
    if i < 0 or i >= len(creds_mgr_descriptors):
        sys.exit('Invalid selection')
    return creds_mgr_descriptors[i]

# vim: sw=4 et
