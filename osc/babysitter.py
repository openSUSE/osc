# Copyright (C) 2008 Novell Inc.  All rights reserved.
# This program is free software; it may be used, copied, modified
# and distributed under the terms of the GNU General Public Licence,
# either version 2, or (at your option) any later version.


import errno
import os
import pdb
import signal
import ssl
import sys
import traceback
from http.client import HTTPException, BadStatusLine
from urllib.error import URLError, HTTPError

import urllib3.exceptions

from . import _private
from . import commandline
from . import conf as osc_conf
from . import core as osc_core
from . import oscerr
from .OscConfigParser import configparser
from .oscssl import CertVerificationError
from .util.cpio import CpioError
from .util.helper import decode_it
from .util.packagequery import PackageError

try:
    # import as RPMError because the class "error" is too generic
    # pylint: disable=E0611
    from rpm import error as RPMError
except:
    # if rpm-python isn't installed (we might be on a debian system):
    class RPMError(Exception):
        pass


try:
    from keyring.errors import KeyringLocked
except ImportError:
    # python-keyring is not installed
    class KeyringLocked(Exception):
        pass


# the good things are stolen from Matt Mackall's mercurial


def catchterm(*args):
    raise oscerr.SignalInterrupt


# Signals which should terminate the program safely
for name in 'SIGBREAK', 'SIGHUP', 'SIGTERM':
    num = getattr(signal, name, None)
    if num:
        signal.signal(num, catchterm)


def run(prg, argv=None):
    try:
        try:
            # we haven't parsed options yet, that's why we rely on argv directly
            if "--debugger" in (argv or sys.argv[1:]):
                pdb.set_trace()
            # here we actually run the program
            prg.main(argv)
            return 0
        except:
            # If any of these was set via the command-line options,
            # the config values are expected to be changed accordingly.
            # That's why we're working only with the config.
            if osc_conf.config["traceback"] or osc_conf.config["post_mortem"]:
                traceback.print_exc(file=sys.stderr)
                # we could use http://aspn.activestate.com/ASPN/Cookbook/Python/Recipe/52215
            # enter the debugger, if desired
            if osc_conf.config["post_mortem"]:
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
        print(f'Link "{e.prj}/{e.pac}" cannot be expanded:\n', e.msg, file=sys.stderr)
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

        if osc_conf.config["debug"]:
            print(e.hdrs, file=sys.stderr)
            print(body, file=sys.stderr)

        if e.code in [400, 403, 404, 500]:
            if b'<summary>' in body:
                msg = body.split(b'<summary>')[1]
                msg = msg.split(b'</summary>')[0]
                msg = _private.api.xml_unescape(msg)
                print(decode_it(msg), file=sys.stderr)
        if e.code >= 500 and e.code <= 599:
            print(f'\nRequest: {e.filename}')
            print('Headers:')
            for h, v in e.hdrs.items():
                if h != 'Set-Cookie':
                    print(f"{h}: {v}")

    except BadStatusLine as e:
        print('Server returned an invalid response:', e, file=sys.stderr)
        print(e.line, file=sys.stderr)
    except HTTPException as e:
        print(e, file=sys.stderr)
    except URLError as e:
        msg = 'Failed to reach a server'
        if hasattr(e, '_osc_host_port'):
            msg += f' ({e._osc_host_port})'
        msg += ':\n'
        print(msg, e.reason, file=sys.stderr)
    except ssl.SSLError as e:
        if 'tlsv1' in str(e):
            print('The python on this system or the server does not support TLSv1.2', file=sys.stderr)
        print("SSL Error:", e, file=sys.stderr)
    except OSError as e:
        # ignore broken pipe
        if e.errno != errno.EPIPE:
            raise
    except OSError as e:
        if e.errno != errno.ENOENT:
            raise
        print(e, file=sys.stderr)
    except (oscerr.ConfigError, oscerr.NoConfigfile) as e:
        print(e, file=sys.stderr)
    except configparser.Error as e:
        print(e.message, file=sys.stderr)
    except oscerr.OscIOError as e:
        print(e.msg, file=sys.stderr)
        if osc_conf.config["debug"]:
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
        print('a package internal error occured\n'
              'please file a bug and attach your current package working copy '
              'and the following traceback to it:', file=sys.stderr)
        print(e.msg, file=sys.stderr)
        traceback.print_exc(file=sys.stderr)
    except oscerr.PackageError as e:
        print(e.msg, file=sys.stderr)
    except PackageError as e:
        print(f'{e.fname}:', e.msg, file=sys.stderr)
    except RPMError as e:
        print(e, file=sys.stderr)
    except KeyringLocked as e:
        print(e, file=sys.stderr)
    except CertVerificationError as e:
        print(e, file=sys.stderr)
    except urllib3.exceptions.MaxRetryError as e:
        print(e.reason, file=sys.stderr)
    except urllib3.exceptions.ProtocolError as e:
        print(e.args[0], file=sys.stderr)
    except CpioError as e:
        print(e, file=sys.stderr)
    except oscerr.OscBaseError as e:
        print('*** Error:', e, file=sys.stderr)
    if osc_core.MESSAGE_BACKUPS:
        print()
        print("If you lost any edited commit messages due to an error, you may find them here:")
        for path in osc_core.MESSAGE_BACKUPS:
            print(f"  - {path}")
    return 1


def main():
    # avoid buffering output on pipes (bnc#930137) Basically,
    # a "print('foo')" call is translated to a corresponding
    # fwrite call that writes to the stdout stream (cf.
    # string_print (Objects/stringobject.c) and builtin_print
    # (Python/bltinmodule.c)); If no pipe is used, stdout is
    # a tty/refers to a terminal => the stream is line buffered
    # (see _IO_file_doallocate (libio/filedoalloc.c)). If a pipe
    # is used, stdout does not refer to a terminal anymore => the
    # stream is fully buffered by default (see
    # _IO_file_doallocate). The following fdopen call makes
    # stdout line buffered again (at least on systems that
    # support setvbuf - if setvbuf is not supported, the stream
    # remains fully buffered (see PyFile_SetBufSize
    # (Objects/fileobject.c))).
    if not os.isatty(sys.stdout.fileno()):
        sys.stdout = os.fdopen(sys.stdout.fileno(), sys.stdout.mode, 1)
        sys.stderr = os.fdopen(sys.stderr.fileno(), sys.stderr.mode, 1)

    appimage = os.getenv("APPIMAGE", None)
    owd = os.getenv("OWD", None)
    if appimage and owd:
        # OWD stands for Original Working Directory and we need to switch there when running in an AppImage
        # https://docs.appimage.org/packaging-guide/environment-variables.html
        os.chdir(owd)

    sys.exit(run(commandline.OscMainCommand()))

# vim: sw=4 et
