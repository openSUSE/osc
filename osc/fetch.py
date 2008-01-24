#!/usr/bin/python

# Copyright (C) 2006 Peter Poeml / Novell Inc.  All rights reserved.
# This program is free software; it may be used, copied, modified
# and distributed under the terms of the GNU General Public Licence,
# either version 2, or (at your option) any later version.

import sys, os
import urllib2
from urlgrabber.grabber import URLGrabber, URLGrabError
from urlgrabber.mirror import MirrorGroup
try:
    from meter import TextMeter
except:
    TextMeter = None


def join_url(self, base_url, rel_url):
    """to override _join_url of MirrorGroup, because we want to
    pass full URLs instead of base URL where relative_url is added later...
    IOW, we make MirrorGroup ignore relative_url""" 
    return base_url


class Fetcher:
    def __init__(self, cachedir = '/tmp', auth_dict = {}, urllist = [], http_debug = False):

        __version__ = '0.1'
        __user_agent__ = 'osbuild/%s' % __version__

        # set up progress bar callback
        if sys.stdout.isatty() and TextMeter:
            self.progress_obj = TextMeter(fo=sys.stdout)
        else:
            self.progress_obj = None


        self.cachedir = cachedir
        self.urllist = urllist
        self.http_debug = http_debug

        passmgr = urllib2.HTTPPasswordMgrWithDefaultRealm()
        for host in auth_dict.keys():
            passmgr.add_password(None, host, auth_dict[host]['user'], auth_dict[host]['pass'])
        authhandler = urllib2.HTTPBasicAuthHandler(passmgr)
        self.gr = URLGrabber(user_agent=__user_agent__,
                            keepalive=1,
                            opener = urllib2.build_opener(authhandler),
                            progress_obj=self.progress_obj,
                            failure_callback=(self.failureReport,(),{}),
                            )


    def failureReport(self, errobj):
        """failure output for failovers from urlgrabber"""

        #log(0, '%s: %s' % (errobj.url, str(errobj.exception)))
        #log(0, 'Trying other mirror.')
        print 'Trying upstream server for %s (%s), since it is not on %s.' \
                % (self.curpac, self.curpac.project, errobj.url.split('/')[2])
        raise errobj.exception


    def fetch(self, pac):
        # for use by the failure callback
        self.curpac = pac

        MirrorGroup._join_url = join_url
        mg = MirrorGroup(self.gr, pac.urllist)

        if self.http_debug:
            print
            print 'URLs to try for package \'%s\':' % pac
            print '\n'.join(pac.urllist)
            print

        try:
            # it returns the filename
            ret = mg.urlgrab(pac.filename, 
                             filename=pac.fullfilename, 
                             text = '(%s) %s' %(pac.project, pac.filename))

        except URLGrabError, e:
            print
            print >>sys.stderr, 'Error:', e.strerror
            print >>sys.stderr, 'Failed to retrieve %s from the following locations (in order):' % pac.filename
            print >>sys.stderr, '\n'.join(pac.urllist)

            sys.exit(1)
        

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
        for i in buildinfo.deps:
            i.makeurls(self.cachedir, self.urllist)

            if os.path.exists(os.path.join(i.localdir, i.fullfilename)):
                #print 'cached:', i.fullfilename
                pass
            else:
                self.dirSetup(i)

                try:
                    # if there isn't a progress bar, there is no output at all
                    if not self.progress_obj:
                        print '(%s) %s' % (i.project, i.filename)
                    self.fetch(i)

                except KeyboardInterrupt:
                    print 'Cancelled by user (ctrl-c)'
                    print 'Exiting.'
                    if os.path.exists(i.fullfilename):
                        print 'Cleaning up incomplete file', i.fullfilename
                        os.unlink(i.fullfilename)
                    sys.exit(0)



def verify_pacs(pac_list):
    """Take a list of rpm filenames and run rpm -K on them. 

       In case of failure, exit.

       Check all packages in one go, since this takes only 6 seconds on my Athlon 700
       instead of 20 when calling 'rpm -K' for each of them.
       """


    if not pac_list:
        return
        
    # we can use os.popen4 because we don't care about the return value.
    # we check the output anyway, and rpm always writes to stdout.

    # save locale first (we rely on English rpm output here)
    saved_LC_ALL = os.environ.get('LC_ALL')
    os.environ['LC_ALL'] = 'en_EN'

    (i, o) = os.popen4(['/bin/rpm', '-K'] + pac_list)

    # restore locale
    if saved_LC_ALL: os.environ['LC_ALL'] = saved_LC_ALL;
    else: os.environ.pop('LC_ALL')

    i.close()

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
    gpg --keyserver pgp.mit.edu --recv-keys %(name)s
    gpg --armor --export %(name)s > %(dir)s/keyfile-%(name)s
  and, as root:
    rpm --import %(dir)s/keyfile-%(name)s

  Then, just start the build again.

- If the key is unavailable, you may use --no-verify (which may pose a risk).
""" % {'name': missing_key, 
       'dir': os.path.expanduser('~')}

            else:
                print >>sys.stderr, """
- If the signature is wrong, you may try deleting the package manually
  and re-run this program, so it is fetched again.
"""

            sys.exit(1)


