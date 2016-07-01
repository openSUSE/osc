# Copyright (C) 2006 Novell Inc.  All rights reserved.
# This program is free software; it may be used, copied, modified
# and distributed under the terms of the GNU General Public Licence,
# either version 2, or (at your option) any later version.

from __future__ import print_function

import os
import re
import sys
import shutil

try:
    from urllib.parse import urlsplit
    from urllib.request import URLError, HTTPError
except ImportError:
    #python 2.x
    from urlparse import urlsplit
    from urllib2 import URLError, HTTPError

from tempfile import NamedTemporaryFile, mkdtemp
from osc.fetch import *
from osc.core import get_buildinfo, store_read_apiurl, store_read_project, store_read_package, meta_exists, quote_plus, get_buildconfig, is_package_dir
from osc.core import get_binarylist, get_binary_file, run_external, raw_input
from osc.util import rpmquery, debquery, archquery
import osc.conf
from . import oscerr
import subprocess
try:
    from xml.etree import cElementTree as ET
except ImportError:
    import cElementTree as ET

from .conf import config, cookiejar

try:
    from .meter import TextMeter
except:
    TextMeter = None

change_personality = {
            'i686':  'linux32',
            'i586':  'linux32',
            'i386':  'linux32',
            'ppc':   'powerpc32',
            's390':  's390',
            'sparc': 'linux32',
            'sparcv8': 'linux32',
        }

# FIXME: qemu_can_build should not be needed anymore since OBS 2.3
qemu_can_build = [ 'armv4l', 'armv5el', 'armv5l', 'armv6l', 'armv7l', 'armv6el', 'armv6hl', 'armv7el', 'armv7hl', 'armv8el',
                   'sh4', 'mips', 'mipsel',
                   'ppc', 'ppc64',
                   's390', 's390x',
                   'sparc64v', 'sparcv9v', 'sparcv9', 'sparcv8', 'sparc',
                   'hppa',
        ]

can_also_build = {
             'aarch64': ['aarch64'], # only needed due to used heuristics in build parameter evaluation
             'armv6l': [                                         'armv4l', 'armv5l', 'armv6l', 'armv5el', 'armv6el'                       ],
             'armv7l': [                                         'armv4l', 'armv5l', 'armv6l', 'armv7l', 'armv5el', 'armv6el', 'armv7el'            ],
             'armv5el': [                                         'armv4l', 'armv5l', 'armv5el'                                  ], # not existing arch, just for compatibility
             'armv6el': [                                         'armv4l', 'armv5l', 'armv6l', 'armv5el', 'armv6el'                       ], # not existing arch, just for compatibility
             'armv6hl': [                                         'armv4l', 'armv5l', 'armv6l', 'armv5el', 'armv6el'                       ],
             'armv7el': [                                         'armv4l', 'armv5l', 'armv6l', 'armv7l', 'armv5el', 'armv6el', 'armv7el'            ], # not existing arch, just for compatibility
             'armv7hl': [                        'armv7hl'                                                             ], # not existing arch, just for compatibility
             'armv8el': [                                         'armv4l', 'armv5el', 'armv6el', 'armv7el', 'armv8el' ], # not existing arch, just for compatibility
             'armv8l': [                                         'armv4l', 'armv5el', 'armv6el', 'armv7el', 'armv8el' ], # not existing arch, just for compatibility
             'armv5tel': [                                        'armv4l', 'armv5el',                                 'armv5tel' ],
             's390x':  ['s390' ],
             'ppc64':  [                        'ppc', 'ppc64', 'ppc64p7', 'ppc64le' ],
             'ppc64le': [ 'ppc64le', 'ppc64' ],
             'i586':   [                'i386' ],
             'i686':   [        'i586', 'i386' ],
             'x86_64': ['i686', 'i586', 'i386' ],
             'sparc64': ['sparc64v', 'sparcv9v', 'sparcv9', 'sparcv8', 'sparc'],
             'parisc': ['hppa'],
        }

# real arch of this machine
hostarch = os.uname()[4]
if hostarch == 'i686': # FIXME
    hostarch = 'i586'

if hostarch == 'parisc':
    hostarch = 'hppa'

