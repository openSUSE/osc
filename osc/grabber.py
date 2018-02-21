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
    from urllib.request import urlopen, HTTPError, url2pathname
except ImportError:
    from urllib2 import urlopen, HTTPError, url2pathname
    from urllib import unquote

class MGError(IOError):
    def __init__(self, *args):
        IOError.__init__(self, *args)

class OscFileGrabber(object):
    def __init__(self, progress_obj=None):
        self.progress_obj = progress_obj

    def urlgrab(self, url, filename=None, text=None, **kwargs):
        if filename is None:
            filename = os.path.basename(unquote(path))
            if not filename:
                # This is better than nothing.
                filename = 'osc_urlgrab_download'
        if url.startswith('file://'):
            f = url.replace('file://', '', 1)
            if os.path.isfile(f):
                return f
            else:
                raise MGError(2, 'Local file \'%s\' does not exist' % f)
        with open(filename, 'wb') as f:
            for i in streamfile(url, progress_obj=self.progress_obj,
                                text=text):
                f.write(i)
            return filename


class OscMirrorGroup(object):
    def __init__(self, grabber, mirrors):
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
                self.grabber.urlgrab(mirror, filename) 
            except HTTPError as e:
                print('Error %s' % e.code)
                if e.code == 414:
                    raise MGError
                tries += 1
                continue

        if max_m == tries:
            raise MGError(256, 'No mirrors left')
