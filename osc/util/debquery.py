
from __future__ import print_function

from . import ar
import os.path
import re
import tarfile
from io import BytesIO
from . import packagequery
import itertools


HAVE_LZMA = True
try:
    import lzma
except ImportError:
    HAVE_LZMA = False


if (not hasattr(itertools, 'zip_longest')
    and hasattr(itertools, 'izip_longest')):
    # python2 case
    itertools.zip_longest = itertools.izip_longest


class DebError(packagequery.PackageError):
    pass

class DebQuery(packagequery.PackageQuery, packagequery.PackageQueryResult):

    default_tags = (b'package', b'version', b'release', b'epoch',
        b'architecture', b'description', b'provides', b'depends',
        b'pre_depends', b'conflicts', b'breaks')

    def __init__(self, fh):
        self.__file = fh
        self.__path = os.path.abspath(fh.name)
        self.filename_suffix = 'deb'
        self.fields = {}

    def read(self, all_tags=False, self_provides=True, *extra_tags):
        arfile = ar.Ar(fh = self.__file)
        arfile.read()
        debbin = arfile.get_file(b'debian-binary')
        if debbin is None:
            raise DebError(self.__path, 'no debian binary')
        if debbin.read() != b'2.0\n':
            raise DebError(self.__path, 'invalid debian binary format')
        control = arfile.get_file(b'control.tar.gz')
        if control is not None:
            # XXX: python2.4 relies on a name
            tar = tarfile.open(name='control.tar.gz', fileobj=control)
        else:
            control = arfile.get_file(b'control.tar.xz')
            if control is None:
                raise DebError(self.__path, 'missing control.tar')
            if not HAVE_LZMA:
                raise DebError(self.__path, 'can\'t open control.tar.xz without python-lzma')
            decompressed = lzma.decompress(control.read())
            tar = tarfile.open(name="control.tar.xz",
                               fileobj=BytesIO(decompressed))
        try:
            name = './control'
            # workaround for python2.4's tarfile module
            if 'control' in tar.getnames():
                name = 'control'
            control = tar.extractfile(name)
        except KeyError:
            raise DebError(self.__path,
                           'missing \'control\' file in control.tar')
        self.__parse_control(control, all_tags, self_provides, *extra_tags)
        return self

    def __parse_control(self, control, all_tags=False, self_provides=True, *extra_tags):
        data = control.readline().strip()
        while data:
            field, val = re.split(b':\s*', data.strip(), 1)
            data = control.readline()
            while data and re.match(b'\s+', data):
                val += b'\n' + data.strip()
                data = control.readline().rstrip()
            field = field.replace(b'-', b'_').lower()
            if field in self.default_tags + extra_tags or all_tags:
                # a hyphen is not allowed in dict keys
                self.fields[field] = val
        versrel = self.fields[b'version'].rsplit(b'-', 1)
        if len(versrel) == 2:
            self.fields[b'version'] = versrel[0]
            self.fields[b'release'] = versrel[1]
        else:
            self.fields[b'release'] = None
        verep = self.fields[b'version'].split(b':', 1)
        if len(verep) == 2:
            self.fields[b'epoch'] = verep[0]
            self.fields[b'version'] = verep[1]
        else:
            self.fields[b'epoch'] = b'0'
        self.fields[b'provides'] = self._split_field_value(b'provides')
        self.fields[b'depends'] = self._split_field_value(b'depends')
        self.fields[b'pre_depends'] = self._split_field_value(b'pre_depends')
        self.fields[b'conflicts'] = self._split_field_value(b'conflicts')
        self.fields[b'breaks'] = self._split_field_value(b'breaks')
        self.fields[b'recommends'] = self._split_field_value(b'recommends')
        self.fields[b'suggests'] = self._split_field_value(b'suggests')
        self.fields[b'enhances'] = self._split_field_value(b'enhances')
        if self_provides:
            # add self provides entry
            self.fields[b'provides'].append(b'%s (= %s)' % (self.name(), b'-'.join(versrel)))

    def _split_field_value(self, field, delimeter=b',\s*'):
        return [i.strip()
                for i in re.split(delimeter, self.fields.get(field, b'')) if i]

    def vercmp(self, debq):
        res = packagequery.cmp(int(self.epoch()), int(debq.epoch()))
        if res != 0:
            return res
        res = DebQuery.debvercmp(self.version(), debq.version())
        if res != 0:
            return res
        res = DebQuery.debvercmp(self.release(), debq.release())
        return res

    def name(self):
        return self.fields[b'package']

    def version(self):
        return self.fields[b'version']

    def release(self):
        return self.fields[b'release']

    def epoch(self):
        return self.fields[b'epoch']

    def arch(self):
        return self.fields[b'architecture']

    def description(self):
        return self.fields[b'description']

    def path(self):
        return self.__path

    def provides(self):
        return self.fields[b'provides']

    def requires(self):
        return self.fields[b'depends'] + self.fields[b'pre_depends']

    def conflicts(self):
        return self.fields[b'conflicts'] + self.fields[b'breaks']

    def obsoletes(self):
        return []

    def recommends(self):
        return self.fields[b'recommends']

    def suggests(self):
        return self.fields[b'suggests']

    def supplements(self):
        # a control file has no notion of "supplements"
        return []

    def enhances(self):
        return self.fields[b'enhances']

    def gettag(self, num):
        return self.fields.get(num, None)

    def canonname(self):
        return DebQuery.filename(self.name(), self.epoch(), self.version(), self.release(), self.arch())

    @staticmethod
    def query(filename, all_tags = False, *extra_tags):
        f = open(filename, 'rb')
        debq = DebQuery(f)
        debq.read(all_tags, *extra_tags)
        f.close()
        return debq

    @staticmethod
    def debvercmp(ver1, ver2):
        """
        implementation of dpkg's version comparison algorithm
        """
        # 32 is arbitrary - it is needed for the "longer digit string wins" handling
        # (found this nice approach in Build/Deb.pm (build package))
        ver1 = re.sub(b'(\d+)', lambda m: (32 * b'0' + m.group(1))[-32:], ver1)
        ver2 = re.sub(b'(\d+)', lambda m: (32 * b'0' + m.group(1))[-32:], ver2)
        vers = itertools.zip_longest(ver1, ver2, fillvalue=b'')
        for v1, v2 in vers:
            if v1 == v2:
                continue
            if not v1:
                # this makes the corresponding condition in the following
                # else part superfluous - keep the superfluous condition for
                # now (just to ease a (hopefully) upcoming refactoring (this
                # method really deserves a cleanup...))
                return -1
            if not v2:
                # see above
                return 1
            v1 = bytes(bytearray([v1]))
            v2 = bytes(bytearray([v2]))
            if (v1.isalpha() and v2.isalpha()) or (v1.isdigit() and v2.isdigit()):
                res = packagequery.cmp(v1, v2)
                if res != 0:
                    return res
            else:
                if v1 == b'~' or not v1:
                    return -1
                elif v2 == b'~' or not v2:
                    return 1
                ord1 = ord(v1)
                if not (v1.isalpha() or v1.isdigit()):
                    ord1 += 256
                ord2 = ord(v2)
                if not (v2.isalpha() or v2.isdigit()):
                    ord2 += 256
                if ord1 > ord2:
                    return 1
                else:
                    return -1
        return 0

    @staticmethod
    def filename(name, epoch, version, release, arch):
        if release:
            return b'%s_%s-%s_%s.deb' % (name, version, release, arch)
        else:
            return b'%s_%s_%s.deb' % (name, version, arch)

if __name__ == '__main__':
    import sys
    try:
        debq = DebQuery.query(sys.argv[1])
    except DebError as e:
        print(e.msg)
        sys.exit(2)
    print(debq.name(), debq.version(), debq.release(), debq.arch())
    print(debq.description())
    print('##########')
    print(b'\n'.join(debq.provides()))
    print('##########')
    print(b'\n'.join(debq.requires()))
