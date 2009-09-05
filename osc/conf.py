# Copyright (C) 2006-2009 Novell Inc.  All rights reserved.
# This program is free software; it may be used, copied, modified
# and distributed under the terms of the GNU General Public Licence,
# either version 2, or version 3 (at your option).

"""Read osc configuration and store it in a dictionary

This module reads and parses ~/.oscrc. The resulting configuration is stored
for later usage in a dictionary named 'config'. 
The .oscrc is kept mode 0600, so that it is not publically readable.
This gives no real security for storing passwords. 
If in doubt, use your favourite keyring.
Password is stored on ~/.oscrc as bz2 compressed and base64 encoded, so that is fairly 
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
import OscConfigParser
from osc import oscerr

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
	    if os.environ['GNOME_DESKTOP_SESSION_ID']:
	       # otherwise gnome keyring bindings spit out errors, when you have
	       # it installed, but you are not under gnome
	       # (even though hundreds of gnome-keyring daemons got started in parallel)
	       # another option would be to support kwallet here
	       GNOME_KEYRING = gnomekeyring.is_available()
	except:
            pass

DEFAULTS = { 'apiurl': 'https://api.opensuse.org',
             'user': 'your_username',
             'pass': 'your_password',
             'passx': '',
             'packagecachedir': '/var/tmp/osbuild-packagecache',
             'su-wrapper': 'su -c',

             # build type settings
             'build-cmd': '/usr/bin/build',
             'build-type' : '', # may be empty for chroot, kvm or xen
             'build-root': '/var/tmp/build-root',
             'build-device': '', # required for VM builds
             'build-memory' : '',# required for VM builds
             'build-swap' : '',  # optional for VM builds

             'debug': '0',
             'http_debug': '0',
             'traceback': '0',
             'post_mortem': '0',
             'use_keyring': '1',
             'gnome_keyring': '1',
             'cookiejar': '~/.osc_cookiejar',
             # enable project tracking by default
             'do_package_tracking': '1',
             # default for osc build
             'extra-pkgs': 'vim gdb strace',
             # default platform
             'build_platform': 'openSUSE_Factory',
             # default project for branch or bco
             'getpac_default_project': 'openSUSE:Factory',
             # alternate filesystem layout: have multiple subdirs, where colons were.
             'checkout_no_colon': '0',
             # local files to ignore with status, addremove, ....
             # local files to ignore with status, addremove, ....
             'exclude_glob': '.osc CVS .svn .* _linkerror *~ #*# *.orig *.bak',
             # keep passwords in plaintext. If you see this comment, your osc 
             # already uses the encrypted password, and only keeps them in plain text
             # for backwards compatibility. Default will change to 0 in future releases.
             'plaintext_passwd': '1',
             # limit the age of requests shown with 'osc req list'.
             # this is a default only, can be overridden by 'osc req list -D NNN'
             # Use 0 for unlimted.
             'request_list_days': 30,
             # check for unversioned/removed files before commit
             'check_filelist': '1',
}

# being global to this module, this dict can be accessed from outside
# it will hold the parsed configuration
config = DEFAULTS.copy()

boolean_opts = ['debug', 'do_package_tracking', 'http_debug', 'post_mortem', 'traceback', 'check_filelist', 'plaintext_passwd',
    'checkout_no_colon']

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
# can contain %%(repo)s, %%(arch)s, %%(project)s and %%(package)s for replacement, e.g.
# /srv/oscbuild/%%(repo)s-%%(arch)s or
# /srv/oscbuild/%%(repo)s-%%(arch)s-%%(project)s-%%(package)s
#build-root = %(build-root)s

# extra packages to install when building packages locally (osc build)
# this corresponds to osc build's -x option and can be overridden with that
# -x '' can also be given on the command line to override this setting, or
# you can have an empty setting here.
#extra-pkgs = vim gdb strace

# build platform is used if the platform argument is omitted to osc build
#build_platform = %(build_platform)s

# default project for getpac or bco
#getpac_default_project = %(getpac_default_project)s

# alternate filesystem layout: have multiple subdirs, where colons were.
#checkout_no_colon = %(checkout_no_colon)s

# local files to ignore with status, addremove, ....
#exclude_glob = %(exclude_glob)s

# keep passwords in plaintext. If you see this comment, your osc
# already uses the encrypted password, and only keeps them in plain text
# for backwards compatibility. Default will change to 0 in future releases.
# You can remove the plaintext password without harm, if you do not need
# backwards compatibility.
#plaintext_passwd = %(plaintext_passwd)s

# limit the age of requests shown with 'osc req list'.
# this is a default only, can be overridden by 'osc req list -D NNN'
# Use 0 for unlimted.
#request_list_days = %(request_list_days)s

# show info useful for debugging
#debug = 1

# show HTTP traffic useful for debugging
#http_debug = 1

# jump into the debugger in case of errors
#post_mortem = 1

# print call traces in case of errors
#traceback = 1

# use KDE/Gnome/MacOS/Windows keyring for credentials if available
#use_keyring = 1

# check for unversioned/removed files before commit
#check_filelist = 1
   
[%(apiurl)s]
user = %(user)s
pass = %(pass)s
passx = %(passx)s
# set aliases for this apiurl
# aliases = foo, bar
# email used in .changes, unless the one from osc meta prj <user> will be used
# email =
# additional headers to pass to a request, e.g. for special authentication
#http_headers = Host: foofoobar,
#       User: mumblegack
# Force using of keyring for this API
#keyring = 1
"""


