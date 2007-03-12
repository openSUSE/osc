#!/usr/bin/python

# Copyright (C) 2006 Peter Poeml / Novell Inc.  All rights reserved.
# This program is free software; it may be used, copied, modified
# and distributed under the terms of the GNU General Public Licence,
# either version 2, or (at your option) any later version.



import os
import sys
from tempfile import NamedTemporaryFile
from osc.fetch import *
import osc.conf
try:
    from xml.etree import cElementTree as ET
except ImportError:
    import cElementTree as ET


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

        print filename
        try:
            tree = ET.parse(filename)
        except:
            print 'could not parse the buildconfig:'
            print open(filename).read()
            sys.exit(1)

        root = tree.getroot()

        if root.find('error') != None:
            sys.stderr.write('buildinfo is broken... it says:\n')
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

    from conf import config

    repo = argv[1]
    arch = argv[2]
    spec = argv[3]
    buildargs = []
    buildargs += argv[4:]

    # make it possible to override configuration of the rc file
    for var in ['OSC_PACKAGECACHEDIR', 'OSC_SU_WRAPPER', 'BUILD_ROOT', 'OSC_BUILD_ROOT']: 
        val = os.getenv(var)
        if val:
            if var.startswith('OSC_'): var = var[4:]
            var = var.lower().replace('_', '-')
            if config.has_key(var):
                print 'Overriding config value for %s=\'%s\' with \'%s\'' % (var, config[var], val)
            config[var] = val


    config['build-root'] = config['build-root'] % {'repo': repo, 'arch': arch}

    if not os.path.exists(spec):
        sys.exit('Error: specfile \'%s\' does not exist.' % spec)

    print 'Getting buildinfo from server'
    bi_file = NamedTemporaryFile(suffix='.xml', prefix='buildinfo.', dir = '/tmp')
    rc = os.system('osc buildinfo %s %s %s > %s' % (repo, arch, spec, bi_file.name))
    if rc:
        print >>sys.stderr, 'wrong repo/arch?'
        sys.exit(rc)
    bi = Buildinfo(bi_file.name)


    print 'Updating cache of required packages'
    fetcher = Fetcher(cachedir = config['packagecachedir'], 
                      urllist = config['urllist'],
                      auth_dict = config['auth_dict'])
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
    rc = os.system('osc buildconfig %s %s > %s' % (repo, arch, bc_file.name))
    if rc: sys.exit(rc)


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
    rc = os.system(cmd)
    if rc: sys.exit(rc)

    pacdirlink = os.path.join(config['build-root'], '.build.packages')
    if os.path.exists(pacdirlink):
        pacdirlink = os.readlink(pacdirlink)
        pacdir = os.path.join(config['build-root'], pacdirlink)

        if os.path.exists(pacdir):
            (s_built, b_built) = get_built_files(pacdir, bi.pacsuffix)

            print
            #print 'built source packages:'
            if s_built: print s_built
            #print 'built binary packages:'
            print b_built


