#!/usr/bin/python

# Copyright (C) 2006 Peter Poeml.  All rights reserved.
# This program is free software; it may be used, copied, modified
# and distributed under the terms of the GNU General Public Licence,
# either version 2, or (at your option) any later version.



import os
import sys
import ConfigParser
import cElementTree as ET
from tempfile import NamedTemporaryFile
from osc.fetch import *

APISRV = 'api.opensuse.org'

DEFAULTS = { 'packagecachedir': '/var/tmp/osbuild-packagecache',
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



text_config_incomplete = """

Your configuration is not complete.
Make sure that you have a [general] section in %%s:
(You can copy&paste it. Some commented defaults are shown.)

[general]

# Downloaded packages are cached here. Must be writable by you.
#packagecachedir: %(packagecachedir)s

# Wrapper to call build as root (sudo, su -, ...)
#su-wrapper: %(su-wrapper)s

# rootdir to setup the chroot environment
#build-root: %(build-root)s


Note:
Configuration can be overridden by envvars, e.g. 
OSC_SU_WRAPPER overrides the setting of su-wrapper.
""" % DEFAULTS

change_personality = {
            'i686': 'linux32',
            'i586': 'linux32',
            'ppc': 'powerpc32',
            's390': 's390',
        }

can_also_build = { 
             'x86_64': ['i686', 'i586'],
             'i686': ['i586'],
             'ppc64': ['ppc'],
             's390x': ['s390'],
            }

# real arch of this machine
hostarch = os.uname()[4]
if hostarch == 'i686': # FIXME
    hostarch = 'i586'


class Buildinfo:
    """represent the contents of a buildinfo file"""

    def __init__(self, filename):

        tree = ET.parse(filename)
        root = tree.getroot()

        if root.find('error') != None:
            sys.stderr.write('buildinfo is borken... it says:\n')
            error = root.find('error').text
            sys.stderr.write(error + '\n')
            sys.exit(1)

        # are we building  .rpm or .deb?
        # need the right suffix for downloading
        # if a package named debhelper is in the dependencies, it must be .deb
        self.pacsuffix = 'rpm'
        for node in root.findall('dep'):
            if node.text == 'debhelper':
                self.pacsuffix = 'deb'
                break

        self.buildarch = root.find('arch').text

        self.deps = []
        for node in root.findall('bdep'):
            p = Pac(node.get('name'),
                    node.get('version'),
                    node.get('release'),
                    node.get('project'),
                    node.get('repository'),
                    node.get('arch'),
                    self.buildarch,       # buildarch is used only for the URL to access the full tree...
                    self.pacsuffix)
            self.deps.append(p)

        self.pdeps = []
        for node in root.findall('pdep'):
            self.pdeps.append(node.text)



class Pac:
    """represent a package to be downloaded"""
    def __init__(self, name, version, release, project, repository, arch, buildarch, pacsuffix):

        self.name = name
        self.version = version
        self.release = release
        self.arch = arch
        self.project = project
        self.repository = repository
        self.buildarch = buildarch
        self.pacsuffix = pacsuffix

        # build a map to fill our the URL templates
        self.mp = {}
        self.mp['name'] = self.name
        self.mp['version'] = self.version
        self.mp['release'] = self.release
        self.mp['arch'] = self.arch
        self.mp['project'] = self.project
        self.mp['repository'] = self.repository
        self.mp['buildarch'] = self.buildarch
        self.mp['pacsuffix'] = self.pacsuffix

        self.filename = '%(name)s-%(version)s-%(release)s.%(arch)s.%(pacsuffix)s' % self.mp

        self.mp['filename'] = self.filename


    def makeurls(self, cachedir, urllist):

        self.urllist = []

        # build up local URL
        # by using the urlgrabber with local urls, we basically build up a cache.
        # the cache has no validation, since the package servers don't support etags,
        # or if-modified-since, so the caching is simply name-based (on the assumption
        # that the filename is suitable as identifier)
        self.localdir = '%s/%s/%s/%s' % (cachedir, self.project, self.repository, self.arch)
        self.fullfilename=os.path.join(self.localdir, self.filename)
        self.url_local = 'file://%s/' % self.fullfilename

        # first, add the local URL 
        self.urllist.append(self.url_local)

        # remote URLs
        for url in urllist:
            self.urllist.append(url % self.mp)


    def __str__(self):
        return self.name




def get_build_conf():
    auth_dict = { } # to hold multiple usernames and passwords

    conffile = os.path.expanduser('~/.oscrc')
    if not os.path.exists(conffile):
        import netrc

        try:
            info = netrc.netrc()
            username, account, password = info.authenticators(APISRV)

        except (IOError, TypeError, netrc.NetrcParseError):
            print >>sys.stderr, 'Error:'
            print >>sys.stderr, 'You need to create ~/.oscrc.'
            print >>sys.stderr, 'Running the osc command will do this for you.'
            sys.exit(1)

        cf = open(conffile, 'w')
        os.chmod(conffile, 0600)
        print 'creating', conffile
        cf.write("""

[general]

# Downloaded packages are cached here. Must be writable by you.
#packagecachedir: /var/tmp/osbuild-packagecache

# Wrapper to call build as root (sudo, su -, ...)
#su-wrapper: su -c

# rootdir to setup the chroot environment
#build-root: /var/tmp/build-root


[%s]
user: %s
pass: %s
""" % (APISRV, username, password))
        cf.close()


    config = ConfigParser.ConfigParser(DEFAULTS)
    config.read(conffile)


    if not config.has_section('general'):
        # FIXME: it might be sufficient to just assume defaults?
        print >>sys.stderr, text_config_incomplete % conffile
        sys.exit(1)


    for host in [ x for x in config.sections() if x != 'general' ]:
        auth_dict[host] = dict(config.items(host))


    config = dict(config.items('general', raw=1))

    # make it possible to override configuration of the rc file
    for var in ['OSC_PACKAGECACHEDIR', 'BUILD_ROOT']:
        val = os.getenv(var)
        if val:
            if var.startswith('OSC_'): var = var[4:]
            var = var.lower().replace('_', '-')
            if config.has_key(var):
                print 'Overriding config value for %s=\'%s\' with \'%s\'' % (var, config[var], val)
            config[var] = val

    # transform 'url1, url2, url3' form into a list
    if type(config['urllist']) == str:
        config['urllist'] = [ i.strip() for i in config['urllist'].split(',') ]

    return config, auth_dict


def get_built_files(pacdir, pactype):
    if pactype == 'rpm':
        b_built = os.popen('find %s -name *.rpm' \
                    % os.path.join(pacdir, 'RPMS')).read().strip()
        s_built = os.popen('find %s -name *.rpm' \
                    % os.path.join(pacdir, 'SRPMS')).read().strip()
    else:
        b_built = os.popen('find %s -name *.deb' \
                    % os.path.join(pacdir, 'DEBS')).read().strip()
        s_built = None
    return s_built, b_built


def main(argv):

    global config
    config, auth = get_build_conf()

    repo = argv[1]
    arch = argv[2]
    spec = argv[3]
    buildargs = []
    buildargs += argv[4:]

    if not os.path.exists(spec):
        print >>sys.stderr, 'Error: specfile \'%s\' does not exist.' % spec
        sys.exit(1)


    print 'Getting buildinfo from server'
    bi_file = NamedTemporaryFile(suffix='.xml', prefix='buildinfo.', dir = '/tmp')
    os.system('osc buildinfo %s %s %s > %s' % (repo, arch, spec, bi_file.name))
    bi = Buildinfo(bi_file.name)


    print 'Updating cache of required packages'
    fetcher = Fetcher(cachedir = config['packagecachedir'], 
                      urllist = config['urllist'],
                      auth_dict = auth)
    # now update the package cache
    fetcher.run(bi)


    if bi.pacsuffix == 'rpm':
        """don't know how to verify .deb packages. They are verified on install
        anyway, I assume... verifying package now saves time though, since we don't
        even try to set up the buildroot if it wouldn't work."""

        print 'Verifying integrity of cached packages'
        verify_pacs([ i.fullfilename for i in bi.deps ])


    print 'Writing build configuration'

    buildconf = [ '%s %s\n' % (i.name, i.fullfilename) for i in bi.deps ]

    buildconf.append('preinstall: ' + ' '.join(bi.pdeps) + '\n')

    rpmlist = NamedTemporaryFile(prefix='rpmlist.', dir = '/tmp')
    rpmlist.writelines(buildconf)
    rpmlist.flush()
    os.fsync(rpmlist)



    print 'Getting buildconfig from server'
    bc_file = NamedTemporaryFile(prefix='buildconfig.', dir = '/tmp')
    os.system('osc buildconfig %s %s > %s' % (repo, arch, bc_file.name))


    print 'Running build'

    buildargs = ' '.join(buildargs)

    cmd = '%s --root=%s --rpmlist=%s --dist=%s %s %s' \
                 % (config['build-cmd'],
                    config['build-root'], 
                    rpmlist.name, 
                    bc_file.name, 
                    spec, 
                    buildargs)

    if config['su-wrapper'].startswith('su '):
        tmpl = '%s \'%s\''
    else:
        tmpl = '%s %s'
    cmd = tmpl % (config['su-wrapper'], cmd)
        
    # real arch of this machine 
    # vs.
    # arch we are supposed to build for
    if hostarch != bi.buildarch:

        # change personality, if needed
        if bi.buildarch in can_also_build.get(hostarch, []):
            cmd = change_personality[bi.buildarch] + ' ' + cmd


    print cmd
    os.system(cmd)

    pacdirlink = os.path.join(config['build-root'], '.build.packages')
    if os.path.exists(pacdirlink):
        pacdirlink = os.readlink(pacdirlink)
        pacdir = os.path.join(config['build-root'] + pacdirlink)

        if os.path.exists(pacdir):
            (s_built, b_built) = get_built_files(pacdir, bi.pacsuffix)

            print
            #print 'built source packages:'
            if s_built: print s_built
            #print 'built binary packages:'
            print b_built


