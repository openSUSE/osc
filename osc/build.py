# Copyright (C) 2006 Novell Inc.  All rights reserved.
# This program is free software; it may be used, copied, modified
# and distributed under the terms of the GNU General Public Licence,
# either version 2, or (at your option) any later version.



import os
import re
import sys
from tempfile import NamedTemporaryFile
from shutil import rmtree
from osc.fetch import *
from osc.core import get_buildinfo, store_read_apiurl, store_read_project, store_read_package, meta_exists, quote_plus, get_buildconfig
import osc.conf
import oscerr
import subprocess
try:
    from xml.etree import cElementTree as ET
except ImportError:
    import cElementTree as ET

from conf import config, cookiejar

change_personality = {
            'i686':  'linux32',
            'i586':  'linux32',
            'i386':  'linux32',
            'ppc':   'powerpc32',
            's390':  's390',
        }

can_also_build = {
             'armv4l': [                                         'armv4l'                                 ],
             'armv5el':[                                         'armv4l', 'armv5el'                      ],
             'armv6l' :[                                         'armv4l', 'armv5el'                      ],
             'armv7el':[                                         'armv4l', 'armv5el', 'armv7el'           ],
             'armv7l' :[                                         'armv4l', 'armv5el', 'armv7el'           ],
             's390x':  ['s390'                                                                            ],
             'ppc64':  [                        'ppc', 'ppc64',                                           ],
             'i386':   [        'i586',                          'armv4l', 'armv5el', 'armv7el',    'sh4' ],
             'i586':   [                'i386',                  'armv4l', 'armv5el', 'armv7el',    'sh4' ],
             'i686':   [        'i586',                          'armv4l', 'armv5el', 'armv7el',    'sh4' ],
             'x86_64': ['i686', 'i586', 'i386',                  'armv4l', 'armv5el', 'armv7el',    'sh4' ],
             }

# real arch of this machine
hostarch = os.uname()[4]
if hostarch == 'i686': # FIXME
    hostarch = 'i586'


class Buildinfo:
    """represent the contents of a buildinfo file"""

    def __init__(self, filename, apiurl, buildtype = 'spec', localpkgs = []):
        try:
            tree = ET.parse(filename)
        except:
            print >>sys.stderr, 'could not parse the buildinfo:'
            print >>sys.stderr, open(filename).read()
            sys.exit(1)

        root = tree.getroot()

        if root.find('error') != None:
            sys.stderr.write('buildinfo is broken... it says:\n')
            error = root.find('error').text
            sys.stderr.write(error + '\n')
            sys.exit(1)

        if not (apiurl.startswith('https://') or apiurl.startswith('http://')):
            raise urllib2.URLError('invalid protocol for the apiurl: \'%s\'' % apiurl)

        self.buildtype = buildtype
        self.apiurl = apiurl

        # are we building .rpm or .deb?
        # XXX: shouldn't we deliver the type via the buildinfo?
        self.pacsuffix = 'rpm'
        if self.buildtype == 'dsc':
            self.pacsuffix = 'deb'

        self.buildarch = root.find('arch').text
        self.release = "0"
        if root.find('release') != None:
            self.release = root.find('release').text
        self.downloadurl = root.get('downloadurl')
        self.debuginfo = 0
        if root.find('debuginfo') != None:
            try:
                self.debuginfo = int(root.find('debuginfo').text)
            except ValueError:
                pass

        self.deps = []
        for node in root.findall('bdep'):
            p = Pac(node, self.buildarch, self.pacsuffix,
                    apiurl, localpkgs)
            self.deps.append(p)

        self.vminstall_list = [ dep.name for dep in self.deps if dep.vminstall ]
        self.preinstall_list = [ dep.name for dep in self.deps if dep.preinstall ]
        self.runscripts_list = [ dep.name for dep in self.deps if dep.runscripts ]


    def has_dep(self, name):
        for i in self.deps:
            if i.name == name:
                return True
        return False

    def remove_dep(self, name):
        for i in self.deps:
            if i.name == name:
                self.deps.remove(i)
                return True
        return False


