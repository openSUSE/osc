# Copyright (C) 2006 Novell Inc.  All rights reserved.
# This program is free software; it may be used, copied, modified
# and distributed under the terms of the GNU General Public Licence,
# either version 2, or (at your option) any later version.

import sys, os
import urllib2
from urlgrabber.grabber import URLGrabError
from urlgrabber.mirror import MirrorGroup
from core import makeurl, streamfile
from util import packagequery, cpio
import conf
import tempfile
try:
    from meter import TextMeter
except:
    TextMeter = None


def join_url(self, base_url, rel_url):
    """to override _join_url of MirrorGroup, because we want to
    pass full URLs instead of base URL where relative_url is added later...
    IOW, we make MirrorGroup ignore relative_url"""
    return base_url

class OscFileGrabber:
    def __init__(self, progress_obj = None):
        self.progress_obj = progress_obj

    def urlgrab(self, url, filename, text = None, **kwargs):
        if url.startswith('file://'):
            file = url.replace('file://', '', 1)
            if os.path.isfile(file):
                return file
            else:
                raise URLGrabError(2, 'Local file \'%s\' does not exist' % file)
        f = open(filename, 'wb')
        try:
            try:
                for i in streamfile(url, progress_obj=self.progress_obj, text=text):
                    f.write(i)
            except urllib2.HTTPError, e:
                exc = URLGrabError(14, str(e))
                exc.url = url
                exc.exception = e
                exc.code = e.code
                raise exc
        finally:
            f.close()
        return filename

