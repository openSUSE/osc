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

import mmap
import os
import stat
import struct
import sys

# workaround for python24
if not hasattr(os, 'SEEK_SET'):
    os.SEEK_SET = 0

# format implementation is based on src/copyin.c and src/util.c (see cpio sources)

class CpioError(Exception):
    """base class for all cpio related errors"""
    def __init__(self, fn, msg):
        Exception.__init__(self)
        self.file = fn
        self.msg = msg
    def __str__(self):
        return '%s: %s' % (self.file, self.msg)

class CpioHdr:
    """
    Represents a cpio header ("New" portable format and CRC format).
    """
    def __init__(self, mgc, ino, mode, uid, gid, nlink, mtime, filesize,
                 dev_maj, dev_min, rdev_maj, rdev_min, namesize, checksum,
                 off = -1, filename = ''):
        """
        All passed parameters are hexadecimal strings (not NUL terminated) except
        off and filename. They will be converted into normal ints.
        """
        self.ino = ino
        self.mode = mode
        self.uid = uid
        self.gid = gid
        self.nlink = nlink
        self.mtime = mtime
        # 0 indicates FIFO or dir
        self.filesize = filesize
        self.dev_maj = dev_maj
        self.dev_min = dev_min
        # only needed for special block/char files
        self.rdev_maj = rdev_maj
        self.rdev_min = rdev_min
        # length of filename (inluding terminating NUL)
        self.namesize = namesize
        # != 0 indicates CRC format (which we do not support atm)
        self.checksum = checksum
        for k,v in self.__dict__.items():
            self.__dict__[k] = int(v, 16)
        self.filename = filename
        # data starts at dataoff and ends at dataoff+filesize
        self.dataoff = off

    def __str__(self):
        return "%s %s %s %s" % (self.filename, self.filesize, self.namesize, self.dataoff)

class CpioRead:
    """
    Represents a cpio archive.
    Supported formats:
    * ascii SVR4 no CRC also called "new_ascii"
    """

    # supported formats - use name -> mgc mapping to increase readabilty
    sfmt = {
             'newascii' : '070701',
           }

    # header format
    hdr_fmt = '6s8s8s8s8s8s8s8s8s8s8s8s8s8s'
    hdr_len = 110

    def __init__(self, filename):
        self.filename = filename
        self.format = -1
        self.__file = None
        self._init_datastructs()

    def __del__(self):
        if self.__file:
            self.__file.close()

    def __iter__(self):
        for h in self.hdrs:
            yield h

    def _init_datastructs(self):
        self.hdrs = []

    def _calc_padding(self, off):
        """
        skip some bytes after a header or a file.
        based on 'static void tape_skip_padding()' in copyin.c.
        """
        if self._is_format('newascii'):
            return (4 - (off % 4)) % 4

    def _is_format(self, type):
        return self.format == self.sfmt[type]

    def _copyin_file(self, hdr, dest, fn):
        """saves file to disk"""
        # TODO: investigate links (e.g. symbolic links are working)
        # check if we have a regular file
        if not stat.S_ISREG(stat.S_IFMT(hdr.mode)):
            msg = '\'%s\' is no regular file - only regular files are supported atm' % hdr.filename
            raise NotImplementedError(msg)
        fn = os.path.join(dest, fn)
        f = open(fn, 'wb')
        self.__file.seek(hdr.dataoff, os.SEEK_SET)
        f.write(self.__file.read(hdr.filesize))
        f.close()
        os.chmod(fn, hdr.mode)
        uid = hdr.uid
        if uid != os.geteuid() or os.geteuid() != 1:
            uid = -1
        gid = hdr.gid
        if not gid in os.getgroups() or os.getegid() != -1:
            gid = -1
        os.chown(fn, uid, gid)

    def _get_hdr(self, fn):
        for h in self.hdrs:
            if h.filename == fn:
                return h
        return None

    def read(self):
        if not self.__file:
            self.__file = open(self.filename, 'rb')
            try:
                if sys.platform[:3] != 'win':
                    self.__file = mmap.mmap(self.__file.fileno(), os.path.getsize(self.__file.name), prot = mmap.PROT_READ)
                else:
                    self.__file = mmap.mmap(self.__file.fileno(), os.path.getsize(self.__file.name))
            except EnvironmentError as e:
                if e.errno == 19 or ( hasattr(e, 'winerror') and e.winerror == 5 ):
                    print >>sys.stderr, 'cannot use mmap to read the file, failing back to default'
                else:
                    raise e
        else:
            self.__file.seek(0, os.SEEK_SET)
        self._init_datastructs()
        data = self.__file.read(6)
        self.format = data
        if not self.format in self.sfmt.values():
            raise CpioError(self.filename, '\'%s\' is not a supported cpio format' % self.format)
        pos = 0
        while (len(data) != 0):
            self.__file.seek(pos, os.SEEK_SET)
            data = self.__file.read(self.hdr_len)
            if not data:
                break
            pos += self.hdr_len
            data = struct.unpack(self.hdr_fmt, data)
            hdr = CpioHdr(*data)
            hdr.filename = self.__file.read(hdr.namesize - 1)
            if hdr.filename == 'TRAILER!!!':
                break
            pos += hdr.namesize
            if self._is_format('newascii'):
                pos += self._calc_padding(hdr.namesize + 110)
            hdr.dataoff = pos
            self.hdrs.append(hdr)
            pos += hdr.filesize + self._calc_padding(hdr.filesize)

    def copyin_file(self, filename, dest = None, new_fn = None):
        """
        copies filename to dest.
        If dest is None the file will be stored in $PWD/filename. If dest points
        to a dir the file will be stored in dest/filename. In case new_fn is specified
        the file will be stored as new_fn.
        """
        hdr = self._get_hdr(filename)
        if not hdr:
            raise CpioError(filename, '\'%s\' does not exist in archive' % filename)
        dest = dest or os.getcwd()
        fn = new_fn or filename
        self._copyin_file(hdr, dest, fn)

    def copyin(self, dest = None):
        """
        extracts the cpio archive to dest.
        If dest is None $PWD will be used.
        """
        dest = dest or os.getcwd()
        for h in self.hdrs:
            self._copyin_file(h, dest, h.filename)

class CpioWrite:
    """cpio archive small files in memory, using new style portable header format"""

    def __init__(self):
        self.cpio = ''

    def add(self, name=None, content=None, perms=0x1a4, type=0x8000):
        namesize = len(name) + 1
        if namesize % 2:
            name += '\0'
        filesize = len(content)
        mode = perms | type

        c = []
        c.append('070701') # magic
        c.append('%08X' % 0) # inode
        c.append('%08X' % mode) # mode
        c.append('%08X' % 0) # uid
        c.append('%08X' % 0) # gid
        c.append('%08X' % 0) # nlink
        c.append('%08X' % 0) # mtime
        c.append('%08X' % filesize)
        c.append('%08X' % 0) # major
        c.append('%08X' % 0) # minor
        c.append('%08X' % 0) # rmajor
        c.append('%08X' % 0) # rminor
        c.append('%08X' % namesize)
        c.append('%08X' % 0) # checksum

        c.append(name + '\0')
        c.append('\0' * (len(''.join(c)) % 4))

        c.append(content)

        c = ''.join(c)
        if len(c) % 4:
            c += '\0' * (4 - len(c) % 4)

        self.cpio += c

    def add_padding(self):
        if len(self.cpio) % 512:
            self.cpio += '\0' * (512 - len(self.cpio) % 512)

    def get(self):
        self.add('TRAILER!!!', '')
        self.add_padding()
        return ''.join(self.cpio)