class Pac:
    """represent a package to be downloaded

    We build a map that's later used to fill our URL templates
    """
    def __init__(self, node, buildarch, pacsuffix, apiurl, localpkgs = []):

        self.mp = {}
        for i in ['name', 'package',
                  'version', 'release',
                  'project', 'repository',
                  'preinstall', 'vminstall', 'noinstall', 'runscripts',
                 ]:
            self.mp[i] = node.get(i)

        self.mp['buildarch']  = buildarch
        self.mp['pacsuffix']  = pacsuffix

        self.mp['arch'] = node.get('arch') or self.mp['buildarch']

        # this is not the ideal place to check if the package is a localdep or not
        localdep = self.mp['name'] in localpkgs
        if not localdep and not (node.get('project') and node.get('repository')):
            raise oscerr.APIError('incomplete information for package %s, may be caused by a broken project configuration.'
                                  % self.mp['name'] )

        if not localdep:
            self.mp['extproject'] = node.get('project').replace(':', ':/')
            self.mp['extrepository'] = node.get('repository').replace(':', ':/')
        self.mp['repopackage'] = node.get('package') or '_repository'
        self.mp['repoarch'] = node.get('repoarch') or self.mp['buildarch']

        if pacsuffix == 'deb' and not (self.mp['name'] and self.mp['arch'] and self.mp['version']):
            raise oscerr.APIError(
                "buildinfo for package %s/%s/%s is incomplete"
                    % (self.mp['name'], self.mp['arch'], self.mp['version']))

        self.mp['apiurl'] = apiurl

        if self.mp['release']:
            self.filename = '%(name)s-%(version)s-%(release)s.%(arch)s.%(pacsuffix)s' % self.mp
        else:
            self.filename = '%(name)s-%(version)s.%(arch)s.%(pacsuffix)s' % self.mp

        self.mp['filename'] = self.filename
        if self.mp['repopackage'] == '_repository':
            self.mp['repofilename'] = self.mp['name']
        else:
            self.mp['repofilename'] = self.mp['filename']

        # make the content of the dictionary accessible as class attributes
        self.__dict__.update(self.mp)


    def makeurls(self, cachedir, urllist):

        self.urllist = []

        # build up local URL
        # by using the urlgrabber with local urls, we basically build up a cache.
        # the cache has no validation, since the package servers don't support etags,
        # or if-modified-since, so the caching is simply name-based (on the assumption
        # that the filename is suitable as identifier)
        self.localdir = '%s/%s/%s/%s' % (cachedir, self.project, self.repository, self.arch)
        self.fullfilename = os.path.join(self.localdir, self.filename)
        self.url_local = 'file://%s/' % self.fullfilename

        # first, add the local URL
        self.urllist.append(self.url_local)

        # remote URLs
        for url in urllist:
            self.urllist.append(url % self.mp)

    def __str__(self):
        return self.name

    def __repr__(self):
        return "%s" % self.name



def get_built_files(pacdir, pactype):
    if pactype == 'rpm':
        b_built = subprocess.Popen(['find', os.path.join(pacdir, 'RPMS'),
                                    '-name', '*.rpm'],
                                   stdout=subprocess.PIPE).stdout.read().strip()
        s_built = subprocess.Popen(['find', os.path.join(pacdir, 'SRPMS'),
                                    '-name', '*.rpm'],
                                   stdout=subprocess.PIPE).stdout.read().strip()
    elif pactype == 'kiwi':
        b_built = subprocess.Popen(['find', os.path.join(pacdir, 'KIWI'),
                                    '-type', 'f'],
                                   stdout=subprocess.PIPE).stdout.read().strip()
    else:
        b_built = subprocess.Popen(['find', os.path.join(pacdir, 'DEBS'),
                                    '-name', '*.deb'],
                                   stdout=subprocess.PIPE).stdout.read().strip()
        s_built = subprocess.Popen(['find', os.path.join(pacdir, 'SOURCES.DEB'),
                                    '-type', 'f'],
                                   stdout=subprocess.PIPE).stdout.read().strip()
    return s_built, b_built


