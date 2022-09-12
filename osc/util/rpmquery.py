import os
import re
import struct
import sys
from . import packagequery

from .helper import decode_it


def cmp(a, b):
    return (a > b) - (a < b)


class RpmError(packagequery.PackageError):
    pass


class RpmHeaderError(RpmError):
    pass


class RpmHeader:
    """corresponds more or less to the indexEntry_s struct"""

    def __init__(self, offset, length):
        self.offset = offset
        # length of the data section (without length of indexEntries)
        self.length = length
        self.entries = []

    def append(self, entry):
        self.entries.append(entry)

    def gettag(self, tag):
        for i in self.entries:
            if i.tag == tag:
                return i
        return None

    def __iter__(self):
        yield from self.entries

    def __len__(self):
        return len(self.entries)


class RpmHeaderEntry:
    """corresponds to the entryInfo_s struct (except the data attribute)"""

    # each element represents an int
    ENTRY_SIZE = 16

    def __init__(self, tag, type, offset, count):
        self.tag = tag
        self.type = type
        self.offset = offset
        self.count = count
        self.data = None


class RpmQuery(packagequery.PackageQuery, packagequery.PackageQueryResult):
    LEAD_SIZE = 96
    LEAD_MAGIC = 0xedabeedb
    HEADER_MAGIC = 0x8eade801
    HEADERSIG_TYPE = 5

    LESS = 1 << 1
    GREATER = 1 << 2
    EQUAL = 1 << 3

    SENSE_STRONG = 1 << 27

    default_tags = (
        1000, 1001, 1002, 1003, 1004, 1022, 1005, 1020,
        1047, 1112, 1113,  # provides
        1049, 1048, 1050,  # requires
        1054, 1053, 1055,  # conflicts
        1090, 1114, 1115,  # obsoletes
        1156, 1158, 1157,  # oldsuggests
        5046, 5047, 5048,  # recommends
        5049, 5051, 5050,  # suggests
        5052, 5053, 5054,  # supplements
        5055, 5056, 5057  # enhances
    )

    def __init__(self, fh):
        self.__file = fh
        self.__path = os.path.abspath(fh.name)
        self.filename_suffix = 'rpm'
        self.header = None

    def read(self, all_tags=False, self_provides=True, *extra_tags, **extra_kw):
        # self_provides is unused because a rpm always has a self provides
        self.__read_lead()
        data = self.__file.read(RpmHeaderEntry.ENTRY_SIZE)
        hdrmgc, reserved, il, dl = struct.unpack('!I3i', data)
        if self.HEADER_MAGIC != hdrmgc:
            raise RpmHeaderError(self.__path, 'invalid headermagic \'%s\'' % hdrmgc)
        # skip signature header for now
        size = il * RpmHeaderEntry.ENTRY_SIZE + dl
        # data is 8 byte aligned
        pad = (size + 7) & ~7
        querysig = extra_kw.get('querysig')
        if not querysig:
            self.__file.read(pad)
            data = self.__file.read(RpmHeaderEntry.ENTRY_SIZE)
        hdrmgc, reserved, il, dl = struct.unpack('!I3i', data)
        self.header = RpmHeader(pad, dl)
        if self.HEADER_MAGIC != hdrmgc:
            raise RpmHeaderError(self.__path, 'invalid headermagic \'%s\'' % hdrmgc)
        data = self.__file.read(il * RpmHeaderEntry.ENTRY_SIZE)
        while len(data) > 0:
            ei = struct.unpack('!4i', data[:RpmHeaderEntry.ENTRY_SIZE])
            self.header.append(RpmHeaderEntry(*ei))
            data = data[RpmHeaderEntry.ENTRY_SIZE:]
        data = self.__file.read(self.header.length)
        for i in self.header:
            if i.tag in self.default_tags + extra_tags or all_tags:
                try:  # this may fail for -debug* packages
                    self.__read_data(i, data)
                except:
                    pass
        return self

    def __read_lead(self):
        data = self.__file.read(self.LEAD_SIZE)
        leadmgc, = struct.unpack('!I', data[:4])
        if leadmgc != self.LEAD_MAGIC:
            raise RpmError(self.__path, 'not a rpm (invalid lead magic \'%s\')' % leadmgc)
        sigtype, = struct.unpack('!h', data[78:80])
        if sigtype != self.HEADERSIG_TYPE:
            raise RpmError(self.__path, 'invalid header signature \'%s\'' % sigtype)

    def __read_data(self, entry, data):
        off = entry.offset
        if entry.type == 2:
            entry.data = struct.unpack('!%dc' % entry.count, data[off:off + 1 * entry.count])
        if entry.type == 3:
            entry.data = struct.unpack('!%dh' % entry.count, data[off:off + 2 * entry.count])
        elif entry.type == 4:
            entry.data = struct.unpack('!%di' % entry.count, data[off:off + 4 * entry.count])
        elif entry.type == 6:
            entry.data = unpack_string(data[off:])
        elif entry.type == 7:
            entry.data = data[off:off + entry.count]
        elif entry.type == 8 or entry.type == 9:
            cnt = entry.count
            entry.data = []
            while cnt > 0:
                cnt -= 1
                s = unpack_string(data[off:])
                # also skip '\0'
                off += len(s) + 1
                entry.data.append(s)
            if entry.type == 8:
                return
            lang = os.getenv('LANGUAGE') or os.getenv('LC_ALL') \
                or os.getenv('LC_MESSAGES') or os.getenv('LANG')
            if lang is None:
                entry.data = entry.data[0]
                return
            # get private i18n table
            table = self.header.gettag(100)
            # just care about the country code
            lang = lang.split('_', 1)[0]
            cnt = 0
            for i in table.data:
                if cnt > len(entry.data) - 1:
                    break
                if i == lang:
                    entry.data = entry.data[cnt]
                    return
                cnt += 1
            entry.data = entry.data[0]
        else:
            raise RpmHeaderError(self.__path, 'unsupported tag type \'%d\' (tag: \'%s\'' % (entry.type, entry.tag))

    def __reqprov(self, tag, flags, version, strong=None):
        pnames = self.header.gettag(tag)
        if not pnames:
            return []
        pnames = pnames.data
        pflags = self.header.gettag(flags).data
        pvers = self.header.gettag(version).data
        if not (pnames and pflags and pvers):
            raise RpmError(self.__path, 'cannot get provides/requires, tags are missing')
        res = []
        for name, flags, ver in zip(pnames, pflags, pvers):
            if strong is not None:
                # compat code for the obsolete RPMTAG_OLDSUGGESTSNAME tag
                # strong == 1 => return only "recommends"
                # strong == 0 => return only "suggests"
                if strong == 1:
                    strong = self.SENSE_STRONG
                if (flags & self.SENSE_STRONG) != strong:
                    continue
            # RPMSENSE_SENSEMASK = 15 (see rpmlib.h) but ignore RPMSENSE_SERIAL (= 1 << 0) therefore use 14
            if flags & 14:
                name += b' '
                if flags & self.GREATER:
                    name += b'>'
                elif flags & self.LESS:
                    name += b'<'
                if flags & self.EQUAL:
                    name += b'='
                name += b' %s' % ver
            res.append(name)
        return res

    def vercmp(self, rpmq):
        res = RpmQuery.rpmvercmp(str(self.epoch()), str(rpmq.epoch()))
        if res != 0:
            return res
        res = RpmQuery.rpmvercmp(self.version(), rpmq.version())
        if res != 0:
            return res
        res = RpmQuery.rpmvercmp(self.release(), rpmq.release())
        return res

    # XXX: create dict for the tag => number mapping?!
    def name(self):
        return self.header.gettag(1000).data

    def version(self):
        return self.header.gettag(1001).data

    def release(self):
        return self.header.gettag(1002).data

    def epoch(self):
        epoch = self.header.gettag(1003)
        if epoch is None:
            return 0
        return epoch.data[0]

    def arch(self):
        return self.header.gettag(1022).data

    def summary(self):
        return self.header.gettag(1004).data

    def description(self):
        return self.header.gettag(1005).data

    def url(self):
        entry = self.header.gettag(1020)
        if entry is None:
            return None
        return entry.data

    def path(self):
        return self.__path

    def provides(self):
        return self.__reqprov(1047, 1112, 1113)

    def requires(self):
        return self.__reqprov(1049, 1048, 1050)

    def conflicts(self):
        return self.__reqprov(1054, 1053, 1055)

    def obsoletes(self):
        return self.__reqprov(1090, 1114, 1115)

    def recommends(self):
        recommends = self.__reqprov(5046, 5048, 5047)
        if not recommends:
            recommends = self.__reqprov(1156, 1158, 1157, 1)
        return recommends

    def suggests(self):
        suggests = self.__reqprov(5049, 5051, 5050)
        if not suggests:
            suggests = self.__reqprov(1156, 1158, 1157, 0)
        return suggests

    def supplements(self):
        return self.__reqprov(5052, 5054, 5053)

    def enhances(self):
        return self.__reqprov(5055, 5057, 5506)

    def is_src(self):
        # SOURCERPM = 1044
        return self.gettag(1044) is None

    def is_nosrc(self):
        # NOSOURCE = 1051, NOPATCH = 1052
        return self.is_src() and \
            (self.gettag(1051) is not None or self.gettag(1052) is not None)

    def gettag(self, num):
        return self.header.gettag(num)

    def canonname(self):
        if self.is_nosrc():
            arch = b'nosrc'
        elif self.is_src():
            arch = b'src'
        else:
            arch = self.arch()
        return RpmQuery.filename(self.name(), None, self.version(), self.release(), arch)

    @staticmethod
    def query(filename):
        f = open(filename, 'rb')
        rpmq = RpmQuery(f)
        rpmq.read()
        f.close()
        return rpmq

    @staticmethod
    def queryhdrmd5(filename):
        f = open(filename, 'rb')
        rpmq = RpmQuery(f)
        rpmq.read(1004, querysig=True)
        f.close()
        entry = rpmq.gettag(1004)
        if entry is None:
            return None
        return ''.join(["%02x" % x for x in struct.unpack('16B', entry.data)])

    @staticmethod
    def rpmvercmp(ver1, ver2):
        """
        implementation of RPM's version comparison algorithm
        (as described in lib/rpmvercmp.c)
        """
        if ver1 == ver2:
            return 0
        res = 0
        ver1 = decode_it(ver1)
        ver2 = decode_it(ver2)
        while res == 0:
            # remove all leading non alphanumeric or tilde chars
            ver1 = re.sub('^[^a-zA-Z0-9~]*', '', ver1)
            ver2 = re.sub('^[^a-zA-Z0-9~]*', '', ver2)
            if ver1.startswith('~') or ver2.startswith('~'):
                if not ver1.startswith('~'):
                    return 1
                elif not ver2.startswith('~'):
                    return -1
                ver1 = ver1[1:]
                ver2 = ver2[1:]
                continue

            if not (len(ver1) and len(ver2)):
                break

            # check if we have a digits segment
            mo1 = re.match(r'(\d+)', ver1)
            mo2 = re.match(r'(\d+)', ver2)
            numeric = True
            if mo1 is None:
                mo1 = re.match('([a-zA-Z]+)', ver1)
                mo2 = re.match('([a-zA-Z]+)', ver2)
                numeric = False
            # check for different types: alpha and numeric
            if mo2 is None:
                if numeric:
                    return 1
                return -1
            seg1 = mo1.group(0)
            ver1 = ver1[mo1.end(0):]
            seg2 = mo2.group(1)
            ver2 = ver2[mo2.end(1):]
            if numeric:
                # remove leading zeros
                seg1 = re.sub('^0+', '', seg1)
                seg2 = re.sub('^0+', '', seg2)
                # longer digit segment wins - if both have the same length
                # a simple ascii compare decides
                res = len(seg1) - len(seg2) or cmp(seg1, seg2)
            else:
                res = cmp(seg1, seg2)
        if res > 0:
            return 1
        elif res < 0:
            return -1
        return cmp(ver1, ver2)

    @staticmethod
    def filename(name, epoch, version, release, arch):
        return b'%s-%s-%s.%s.rpm' % (name, version, release, arch)


def unpack_string(data, encoding=None):
    """unpack a '\\0' terminated string from data"""
    idx = data.find(b'\0')
    if idx == -1:
        raise ValueError('illegal string: not \\0 terminated')
    data = data[:idx]
    if encoding is not None:
        data = data.decode(encoding)
    return data


if __name__ == '__main__':
    try:
        rpmq = RpmQuery.query(sys.argv[1])
    except RpmError as e:
        print(e.msg)
        sys.exit(2)
    print(rpmq.name(), rpmq.version(), rpmq.release(), rpmq.arch(), rpmq.url())
    print(rpmq.summary())
    print(rpmq.description())
    print('##########')
    print('\n'.join(rpmq.provides()))
    print('##########')
    print('\n'.join(rpmq.requires()))
    print('##########')
    print(RpmQuery.queryhdrmd5(sys.argv[1]))
