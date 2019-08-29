# Copyright (C) 2018 SUSE Linux.  All rights reserved.
# This program is free software; it may be used, copied, modified
# and distributed under the terms of the GNU General Public Licence,
# either version 2, or (at your option) any later version.


def cmp_to_key(mycmp):
    """ Converts a cmp= function into a key= function.
    """

    class K(object):
        def __init__(self, obj, *args):
            self.obj = obj

        def __lt__(self, other):
            return mycmp(self.obj, other.obj) < 0

        def __gt__(self, other):
            return mycmp(self.obj, other.obj) > 0

        def __eq__(self, other):
            return mycmp(self.obj, other.obj) == 0

        def __le__(self, other):
            return mycmp(self.obj, other.obj) <= 0

        def __ge__(self, other):
            return mycmp(self.obj, other.obj) >= 0

        def __ne__(self, other):
            return mycmp(self.obj, other.obj) != 0

        def __hash__(self):
            raise TypeError('hash not implemented')

    return K


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
    """ Decodes the given object if obj is not a string
        based on the chardet module if possible
    """

    if obj is None or isinstance(obj, str):
        return obj
    else:
        try:
            import chardet
            return obj.decode(chardet.detect(obj)['encoding'])
        except:
            try:
                import locale
                return obj.decode(locale.getlocale()[1])
            except:
                return obj.decode('latin-1')


def raw_input(*args):
    try:
        import builtins
        func = builtins.input
    except ImportError:
        #python 2.7
        import __builtin__
        func = __builtin__.raw_input

    try:
        return func(*args)
    except EOFError:
        # interpret ctrl-d as user abort
        raise oscerr.UserAbort()