def get_prefer_pkgs(dirs, wanted_arch, type):
    import glob
    from util import packagequery, cpio
    # map debian arches to common obs arches
    arch_map = {'i386': ['i586', 'i686'], 'amd64': ['x86_64']}
    paths = []
    suffix = '*.rpm'
    if type == 'dsc':
        suffix = '*.deb'
    for dir in dirs:
        paths += glob.glob(os.path.join(os.path.abspath(dir), suffix))
    prefer_pkgs = {}
    pkgqs = {}
    for path in paths:
        if path.endswith('src.rpm'):
            continue
        if path.find('-debuginfo-') > 0:
            continue
        pkgq = packagequery.PackageQuery.query(path)
        arch = pkgq.arch()
        name = pkgq.name()
        # instead of thip assumption, we should probably rather take the
        # requested arch for this package from buildinfo
        # also, it will ignore i686 packages, how to handle those?
        if arch in [wanted_arch, 'noarch', 'all'] or wanted_arch in arch_map.get(arch, []):
            curpkgq = pkgqs.get(name)
            if curpkgq is not None and curpkgq.vercmp(pkgq) > 0:
                continue
            prefer_pkgs[name] = path
            pkgqs[name] = pkgq
    depfile = create_deps(pkgqs.values())
    cpio = cpio.CpioWrite()
    cpio.add('deps', '\n'.join(depfile))
    return prefer_pkgs, cpio


def create_deps(pkgqs):
    """
    creates a list of requires/provides which corresponds to build's internal
    dependency file format
    """
    depfile = []
    for p in pkgqs:
        id = '%s.%s-0/0/0: ' % (p.name(), p.arch())
        depfile.append('R:%s%s' % (id, ' '.join(p.requires())))
        depfile.append('P:%s%s' % (id, ' '.join(p.provides())))
    return depfile


def main(opts, argv):

    repo = argv[0]
    arch = argv[1]
    build_descr = argv[2]
    xp = []

    build_type = os.path.splitext(build_descr)[1][1:]
    if build_type not in ['spec', 'dsc', 'kiwi']:
        raise oscerr.WrongArgs(
                "Unknown build type: '%s'. Build description should end in .spec, .dsc or .kiwi." \
                        % build_type)

    buildargs = []
    if not opts.userootforbuild:
        buildargs.append('--norootforbuild')
    if opts.clean:
        buildargs.append('--clean')
    if opts.noinit:
        buildargs.append('--noinit')
    if opts.nochecks:
        buildargs.append('--no-checks')
    if not opts.no_changelog:
        buildargs.append('--changelog')
    if opts.jobs:
        buildargs.append('--jobs %s' % opts.jobs)
    else:
        smp_mflags = os.sysconf('SC_NPROCESSORS_ONLN')
        if smp_mflags > 1:
            buildargs.append('--jobs %s' % smp_mflags)
    if opts.icecream:
        buildargs.append('--icecream %s' % opts.icecream)
        xp.append('icecream')
        xp.append('gcc-c++')
    if opts.ccache:
        buildargs.append('--ccache')
        xp.append('ccache')
    if opts.baselibs:
        buildargs.append('--baselibs')
    if opts.debuginfo:
        buildargs.append('--debug')
    if opts._with:
        buildargs.append('--with %s' % opts._with)
    if opts.without:
        buildargs.append('--without %s' % opts.without)
