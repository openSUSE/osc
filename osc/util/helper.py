# Copyright (C) 2018 SUSE Linux.  All rights reserved.
# This program is free software; it may be used, copied, modified
# and distributed under the terms of the GNU General Public Licence,
# either version 2, or (at your option) any later version.


import builtins
import html
import signal
import subprocess
import threading

from .. import oscerr


def decode_list(ilist):
    """ Decodes the elements of a list if needed
    """

    dlist = []
    for elem in ilist:
        if not isinstance(elem, str):
            dlist.append(decode_it(elem))
        else:
            dlist.append(elem)
    return dlist


def decode_it(obj):
    """Decode the given object unless it is a str.

    If the given object is a str or has no decode method, the object itself is
    returned. Otherwise, try to decode the object using utf-8. If this
    fails due to a UnicodeDecodeError, try to decode the object using
    latin-1.
    """
    if isinstance(obj, str) or not hasattr(obj, 'decode'):
        return obj
    try:
        return obj.decode('utf-8')
    except UnicodeDecodeError:
        return obj.decode('latin-1')


def raw_input(*args):
    func = builtins.input

    try:
        return func(*args)
    except EOFError:
        # interpret ctrl-d as user abort
        raise oscerr.UserAbort()


def run_interactive(cmd, **kwargs):
    """
    Run an interactive program (an editor, for example) and wait for it.

    Pressing Ctrl-C in a terminal sends SIGINT to the whole foreground
    process group, that is, to osc as well as to the child. Editors such
    as vis keep ISIG enabled and handle SIGINT themselves; without
    protection osc would get KeyboardInterrupt and subprocess would kill
    the editor in the middle of editing.

    Like system(3) and git's editor launcher, ignore SIGINT and SIGQUIT
    in osc while the child is running. The signals are ignored only after
    the child has been spawned, so it does not inherit SIG_IGN.

    Returns the exit code of the child.
    """
    proc = subprocess.Popen(cmd, **kwargs)

    if threading.current_thread() is not threading.main_thread():
        # signal handlers can be changed only from the main thread
        return proc.wait()

    signums = [signal.SIGINT]
    if hasattr(signal, "SIGQUIT"):
        signums.append(signal.SIGQUIT)

    old_handlers = {}
    try:
        for signum in signums:
            old_handlers[signum] = signal.signal(signum, signal.SIG_IGN)
        return proc.wait()
    finally:
        for signum, handler in old_handlers.items():
            # None means the handler was not installed from Python
            signal.signal(signum, signal.SIG_DFL if handler is None else handler)


def _html_escape(data):
    return html.escape(data, quote=False)


def format_table(rows, headers):
    """Format list of tuples into equal width table with headers"""
    maxlens = [len(h) for h in headers]
    for r in rows:
        for i, c in enumerate(r):
            maxlens[i] = max(maxlens[i], len(c))
    tpltpl = []
    for i, m in enumerate(maxlens):
        tpltpl.append('{%s:<%s}' % (i, m))
    # {0:12}  {1:7}  {2:10}  {3:8}
    templ = '  '.join(tpltpl) + '\n'

    out = templ.format(*headers)
    out += templ.format(*['-' * m for m in maxlens])
    for r in rows:
        out += templ.format(*r)
    return out
