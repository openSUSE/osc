# Copyright (C) 2018 SUSE Linux.  All rights reserved.
# This program is free software; it may be used, copied, modified
# and distributed under the terms of the GNU General Public Licence,
# either version 2, or (at your option) any later version.

import sys
import os.path
from shutil import copyfile
import progressbar as pb
from .core import streamfile

try:
    from urllib.request import urlopen, HTTPError, url2pathname
except ImportError:
    from urllib2 import urlopen, HTTPError, url2pathname

class MGError(IOError):
    def __init__(self, *args):
        IOError.__init__(self, *args)

class OscMirrorGroup:
    def __init__(self, grabber, mirrors, **kwargs):
        self.grabber = grabber
        self.mirrors = mirrors

    def urlgrab(self, url, filename=None, **kwargs):
        max_m = len(self.mirrors)
        tries = 0
        for mirror in self.mirrors:
            if mirror.startswith('file'):
                path = mirror.replace('file:/', '')
                if not os.path.exists(path):
                    tries += 1
                    continue
                else:
                    copyfile(path,filename)
                    break
            try:
                u = urlopen(mirror)
            except HTTPError as e:
                if e.code == 414:
                    raise MGError
                tries += 1
                continue
            f = open(filename, 'wb')
            for i in streamfile(mirror, progress_obj=pb):
                f.write(i)
            f.flush
            f.close
            break

        if max_m == tries:
            raise MGError(256, 'No mirrors left')
