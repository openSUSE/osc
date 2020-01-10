# Copyright (C) 2006 Novell Inc.  All rights reserved.
# This program is free software; it may be used, copied, modified
# and distributed under the terms of the GNU General Public Licence,
# either version 2, or (at your option) any later version.

from __future__ import print_function

import sys, os

try:
    from urllib.parse import quote_plus
    from urllib.request import HTTPBasicAuthHandler, HTTPCookieProcessor, HTTPPasswordMgrWithDefaultRealm, HTTPError
except ImportError:
    #python 2.x
    from urllib import quote_plus
    from urllib2 import HTTPBasicAuthHandler, HTTPCookieProcessor, HTTPPasswordMgrWithDefaultRealm, HTTPError

from .core import makeurl, streamfile, dgst
from .grabber import OscFileGrabber, OscMirrorGroup
from .util import packagequery, cpio
from . import conf
from . import oscerr
import tempfile
import re

from osc.util.helper import decode_it
from .meter import create_text_meter

class Fetcher:
    def __init__(self, cachedir='/tmp', api_host_options={}, urllist=[],
                 http_debug=False, cookiejar=None, offline=False,
                 enable_cpio=True, modules=[]):
        # set up progress bar callback
        self.progress_obj = None
        if sys.stdout.isatty():
            self.progress_obj = create_text_meter(use_pb_fallback=False)

        self.cachedir = cachedir
        self.urllist = urllist
        self.modules = modules
        self.http_debug = http_debug
        self.offline = offline
        self.cpio = {}
        self.enable_cpio = enable_cpio

        passmgr = HTTPPasswordMgrWithDefaultRealm()
        for host in api_host_options:
            passmgr.add_password(None, host, api_host_options[host]['user'],
                                 api_host_options[host]['pass'])
        openers = (HTTPBasicAuthHandler(passmgr), )
        if cookiejar:
            openers += (HTTPCookieProcessor(cookiejar), )
        self.gr = OscFileGrabber(progress_obj=self.progress_obj)

    def __add_cpio(self, pac):
        prpap = '%s/%s/%s/%s' % (pac.project, pac.repository, pac.repoarch, pac.repopackage)
        self.cpio.setdefault(prpap, {})[pac.repofilename] = pac

    def __download_cpio_archive(self, apiurl, project, repo, arch, package, **pkgs):
        if not pkgs:
            return
        query = ['binary=%s' % quote_plus(i) for i in pkgs]
        query.append('view=cpio')
        for module in self.modules:
            query.append('module=' + module)
        try:
            url = makeurl(apiurl, ['build', project, repo, arch, package], query=query)
            sys.stdout.write("preparing download ...\r")
            sys.stdout.flush()
            with tempfile.NamedTemporaryFile(prefix='osc_build_cpio') as tmparchive:
                self.gr.urlgrab(url, filename=tmparchive.name,
                                text='fetching packages for \'%s\'' % project)
                archive = cpio.CpioRead(tmparchive.name)
                archive.read()
                for hdr in archive:
                    # XXX: we won't have an .errors file because we're using
                    # getbinarylist instead of the public/... route
                    # (which is routed to getbinaries)
                    # getbinaries does not support kiwi builds
                    if hdr.filename == b'.errors':
                        archive.copyin_file(hdr.filename)
                        raise oscerr.APIError('CPIO archive is incomplete '
                                              '(see .errors file)')
                    if package == '_repository':
                        n = re.sub(b'\.pkg\.tar\.(zst|.z)$', b'.arch', hdr.filename)
                        if n.startswith(b'container:'):
                            n = re.sub(b'\.tar\.(zst|.z)$', b'.tar', hdr.filename)
                            pac = pkgs[decode_it(n.rsplit(b'.', 1)[0])]
                            pac.canonname = hdr.filename
                        else:
                            pac = pkgs[decode_it(n.rsplit(b'.', 1)[0])]
                    else:
                        # this is a kiwi product
                        pac = pkgs[decode_it(hdr.filename)]

                    # Extract a single file from the cpio archive
                    try:
                        fd, tmpfile = tempfile.mkstemp(prefix='osc_build_file')
                        archive.copyin_file(hdr.filename,
                                            os.path.dirname(tmpfile),
                                            os.path.basename(tmpfile))
                        self.move_package(tmpfile, pac.localdir, pac)
                    finally:
                        os.close(fd)
                        if os.path.exists(tmpfile):
                            os.unlink(tmpfile)

                for pac in pkgs.values():
                    if not os.path.isfile(pac.fullfilename):
                        raise oscerr.APIError('failed to fetch file \'%s\': '
                                              'missing in CPIO archive' %
                                              pac.repofilename)
        except HTTPError as e:
            if e.code != 414:
                raise
            # query str was too large
            keys = list(pkgs.keys())
            if len(keys) == 1:
                raise oscerr.APIError('unable to fetch cpio archive: '
                                      'server always returns code 414')
            n = int(len(pkgs) / 2)
            new_pkgs = dict([(k, pkgs[k]) for k in keys[:n]])
            self.__download_cpio_archive(apiurl, project, repo, arch,
                                         package, **new_pkgs)
            new_pkgs = dict([(k, pkgs[k]) for k in keys[n:]])
            self.__download_cpio_archive(apiurl, project, repo, arch,
                                         package, **new_pkgs)

    def __fetch_cpio(self, apiurl):
        for prpap, pkgs in self.cpio.items():
            project, repo, arch, package = prpap.split('/', 3)
            self.__download_cpio_archive(apiurl, project, repo, arch, package, **pkgs)

    def fetch(self, pac, prefix=''):
        # for use by the failure callback
        self.curpac = pac

        mg = OscMirrorGroup(self.gr, pac.urllist)

        if self.http_debug:
            print('\nURLs to try for package \'%s\':' % pac, file=sys.stderr)
            print('\n'.join(pac.urllist), file=sys.stderr)
            print(file=sys.stderr)

        try:
            with tempfile.NamedTemporaryFile(prefix='osc_build',
                                             delete=False) as tmpfile:
                mg_stat = mg.urlgrab(pac.filename, filename=tmpfile.name,
                           text='%s(%s) %s' % (prefix, pac.project, pac.filename))
                if mg_stat:
                    self.move_package(tmpfile.name, pac.localdir, pac)

            if not mg_stat:
                if self.enable_cpio:
                    print('%s/%s: attempting download from api, since not found'
                          % (pac.project, pac.name))
                    self.__add_cpio(pac)
                    return
                print()
                print('Error: Failed to retrieve %s from the following locations '
                      '(in order):' % pac.filename, file=sys.stderr)
                print('\n'.join(pac.urllist), file=sys.stderr)
                sys.exit(1)
        finally:
            if os.path.exists(tmpfile.name):
                os.unlink(tmpfile.name)

    def move_package(self, tmpfile, destdir, pac_obj=None):
        import shutil
        canonname = None
        if pac_obj and pac_obj.name.startswith('container:'):
            canonname = pac_obj.canonname
        if canonname is None:
            pkgq = packagequery.PackageQuery.query(tmpfile, extra_rpmtags=(1044, 1051, 1052))
            if pkgq:
                canonname = pkgq.canonname()
            else:
                if pac_obj is None:
                    print('Unsupported file type: ', tmpfile, file=sys.stderr)
                    sys.exit(1)
                canonname = pac_obj.binary

        fullfilename = os.path.join(destdir, decode_it(canonname))
        if pac_obj is not None:
            pac_obj.canonname = canonname
            pac_obj.fullfilename = fullfilename
        shutil.move(tmpfile, fullfilename)
        os.chmod(fullfilename, 0o644)

    def dirSetup(self, pac):
        dir = os.path.join(self.cachedir, pac.localdir)
        if not os.path.exists(dir):
            try:
                os.makedirs(dir, mode=0o755)
            except OSError as e:
                print('packagecachedir is not writable for you?', file=sys.stderr)
                print(e, file=sys.stderr)
                sys.exit(1)

    def run(self, buildinfo):
        cached = 0
        all = len(buildinfo.deps)
        for i in buildinfo.deps:
            i.makeurls(self.cachedir, self.urllist)
            # find container extension by looking in the cache
            if i.name.startswith('container:') and i.fullfilename.endswith('.tar.xz'):
                for ext in ['.tar.xz', '.tar.gz', '.tar']:
                    if os.path.exists(i.fullfilename[:-7] + ext):
                        i.canonname = i.canonname[:-7] + ext
                        i.makeurls(self.cachedir, self.urllist)

            if os.path.exists(i.fullfilename):
                cached += 1
                if i.hdrmd5:
                    from .util import packagequery
                    if i.name.startswith('container:'):
                        hdrmd5 = dgst(i.fullfilename)
                    else:
                        hdrmd5 = packagequery.PackageQuery.queryhdrmd5(i.fullfilename)
                    if not hdrmd5 or hdrmd5 != i.hdrmd5:
                        os.unlink(i.fullfilename)
                        cached -= 1
        miss = 0
        needed = all - cached
        if all:
            miss = 100.0 * needed / all
        print("%.1f%% cache miss. %d/%d dependencies cached.\n" % (miss, cached, all))
        done = 1
        for i in buildinfo.deps:
            i.makeurls(self.cachedir, self.urllist)
            if not os.path.exists(i.fullfilename):
                if self.offline:
                    raise oscerr.OscIOError(None,
                                            'Missing \'%s\' in cache: '
                                            '--offline not possible.' %
                                            i.fullfilename)
                self.dirSetup(i)
                if i.hdrmd5 and self.enable_cpio:
                    self.__add_cpio(i)
                    done += 1
                    continue
                try:
                    # if there isn't a progress bar, there is no output at all
                    prefix = ''
                    if not self.progress_obj:
                        print('%d/%d (%s) %s' % (done, needed, i.project, i.filename))
                    else:
                        prefix = '[%d/%d] ' % (done, needed)
                    self.fetch(i, prefix=prefix)

                except KeyboardInterrupt:
                    print('Cancelled by user (ctrl-c)')
                    print('Exiting.')
                    sys.exit(0)
                done += 1

        self.__fetch_cpio(buildinfo.apiurl)

        prjs = list(buildinfo.projects.keys())
        for i in prjs:
            dest = "%s/%s" % (self.cachedir, i)
            if not os.path.exists(dest):
                os.makedirs(dest, mode=0o755)
            dest += '/_pubkey'

            url = makeurl(buildinfo.apiurl, ['source', i, '_pubkey'])
            try_parent = False
            try:
                if self.offline and not os.path.exists(dest):
                    # may need to try parent
                    try_parent = True
                elif not self.offline:
                    OscFileGrabber().urlgrab(url, dest)
                # not that many keys usually
                if i not in buildinfo.prjkeys and not try_parent:
                    buildinfo.keys.append(dest)
                    buildinfo.prjkeys.append(i)
            except KeyboardInterrupt:
                print('Cancelled by user (ctrl-c)')
                print('Exiting.')
                if os.path.exists(dest):
                    os.unlink(dest)
                sys.exit(0)
            except HTTPError as e:
                # Not found is okay, let's go to the next project
                if e.code != 404:
                    print("Invalid answer from server", e, file=sys.stderr)
                    sys.exit(1)
                try_parent = True

            if try_parent:
                if self.http_debug:
                    print("can't fetch key for %s" % (i), file=sys.stderr)
                    print("url: %s" % url, file=sys.stderr)

                if os.path.exists(dest):
                    os.unlink(dest)

                l = i.rsplit(':', 1)
                # try key from parent project
                if len(l) > 1 and l[1] and not l[0] in buildinfo.projects:
                    prjs.append(l[0])


