# Copyright (C) 2018 SUSE Linux.  All rights reserved.
# This program is free software; it may be used, copied, modified
# and distributed under the terms of the GNU General Public Licence,
# either version 2, or (at your option) any later version.

import sys
import os.path
from shutil import copyfile
from .core import streamfile

try:
    from urllib.parse import unquote
    from urllib.request import HTTPError
except ImportError:
    from urllib2 import HTTPError
    from urllib import unquote


class MGError(IOError):
    pass


class OscFileGrabber(object):
    def __init__(self, progress_obj=None):
        self.progress_obj = progress_obj

    def urlgrab(self, url, filename, text=None):
        with open(filename, 'wb') as f:
            for i in streamfile(url, progress_obj=self.progress_obj,
                                text=text):
                f.write(i)


class OscMirrorGroup(object):
    def __init__(self, grabber, mirrors):
        self._grabber = grabber
        self._mirrors = mirrors

    def urlgrab(self, url, filename=None, text=None):
        tries = 0
        for mirror in self._mirrors:
            try:
                self._grabber.urlgrab(mirror, filename, text)
            except HTTPError as e:
                if e.code == 414:
                    raise HTTPError(e)
                tries += 1

        if len(self._mirrors) == tries:
            raise MGError(256, 'No mirrors left')
