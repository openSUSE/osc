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
 'auth_dict': {'api.opensuse.org': {'user': 'poeml', 'pass': 'secret'},
               'apitest.opensuse.org': {'user': 'poeml', 'pass': 'secret'},
               'foo.opensuse.org': {'user': 'foo', 'pass': 'foo'}},
 'build-cmd': '/usr/bin/build',
 'build-root': '/abuild/oscbuild-%(repo)s-%(arch)s',
 'packagecachedir': '/var/cache/osbuild',
 'su-wrapper': 'sudo',
 'urllist': ['http://download.opensuse.org/repositories/%(project)s/%(repository)s/%(arch)s/%(filename)s',
             'http://api.opensuse.org/rpm/%(project)s/%(repository)s/_repository/%(buildarch)s/%(name)s'],
 }

"""

import ConfigParser

# being global to this module, this dict can be accessed from outside
# it will hold the parsed configuration
config = { }

DEFAULTS = { 'apisrv': 'https://api.opensuse.org/',
             'scheme': 'https',
             'user': 'your_username',
             'packagecachedir': '/var/tmp/osbuild-packagecache',
             'su-wrapper': 'su -c',
             'build-cmd': '/usr/bin/build',
             'build-root': '/var/tmp/build-root',

             # default list of download URLs, which will be tried in order
             'urllist': [
                # the normal repo server, redirecting to mirrors
                'http://download.opensuse.org/repositories/%(project)s/%(repository)s/%(arch)s/%(filename)s',
                # direct access to "full" tree
                '%(scheme)s://%(apisrv)s/build/%(project)s/%(repository)s/%(buildarch)s/_repository/%(name)s',
              ],

             'http_debug': '0',
             'cookiejar': '~/.osc_cookiejar',
}
boolean_opts = ['http_debug']

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
# can contain %%(repo)s and/or %%(arch)s for replacement, e.g.
# /srv/oscbuild/%%(repo)s-%%(arch)s
#build-root = %(build-root)s

# show HTTP traffic useful for debugging 
#http_debug = 1
    
[%(apisrv)s]
user = %(user)s
pass = %(pass)s
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

cookiejar = None

def parse_apisrv_url(scheme, apisrv):
    import urlparse
    if apisrv.startswith('http://') or apisrv.startswith('https://'):
        return urlparse.urlsplit(apisrv)[0:2]
    else:
        return scheme, apisrv

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
    for host, auth in config['auth_dict'].iteritems():
        authhandler.add_password(None, host, auth['user'], auth['pass'])


def get_config():
    """do the actual work (see module documentation)"""
    import os
    import sys
    global config

    conffile = os.path.expanduser('~/.oscrc')

    if not os.path.exists(conffile):

        # okay, let's create a fresh config file
        # if credentials are found in .netrc, use those
        # otherwise ask

        config = DEFAULTS.copy()

        # try .netrc
        # the needed entry needs to look like this:
        # machine api.opensuse.org login your_login password your_pass
        # note that it is not suited for credentials containing spaces
        import netrc
        try:
            # XXX: apisrv is a URL now, thus requiring the "scheme" setting if https is to be used
            netrc_host = parse_apisrv_url(None, DEFAULTS['apisrv'])[1]
            config['user'], account, config['pass'] = \
                    netrc.netrc().authenticators(netrc_host)
            print >>sys.stderr, 'Read credentials from %s.' % os.path.expanduser('~/.netrc')
        except (IOError, TypeError, netrc.NetrcParseError):
            #
            # last resort... ask the user
            #
            import getpass
            print >>sys.stderr, account_not_configured_text % conffile
            config['user'] = raw_input('Username: ')
            config['pass'] = getpass.getpass()

        print >>sys.stderr, 'Creating osc configuration file %s ...' % conffile
        fd = open(conffile, 'w')
        os.chmod(conffile, 0600)
        fd.write(new_conf_template % config)
        fd.close()
        print >>sys.stderr, 'done.'
        #print >>sys.stderr, ('Now re-run the command.')
        #sys.exit(0)


    # okay, we made sure that .oscrc exists

    cp = ConfigParser.SafeConfigParser(DEFAULTS)
    cp.read(conffile)

    if not cp.has_section('general'):
        # FIXME: it might be sufficient to just assume defaults?
        print >>sys.stderr, config_incomplete_text % conffile
        print >>sys.stderr, new_conf_template % DEFAULTS
        sys.exit(1)

    config = dict(cp.items('general', raw=1))

    config['scheme'], config['apisrv'] = \
        parse_apisrv_url(config['scheme'], config['apisrv'])

    for i in boolean_opts:
        try:
            if int(config.get(i)):
                config[i] = True
            else:
                config[i] = False
        except:
            sys.exit('option %s requires an integer value' % i)

    packagecachedir = os.path.expanduser(config['packagecachedir'])

    # transform 'url1, url2, url3' form into a list
    if type(config['urllist']) == str:
        config['urllist'] = [ i.strip() for i in config['urllist'].split(',') ]

    # holds multiple usernames and passwords
    auth_dict = { } 
    for url in [ x for x in cp.sections() if x != 'general' ]:
        dummy, host = \
            parse_apisrv_url(config['scheme'], url)
        auth_dict[host] = { 'user': cp.get(url, 'user'), 
                            'pass': cp.get(url, 'pass') }

    # add the auth data we collected to the config dict
    config['auth_dict'] = auth_dict

