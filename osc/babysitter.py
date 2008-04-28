#!/usr/bin/python

# Copyright (C) 2008 Peter Poeml / Novell Inc.  All rights reserved.
# This program is free software; it may be used, copied, modified
# and distributed under the terms of the GNU General Public Licence,
# either version 2, or (at your option) any later version.

import sys
import signal
from osc import oscerr
from urllib2 import URLError, HTTPError

# the good things are stolen from Matt Mackall's mercurial

def catchterm(*args):
    raise oscerr.SignalInterrupt

for name in 'SIGBREAK', 'SIGHUP', 'SIGTERM':
    num = getattr(signal, name, None)
    if num: signal.signal(num, catchterm)


def run(prg):

    try:

        try:
            if '--debugger' in sys.argv:
                import pdb
                pdb.set_trace()

            # here we actually run the program:
            return prg.main()

        except:
            # look for an option in the prg.options object and in the config dict
            # print stack trace, if desired
            if getattr(prg.options, 'traceback', None) or getattr(prg.conf, 'config', {}).get('traceback', None) or \
               getattr(prg.options, 'post_mortem', None) or getattr(prg.conf, 'config', {}).get('post_mortem', None):
                import traceback
                traceback.print_exc(file=sys.stderr)
                # we could use http://aspn.activestate.com/ASPN/Cookbook/Python/Recipe/52215

            # enter the debugger, if desired
            if getattr(prg.options, 'post_mortem', None) or getattr(prg.conf, 'config', {}).get('post_mortem', None):
                if sys.stdout.isatty() and not hasattr(sys, 'ps1'):
                    import pdb
                    pdb.post_mortem(sys.exc_info()[2])
                else:
                    print >>sys.stderr, 'sys.stdout is not a tty. Not jumping into pdb.'
            raise

    except oscerr.SignalInterrupt:
        print >>sys.stderr, 'killed!'
        return 1

    except KeyboardInterrupt:
        print >>sys.stderr, 'interrupted!'
        return 1

    except oscerr.UnreadableFile, e:
        print >>sys.stderr, e.msg
        return 1

    except (oscerr.NoWorkingCopy, oscerr.WorkingCopyWrongVersion), e:
        print >>sys.stderr, e
        return 1

    except HTTPError, e:
        print >>sys.stderr, 'Server returned an error:', e
        if hasattr(e, 'osc_msg'):
            print >>sys.stderr, e.osc_msg

        if getattr(prg.options, 'debug', None) or \
           getattr(prg.conf, 'config', {}).get('debug', None):
                print >>sys.stderr, e.hdrs
                print >>sys.stderr, e.read()

        # For 404s, check out _which_ part was not found
        #
        # It is very ugly, but may be Good for pragmatic reasons
        #
        # FIXME this can be obsoleted when the api returns a more specific error code
        #       like "project not found" right away
        if e.code == 404:
            import urlparse
            scheme, netloc, path = urlparse.urlsplit(e.url)[0:3]
            parts = path.split('/')
            # we know how to do this for /source URLs. I don't know for others right now...
            if len(parts) > 1 and parts[1] == 'source':
                if len(parts) == 3:
                    # it was a request on /source/project
                    print >>sys.stderr, 'A project named \'%s\' does not exist.' % parts[2]
                if len(parts) == 4:
                    # it was a request on /source/project/package
                    prjurl = urlparse.urlunsplit((scheme, netloc, '/'.join(parts[:3]), None, None))
                    import osc.core
                    try:
                        osc.core.http_GET(prjurl)
                    except:
                        print >>sys.stderr, 'A project named \'%s\' does not exist.' % parts[2]
                    else:
                        print >>sys.stderr, \
                              'A package named \'%s\' does not exist in project \'%s\'.' \
                              % (parts[3], parts[2])
                else:
                    # not handled...
                    pass

        return 1

    except URLError, e:
        print >>sys.stderr, 'Failed to reach a server:', e.reason
        return 1

    except (oscerr.ConfigError, oscerr.NoConfigfile), e:
        print >>sys.stderr, e.msg
        return 1

    except oscerr.OscIOError, e:
        print >>sys.stderr, e.msg
        if getattr(prg.options, 'debug', None) or \
           getattr(prg.conf, 'config', {}).get('debug', None):
                print >>sys.stderr, e.e
        return 1

    except (oscerr.WrongOptions, oscerr.WrongArgs), e:
        print >>sys.stderr, e
        return 2

    except oscerr.WorkingCopyOutdated, e:
        print >>sys.stderr, e
        return 1

    except (oscerr.PackageExists, oscerr.PackageMissing), e:
        print >>sys.stderr, e.msg
        return 1

    except IOError, e:
        print >>sys.stderr, e
        return 1

    except AttributeError, e:
        print >>sys.stderr, e
        return 1
