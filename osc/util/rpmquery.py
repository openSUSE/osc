import os
import sys
import struct

class RpmError(Exception):
    def __init__(self, msg):
        self.msg = msg

class RpmHeaderError(RpmError):
    pass

class RpmHeader():
    """corresponds more or less to the indexEntry_s struct"""
    def __init__(self, offset, length):
        self.offset = offset
        # length of the data section (without length of indexEntries)
        self.length = length
        self.entries = []

    def append(self, entry):
        self.entries.append(entry)

    def getTag(self, tag):
        for i in self.entries:
            if i.tag == tag:
                return i
        return None

    def __iter__(self):
        for i in self.entries:
            yield i

    def __len__(self):
        return len(self.entries)

class RpmHeaderEntry():
    """corresponds to the entryInfo_s struct (except the data attribute)"""

    # each element represents an int
    ENTRY_SIZE = 16
    def __init__(self, tag, type, offset, count):
        self.tag = tag
        self.type = type
        self.offset = offset
        self.count = count
        self.data = None

class RpmQuery():
    LEAD_SIZE = 96
    LEAD_MAGIC = 0xedabeedb
    HEADER_MAGIC = 0x8eade801
    HEADERSIG_TYPE = 5

    LESS = 1 << 1
    GREATER = 1 << 2
    EQUAL = 1 << 3
    def __init__(self, fh):
        self.__file = fh
        self.header = None

    def read(self, *tags):
        self.__read_lead()
        data = self.__file.read(RpmHeaderEntry.ENTRY_SIZE)
        hdrmgc, reserved, il, dl = struct.unpack('!I3i', data)
        if self.HEADER_MAGIC != hdrmgc:
            raise RpmHeaderError('invalid headermagic \'%s\'' % hdrmgc)
        # skip signature header for now
        size = il * RpmHeaderEntry.ENTRY_SIZE + dl
        # data is 8 byte aligned
        pad = (size + 7) & ~7
        self.__file.read(pad)
        data = self.__file.read(RpmHeaderEntry.ENTRY_SIZE)
        hdrmgc, reserved, il, dl = struct.unpack('!I3i', data)
        self.header = RpmHeader(pad, dl)
        if self.HEADER_MAGIC != hdrmgc:
            raise RpmHeaderError('invalid headermagic \'%s\'' % hdrmgc)
        data = self.__file.read(il * RpmHeaderEntry.ENTRY_SIZE)
        while len(data) > 0:
            ei = struct.unpack('!4i', data[:RpmHeaderEntry.ENTRY_SIZE])
            self.header.append(RpmHeaderEntry(*ei))
            data = data[RpmHeaderEntry.ENTRY_SIZE:]
        data = self.__file.read(self.header.length)
        for i in self.header:
            if i.tag in tags or len(tags) == 0:
                self.__read_data(i, data)

    def __read_lead(self):
        data = self.__file.read(self.LEAD_SIZE)
        leadmgc, = struct.unpack('!I', data[:4])
        if leadmgc != self.LEAD_MAGIC:
            raise RpmError('invalid lead magic \'%s\'' % leadmgc)
        sigtype, = struct.unpack('!h', data[78:80])
        if sigtype != self.HEADERSIG_TYPE:
            raise RpmError('invalid header signature \'%s\'' % sigtype)

    def __read_data(self, entry, data):
        off = entry.offset
        if entry.type == 2:
            entry.data = struct.unpack('!%dc' % entry.count, data[off:off + 1 * entry.count])
        if entry.type == 3:
            entry.data = struct.unpack('!%dh' % entry.count, data[off:off + 2 * entry.count])
        elif entry.type == 4:
            entry.data = struct.unpack('!%di' % entry.count, data[off:off + 4 * entry.count])
        elif entry.type == 6 or entry.type == 7:
            # XXX: what to do with binary data? for now treat it as a string
            entry.data = unpack_string(data[off:])
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
            table = self.header.getTag(100)
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
            raise RpmHeaderError('unsupported tag type \'%d\' (tag: \'%s\'' % (entry.type, entry.tag))

    def __reqprov(self, tag, flags, version):
        pnames = self.header.getTag(tag).data
        pflags = self.header.getTag(flags).data
        pvers = self.header.getTag(version).data
        if not (pnames and pflags and pvers):
            raise RpmError('cannot get provides/requires, tags are missing')
        res = []
        for name, flags, ver in zip(pnames, pflags, pvers):
            # RPMSENSE_SENSEMASK = 15 (see rpmlib.h) but ignore RPMSENSE_SERIAL (= 1 << 0) therefore use 14
            if flags & 14:
                name += ' '
                if flags & self.GREATER:
                    name += '>'
                elif flags & self.LESS:
                    name += '<'
                if flags & self.EQUAL:
                    name += '='
                name += ' %s' % ver
            res.append(name)
        return res

    # XXX: create dict for the tag => number mapping?!
    def name(self):
        return self.header.getTag(1000).data

    def version(self):
        return self.header.getTag(1001).data

    def release(self):
        return self.header.getTag(1002).data

    def arch(self):
        return self.header.getTag(1022).data

    def summary(self):
        return self.header.getTag(1004).data

    def description(self):
        return self.header.getTag(1005).data

    def url(self):
        entry = self.header.getTag(1020)
        if entry is None:
            return None
        return entry.data

    def provides(self):
        return self.__reqprov(1047, 1112, 1113)

    def requires(self):
        return self.__reqprov(1049, 1048, 1050)

    def getTag(num):
        return self.header.getTag(num)

def unpack_string(data):
    """unpack a '\\0' terminated string from data"""
    val = ''
    for c in data:
        c, = struct.unpack('!c', c)
        if c == '\0':
            break
        else:
            val += c
    return val

if __name__ == '__main__':
    f = open(sys.argv[1], 'rb')
    rpmq = RpmQuery(f)
    try:
        rpmq.read()
    except RpmError, e:
        print e.msg
    f.close()
    print rpmq.name(), rpmq.version(), rpmq.release(), rpmq.arch(), rpmq.url()
    print rpmq.summary()
    print rpmq.description()
    print '##########'
    print '\n'.join(rpmq.provides())
    print '##########'
    print '\n'.join(rpmq.requires())
