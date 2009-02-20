#!/usr/bin/python

# Copyright (C) 2006 Peter Poeml / Novell Inc.  All rights reserved.
# This program is free software; it may be used, copied, modified
# and distributed under the terms of the GNU General Public Licence,
# either version 2, or (at your option) any later version.

"""Read osc configuration and store it in a dictionary

This module reads and parses ~/.oscrc. The resulting configuration is stored
for later usage in a dictionary named 'config'. 

In the absence of .oscrc, it tries .netrc.
If information is missing, it asks the user questions.

After reading the config, urllib2 is initialized.

The configuration dictionary could look like this:

{'apisrv': 'https://api.opensuse.org/',
 'user': 'poeml',
 'api_host_options': {'api.opensuse.org': {'user': 'poeml', 'pass': 'secret'},
                      'apitest.opensuse.org': {'user': 'poeml', 'pass': 'secret',
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

# being global to this module, this dict can be accessed from outside
# it will hold the parsed configuration
config = { }

DEFAULTS = { 'apisrv': 'https://api.opensuse.org/',
             'scheme': 'https',
             'user': 'your_username',
             'pass': 'your_password',
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
             'cookiejar': '~/.osc_cookiejar',
             # disable project tracking by default
             'do_package_tracking': '0',
             # default for osc build
             'extra-pkgs': 'vim gdb strace',
             # default platform
             'build_platform': 'openSUSE_Factory',
}
boolean_opts = ['debug', 'do_package_tracking', 'http_debug', 'post_mortem', 'traceback']

new_conf_template = """
[general]

# URL to access API server, e.g. %(apisrv)s
# you also need a section [%(apisrv)s] with the credentials
#apisrv = %(apisrv)s

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
#build_platform = openSUSE_Factory

# show info useful for debugging 
#debug = 1
    
# show HTTP traffic useful for debugging 
#http_debug = 1
    
# jump into the debugger in case of errors
#post_mortem = 1
    
# print call traces in case of errors
#traceback = 1
    
[%(apisrv)s]
user = %(user)s
pass = %(pass)s
# additional headers to pass to a request, e.g. for special authentication
#http_headers = Host: foofoobar,
#       User: mumblegack
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
    else:
        return scheme, apisrv

def get_apiurl_api_host_options(apiurl):
    """
    Returns all apihost specific options for the given apiurl, None if
    no such specific optiosn exist.
    """
    # FIXME: in A Better World (tm) there was a config object which
    # knows this instead of having to extract it from a url where it
    # had been mingled into before.  But this works fine for now.
    scheme, apisrv = parse_apisrv_url(None, apiurl)
    return config['api_host_options'][apisrv]

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


def get_config(override_conffile = None, 
               override_apisrv = None,
               override_debug = None, 
               override_http_debug = None, 
               override_traceback = None,
               override_post_mortem = None):
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

    cp = get_configParser(conffile)

    if not cp.has_section('general'):
        # FIXME: it might be sufficient to just assume defaults?
        msg = config_incomplete_text % conffile
        msg += new_conf_template % DEFAULTS
        raise oscerr.ConfigError(msg, conffile)

    config = dict(cp.items('general', raw=1))

    config['scheme'], config['apisrv'] = \
        parse_apisrv_url(config['scheme'], config['apisrv'])

    for i in boolean_opts:
        try:
            config[i] = cp.getboolean('general', i)
        except ValueError, e:
            raise oscerr.ConfigError('cannot parse \'%s\' setting: ' % i + str(e), conffile)

    config['packagecachedir'] = os.path.expanduser(config['packagecachedir'])

    re_clist = re.compile('[, ]+')
    config['extra-pkgs'] = [ i.strip() for i in re_clist.split(config['extra-pkgs'].strip()) if i ]
    if config['extra-pkgs'] == []: 
        config['extra-pkgs'] = None

    # collect the usernames, passwords and additional options for each api host
    api_host_options = { }

    # Regexp to split extra http headers into a dictionary
    # the text to be matched looks essentially looks this:
    # "Attribute1: value1, Attribute2: value2, ..."
    # there may be arbitray leading and intermitting whitespace.
    # the following regexp does _not_ support quoted commas within the value.
    http_header_regexp = re.compile(r"\s*(.*?)\s*:\s*(.*?)\s*(?:,\s*|\Z)")

    for url in [ x for x in cp.sections() if x != 'general' ]:
        dummy, host = \
            parse_apisrv_url(config['scheme'], url)
        #FIXME: this could actually be the ideal spot to take defaults
        #from the general section.
        user         = cp.get(url, 'user')
        password     = cp.get(url, 'pass')

        if cp.has_option(url, 'http_headers'):
            http_headers = cp.get(url, 'http_headers')
            http_headers = http_header_regexp.findall(http_headers)
        else:
            http_headers = []

        api_host_options[host] = { 'user': user,
                                   'pass': password,
                                   'http_headers': http_headers};

    # add the auth data we collected to the config dict
    config['api_host_options'] = api_host_options

    # override values which we were called with
    if override_debug: 
        config['debug'] = override_debug
    if override_http_debug: 
        config['http_debug'] = override_http_debug
    if override_traceback:
        config['traceback'] = override_traceback
    if override_post_mortem:
        config['post_mortem'] = override_post_mortem
    if override_apisrv:
        config['scheme'], config['apisrv'] = \
            parse_apisrv_url(config['scheme'], override_apisrv)

    # to make the mess complete, set up the more convenient api url which we'll rather use
    config['apiurl'] = config['scheme'] + '://' + config['apisrv']

    # XXX unless config['user'] goes away (and is replaced with a handy function, or 
    # config becomes an object, even better), set the global 'user' here as well,
    # provided that there _are_ credentials for the chosen apisrv:
    if config['apisrv'] in config['api_host_options'].keys():
        config['user'] = config['api_host_options'][config['apisrv']]['user']
    else:
        raise oscerr.ConfigMissingApiurl(config_missing_apiurl_text % config['apisrv'],
                                         conffile, config['apiurl'])

    # finally, initialize urllib2 for to use the credentials for Basic Authentication
    init_basicauth(config)