class Buildinfo:
    """represent the contents of a buildinfo file"""

    def __init__(self, filename, apiurl, buildtype = 'spec', localpkgs = []):
        try:
            tree = ET.parse(filename)
        except:
            print('could not parse the buildinfo:', file=sys.stderr)
            print(open(filename).read(), file=sys.stderr)
            sys.exit(1)

        root = tree.getroot()

        self.apiurl = apiurl

        if root.find('error') != None:
            sys.stderr.write('buildinfo is broken... it says:\n')
            error = root.find('error').text
            if error.startswith('unresolvable: '):
                sys.stderr.write('unresolvable: ')
                sys.stderr.write('\n     '.join(error[14:].split(',')))
            else:
                sys.stderr.write(error)
            sys.stderr.write('\n')
            sys.exit(1)

        if not (apiurl.startswith('https://') or apiurl.startswith('http://')):
            raise URLError('invalid protocol for the apiurl: \'%s\'' % apiurl)

        self.buildtype = buildtype
        self.apiurl = apiurl

        # are we building .rpm or .deb?
        # XXX: shouldn't we deliver the type via the buildinfo?
        self.pacsuffix = 'rpm'
        if self.buildtype == 'dsc' or self.buildtype == 'collax':
            self.pacsuffix = 'deb'
        if self.buildtype == 'arch':
            self.pacsuffix = 'arch'
        if self.buildtype == 'livebuild':
            self.pacsuffix = 'deb'
        if self.buildtype == 'snapcraft':
            # atm ubuntu is used as base, but we need to be more clever when 
            # snapcraft also supports rpm
            self.pacsuffix = 'deb'

        self.buildarch = root.find('arch').text
        if root.find('hostarch') != None:
            self.hostarch = root.find('hostarch').text
        else:
            self.hostarch = None
        if root.find('release') != None:
            self.release = root.find('release').text
        else:
            self.release = None
        self.downloadurl = root.get('downloadurl')
        self.debuginfo = 0
        if root.find('debuginfo') != None:
            try:
                self.debuginfo = int(root.find('debuginfo').text)
            except ValueError:
                pass

        self.deps = []
        self.projects = {}
        self.keys = []
        self.prjkeys = []
        self.pathes = []
        for node in root.findall('bdep'):
            p = Pac(node, self.buildarch, self.pacsuffix,
                    apiurl, localpkgs)
            if p.project:
                self.projects[p.project] = 1
            self.deps.append(p)
        for node in root.findall('path'):
            self.pathes.append(node.get('project')+"/"+node.get('repository'))

        self.vminstall_list = [ dep.name for dep in self.deps if dep.vminstall ]
        self.preinstall_list = [ dep.name for dep in self.deps if dep.preinstall ]
        self.runscripts_list = [ dep.name for dep in self.deps if dep.runscripts ]
        self.noinstall_list = [ dep.name for dep in self.deps if dep.noinstall ]
        self.installonly_list = [ dep.name for dep in self.deps if dep.installonly ]

        if root.find('preinstallimage') != None:
            self.preinstallimage = root.find('preinstallimage')
        else:
            self.preinstallimage = None


    def has_dep(self, name):
        for i in self.deps:
            if i.name == name:
                return True
        return False

    def remove_dep(self, name):
        # we need to iterate over all deps because if this a
        # kiwi build the same package might appear multiple times
        # NOTE: do not loop and remove items, the second same one would not get catched
        self.deps = [i for i in self.deps if not i.name == name]


class Pac:
    """represent a package to be downloaded

    We build a map that's later used to fill our URL templates
    """
    def __init__(self, node, buildarch, pacsuffix, apiurl, localpkgs = []):

        self.mp = {}
        for i in ['binary', 'package',
                  'epoch', 'version', 'release', 'hdrmd5',
                  'project', 'repository',
                  'preinstall', 'vminstall', 'noinstall', 'installonly', 'runscripts',
                 ]:
            self.mp[i] = node.get(i)

        self.mp['buildarch']  = buildarch
        self.mp['pacsuffix']  = pacsuffix

        self.mp['arch'] = node.get('arch') or self.mp['buildarch']
        self.mp['name'] = node.get('name') or self.mp['binary']

        # this is not the ideal place to check if the package is a localdep or not
        localdep = self.mp['name'] in localpkgs # and not self.mp['noinstall']
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

        if pacsuffix == 'deb':
            canonname = debquery.DebQuery.filename(self.mp['name'], self.mp['epoch'], self.mp['version'], self.mp['release'], self.mp['arch'])
        elif pacsuffix == 'arch':
            canonname = archquery.ArchQuery.filename(self.mp['name'], self.mp['epoch'], self.mp['version'], self.mp['release'], self.mp['arch'])
        else:
            canonname = rpmquery.RpmQuery.filename(self.mp['name'], self.mp['epoch'], self.mp['version'], self.mp['release'], self.mp['arch'])

        self.mp['canonname'] = canonname
        # maybe we should rename filename key to binary
        self.mp['filename'] = node.get('binary') or canonname
        if self.mp['repopackage'] == '_repository':
            self.mp['repofilename'] = self.mp['name']
        else:
            # OBS 2.3 puts binary into product bdeps (noinstall ones)
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
        self.fullfilename = os.path.join(self.localdir, self.canonname)
        self.url_local = 'file://%s' % self.fullfilename

        # first, add the local URL
        self.urllist.append(self.url_local)

        # remote URLs
        for url in urllist:
            self.urllist.append(url % self.mp)

    def __str__(self):
        return self.name

    def __repr__(self):
        return "%s" % self.name


def get_preinstall_image(apiurl, arch, cache_dir, img_info):
    """
    Searches preinstall image according to build info and downloads it to cache.
    Returns preinstall image path, source and list of image binaries, which can
    be used to create rpmlist.
    NOTE: preinstall image can be used only for new build roots!
    """
    imagefile = ''
    imagesource = ''
    img_bins = []
    for bin in img_info.findall('binary'):
        img_bins.append(bin.text)

    img_project = img_info.get('project')
    img_repository = img_info.get('repository')
    img_arch = arch
    img_pkg = img_info.get('package')
    img_file = img_info.get('filename')
    img_hdrmd5 = img_info.get('hdrmd5')
    if not img_hdrmd5:
        img_hdrmd5 = img_file
    cache_path = '%s/%s/%s/%s' % (cache_dir, img_project, img_repository, img_arch)
    ifile_path = '%s/%s' % (cache_path, img_file)
    ifile_path_part = '%s.part' % ifile_path

    imagefile = ifile_path
    imagesource = "%s/%s/%s [%s]" % (img_project, img_repository, img_pkg, img_hdrmd5)

    if not os.path.exists(ifile_path):
        url = "%s/build/%s/%s/%s/%s/%s" % (apiurl, img_project, img_repository, img_arch, img_pkg, img_file)
        print("downloading preinstall image %s" % imagesource)
        if not os.path.exists(cache_path):
            try:
                os.makedirs(cache_path, mode=0o755)
            except OSError as e:
                print('packagecachedir is not writable for you?', file=sys.stderr)
                print(e, file=sys.stderr)
                sys.exit(1)
        if sys.stdout.isatty() and TextMeter:
            progress_obj = TextMeter(fo=sys.stdout)
        else:
            progress_obj = None
        gr = OscFileGrabber(progress_obj=progress_obj)
        try:
            gr.urlgrab(url, filename=ifile_path_part, text='fetching image')
        except URLGrabError as e:
            print("Failed to download! ecode:%i errno:%i" % (e.code, e.errno))
            return ('', '', [])
        # download ok, rename partial file to final file name
        os.rename(ifile_path_part, ifile_path)
    return (imagefile, imagesource, img_bins)

