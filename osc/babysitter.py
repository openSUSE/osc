# Copyright (C) 2008 Novell Inc.  All rights reserved.
# This program is free software; it may be used, copied, modified
# and distributed under the terms of the GNU General Public Licence,
# either version 2, or (at your option) any later version.

from __future__ import print_function

import errno
import os.path
import pdb
import sys
import signal
import traceback

from osc import oscerr
from .oscsslexcp import NoSecureSSLError
from osc.util.cpio import CpioError
from osc.util.packagequery import PackageError
from osc.util.helper import decode_it

try:
    from M2Crypto.SSL.Checker import SSLVerificationError
    from M2Crypto.SSL import SSLError as SSLError
except:
    SSLError = None
    SSLVerificationError = None

try:
    # import as RPMError because the class "error" is too generic
    from rpm import error as RPMError
except:
    # if rpm-python isn't installed (we might be on a debian system):
    class RPMError(Exception):
        pass

try:
    from http.client import HTTPException, BadStatusLine
    from urllib.error import URLError, HTTPError
except ImportError:
    #python 2.x
    from httplib import HTTPException, BadStatusLine
    from urllib2 import URLError, HTTPError

# the good things are stolen from Matt Mackall's mercurial


def catchterm(*args):
    raise oscerr.SignalInterrupt

for name in 'SIGBREAK', 'SIGHUP', 'SIGTERM':
    num = getattr(signal, name, None)
    if num:
        signal.signal(num, catchterm)


def run(prg, argv=None):
    try:
        try:
            if '--debugger' in sys.argv:
                pdb.set_trace()
            # here we actually run the program:
            return prg.main(argv)
        except:
            # look for an option in the prg.options object and in the config
            # dict print stack trace, if desired
            if getattr(prg.options, 'traceback', None) or getattr(prg.conf, 'config', {}).get('traceback', None) or \
               getattr(prg.options, 'post_mortem', None) or getattr(prg.conf, 'config', {}).get('post_mortem', None):
                traceback.print_exc(file=sys.stderr)
                # we could use http://aspn.activestate.com/ASPN/Cookbook/Python/Recipe/52215
            # enter the debugger, if desired
            if getattr(prg.options, 'post_mortem', None) or getattr(prg.conf, 'config', {}).get('post_mortem', None):
                if sys.stdout.isatty() and not hasattr(sys, 'ps1'):
                    pdb.post_mortem(sys.exc_info()[2])
                else:
                    print('sys.stdout is not a tty. Not jumping into pdb.', file=sys.stderr)
            raise
    except oscerr.SignalInterrupt:
        print('killed!', file=sys.stderr)
    except KeyboardInterrupt:
        print('interrupted!', file=sys.stderr)
        return 130
    except oscerr.UserAbort:
        print('aborted.', file=sys.stderr)
    except oscerr.APIError as e:
        print('BuildService API error:', e.msg, file=sys.stderr)
    except oscerr.LinkExpandError as e:
        print('Link "%s/%s" cannot be expanded:\n' % (e.prj, e.pac), e.msg, file=sys.stderr)
        print('Use "osc repairlink" to fix merge conflicts.\n', file=sys.stderr)
    except oscerr.WorkingCopyWrongVersion as e:
        print(e, file=sys.stderr)
    except oscerr.NoWorkingCopy as e:
        print(e, file=sys.stderr)
        if os.path.isdir('.git'):
            print("Current directory looks like git.", file=sys.stderr)
        if os.path.isdir('.hg'):
            print("Current directory looks like mercurial.", file=sys.stderr)
        if os.path.isdir('.svn'):
            print("Current directory looks like svn.", file=sys.stderr)
        if os.path.isdir('CVS'):
            print("Current directory looks like cvs.", file=sys.stderr)
    except HTTPError as e:
        print('Server returned an error:', e, file=sys.stderr)
        if hasattr(e, 'osc_msg'):
            print(e.osc_msg, file=sys.stderr)

        try:
            body = e.read()
        except AttributeError:
            body = ''

        if getattr(prg.options, 'debug', None) or \
           getattr(prg.conf, 'config', {}).get('debug', None):
            print(e.hdrs, file=sys.stderr)
            print(body, file=sys.stderr)

        if e.code in [400, 403, 404, 500]:
            if b'<summary>' in body:
                msg = body.split(b'<summary>')[1]
                msg = msg.split(b'</summary>')[0]
                msg = msg.replace(b'&lt;', b'<').replace(b'&gt;' , b'>').replace(b'&amp;', b'&')
                print(decode_it(msg), file=sys.stderr)
        if e.code >= 500 and e.code <= 599:
            print('\nRequest: %s' % e.filename)
            print('Headers:')
            for h, v in e.hdrs.items():
                if h != 'Set-Cookie':
                    print("%s: %s" % (h, v))

    except BadStatusLine as e:
        print('Server returned an invalid response:', e, file=sys.stderr)
        print(e.line, file=sys.stderr)
    except HTTPException as e:
        print(e, file=sys.stderr)
    except URLError as e:
        print('Failed to reach a server:\n', e.reason, file=sys.stderr)
    except IOError as e:
        # ignore broken pipe
        if e.errno != errno.EPIPE:
            raise
    except OSError as e:
        if e.errno != errno.ENOENT:
            raise
        print(e, file=sys.stderr)
    except (oscerr.ConfigError, oscerr.NoConfigfile) as e:
        print(e.msg, file=sys.stderr)
    except oscerr.OscIOError as e:
        print(e.msg, file=sys.stderr)
        if getattr(prg.options, 'debug', None) or \
           getattr(prg.conf, 'config', {}).get('debug', None):
            print(e.e, file=sys.stderr)
    except (oscerr.WrongOptions, oscerr.WrongArgs) as e:
        print(e, file=sys.stderr)
        return 2
    except oscerr.ExtRuntimeError as e:
        print(e.file + ':', e.msg, file=sys.stderr)
    except oscerr.ServiceRuntimeError as e:
        print(e.msg, file=sys.stderr)
    except oscerr.WorkingCopyOutdated as e:
        print(e, file=sys.stderr)
    except (oscerr.PackageExists, oscerr.PackageMissing, oscerr.WorkingCopyInconsistent) as e:
        print(e.msg, file=sys.stderr)
    except oscerr.PackageInternalError as e:
        print('a package internal error occured\n' \
            'please file a bug and attach your current package working copy ' \
            'and the following traceback to it:', file=sys.stderr)
        print(e.msg, file=sys.stderr)
        traceback.print_exc(file=sys.stderr)
    except oscerr.PackageError as e:
        print(e.msg, file=sys.stderr)
    except PackageError as e:
        print('%s:' % e.fname, e.msg, file=sys.stderr)
    except RPMError as e:
        print(e, file=sys.stderr)
    except SSLError as e:
        if 'tlsv1' in str(e):
            print('The python on this system does not support TLSv1.2', file=sys.stderr)
        print("SSL Error:", e, file=sys.stderr)
    except SSLVerificationError as e:
        print("Certificate Verification Error:", e, file=sys.stderr)
    except NoSecureSSLError as e:
        print(e, file=sys.stderr)
    except CpioError as e:
        print(e, file=sys.stderr)
    except oscerr.OscBaseError as e:
        print('*** Error:', e, file=sys.stderr)
    return 1

# vim: sw=4 et
