# Copyright (C) 2018 SUSE Linux.  All rights reserved.
# This program is free software; it may be used, copied, modified
# and distributed under the terms of the GNU General Public Licence,
# either version 2, or (at your option) any later version.


import html

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
    import builtins
    func = builtins.input

    try:
        return func(*args)
    except EOFError:
        # interpret ctrl-d as user abort
        raise oscerr.UserAbort()


def _html_escape(data):
    return html.escape(data, quote=False)