def get_built_files(pacdir, buildtype):
    if buildtype == 'spec':
        b_built = subprocess.Popen(['find', os.path.join(pacdir, 'RPMS'),
                                    '-name', '*.rpm'],
                                   stdout=subprocess.PIPE).stdout.read().strip()
        s_built = subprocess.Popen(['find', os.path.join(pacdir, 'SRPMS'),
                                    '-name', '*.rpm'],
                                   stdout=subprocess.PIPE).stdout.read().strip()
    elif buildtype == 'kiwi':
        b_built = subprocess.Popen(['find', os.path.join(pacdir, 'KIWI'),
                                    '-type', 'f'],
                                   stdout=subprocess.PIPE).stdout.read().strip()
        s_built = ''
    elif buildtype == 'dsc' or buildtype == 'collax':
        b_built = subprocess.Popen(['find', os.path.join(pacdir, 'DEBS'),
                                    '-name', '*.deb'],
                                   stdout=subprocess.PIPE).stdout.read().strip()
        s_built = subprocess.Popen(['find', os.path.join(pacdir, 'SOURCES.DEB'),
                                    '-type', 'f'],
                                   stdout=subprocess.PIPE).stdout.read().strip()
    elif buildtype == 'arch':
        b_built = subprocess.Popen(['find', os.path.join(pacdir, 'ARCHPKGS'),
                                    '-name', '*.pkg.tar*'],
                                   stdout=subprocess.PIPE).stdout.read().strip()
        s_built = ''
    elif buildtype == 'livebuild':
        b_built = subprocess.Popen(['find', os.path.join(pacdir, 'OTHER'),
                                    '-name', '*.iso*'],
                                   stdout=subprocess.PIPE).stdout.read().strip()
        s_built = ''
    elif buildtype == 'snapcraft':
        b_built = subprocess.Popen(['find', os.path.join(pacdir, 'OTHER'),
                                    '-name', '*.snap'],
                                   stdout=subprocess.PIPE).stdout.read().strip()
        s_built = ''
    else:
        print('WARNING: Unknown package type \'%s\'.' % buildtype, file=sys.stderr)
        b_built = ''
        s_built = ''
    return s_built, b_built

def get_repo(path):
    """Walks up path looking for any repodata directories.

    @param path path to a directory
    @return str path to repository directory containing repodata directory
    """
    oldDirectory = None
    currentDirectory = os.path.abspath(path)
    repositoryDirectory = None

    # while there are still parent directories
    while currentDirectory != oldDirectory:
        children = os.listdir(currentDirectory)

        if "repodata" in children:
            repositoryDirectory = currentDirectory
            break

        # ascend
        oldDirectory = currentDirectory
        currentDirectory = os.path.abspath(os.path.join(oldDirectory,
                                                        os.pardir))

    return repositoryDirectory

def get_prefer_pkgs(dirs, wanted_arch, type, cpio):
    import glob
    from .util import repodata, packagequery
    paths = []
    repositories = []

    suffix = '*.rpm'
    if type == 'dsc' or type == 'collax' or type == 'livebuild':
        suffix = '*.deb'
    elif type == 'arch':
        suffix = '*.pkg.tar.xz'

    for dir in dirs:
        # check for repodata
        repository = get_repo(dir)
        if repository is None:
            paths += glob.glob(os.path.join(os.path.abspath(dir), suffix))
        else:
            repositories.append(repository)

    packageQueries = packagequery.PackageQueries(wanted_arch)

    for repository in repositories:
        repodataPackageQueries = repodata.queries(repository)

        for packageQuery in repodataPackageQueries:
            packageQueries.add(packageQuery)

    for path in paths:
        if path.endswith('.src.rpm') or path.endswith('.nosrc.rpm'):
            continue
        if path.endswith('.patch.rpm') or path.endswith('.delta.rpm'):
            continue
        if path.find('-debuginfo-') > 0:
            continue
        packageQuery = packagequery.PackageQuery.query(path)
        packageQueries.add(packageQuery)

    prefer_pkgs = dict((name, packageQuery.path())
                       for name, packageQuery in packageQueries.items())

    depfile = create_deps(packageQueries.values())
    cpio.add('deps', '\n'.join(depfile))
    return prefer_pkgs


def create_deps(pkgqs):
    """
    creates a list of dependencies which corresponds to build's internal
    dependency file format
    """
    depfile = []
    for p in pkgqs:
        id = '%s.%s-0/0/0: ' % (p.name(), p.arch())
        depfile.append('P:%s%s' % (id, ' '.join(p.provides())))
        depfile.append('R:%s%s' % (id, ' '.join(p.requires())))
        d = p.conflicts()
        if d:
            depfile.append('C:%s%s' % (id, ' '.join(d)))
        d = p.obsoletes()
        if d:
            depfile.append('O:%s%s' % (id, ' '.join(d)))
        depfile.append('I:%s%s-%s 0-%s' % (id, p.name(), p.evr(), p.arch()))
    return depfile