def verify_pacs_old(pac_list):
    """Take a list of rpm filenames and run rpm -K on them.

       In case of failure, exit.

       Check all packages in one go, since this takes only 6 seconds on my Athlon 700
       instead of 20 when calling 'rpm -K' for each of them.
       """
    import subprocess

    if not pac_list:
        return

    # don't care about the return value because we check the
    # output anyway, and rpm always writes to stdout.

    # save locale first (we rely on English rpm output here)
    saved_LC_ALL = os.environ.get('LC_ALL')
    os.environ['LC_ALL'] = 'en_EN'

    o = subprocess.Popen(['rpm', '-K'] + pac_list, stdout=subprocess.PIPE,
                         stderr=subprocess.STDOUT, close_fds=True).stdout

    # restore locale
    if saved_LC_ALL:
        os.environ['LC_ALL'] = saved_LC_ALL
    else:
        os.environ.pop('LC_ALL')

    for line in o.readlines():

        if 'OK' not in line:
            print()
            print('The following package could not be verified:', file=sys.stderr)
            print(line, file=sys.stderr)
            sys.exit(1)

        if 'NOT OK' in line:
            print()
            print('The following package could not be verified:', file=sys.stderr)
            print(line, file=sys.stderr)

            if 'MISSING KEYS' in line:
                missing_key = line.split('#')[-1].split(')')[0]

                print("""
- If the key (%(name)s) is missing, install it first.
  For example, do the following:
    osc signkey PROJECT > file
  and, as root:
    rpm --import %(dir)s/keyfile-%(name)s

  Then, just start the build again.

- If you do not trust the packages, you should configure osc build for XEN or KVM

- You may use --no-verify to skip the verification (which is a risk for your system).
""" % {'name': missing_key,
       'dir': os.path.expanduser('~')}, file=sys.stderr)

            else:
                print("""
- If the signature is wrong, you may try deleting the package manually
  and re-run this program, so it is fetched again.
""", file=sys.stderr)

            sys.exit(1)


def verify_pacs(bi):
    """Take a list of rpm filenames and verify their signatures.

       In case of failure, exit.
       """

    pac_list = [i.fullfilename for i in bi.deps]
    if conf.config['builtin_signature_check'] is not True:
        return verify_pacs_old(pac_list)

    if not pac_list:
        return

    if not bi.keys:
        raise oscerr.APIError("can't verify packages due to lack of GPG keys")

    print("using keys from", ', '.join(bi.prjkeys))

    from . import checker
    failed = False
    checker = checker.Checker()
    try:
        checker.readkeys(bi.keys)
        for pkg in pac_list:
            try:
                checker.check(pkg)
            except Exception as e:
                failed = True
                print(pkg, ':', e)
    except:
        checker.cleanup()
        raise

    if failed:
        checker.cleanup()
        sys.exit(1)

    checker.cleanup()

# vim: sw=4 et
