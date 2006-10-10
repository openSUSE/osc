#!/usr/bin/python

# Copyright (C) 2006 Peter Poeml.  All rights reserved.
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

{'apisrv': 'api.opensuse.org',
 'scheme': 'http',
 'user': 'poeml',
 'pass': 'secret',
 'auth_dict': {'api.opensuse.org': {'user': 'poeml', 'pass': 'secret'},
               'apitest.opensuse.org': {'user': 'poeml', 'pass': 'secret'},
               'foo.opensuse.org': {'user': 'foo', 'pass': 'foo'}},
 'build-cmd': '/usr/bin/build',
 'build-root': '/abuild/oscbuild-%(repo)s-%(arch)s',
 'packagecachedir': '/var/cache/osbuild',
 'su-wrapper': 'sudo',
 'urllist': ['http://software.opensuse.org/download/%(project)s/%(repository)s/%(arch)s/%(filename)s',
             'http://api.opensuse.org/rpm/%(project)s/%(repository)s/_repository/%(buildarch)s/%(name)s'],
 }

"""

import ConfigParser

# being global to this module, this dict can be accessed from outside
# it will hold the parsed configuration
config = { }

DEFAULTS = { 'apisrv': 'api.opensuse.org',
             'scheme': 'http',
             'user': 'your_username',
             'pass': 'your_password',
             'packagecachedir': '/var/tmp/osbuild-packagecache',
             'su-wrapper': 'su -c',
             'build-cmd': '/usr/bin/build',
             'build-root': '/var/tmp/build-root',

             # default list of download URLs, which will be tried in order
             'urllist': [
                # the normal repo server, redirecting to mirrors
                'http://software.opensuse.org/download/%(project)s/%(repository)s/%(arch)s/%(filename)s',
                # direct access to "full" tree
                'http://api.opensuse.org/rpm/%(project)s/%(repository)s/_repository/%(buildarch)s/%(name)s',
              ],
}

new_conf_template = """
[general]

# Downloaded packages are cached here. Must be writable by you.
#packagecachedir = %(packagecachedir)s

# Wrapper to call build as root (sudo, su -, ...)
#su-wrapper = %(su-wrapper)s

# rootdir to setup the chroot environment
# can contain %%(repo)s and/or %%(arch)s for replacement
#build-root = %(build-root)s

# use this API server
# (it needs a section [%(apisrv)s] with the credentials)
#apisrv = %(apisrv)s

    
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


def init_basicauth(config):
    """initialize urllib2 with the credentials for Basic Authentication"""
    import urllib2
    from osc.core import __version__

    passmgr = urllib2.HTTPPasswordMgrWithDefaultRealm()
    # this creates a password manager
    passmgr.add_password(None, config['apisrv'], config['user'], config['pass'])
    # because we have put None at the start it will always
    # use this username/password combination for  urls
    # for which `apisrv` is a super-url

    authhandler = urllib2.HTTPBasicAuthHandler(passmgr)
    # create the AuthHandler

    opener = urllib2.build_opener(authhandler)
    opener.addheaders = [('User-agent', 'osc/%s' % __version__)]

    urllib2.install_opener(opener)
    # All calls to urllib2.urlopen will now use our handler
    # Make sure not to include the protocol in with the URL, or
    # HTTPPasswordMgrWithDefaultRealm will be very confused.
    # You must (of course) use it when fetching the page though.



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
            config['user'], account, config['pass'] = \
                    netrc.netrc().authenticators(DEFAULTS['apisrv'])
            print >>sys.stderr, 'Read credentials from %s.' % os.path.expanduser('~/.netrc')
        except (IOError, TypeError, netrc.NetrcParseError):
            #
            # last resort... ask the user
            #
            import getpass
            print >>sys.stderr, account_not_configured_text % conffile
            config['user'] = raw_input('Username: ')
            config['pass'] = getpass.getpass()

        print >>sys.stderr, 'Created osc configuration file %s.\n' % conffile
        fd = open(conffile, 'w')
        os.chmod(conffile, 0600)
        fd.write(new_conf_template % config)
        fd.close()
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

    # holds multiple usernames and passwords
    # it is used by urlgrabber's mirror fetcher
    auth_dict = { } 
    for host in [ x for x in cp.sections() if x != 'general' ]:
        auth_dict[host] = { 'user': cp.get(host, 'user'), 
                            'pass': cp.get(host, 'pass') }

    config = dict(cp.items('general', raw=1))

    # transform 'url1, url2, url3' form into a list
    if type(config['urllist']) == str:
        config['urllist'] = [ i.strip() for i in config['urllist'].split(',') ]

    # add the auth data we collected to the config dict
    config['auth_dict'] = auth_dict

    # for easier access to the api server's credentials, copy them to the "top":
    config['user'] = config['auth_dict'][config['apisrv']]['user']
    config['pass'] = config['auth_dict'][config['apisrv']]['pass']

    # finally, initialize urllib2 for to use the credentials for Basic Authentication
    init_basicauth(config)

