
from __future__ import print_function

from . import ar
import os.path
import re
import tarfile
from . import packagequery

class DebError(packagequery.PackageError):
    pass

class DebQuery(packagequery.PackageQuery, packagequery.PackageQueryResult):

    default_tags = ('package', 'version', 'release', 'epoch', 'architecture', 'description',
        'provides', 'depends', 'pre_depends', 'conflicts', 'breaks')

    def __init__(self, fh):
        self.__file = fh
        self.__path = os.path.abspath(fh.name)
        self.filename_suffix = 'deb'
        self.fields = {}

    def read(self, all_tags=False, self_provides=True, *extra_tags):
        arfile = ar.Ar(fh = self.__file)
        arfile.read()
        debbin = arfile.get_file('debian-binary')
        if debbin is None:
            raise DebError(self.__path, 'no debian binary')
        if debbin.read() != '2.0\n':
            raise DebError(self.__path, 'invalid debian binary format')
        control = arfile.get_file('control.tar.gz')
        if control is None:
            raise DebError(self.__path, 'missing control.tar.gz')
        # XXX: python2.4 relies on a name
        tar = tarfile.open(name = 'control.tar.gz', fileobj = control)
        try:
            name = './control'
            # workaround for python2.4's tarfile module
            if 'control' in tar.getnames():
                name = 'control'
            control = tar.extractfile(name)
        except KeyError:
            raise DebError(self.__path, 'missing \'control\' file in control.tar.gz')
        self.__parse_control(control, all_tags, self_provides, *extra_tags)
        return self

    def __parse_control(self, control, all_tags=False, self_provides=True, *extra_tags):
        data = control.readline().strip()
        while data:
            field, val = re.split(':\s*', data.strip(), 1)
            data = control.readline()
            while data and re.match('\s+', data):
                val += '\n' + data.strip()
                data = control.readline().rstrip()
            field = field.replace('-', '_').lower()
            if field in self.default_tags + extra_tags or all_tags:
                # a hyphen is not allowed in dict keys
                self.fields[field] = val
        versrel = self.fields['version'].rsplit('-', 1)
        if len(versrel) == 2:
            self.fields['version'] = versrel[0]
            self.fields['release'] = versrel[1]
        else:
            self.fields['release'] = None
        verep = self.fields['version'].split(':', 1)
        if len(verep) == 2:
            self.fields['epoch'] = verep[0]
            self.fields['version'] = verep[1]
        else:
            self.fields['epoch'] = '0'
        self.fields['provides'] = [ i.strip() for i in re.split(',\s*', self.fields.get('provides', '')) if i ]
        self.fields['depends'] = [ i.strip() for i in re.split(',\s*', self.fields.get('depends', '')) if i ]
        self.fields['pre_depends'] = [ i.strip() for i in re.split(',\s*', self.fields.get('pre_depends', '')) if i ]
        self.fields['conflicts'] = [ i.strip() for i in re.split(',\s*', self.fields.get('conflicts', '')) if i ]
        self.fields['breaks'] = [ i.strip() for i in re.split(',\s*', self.fields.get('breaks', '')) if i ]
        if self_provides:
            # add self provides entry
            self.fields['provides'].append('%s (= %s)' % (self.name(), '-'.join(versrel)))

    def vercmp(self, debq):
        res = cmp(int(self.epoch()), int(debq.epoch()))
        if res != 0:
            return res
        res = DebQuery.debvercmp(self.version(), debq.version())
        if res != None:
            return res
        res = DebQuery.debvercmp(self.release(), debq.release())
        return res

    def name(self):
        return self.fields['package']

    def version(self):
        return self.fields['version']

    def release(self):
        return self.fields['release']

    def epoch(self):
        return self.fields['epoch']

    def arch(self):
        return self.fields['architecture']

    def description(self):
        return self.fields['description']

    def path(self):
        return self.__path

    def provides(self):
        return self.fields['provides']

    def requires(self):
        return self.fields['depends'] + self.fields['pre_depends']

    def conflicts(self):
        return self.fields['conflicts'] + self.fields['breaks']

    def obsoletes(self):
        return []

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
        ver1 = re.sub('(\d+)', lambda m: (32 * '0' + m.group(1))[-32:], ver1)
        ver2 = re.sub('(\d+)', lambda m: (32 * '0' + m.group(1))[-32:], ver2)
        vers = map(lambda x, y: (x or '', y or ''), ver1, ver2)
        for v1, v2 in vers:
            if v1 == v2:
                continue
            if (v1.isalpha() and v2.isalpha()) or (v1.isdigit() and v2.isdigit()):
                res = cmp(v1, v2)
                if res != 0:
                    return res
            else:
                if v1 == '~' or not v1:
                    return -1
                elif v2 == '~' or not v2:
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
            return '%s_%s-%s_%s.deb' % (name, version, release, arch)
        else:
            return '%s_%s_%s.deb' % (name, version, arch)

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
    print('\n'.join(debq.provides()))
    print('##########')
    print('\n'.join(debq.requires()))