account_not_configured_text ="""
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
    import urlparse
    if apisrv.startswith('http://') or apisrv.startswith('https://'):
        return urlparse.urlsplit(apisrv)[0:2]
    elif scheme != None:
        # the split/join is needed to get a proper url (e.g. without a trailing slash)
        return urlparse.urlsplit(urljoin(scheme, apisrv))[0:2]
    else:
        from urllib2 import URLError
        msg = 'invalid apiurl \'%s\' (specify the protocol (http:// or https://))' % apisrv
        raise URLError(msg)

def urljoin(scheme, apisrv):
    return '://'.join([scheme, apisrv])

def get_apiurl_api_host_options(apiurl):
    """
    Returns all apihost specific options for the given apiurl, None if
    no such specific optiosn exist.
    """
    # FIXME: in A Better World (tm) there was a config object which
    # knows this instead of having to extract it from a url where it
    # had been mingled into before.  But this works fine for now.

    apiurl = urljoin(*parse_apisrv_url(None, apiurl))
    try:
        return config['api_host_options'][apiurl]
    except KeyError:
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

    import sys
    try:
        return get_apiurl_api_host_options(apiurl)['user']
    except KeyError:
        print >>sys.stderr, 'no specific section found in config file for host of [\'%s\'] - using default user: \'%s\'' \
            % (apiurl, config['user'])
        return config['user']

def init_basicauth(config):
    """initialize urllib2 with the credentials for Basic Authentication"""

    from osc.core import __version__
    import os, urllib2
    import cookielib

    global cookiejar

    # HTTPS proxy is not supported by urllib2. It only leads to an error
    # or, at best, a warning.
    # https://bugzilla.novell.com/show_bug.cgi?id=214983
    # https://bugzilla.novell.com/show_bug.cgi?id=298378
    if 'https_proxy' in os.environ:
        del os.environ['https_proxy']
    if 'HTTPS_PROXY' in os.environ:
        del os.environ['HTTPS_PROXY']

    if config['http_debug']:
        # brute force
        def urllib2_debug_init(self, debuglevel=0):
            self._debuglevel = 1
        urllib2.AbstractHTTPHandler.__init__ = urllib2_debug_init

    authhandler = urllib2.HTTPBasicAuthHandler( \
        urllib2.HTTPPasswordMgrWithDefaultRealm())

    cookie_file = os.path.expanduser(config['cookiejar'])
    cookiejar = cookielib.LWPCookieJar(cookie_file)
    try: 
        cookiejar.load(ignore_discard=True)
    except IOError:
        try:
            open(cookie_file, 'w').close()
            os.chmod(cookie_file, 0600)
        except:
            #print 'Unable to create cookiejar file: \'%s\'. Using RAM-based cookies.' % cookie_file
            cookiejar = cookielib.CookieJar()

    opener = urllib2.build_opener(urllib2.HTTPCookieProcessor(cookiejar), authhandler)
    urllib2.install_opener(opener)

    opener.addheaders = [('User-agent', 'osc/%s' % __version__)]

    # with None as first argument, it will always use this username/password
    # combination for urls for which arg2 (apisrv) is a super-url
    for host, auth in config['api_host_options'].iteritems():
        authhandler.add_password(None, host, auth['user'], auth['pass'])


def get_configParser(conffile=None, force_read=False):
    """
    Returns an ConfigParser() object. After its first invocation the
    ConfigParser object is stored in a method attribute and this attribute
    is returned unless you pass force_read=True.
    """
    import os
    conffile = conffile or os.environ.get('OSC_CONFIG', '~/.oscrc')
    conffile = os.path.expanduser(conffile)
    if force_read or not get_configParser.__dict__.has_key('cp'):
        get_configParser.cp = OscConfigParser.OscConfigParser(DEFAULTS)
        get_configParser.cp.read(conffile)
    return get_configParser.cp


def write_initial_config(conffile, entries, custom_template = ''):
    """
    write osc's intial configuration file. entries is a dict which contains values
    for the config file (e.g. { 'user' : 'username', 'pass' : 'password' } ).
    custom_template is an optional configuration template.
    """
    import os, StringIO, sys
    conf_template = custom_template or new_conf_template
    config = DEFAULTS.copy()
    config.update(entries)
    config['passx'] = config['pass'].encode('bz2').encode('base64')
    if config['use_keyring'] and GENERIC_KEYRING:
        protocol, host = \
            parse_apisrv_url(None, config['apiurl'])
        keyring.set_password(host, config['user'], config['pass'])
        config['pass'] = ''
        config['passx'] = ''
    elif config['gnome_keyring'] and GNOME_KEYRING:
        protocol, host = \
            parse_apisrv_url(None, config['apiurl'])
        gnomekeyring.set_network_password_sync(
            user = config['user'],
            password = config['pass'],
            protocol = protocol,
            server = host)
        config['user'] = ''
        config['pass'] = ''
        config['passx'] = ''
    if not config['plaintext_passwd']:
        config['pass'] = ''
    sio = StringIO.StringIO(conf_template.strip() % config)
    cp = OscConfigParser.OscConfigParser(DEFAULTS)
    cp.readfp(sio)

    file = None
    try:
        file = open(conffile, 'w')
    except IOError, e:
        raise oscerr.OscIOError(e, 'cannot open configfile \'%s\'' % conffile)
    try:
        try:
            os.chmod(conffile, 0600)
            cp.write(file, True)
        except IOError, e:
            raise oscerr.OscIOError(e, 'cannot write configfile \'s\'' % conffile)
    finally:
        if file: file.close()

def add_section(filename, url, user, passwd):
    """
    Add a section to config file for new api url.
    """
    global config
    cp = get_configParser(filename)
    try:
        cp.add_section(url)
    except OscConfigParser.ConfigParser.DuplicateSectionError:
        # Section might have existed, but was empty
        pass
    if config['use_keyring'] and GENERIC_KEYRING:
        protocol, host = \
            parse_apisrv_url(None, url)
        keyring.set_password(host, user, passwd)
        cp.set(url, 'keyring', '1')
        cp.set(url, 'user', user)
        cp.remove_option(url, 'pass')
        cp.remove_option(url, 'passx')
    elif config['gnome_keyring'] and GNOME_KEYRING:
        protocol, host = \
            parse_apisrv_url(None, url)
        gnomekeyring.set_network_password_sync(
            user = user,
            password = passwd,
            protocol = protocol,
            server = host)
        cp.set(url, 'keyring', '1')
        cp.remove_option(url, 'pass')
        cp.remove_option(url, 'passx')
    else:
        cp.set(url, 'user', user)
        if not config['plaintext_passwd']:
            cp.remove_option(url, 'pass')
        cp.set(url, 'passx', passwd.encode('bz2').encode('base64'))
    file = open(filename, 'w')
    cp.write(file, True)
    if file: file.close()


def get_config(override_conffile = None, 
               override_apiurl = None,
               override_debug = None, 
               override_http_debug = None, 
               override_traceback = None,
               override_post_mortem = None,
               override_no_keyring = None,
               override_no_gnome_keyring = None,
               override_verbose = None):
    """do the actual work (see module documentation)"""
    import os
    import sys
    import re
    global config

    conffile = override_conffile or os.environ.get('OSC_CONFIG', '~/.oscrc')
    conffile = os.path.expanduser(conffile)

    if not os.path.exists(conffile):
        raise oscerr.NoConfigfile(conffile, \
                                  account_not_configured_text % conffile)

    # okay, we made sure that .oscrc exists

    # make sure it is not world readable, it may contain a password.
    os.chmod(conffile, 0600)

    cp = get_configParser(conffile)

    if not cp.has_section('general'):
        # FIXME: it might be sufficient to just assume defaults?
        msg = config_incomplete_text % conffile
        msg += new_conf_template % DEFAULTS
        raise oscerr.ConfigError(msg, conffile)

    config = dict(cp.items('general', raw=1))
    config['apiurl'] = urljoin(*parse_apisrv_url(None, config['apiurl']))

    # backward compatibility
    if config.has_key('apisrv'):
        apisrv = config['apisrv'].lstrip('http://')
        apisrv = apisrv.lstrip('https://')
        scheme = config.get('scheme', 'https')
        config['apiurl'] = urljoin(scheme, apisrv)
    if config.has_key('apisrv') or config.has_key('scheme'):
        print >>sys.stderr, 'Warning: Use of the \'scheme\' or \'apisrv\' in ~/.oscrc is deprecated!\n' \
                            'Warning: See README for migration details.'

    for i in boolean_opts:
        try:
            config[i] = cp.getboolean('general', i)
        except ValueError, e:
            raise oscerr.ConfigError('cannot parse \'%s\' setting: ' % i + str(e), conffile)

    config['packagecachedir'] = os.path.expanduser(config['packagecachedir'])
    config['exclude_glob'] = config['exclude_glob'].split()

    re_clist = re.compile('[, ]+')
    config['extra-pkgs'] = [ i.strip() for i in re_clist.split(config['extra-pkgs'].strip()) if i ]
    if config['extra-pkgs'] == []: 
        config['extra-pkgs'] = None

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
    for url in [ x for x in cp.sections() if x != 'general' ]:
        # backward compatiblity
        scheme, host = \
            parse_apisrv_url(config.get('scheme', 'https'), url)
        apiurl = urljoin(scheme, host)
        user = cp.get( url, 'user' )
        if config['use_keyring'] and GENERIC_KEYRING:
            try:
                # Read from keyring lib if available
                password = keyring.get_password(host, user)
            except:
                # Fallback to file based auth.
                pass
        elif config['gnome_keyring'] and GNOME_KEYRING:
            # Read from gnome keyring if available
            try:
                gk_data = gnomekeyring.find_network_password_sync(
                    protocol = scheme,
                    server = host)
                password = gk_data[0]['password']
                user = gk_data[0]['user']
            except gnomekeyring.NoMatchError:
                # Fallback to file based auth.
                pass
        # Read credentials from config
        if user is None:
            #FIXME: this could actually be the ideal spot to take defaults
            #from the general section.
            user         = cp.get(url, 'user', raw=True) # need to set raw to prevent '%' expansion
            password     = cp.get(url, 'pass', raw=True) # especially on password!
            passwordx    = cp.get(url, 'passx', raw=True) # especially on password!
            if password is None or password == 'your_password':
                try:
                    password = passwordx.decode('base64').decode('bz2');
                except:
                     print "%s: no credentials known" % url
                     password = 'your_password'
            else:
                if not passwordx:
                    print "%s: rewriting from plain pass to encoded pass\n" % url
                    add_section(conffile, url, user, password)
            if cp.has_option(url, 'keyring') and cp.get(url, 'keyring'):
                # This APIURL was configured to use keyring by
                continue
        email        = ''
        if cp.has_option(url, 'email'):
            email    = cp.get(url, 'email')

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
                if aliases.has_key(key):
                    msg = 'duplicate alias entry: \'%s\' is already used for another apiurl' % key
                    raise oscerr.ConfigError(msg, conffile)
                aliases[key] = url

        api_host_options[apiurl] = { 'user': user,
                                     'pass': password,
                                     'http_headers': http_headers}
        if email:
            api_host_options[apiurl]['email'] = email

    # add the auth data we collected to the config dict
    config['api_host_options'] = api_host_options

    # override values which we were called with
    if override_verbose:
        config['verbose'] = override_verbose + 1
    if not config.has_key('verbose') : config['verbose'] = 1;

    if override_debug:
        config['debug'] = override_debug
    if override_http_debug:
        config['http_debug'] = override_http_debug
    if override_traceback:
        config['traceback'] = override_traceback
    if override_post_mortem:
        config['post_mortem'] = override_post_mortem
    if override_apiurl:
        apiurl = aliases.get(override_apiurl, override_apiurl)
        # check if apiurl is a valid url
        parse_apisrv_url(None, apiurl)
        config['apiurl'] = apiurl

    # XXX unless config['user'] goes away (and is replaced with a handy function, or
    # config becomes an object, even better), set the global 'user' here as well,
    # provided that there _are_ credentials for the chosen apiurl:
    try:
        config['user'] = get_apiurl_usr(config['apiurl'])
    except oscerr.ConfigMissingApiurl, e:
        e.msg = config_missing_apiurl_text % config['apiurl']
        e.file = conffile
        raise e

    # finally, initialize urllib2 for to use the credentials for Basic Authentication
    init_basicauth(config)

