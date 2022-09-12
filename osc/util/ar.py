# Copyright 2009 Marcus Huewe <suse-tux@gmx.de>
#
# This program is free software; you can redistribute it and/or
# modify it under the terms of the GNU General Public License version 2
# as published by the Free Software Foundation;
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program; if not, write to the Free Software
# Foundation, Inc., 51 Franklin Street, Fifth Floor, Boston, MA  02110-1301, USA


import os
import re
import stat
import sys
from io import BytesIO


# workaround for python24
if not hasattr(os, 'SEEK_SET'):
    os.SEEK_SET = 0


class ArError(Exception):
    """Base class for all ar related errors"""

    def __init__(self, fn, msg):
        super().__init__()
        self.file = fn
        self.msg = msg

    def __str__(self):
        return 'ar error: %s' % self.msg


class ArHdr:
    """Represents an ar header entry"""

    def __init__(self, fn, date, uid, gid, mode, size, fmag, off):
        self.file = fn.strip()
        self.date = date.strip()
        self.uid = uid.strip()
        self.gid = gid.strip()
        if not mode.strip():
            # provide a dummy mode for the ext_fn hdr
            mode = '0'
        self.mode = stat.S_IMODE(int(mode, 8))
        self.size = int(size)
        self.fmag = fmag
        # data section starts at off and ends at off + size
        self.dataoff = int(off)

    def __str__(self):
        return '%16s %d' % (self.file, self.size)


class ArFile(BytesIO):
    """Represents a file which resides in the archive"""

    def __init__(self, fn, uid, gid, mode, buf):
        super().__init__(buf)
        self.name = fn
        self.uid = uid
        self.gid = gid
        self.mode = mode

    def saveTo(self, dir=None):
        """
        writes file to dir/filename if dir isn't specified the current
        working dir is used. Additionally it tries to set the owner/group
        and permissions.
        """
        if not dir:
            dir = os.getcwdb()
        fn = os.path.join(dir, self.name)
        with open(fn, 'wb') as f:
            f.write(self.getvalue())
        os.chmod(fn, self.mode)
        uid = self.uid
        if uid != os.geteuid() or os.geteuid() != 0:
            uid = -1
        gid = self.gid
        if gid not in os.getgroups() or os.getegid() != 0:
            gid = -1
        os.chown(fn, uid, gid)

    def __str__(self):
        return '%s %s %s %s' % (self.name, self.uid,
                                self.gid, self.mode)


class Ar:
    """
    Represents an ar archive (only GNU format is supported).
    Readonly access.
    """
    hdr_len = 60
    hdr_pat = re.compile(b'^(.{16})(.{12})(.{6})(.{6})(.{8})(.{10})(.{2})',
                         re.DOTALL)

    def __init__(self, fn=None, fh=None):
        if fn is None and fh is None:
            raise ValueError('either \'fn\' or \'fh\' must be is not None')
        if fh is not None:
            self.__file = fh
            self.__closefile = False
            self.filename = fh.name
        else:
            # file object: will be closed in __del__()
            self.__file = None
            self.__closefile = True
            self.filename = fn
        self._init_datastructs()

    def __del__(self):
        if self.__file and self.__closefile:
            self.__file.close()

    def _init_datastructs(self):
        self.hdrs = []
        self.ext_fnhdr = None

    def _appendHdr(self, hdr):
        # GNU uses an internal '//' file to store very long filenames
        if hdr.file.startswith(b'//'):
            self.ext_fnhdr = hdr
        else:
            self.hdrs.append(hdr)

    def _fixupFilenames(self):
        """
        support the GNU approach for very long filenames:
        every filename which exceeds 16 bytes is stored in the data section of a special file ('//')
        and the filename in the header of this long file specifies the offset in the special file's
        data section. The end of such a filename is indicated with a trailing '/'.
        Another special file is the '/' which contains the symbol lookup table.
        """
        for h in self.hdrs:
            if h.file == b'/':
                continue
            # remove slashes which are appended by ar
            h.file = h.file.rstrip(b'/')
            if not h.file.startswith(b'/'):
                continue
            # handle long filename
            off = int(h.file[1:len(h.file)])
            start = self.ext_fnhdr.dataoff + off
            self.__file.seek(start, os.SEEK_SET)
            # XXX: is it safe to read all the data in one chunk? I assume the '//' data section
            #      won't be too large
            data = self.__file.read(self.ext_fnhdr.size)
            end = data.find(b'/')
            if end != -1:
                h.file = data[0:end]
            else:
                raise ArError(b'//', 'invalid data section - trailing slash (off: %d)' % start)

    def _get_file(self, hdr):
        self.__file.seek(hdr.dataoff, os.SEEK_SET)
        return ArFile(hdr.file, hdr.uid, hdr.gid, hdr.mode,
                      self.__file.read(hdr.size))

    def read(self):
        """reads in the archive."""
        if not self.__file:
            self.__file = open(self.filename, 'rb')
        else:
            self.__file.seek(0, os.SEEK_SET)
        self._init_datastructs()
        data = self.__file.read(7)
        if data != b'!<arch>':
            raise ArError(self.filename, 'no ar archive')
        pos = 8
        while len(data) != 0:
            self.__file.seek(pos, os.SEEK_SET)
            data = self.__file.read(self.hdr_len)
            if not data:
                break
            pos += self.hdr_len
            m = self.hdr_pat.search(data)
            if not m:
                raise ArError(self.filename, 'unexpected hdr entry')
            args = m.groups() + (pos, )
            hdr = ArHdr(*args)
            self._appendHdr(hdr)
            # data blocks are 2 bytes aligned - if they end on an odd
            # offset ARFMAG[0] will be used for padding (according to the current binutils code)
            pos += hdr.size + (hdr.size & 1)
        self._fixupFilenames()

    def get_file(self, fn):
        for h in self.hdrs:
            if h.file == fn:
                return self._get_file(h)
        return None

    def __iter__(self):
        for h in self.hdrs:
            if h.file == b'/':
                continue
            yield self._get_file(h)


if __name__ == '__main__':
    if len(sys.argv) != 2:
        print('usage: %s <arfile>' % sys.argv[0])
        sys.exit(1)
    # a potential user might want to pass a bytes instead of a str
    # to make sure that the ArError's file attribute is always a
    # bytes
    ar = Ar(fn=sys.argv[1])
    ar.read()
    for hdr in ar.hdrs:
        print(hdr)