class Fetcher:
    def __init__(self, cachedir = '/tmp', api_host_options = {}, urllist = [], http_debug = False,
                 cookiejar = None, noinit = False, offline = False, enable_cpio = False):
        # set up progress bar callback
        if sys.stdout.isatty() and TextMeter:
            self.progress_obj = TextMeter(fo=sys.stdout)
        else:
            self.progress_obj = None

        self.cachedir = cachedir
        self.urllist = urllist
        self.http_debug = http_debug
        self.noinit = noinit
        self.offline = offline
        self.cpio = {}
        self.enable_cpio = enable_cpio

        passmgr = urllib2.HTTPPasswordMgrWithDefaultRealm()
        for host in api_host_options.keys():
            passmgr.add_password(None, host, api_host_options[host]['user'], api_host_options[host]['pass'])
        openers = (urllib2.HTTPBasicAuthHandler(passmgr), )
        if cookiejar:
            openers += (urllib2.HTTPCookieProcessor(cookiejar), )
        self.gr = OscFileGrabber(progress_obj=self.progress_obj)

    def failureReport(self, errobj):
        """failure output for failovers from urlgrabber"""
        if errobj.url.startswith('file://'):
            return {}
        print 'Trying openSUSE Build Service server for %s (%s), not found at %s.' \
              % (self.curpac, self.curpac.project, errobj.url.split('/')[2])
        return {}

    def fetch(self, pac, prefix=''):
        # for use by the failure callback
        self.curpac = pac

        if self.noinit or self.offline:
            return True

        MirrorGroup._join_url = join_url
        mg = MirrorGroup(self.gr, pac.urllist, failure_callback=(self.failureReport,(),{}))

        if self.http_debug:
            print
            print 'URLs to try for package \'%s\':' % pac
            print '\n'.join(pac.urllist)
            print

        (fd, tmpfile) = tempfile.mkstemp(prefix='osc_build')
        try:
            try:
                mg.urlgrab(pac.filename,
                           filename = tmpfile,
                           text = '%s(%s) %s' %(prefix, pac.project, pac.filename))
                self.move_package(tmpfile, pac.localdir, pac)
            except URLGrabError, e:
                if self.enable_cpio and e.errno == 256:
                    self.cpio.setdefault(pac.project, {})[pac.name] = pac
                    return
                print
                print >>sys.stderr, 'Error:', e.strerror
                print >>sys.stderr, 'Failed to retrieve %s from the following locations (in order):' % pac.filename
                print >>sys.stderr, '\n'.join(pac.urllist)
                sys.exit(1)
        finally:
            os.close(fd)
            if os.path.exists(tmpfile):
                os.unlink(tmpfile)

    def move_package(self, tmpfile, destdir, pac_obj = None):
        import shutil
        pkgq = packagequery.PackageQuery.query(tmpfile, extra_rpmtags=(1044, 1051, 1052))
        arch = pkgq.arch()
        # SOURCERPM = 1044
        if pkgq.filename_suffix == 'rpm' and not pkgq.gettag(1044):
            # NOSOURCE = 1051, NOPATCH = 1052
            if pkgq.gettag(1051) or pkgq.gettag(1052):
                arch = "nosrc"
            else:
                arch = "src"
        canonname = pkgq.canonname()
        fullfilename = os.path.join(destdir, canonname)
        if pac_obj is not None:
            pac_obj.filename = canonname
            pac_obj.fullfilename = fullfilename
        shutil.move(tmpfile, fullfilename)

    def dirSetup(self, pac):
        dir = os.path.join(self.cachedir, pac.localdir)
        if not os.path.exists(dir):
            try:
                os.makedirs(dir, mode=0755)
            except OSError, e:
                print >>sys.stderr, 'packagecachedir is not writable for you?'
                print >>sys.stderr, e
                sys.exit(1)

    def run(self, buildinfo):
        from urllib import quote_plus
        cached = 0
        all = len(buildinfo.deps)
        for i in buildinfo.deps:
            i.makeurls(self.cachedir, self.urllist)
            if os.path.exists(i.fullfilename):
                cached += 1
        miss = 0
        needed = all - cached
        if all:
            miss = 100.0 * needed / all
        print "%.1f%% cache miss. %d/%d dependencies cached.\n" % (miss, cached, all)
        done = 1
        for i in buildinfo.deps:
            i.makeurls(self.cachedir, self.urllist)
            if not os.path.exists(i.fullfilename):
                if self.offline:
                    print "Missing package '%s' in cache: --offline not possible." % i.fullfilename
                    sys.exit(1)
                self.dirSetup(i)
                try:
                    # if there isn't a progress bar, there is no output at all
                    if not self.progress_obj:
                        print '%d/%d (%s) %s' % (done, needed, i.project, i.filename)
                    self.fetch(i)
                    if self.progress_obj:
                        print "  %d/%d\r" % (done, needed),
                        sys.stdout.flush()

                except KeyboardInterrupt:
                    print 'Cancelled by user (ctrl-c)'
                    print 'Exiting.'
                    sys.exit(0)
                done += 1
        for project, pkgs in self.cpio.iteritems():
            repo = pkgs.values()[0].repository
            query = [ 'binary=%s' % quote_plus(i) for i in pkgs.keys() ]
            query.append('view=cpio')
            try:
                (fd, tmparchive) = tempfile.mkstemp(prefix='osc_build_cpio')
                (fd, tmpfile) = tempfile.mkstemp(prefix='osc_build')
                url = makeurl(buildinfo.apiurl,
                              ['public/build', project, repo, buildinfo.buildarch, '_repository'],
                              query=query)
                self.gr.urlgrab(url, filename = tmparchive, text = 'fetching cpio for \'%s\'' % project)
                archive = cpio.CpioRead(tmparchive)
                archive.read()
                for hdr in archive:
                    if hdr.filename == '.errors':
                        import oscerr
                        archive.copyin_file(hdr.filename)
                        raise oscerr.APIError('CPIO archive is incomplete (see .errors file)')
                    pac = pkgs[hdr.filename.rsplit('.', 1)[0]]
                    archive.copyin_file(hdr.filename, os.path.dirname(tmpfile), os.path.basename(tmpfile))
                    self.move_package(tmpfile, pac.localdir, pac)
            finally:
                if os.path.exists(tmparchive):
                    os.unlink(tmparchive)
                if os.path.exists(tmpfile):
                    os.unlink(tmpfile)

        prjs = buildinfo.projects.keys()
        for i in prjs:
            dest = "%s/%s" % (self.cachedir, i)
            if not os.path.exists(dest):
                os.makedirs(dest, mode=0755)
            dest += '/_pubkey'

            if os.path.exists(dest):
                buildinfo.keys.append(dest)
                buildinfo.prjkeys.append(i)
            else:
                url = "%s/source/%s/_pubkey" % (buildinfo.apiurl, i)
                try:
                    self.gr.urlgrab(url, dest, text="fetching key for %s" % i)
                    buildinfo.keys.append(dest)
                    buildinfo.prjkeys.append(i)
                except KeyboardInterrupt:
                    print 'Cancelled by user (ctrl-c)'
                    print 'Exiting.'
                    if os.path.exists(dest):
                        os.unlink(dest)
                    sys.exit(0)
                except URLGrabError, e:
                    if self.http_debug:
                        print "can't fetch key for %s: %s" %(i, e.strerror)
                        print "url: %s" % url
                    else:
                        print "%s doesn't have a gpg key" % i

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
    if saved_LC_ALL: os.environ['LC_ALL'] = saved_LC_ALL
    else: os.environ.pop('LC_ALL')

    for line in o.readlines():

        if not 'OK' in line:
            print
            print >>sys.stderr, 'The following package could not be verified:'
            print >>sys.stderr, line
            sys.exit(1)

        if 'NOT OK' in line:
            print
            print >>sys.stderr, 'The following package could not be verified:'
            print >>sys.stderr, line

            if 'MISSING KEYS' in line:
                missing_key = line.split('#')[-1].split(')')[0]

                print >>sys.stderr, """
- If the key is missing, install it first.
  For example, do the following:
    osc signkey PROJECT > file
  and, as root:
    rpm --import %(dir)s/keyfile-%(name)s

  Then, just start the build again.

- If you do not trust the packages, you should configure osc build for XEN or KVM

- You may use --no-verify to skip the verification (which is a risk for your system).
""" % {'name': missing_key,
       'dir': os.path.expanduser('~')}

            else:
                print >>sys.stderr, """
- If the signature is wrong, you may try deleting the package manually
  and re-run this program, so it is fetched again.
"""

            sys.exit(1)


def verify_pacs(pac_list, key_list):
    """Take a list of rpm filenames and verify their signatures.

       In case of failure, exit.
       """

    # XXX: remove if new code stable
    if not conf.config.get('builtin_signature_check', False):
        return verify_pacs_old(pac_list)

    if not pac_list:
        return

    if not key_list:
        print "no keys"
        sys.exit(1)
        return

    print key_list

    import checker
    failed = False
    checker = checker.Checker()
    try:
        checker.readkeys(key_list)
        for pkg in pac_list:
            try:
                checker.check(pkg)
            except Exception, e:
                failed = True
                print pkg, ':', e
    except:
        checker.cleanup()
        raise

    if failed:
        checker.cleanup()
        sys.exit(1)

    checker.cleanup()

# vim: sw=4 et