trustprompt = """Would you like to ...
0 - quit (default)
1 - always trust packages from '%(project)s'
2 - trust packages just this time
? """
def check_trusted_projects(apiurl, projects):
    trusted = config['api_host_options'][apiurl]['trusted_prj']
    tlen = len(trusted)
    for prj in projects:
        if not prj in trusted:
            print("\nThe build root needs packages from project '%s'." % prj)
            print("Note that malicious packages can compromise the build result or even your system.")
            r = raw_input(trustprompt % { 'project': prj })
            if r == '1':
                print("adding '%s' to ~/.oscrc: ['%s']['trusted_prj']" % (prj, apiurl))
                trusted.append(prj)
            elif r != '2':
                print("Well, good good bye then :-)")
                raise oscerr.UserAbort()

    if tlen != len(trusted):
        config['api_host_options'][apiurl]['trusted_prj'] = trusted
        conf.config_set_option(apiurl, 'trusted_prj', ' '.join(trusted))

def main(apiurl, opts, argv):

    repo = argv[0]
    arch = argv[1]
    build_descr = argv[2]
    xp = []
    build_root = None
    cache_dir  = None
    build_uid = ''
    vm_type = config['build-type']
    vm_telnet = None

    build_descr = os.path.abspath(build_descr)
    build_type = os.path.splitext(build_descr)[1][1:]
    if os.path.basename(build_descr) == 'PKGBUILD':
        build_type = 'arch'
    if os.path.basename(build_descr) == 'build.collax':
        build_type = 'collax'
    if os.path.basename(build_descr) == 'snapcraft.yaml':
        build_type = 'snapcraft'
    if build_type not in ['spec', 'dsc', 'kiwi', 'arch', 'collax', 'livebuild', 'snapcraft']:
        raise oscerr.WrongArgs(
                'Unknown build type: \'%s\'. Build description should end in .spec, .dsc, .kiwi, .yaml or .livebuild.' \
                        % build_type)
    if not os.path.isfile(build_descr):
        raise oscerr.WrongArgs('Error: build description file named \'%s\' does not exist.' % build_descr)

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
    if opts.root:
        build_root = opts.root
    if opts.target:
        buildargs.append('--target=%s' % opts.target)
    if opts.threads:
        buildargs.append('--threads=%s' % opts.threads)
    if opts.jobs:
        buildargs.append('--jobs=%s' % opts.jobs)
    elif config['build-jobs'] > 1:
        buildargs.append('--jobs=%s' % config['build-jobs'])
    if opts.icecream or config['icecream'] != '0':
        if opts.icecream:
            num = opts.icecream
        else:
            num = config['icecream']

        if int(num) > 0:
            buildargs.append('--icecream=%s' % num)
            xp.append('icecream')
            xp.append('gcc-c++')
    if opts.ccache:
        buildargs.append('--ccache')
        xp.append('ccache')
    if opts.linksources:
        buildargs.append('--linksources')
    if opts.baselibs:
        buildargs.append('--baselibs')
    if opts.debuginfo:
        buildargs.append('--debug')
    if opts._with:
        for o in opts._with:
            buildargs.append('--with=%s' % o)
    if opts.without:
        for o in opts.without:
            buildargs.append('--without=%s' % o)
    if opts.define:
        for o in opts.define:
            buildargs.append('--define=%s' % o)
    if config['build-uid']:
        build_uid = config['build-uid']
    if opts.build_uid:
        build_uid = opts.build_uid
    if build_uid:
        buildidre = re.compile('^[0-9]{1,5}:[0-9]{1,5}$')
        if build_uid == 'caller':
            buildargs.append('--uid=%s:%s' % (os.getuid(), os.getgid()))
        elif buildidre.match(build_uid):
            buildargs.append('--uid=%s' % build_uid)
        else:
            print('Error: build-uid arg must be 2 colon separated numerics: "uid:gid" or "caller"', file=sys.stderr)
            return 1
    if opts.vm_type:
        vm_type = opts.vm_type
    if opts.vm_telnet:
        vm_telnet = opts.vm_telnet
    if opts.alternative_project:
        prj = opts.alternative_project
        pac = '_repository'
    else:
        prj = store_read_project(os.curdir)
        if opts.local_package:
            pac = '_repository'
        else:
            pac = store_read_package(os.curdir)
    if opts.shell:
        buildargs.append("--shell")

    orig_build_root = config['build-root']
    # make it possible to override configuration of the rc file
    for var in ['OSC_PACKAGECACHEDIR', 'OSC_SU_WRAPPER', 'OSC_BUILD_ROOT']:
        val = os.getenv(var)
        if val:
            if var.startswith('OSC_'): var = var[4:]
            var = var.lower().replace('_', '-')
            if var in config:
                print('Overriding config value for %s=\'%s\' with \'%s\'' % (var, config[var], val))
            config[var] = val

    pacname = pac
    if pacname == '_repository':
        if not opts.local_package:
            try:
                pacname = store_read_package(os.curdir)
            except oscerr.NoWorkingCopy:
                opts.local_package = True
        if opts.local_package:
            pacname = os.path.splitext(build_descr)[0]
    apihost = urlsplit(apiurl)[1]
    if not build_root:
        build_root = config['build-root']
        if build_root == orig_build_root:
            # ENV var was not set
            build_root = config['api_host_options'][apiurl].get('build-root', build_root)
        try:
            build_root = build_root % {'repo': repo, 'arch': arch,
                         'project': prj, 'package': pacname, 'apihost': apihost}
        except:
            pass

    cache_dir = config['packagecachedir'] % {'apihost': apihost}

    extra_pkgs = []
    if not opts.extra_pkgs:
        extra_pkgs = config['extra-pkgs']
    elif opts.extra_pkgs != ['']:
        extra_pkgs = opts.extra_pkgs

    if xp:
        extra_pkgs += xp

    prefer_pkgs = {}
    build_descr_data = open(build_descr).read()

    # XXX: dirty hack but there's no api to provide custom defines
    if opts.without:
        s = ''
        for i in opts.without:
            s += "%%define _without_%s 1\n" % i
        build_descr_data = s + build_descr_data
    if opts._with:
        s = ''
        for i in opts._with:
            s += "%%define _with_%s 1\n" % i
        build_descr_data = s + build_descr_data
    if opts.define:
        s = ''
        for i in opts.define:
            s += "%%define %s\n" % i
        build_descr_data = s + build_descr_data

    cpiodata = None
    servicefile = os.path.join(os.path.dirname(build_descr), "_service")
    if not os.path.isfile(servicefile):
        servicefile = os.path.join(os.path.dirname(build_descr), "_service")
        if not os.path.isfile(servicefile):
            servicefile = None
        else:
            print('Using local _service file')
    buildenvfile = os.path.join(os.path.dirname(build_descr), "_buildenv." + repo + "." + arch)
    if not os.path.isfile(buildenvfile):
        buildenvfile = os.path.join(os.path.dirname(build_descr), "_buildenv")
        if not os.path.isfile(buildenvfile):
            buildenvfile = None
        else:
            print('Using local buildenv file: %s' % os.path.basename(buildenvfile))
    if buildenvfile or servicefile:
        from .util import cpio
        if not cpiodata:
            cpiodata = cpio.CpioWrite()

    if opts.prefer_pkgs:
        print('Scanning the following dirs for local packages: %s' % ', '.join(opts.prefer_pkgs))
        from .util import cpio
        if not cpiodata:
            cpiodata = cpio.CpioWrite()
        prefer_pkgs = get_prefer_pkgs(opts.prefer_pkgs, arch, build_type, cpiodata)

    if cpiodata:
        cpiodata.add(os.path.basename(build_descr), build_descr_data)
        # buildenv must come last for compatibility reasons...
        if buildenvfile:
            cpiodata.add("buildenv", open(buildenvfile).read())
        if servicefile:
            cpiodata.add("_service", open(servicefile).read())
        build_descr_data = cpiodata.get()

    # special handling for overlay and rsync-src/dest
    specialcmdopts = []
    if opts.rsyncsrc or opts.rsyncdest :
        if not opts.rsyncsrc or not opts.rsyncdest:
            raise oscerr.WrongOptions('When using --rsync-{src,dest} both parameters have to be specified.')
        myrsyncsrc = os.path.abspath(os.path.expanduser(os.path.expandvars(opts.rsyncsrc)))
        if not os.path.isdir(myrsyncsrc):
            raise oscerr.WrongOptions('--rsync-src %s is no valid directory!' % opts.rsyncsrc)
        # can't check destination - its in the target chroot ;) - but we can check for sanity
        myrsyncdest = os.path.expandvars(opts.rsyncdest)
        if not os.path.isabs(myrsyncdest):
            raise oscerr.WrongOptions('--rsync-dest %s is no absolute path (starting with \'/\')!' % opts.rsyncdest)
        specialcmdopts = ['--rsync-src='+myrsyncsrc, '--rsync-dest='+myrsyncdest]
    if opts.overlay:
        myoverlay = os.path.abspath(os.path.expanduser(os.path.expandvars(opts.overlay)))
        if not os.path.isdir(myoverlay):
            raise oscerr.WrongOptions('--overlay %s is no valid directory!' % opts.overlay)
        specialcmdopts += ['--overlay='+myoverlay]

    bi_file = None
    bc_file = None
    bi_filename = '_buildinfo-%s-%s.xml' % (repo, arch)
    bc_filename = '_buildconfig-%s-%s' % (repo, arch)
    if is_package_dir('.') and os.access(osc.core.store, os.W_OK):
        bi_filename = os.path.join(os.getcwd(), osc.core.store, bi_filename)
        bc_filename = os.path.join(os.getcwd(), osc.core.store, bc_filename)
    elif not os.access('.', os.W_OK):
        bi_file = NamedTemporaryFile(prefix=bi_filename)
        bi_filename = bi_file.name
        bc_file = NamedTemporaryFile(prefix=bc_filename)
        bc_filename = bc_file.name
    else:
        bi_filename = os.path.abspath(bi_filename)
        bc_filename = os.path.abspath(bc_filename)

    try:
        if opts.noinit:
            if not os.path.isfile(bi_filename):
                raise oscerr.WrongOptions('--noinit is not possible, no local buildinfo file')
            print('Use local \'%s\' file as buildinfo' % bi_filename)
            if not os.path.isfile(bc_filename):
                raise oscerr.WrongOptions('--noinit is not possible, no local buildconfig file')
            print('Use local \'%s\' file as buildconfig' % bc_filename)
        elif opts.offline:
            if not os.path.isfile(bi_filename):
                raise oscerr.WrongOptions('--offline is not possible, no local buildinfo file')
            print('Use local \'%s\' file as buildinfo' % bi_filename)
            if not os.path.isfile(bc_filename):
                raise oscerr.WrongOptions('--offline is not possible, no local buildconfig file')
        else:
            print('Getting buildinfo from server and store to %s' % bi_filename)
            bi_text = ''.join(get_buildinfo(apiurl,
                                            prj,
                                            pac,
                                            repo,
                                            arch,
                                            specfile=build_descr_data,
                                            addlist=extra_pkgs))
            if not bi_file:
                bi_file = open(bi_filename, 'w')
            # maybe we should check for errors before saving the file
            bi_file.write(bi_text)
            bi_file.flush()
            print('Getting buildconfig from server and store to %s' % bc_filename)
            bc = get_buildconfig(apiurl, prj, repo)
            if not bc_file:
                bc_file = open(bc_filename, 'w')
            bc_file.write(bc)
            bc_file.flush()
    except HTTPError as e:
        if e.code == 404:
            # check what caused the 404
            if meta_exists(metatype='prj', path_args=(quote_plus(prj), ),
                           template_args=None, create_new=False, apiurl=apiurl):
                pkg_meta_e = None
                try:
                    # take care, not to run into double trouble.
                    pkg_meta_e = meta_exists(metatype='pkg', path_args=(quote_plus(prj),
                                        quote_plus(pac)), template_args=None, create_new=False,
                                        apiurl=apiurl)
                except:
                    pass

                if pkg_meta_e:
                    print('ERROR: Either wrong repo/arch as parameter or a parse error of .spec/.dsc/.kiwi file due to syntax error', file=sys.stderr)
                else:
                    print('The package \'%s\' does not exist - please ' \
                                        'rerun with \'--local-package\'' % pac, file=sys.stderr)
            else:
                print('The project \'%s\' does not exist - please ' \
                                    'rerun with \'--alternative-project <alternative_project>\'' % prj, file=sys.stderr)
            sys.exit(1)
        else:
            raise

    bi = Buildinfo(bi_filename, apiurl, build_type, list(prefer_pkgs.keys()))

    if bi.debuginfo and not (opts.disable_debuginfo or '--debug' in buildargs):
        buildargs.append('--debug')

    if opts.release:
        bi.release = opts.release

    if bi.release:
        buildargs.append('--release=%s' % bi.release)

    # real arch of this machine
    # vs.
    # arch we are supposed to build for
    if bi.hostarch != None:
        if hostarch != bi.hostarch and not bi.hostarch in can_also_build.get(hostarch, []):
            print('Error: hostarch \'%s\' is required.' % (bi.hostarch), file=sys.stderr)
            return 1
    elif hostarch != bi.buildarch:
        if not bi.buildarch in can_also_build.get(hostarch, []):
            # OBSOLETE: qemu_can_build should not be needed anymore since OBS 2.3
            if vm_type != "emulator" and not bi.buildarch in qemu_can_build:
                print('Error: hostarch \'%s\' cannot build \'%s\'.' % (hostarch, bi.buildarch), file=sys.stderr)
                return 1
            print('WARNING: It is guessed to build on hostarch \'%s\' for \'%s\' via QEMU.' % (hostarch, bi.buildarch), file=sys.stderr)

    rpmlist_prefers = []
    if prefer_pkgs:
        print('Evaluating preferred packages')
        for name, path in prefer_pkgs.items():
            if bi.has_dep(name):
                # We remove a preferred package from the buildinfo, so that the
                # fetcher doesn't take care about them.
                # Instead, we put it in a list which is appended to the rpmlist later.
                # At the same time, this will make sure that these packages are
                # not verified.
                bi.remove_dep(name)
                rpmlist_prefers.append((name, path))
                print(' - %s (%s)' % (name, path))

    print('Updating cache of required packages')

    urllist = []
    if not opts.download_api_only:
        # transform 'url1, url2, url3' form into a list
        if 'urllist' in config:
            if isinstance(config['urllist'], str):
                re_clist = re.compile('[, ]+')
                urllist = [ i.strip() for i in re_clist.split(config['urllist'].strip()) ]
            else:
                urllist = config['urllist']

        # OBS 1.5 and before has no downloadurl defined in buildinfo
        if bi.downloadurl:
            urllist.append(bi.downloadurl + '/%(extproject)s/%(extrepository)s/%(arch)s/%(filename)s')
    if opts.disable_cpio_bulk_download:
        urllist.append( '%(apiurl)s/build/%(project)s/%(repository)s/%(repoarch)s/%(repopackage)s/%(repofilename)s' )

    fetcher = Fetcher(cache_dir,
                      urllist = urllist,
                      api_host_options = config['api_host_options'],
                      offline = opts.noinit or opts.offline,
                      http_debug = config['http_debug'],
                      enable_cpio = not opts.disable_cpio_bulk_download,
                      cookiejar=cookiejar)

    if not opts.trust_all_projects:
        # implicitly trust the project we are building for
        check_trusted_projects(apiurl, [ i for i in bi.projects.keys() if not i == prj ])

    imagefile = ''
    imagesource = ''
    imagebins = []
    if (not config['no_preinstallimage'] and not opts.nopreinstallimage and
        bi.preinstallimage and
        not opts.noinit and not opts.offline and
        (opts.clean or (not os.path.exists(build_root + "/installed-pkg") and
                        not os.path.exists(build_root + "/.build/init_buildsystem.data")))):
        (imagefile, imagesource, imagebins) = get_preinstall_image(apiurl, arch, cache_dir, bi.preinstallimage)
        if imagefile:
            # remove binaries from build deps which are included in preinstall image
            for i in bi.deps:
                if i.name in imagebins:
                    bi.remove_dep(i.name)

    # now update the package cache
    fetcher.run(bi)

    old_pkg_dir = None
    if opts.oldpackages:
        old_pkg_dir = opts.oldpackages
        if not old_pkg_dir.startswith('/') and not opts.offline:
            data = [ prj, pacname, repo, arch]
            if old_pkg_dir == '_link':
                p = osc.core.findpacs(os.curdir)[0]
                if not p.islink():
                    raise oscerr.WrongOptions('package is not a link')
                data[0] = p.linkinfo.project
                data[1] = p.linkinfo.package
                repos = osc.core.get_repositories_of_project(apiurl, data[0])
                # hack for links to e.g. Factory
                if not data[2] in repos and 'standard' in repos:
                    data[2] = 'standard'
            elif old_pkg_dir != '' and old_pkg_dir != '_self':
                a = old_pkg_dir.split('/')
                for i in range(0, len(a)):
                    data[i] = a[i]

            destdir = os.path.join(cache_dir, data[0], data[2], data[3])
            old_pkg_dir = None
            try:
                print("Downloading previous build from %s ..." % '/'.join(data))
                binaries = get_binarylist(apiurl, data[0], data[2], data[3], package=data[1], verbose=True)
            except Exception as e:
                print("Error: failed to get binaries: %s" % str(e))
                binaries = []

            if binaries:
                class mytmpdir:
                    """ temporary directory that removes itself"""
                    def __init__(self, *args, **kwargs):
                        self.name = mkdtemp(*args, **kwargs)
                    _rmtree = staticmethod(shutil.rmtree)
                    def cleanup(self):
                        self._rmtree(self.name)
                    def __del__(self):
                        self.cleanup()
                    def __exit__(self):
                        self.cleanup()
                    def __str__(self):
                        return self.name

                old_pkg_dir = mytmpdir(prefix='.build.oldpackages', dir=os.path.abspath(os.curdir))
                if not os.path.exists(destdir):
                    os.makedirs(destdir)
            for i in binaries:
                fname = os.path.join(destdir, i.name)
                os.symlink(fname, os.path.join(str(old_pkg_dir), i.name))
                if os.path.exists(fname):
                    st = os.stat(fname)
                    if st.st_mtime == i.mtime and st.st_size == i.size:
                        continue
                get_binary_file(apiurl,
                                data[0],
                                data[2], data[3],
                                i.name,
                                package = data[1],
                                target_filename = fname,
                                target_mtime = i.mtime,
                                progress_meter = True)

        if old_pkg_dir != None:
            buildargs.append('--oldpackages=%s' % old_pkg_dir)

    # Make packages from buildinfo available as repos for kiwi
    if build_type == 'kiwi':
        if os.path.exists('repos'):
            shutil.rmtree('repos')
        os.mkdir('repos')
        for i in bi.deps:
            if not i.extproject:
                # remove
                bi.deps.remove(i)
                continue
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
            filename = sffn.split("/")[-1]
            # target fullfilename
            tffn = pradir+"/"+filename
            if not os.path.exists(os.path.join(pradir)):
                os.makedirs(os.path.join(pradir))
            if not os.path.exists(tffn):
                print("Using package: "+sffn)
                if opts.linksources:
                    os.link(sffn, tffn)
                else:
                    os.symlink(sffn, tffn)
            if prefer_pkgs:
                for name, path in prefer_pkgs.items():
                    if name == filename:
                        print("Using prefered package: " + path + "/" + filename)
                        os.unlink(tffn)
                        if opts.linksources:
                            os.link(path + "/" + filename, tffn)
                        else:
                            os.symlink(path + "/" + filename, tffn)
        # Is a obsrepositories tag used?
        try:
            tree = ET.parse(build_descr)
        except:
            print('could not parse the kiwi file:', file=sys.stderr)
            print(open(build_descr).read(), file=sys.stderr)
            sys.exit(1)
        root = tree.getroot()
        # product
        for xml in root.findall('instsource'):
            if xml.find('instrepo').find('source').get('path') == 'obsrepositories:/':
                print("obsrepositories:/ for product builds is not yet supported in osc!")
                sys.exit(1)
        # appliance
        expand_obsrepos=None
        for xml in root.findall('repository'):
            if xml.find('source').get('path') == 'obsrepositories:/':
                expand_obsrepos=True
        if expand_obsrepos:
          buildargs.append('--kiwi-parameter')
          buildargs.append('--ignore-repos')
          for xml in root.findall('repository'):
              if xml.find('source').get('path') == 'obsrepositories:/':
                  for path in bi.pathes:
                      if not os.path.isdir("repos/"+path):
                          continue
                      buildargs.append('--kiwi-parameter')
                      buildargs.append('--add-repo')
                      buildargs.append('--kiwi-parameter')
                      buildargs.append("repos/"+path)
                      buildargs.append('--kiwi-parameter')
                      buildargs.append('--add-repotype')
                      buildargs.append('--kiwi-parameter')
                      buildargs.append('rpm-md')
                      if xml.get('priority'):
                          buildargs.append('--kiwi-parameter')
                          buildargs.append('--add-repoprio='+xml.get('priority'))
              else:
                   m = re.match(r"obs://[^/]+/([^/]+)/(\S+)", xml.find('source').get('path'))
                   if not m:
                       # short path without obs instance name
                       m = re.match(r"obs://([^/]+)/(.+)", xml.find('source').get('path'))
                   project=m.group(1).replace(":", ":/")
                   repo=m.group(2)
                   buildargs.append('--kiwi-parameter')
                   buildargs.append('--add-repo')
                   buildargs.append('--kiwi-parameter')
                   buildargs.append("repos/"+project+"/"+repo)
                   buildargs.append('--kiwi-parameter')
                   buildargs.append('--add-repotype')
                   buildargs.append('--kiwi-parameter')
                   buildargs.append('rpm-md')
                   if xml.get('priority'):
                       buildargs.append('--kiwi-parameter')
                       buildargs.append('--add-repopriority='+xml.get('priority'))

    if vm_type == "xen" or vm_type == "kvm" or vm_type == "lxc":
        print('Skipping verification of package signatures due to secure VM build')
    elif bi.pacsuffix == 'rpm':
        if opts.no_verify:
            print('Skipping verification of package signatures')
        else:
            print('Verifying integrity of cached packages')
            verify_pacs(bi)
    elif bi.pacsuffix == 'deb':
        if opts.no_verify or opts.noinit:
            print('Skipping verification of package signatures')
        else:
            print('WARNING: deb packages get not verified, they can compromise your system !')
    else:
        print('WARNING: unknown packages get not verified, they can compromise your system !')

    for i in bi.deps:
        if i.hdrmd5:
            from .util import packagequery
            hdrmd5 = packagequery.PackageQuery.queryhdrmd5(i.fullfilename)
            if not hdrmd5:
                print("Error: cannot get hdrmd5 for %s" % i.fullfilename)
                sys.exit(1)
            if hdrmd5 != i.hdrmd5:
                print("Error: hdrmd5 mismatch for %s: %s != %s" % (i.fullfilename, hdrmd5, i.hdrmd5))
                sys.exit(1)

    print('Writing build configuration')

    if build_type == 'kiwi':
        rpmlist = [ '%s %s\n' % (i.name, i.fullfilename) for i in bi.deps if not i.noinstall ]
    else:
        rpmlist = [ '%s %s\n' % (i.name, i.fullfilename) for i in bi.deps ]
    for i in imagebins:
        rpmlist.append('%s preinstallimage\n' % i)
    rpmlist += [ '%s %s\n' % (i[0], i[1]) for i in rpmlist_prefers ]

    if imagefile:
        rpmlist.append('preinstallimage: %s\n' % imagefile)
    if imagesource:
        rpmlist.append('preinstallimagesource: %s\n' % imagesource)

    rpmlist.append('preinstall: ' + ' '.join(bi.preinstall_list) + '\n')
    rpmlist.append('vminstall: ' + ' '.join(bi.vminstall_list) + '\n')
    rpmlist.append('runscripts: ' + ' '.join(bi.runscripts_list) + '\n')
    if build_type != 'kiwi' and bi.noinstall_list:
        rpmlist.append('noinstall: ' + ' '.join(bi.noinstall_list) + '\n')
    if build_type != 'kiwi' and bi.installonly_list:
        rpmlist.append('installonly: ' + ' '.join(bi.installonly_list) + '\n')

    rpmlist_file = NamedTemporaryFile(prefix='rpmlist.')
    rpmlist_filename = rpmlist_file.name
    rpmlist_file.writelines(rpmlist)
    rpmlist_file.flush()

    subst = { 'repo': repo, 'arch': arch, 'project' : prj, 'package' : pacname }
    vm_options = []
    # XXX check if build-device present
    my_build_device = ''
    if config['build-device']:
        my_build_device = config['build-device'] % subst
    else:
        # obs worker uses /root here but that collides with the
        # /root directory if the build root was used without vm
        # before
        my_build_device = build_root + '/img'

    need_root = True
    if vm_type:
        if config['build-swap']:
            my_build_swap = config['build-swap'] % subst
        else:
            my_build_swap = build_root + '/swap'

        vm_options = [ '--vm-type=%s' % vm_type ]
        if vm_telnet:
            vm_options += [ '--vm-telnet=' + vm_telnet ]
        if config['build-memory']:
            vm_options += [ '--memory=' + config['build-memory'] ]
        if vm_type != 'lxc':
            vm_options += [ '--vm-disk=' + my_build_device ]
            vm_options += [ '--vm-swap=' + my_build_swap ]
            vm_options += [ '--logfile=%s/.build.log' % build_root ]
            if vm_type == 'kvm':
                if os.access(build_root, os.W_OK) and os.access('/dev/kvm', os.W_OK):
                    # so let's hope there's also an fstab entry
                    need_root = False
                if config['build-kernel']:
                    vm_options += [ '--vm-kernel=' + config['build-kernel'] ]
                if config['build-initrd']:
                    vm_options += [ '--vm-initrd=' + config['build-initrd'] ]

            build_root += '/.mount'

        if config['build-memory']:
            vm_options += [ '--memory=' + config['build-memory'] ]
        if config['build-vmdisk-rootsize']:
            vm_options += [ '--vmdisk-rootsize=' + config['build-vmdisk-rootsize'] ]
        if config['build-vmdisk-swapsize']:
            vm_options += [ '--vmdisk-swapsize=' + config['build-vmdisk-swapsize'] ]
        if config['build-vmdisk-filesystem']:
            vm_options += [ '--vmdisk-filesystem=' + config['build-vmdisk-filesystem'] ]
        if config['build-vm-user']:
            vm_options += [ '--vm-user=' + config['build-vm-user'] ]


    if opts.preload:
        print("Preload done for selected repo/arch.")
        sys.exit(0)

    print('Running build')
    cmd = [ config['build-cmd'], '--root='+build_root,
                    '--rpmlist='+rpmlist_filename,
                    '--dist='+bc_filename,
                    '--arch='+bi.buildarch ]
    cmd += specialcmdopts + vm_options + buildargs
    cmd += [ build_descr ]

    if need_root:
        sucmd = config['su-wrapper'].split()
        if sucmd[0] == 'su':
            if sucmd[-1] == '-c':
                sucmd.pop()
            cmd = sucmd + ['-s', cmd[0], 'root', '--' ] + cmd[1:]
        else:
            cmd = sucmd + cmd

    # change personality, if needed
    if hostarch != bi.buildarch and bi.buildarch in change_personality:
        cmd = [ change_personality[bi.buildarch] ] + cmd

    try:
        rc = run_external(cmd[0], *cmd[1:])
        if rc:
            print()
            print('The buildroot was:', build_root)
            sys.exit(rc)
    except KeyboardInterrupt as i:
        print("keyboard interrupt, killing build ...")
        cmd.append('--kill')
        run_external(cmd[0], *cmd[1:])
        raise i

    pacdir = os.path.join(build_root, '.build.packages')
    if os.path.islink(pacdir):
        pacdir = os.readlink(pacdir)
        pacdir = os.path.join(build_root, pacdir)

    if os.path.exists(pacdir):
        (s_built, b_built) = get_built_files(pacdir, bi.buildtype)

        print()
        if s_built: print(s_built)
        print()
        print(b_built)

        if opts.keep_pkgs:
            for i in b_built.splitlines() + s_built.splitlines():
                shutil.copy2(i, os.path.join(opts.keep_pkgs, os.path.basename(i)))

    if bi_file:
        bi_file.close()
    if bc_file:
        bc_file.close()
    rpmlist_file.close()

# vim: sw=4 et