# FIXME: quoting
#    if opts.define:
#        buildargs.append('--define "%s"' % opts.define)

    if opts.alternative_project:
        prj = opts.alternative_project
        pac = '_repository'
        apiurl = config['apiurl']
    else:
        prj = store_read_project(os.curdir)
        if opts.local_package:
            pac = '_repository'
        else:
            pac = store_read_package(os.curdir)
        apiurl = store_read_apiurl(os.curdir)

    if not os.path.exists(build_descr):
        print >>sys.stderr, 'Error: build description named \'%s\' does not exist.' % build_descr
        return 1

    # make it possible to override configuration of the rc file
    for var in ['OSC_PACKAGECACHEDIR', 'OSC_SU_WRAPPER', 'OSC_BUILD_ROOT']:
        val = os.getenv(var)
        if val:
            if var.startswith('OSC_'): var = var[4:]
            var = var.lower().replace('_', '-')
            if config.has_key(var):
                print 'Overriding config value for %s=\'%s\' with \'%s\'' % (var, config[var], val)
            config[var] = val

    config['build-root'] = config['build-root'] % { 'repo': repo, 'arch': arch,
                                                    'project' : prj, 'package' : pac
                                                  }

    extra_pkgs = []
    if not opts.extra_pkgs:
        extra_pkgs = config['extra-pkgs']
    elif opts.extra_pkgs != ['']:
        extra_pkgs = opts.extra_pkgs

    if xp:
        extra_pkgs += xp

    prefer_pkgs = {}
    build_descr_data = open(build_descr).read()
    if opts.prefer_pkgs:
        print 'Scanning the following dirs for local packages: %s' % ', '.join(opts.prefer_pkgs)
        prefer_pkgs, cpio = get_prefer_pkgs(opts.prefer_pkgs, arch, build_type)
        cpio.add(os.path.basename(build_descr), build_descr_data)
        build_descr_data = cpio.get()

    bi_filename = os.path.join(os.getcwd(), '.osc/_buildinfo-%s-%s.xml' % (repo, arch))
    bc_filename = os.path.join(os.getcwd(), '.osc/_buildconfig-%s-%s' % (repo, arch))
    try:
        if opts.noinit:
            if not os.path.isfile(bi_filename):
                print >>sys.stderr, '--noinit is not possible, no local buildinfo file'
                sys.exit(1)
            print 'Use local \'%s\' file as buildinfo' % bi_filename
            if not os.path.isfile(bc_filename):
                print >>sys.stderr, '--noinit is not possible, no local buildconfig file'
                sys.exit(1)
            print 'Use local \'%s\' file as buildconfig' % bc_filename
        else:
            print 'Getting buildinfo from server and store to %s' % bi_filename
            bi_file = open(bi_filename, 'w')
            bi_text = ''.join(get_buildinfo(apiurl,
                                            prj,
                                            pac,
                                            repo,
                                            arch,
                                            specfile=build_descr_data,
                                            addlist=extra_pkgs))
            bi_file.write(bi_text)
            bi_file.close()
            print 'Getting buildconfig from server and store to %s' % bc_filename
            bc_file = open(bc_filename, 'w')
            bc_file.write(get_buildconfig(apiurl, prj, pac, repo, arch))
            bc_file.close()
    except urllib2.HTTPError, e:
        if e.code == 404:
        # check what caused the 404
            if meta_exists(metatype='prj', path_args=(quote_plus(prj), ),
                           template_args=None, create_new=False, apiurl=apiurl):
                if pac == '_repository' or meta_exists(metatype='pkg', path_args=(quote_plus(prj), quote_plus(pac)),
                                                       template_args=None, create_new=False, apiurl=apiurl):
                    print >>sys.stderr, 'ERROR: Either wrong repo/arch as parameter or a parse error of .spec/.dsc/.kiwi file due to syntax error'
                else:
                    print >>sys.stderr, 'The package \'%s\' does not exists - please ' \
                                        'rerun with \'--local-package\'' % pac
            else:
                print >>sys.stderr, 'The project \'%s\' does not exists - please ' \
                                    'rerun with \'--alternative-project <alternative_project>\'' % prj
            sys.exit(1)
        else:
            raise

    bi = Buildinfo(bi_filename, apiurl, build_type, prefer_pkgs.keys())
    if bi.debuginfo and not opts.disable_debuginfo:
        buildargs.append('--debug')
    buildargs = ' '.join(set(buildargs))

    # real arch of this machine
    # vs.
    # arch we are supposed to build for
    if hostarch != bi.buildarch:
        if not bi.buildarch in can_also_build.get(hostarch, []):
            print >>sys.stderr, 'Error: hostarch \'%s\' cannot build \'%s\'.' % (hostarch, bi.buildarch)
            return 1

    rpmlist_prefers = []
    if prefer_pkgs:
        print 'Evaluating preferred packages'
        for name, path in prefer_pkgs.iteritems():
            if bi.has_dep(name):
                # We remove a preferred package from the buildinfo, so that the
                # fetcher doesn't take care about them.
                # Instead, we put it in a list which is appended to the rpmlist later.
                # At the same time, this will make sure that these packages are
                # not verified.
                bi.remove_dep(name)
                rpmlist_prefers.append((name, path))
                print ' - %s (%s)' % (name, path)
                continue

    print 'Updating cache of required packages'

    urllist = []
    # transform 'url1, url2, url3' form into a list
    if 'urllist' in config:
        if type(config['urllist']) == str:
            re_clist = re.compile('[, ]+')
            urllist = [ i.strip() for i in re_clist.split(config['urllist'].strip()) ]
        else:
            urllist = config['urllist']

    # OBS 1.5 and before has no downloadurl defined in buildinfo
    if bi.downloadurl:
        urllist.append(bi.downloadurl + '/%(extproject)s/%(extrepository)s/%(arch)s/%(filename)s')

    fetcher = Fetcher(cachedir = config['packagecachedir'],
                      urllist = urllist,
                      api_host_options = config['api_host_options'],
                      offline = opts.noinit,
                      http_debug = config['http_debug'],
                      cookiejar=cookiejar)

    # now update the package cache
    fetcher.run(bi)

    # Make packages from buildinfo available as repos for kiwi
    if build_type == 'kiwi':
        if not os.path.exists('repos'):
            os.mkdir('repos')
        else:
            rmtree('repos')
            os.mkdir('repos')
        for i in bi.deps:
            # project
            pdir = str(i.extproject).replace(':/', ':')
            # repo
            rdir = str(i.extrepository).replace(':/', ':')
            # arch
            adir = i.repoarch
            # project/repo
            prdir = "repos/"+pdir+"/"+rdir
            # project/repo/arch
            pradir = prdir+"/"+adir
            # source fullfilename
            sffn = i.fullfilename
            print "Using package: "+sffn
            # target fullfilename
            tffn = pradir+"/"+sffn.split("/")[-1]
            if not os.path.exists(os.path.join(pradir)):
                os.makedirs(os.path.join(pradir))
            if not os.path.exists(tffn):
                os.symlink(sffn, tffn)

    if bi.pacsuffix == 'rpm':
        if config['build-type'] == "xen" or config['build-type'] == "kvm":
            print 'Skipping verification of package signatures due to secure VM build'
        elif opts.no_verify or opts.noinit:
            print 'Skipping verification of package signatures'
        else:
            print 'Verifying integrity of cached packages'
            verify_pacs([ i.fullfilename for i in bi.deps ])
    elif bi.pacsuffix == 'deb':
        if config['build-type'] == "xen" or config['build-type'] == "kvm":
            print 'Skipping verification of package signatures due to secure VM build'
        elif opts.no_verify or opts.noinit:
            print 'Skipping verification of package signatures'
        else:
            print 'WARNING: deb packages get not verified, they can compromise your system !'
    else:
            print 'WARNING: unknown packages get not verified, they can compromise your system !'

    print 'Writing build configuration'

    rpmlist = [ '%s %s\n' % (i.name, i.fullfilename) for i in bi.deps if not i.noinstall ]
    rpmlist += [ '%s %s\n' % (i[0], i[1]) for i in rpmlist_prefers ]

    rpmlist.append('preinstall: ' + ' '.join(bi.preinstall_list) + '\n')
    rpmlist.append('vminstall: ' + ' '.join(bi.vminstall_list) + '\n')
    rpmlist.append('runscripts: ' + ' '.join(bi.runscripts_list) + '\n')

    rpmlist_file = NamedTemporaryFile(prefix='rpmlist.')
    rpmlist_filename = rpmlist_file.name
    rpmlist_file.writelines(rpmlist)
    rpmlist_file.flush()

    vm_options=""
    if config['build-device'] and config['build-memory'] and config['build-type']:
        if config['build-type'] == "kvm":
            vm_options="--kvm " + config['build-device']
        elif config['build-type'] == "xen":
            vm_options="--xen " + config['build-device']
        else:
            print "ERROR: unknown VM is set ! (" + config['build-type'] + ")"
            sys.exit(1)
        if config['build-swap']:
            vm_options+=" --swap " + config['build-swap']
        if config['build-memory']:
            vm_options+=" --memory " + config['build-memory']

    print 'Running build'
    # special handling for overlay and rsync-src/dest
    specialcmdopts = " "
    if opts.rsyncsrc or opts.rsyncdest :
        if not opts.rsyncsrc or not opts.rsyncdest:
            print "When using --rsync-{src,dest} both parameters have to be specified."
            sys.exit(1)
        myrsyncsrc = os.path.expanduser(os.path.expandvars(opts.rsyncsrc))
        myrsyncdest = ""
        if os.path.isdir(myrsyncsrc):
            myrsyncsrc = os.path.abspath(myrsyncsrc)
        else:
            print "--rsync-src " + str(opts.rsyncsrc) + " is no valid directory!"
            sys.exit(1)
        # can't check destination - its in the target chroot ;) - but we can check for sanity
        if not opts.rsyncdest.startswith("/"):
            print "--rsync-dest " + str(opts.rsyncsrc) + " is no absolute path (starting with '/')!"
            sys.exit(1)
        myrsyncdest = os.path.expandvars(opts.rsyncdest)
        specialcmdopts += '--rsync-src=%s --rsync-dest=%s' \
                            % (myrsyncsrc,
                               myrsyncdest)
    if opts.overlay:
        myoverlay = os.path.expanduser(os.path.expandvars(opts.overlay))
        if not os.path.isdir(myoverlay):
            print "--overlay " + str(opts.overlay) + " is no valid directory!"
            sys.exit(1)
        myoverlay = os.path.abspath(myoverlay)
        specialcmdopts += '--overlay=%s' \
                            % (myoverlay)

    cmd = '%s --root=%s --rpmlist=%s --dist=%s %s --arch=%s --release=%s %s %s %s' \
                 % (config['build-cmd'],
                    config['build-root'],
                    rpmlist_filename,
                    bc_filename,
                    specialcmdopts,
                    bi.buildarch,
                    bi.release,
                    vm_options,
                    build_descr,
                    buildargs)
    if config['su-wrapper'].startswith('su '):
        tmpl = '%s \'%s\''
    else:
        tmpl = '%s %s'

    # change personality, if needed
    cmd = tmpl % (config['su-wrapper'], cmd)
    if hostarch != bi.buildarch:
        cmd = (change_personality.get(bi.buildarch, '') + ' ' + cmd).strip()

    rc = subprocess.call(cmd, shell=True)
    if rc:
        print
        print 'The buildroot was:', config['build-root']
        sys.exit(rc)

    pacdir = os.path.join(config['build-root'], '.build.packages')
    if os.path.islink(pacdir):
        pacdir = os.readlink(pacdir)
        pacdir = os.path.join(config['build-root'], pacdir)

    if os.path.exists(pacdir):
        (s_built, b_built) = get_built_files(pacdir, bi.pacsuffix)

        print
        if s_built: print s_built
        print
        print b_built

        if opts.keep_pkgs:
            for i in b_built.splitlines() + s_built.splitlines():
                import shutil
                shutil.copy2(i, os.path.join(opts.keep_pkgs, os.path.basename(i)))
