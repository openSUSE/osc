#!/usr/bin/env python

# this wrapper exists so it can be put into /usr/bin, but still allows the
# python module to be called within the source directory during development

import locale
import sys
import os

from osc import commandline, babysitter

try:
# this is a hack to make osc work as expected with utf-8 characters,
# no matter how site.py is set...
    reload(sys)
    loc = locale.getpreferredencoding()
    if not loc:
        loc = sys.getpreferredencoding()
    sys.setdefaultencoding(loc)
    del sys.setdefaultencoding
except NameError:
    #reload, neither setdefaultencoding are in python3
    pass

# avoid buffering output on pipes (bnc#930137)
# Basically, a "print('foo')" call is translated to a corresponding
# fwrite call that writes to the stdout stream (cf. string_print
# (Objects/stringobject.c) and builtin_print (Python/bltinmodule.c));
# If no pipe is used, stdout is a tty/refers to a terminal =>
# the stream is line buffered (see _IO_file_doallocate (libio/filedoalloc.c)).
# If a pipe is used, stdout does not refer to a terminal anymore =>
# the stream is fully buffered by default (see _IO_file_doallocate).
# The following fdopen call makes stdout line buffered again (at least on
# systems that support setvbuf - if setvbuf is not supported, the stream
# remains fully buffered (see PyFile_SetBufSize (Objects/fileobject.c))).
if not os.isatty(sys.stdout.fileno()):
    sys.stdout = os.fdopen(sys.stdout.fileno(), sys.stdout.mode, 1)

osccli = commandline.Osc()

r = babysitter.run(osccli)
sys.exit(r)
