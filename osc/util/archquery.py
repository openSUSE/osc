
from __future__ import print_function

import os.path
import re
import tarfile
from . import packagequery
import subprocess

class ArchError(packagequery.PackageError):
    pass

class ArchQuery(packagequery.PackageQuery, packagequery.PackageQueryResult):
    def __init__(self, fh):
        self.__file = fh
        self.__path = os.path.abspath(fh.name)
        self.fields = {}
        #self.magic = None
        #self.pkgsuffix = 'pkg.tar.gz'
        self.pkgsuffix = 'arch'

    def read(self, all_tags=True, self_provides=True, *extra_tags):
        # all_tags and *extra_tags are currently ignored
        f = open(self.__path, 'rb')
        #self.magic = f.read(5)
        #if self.magic == '\375\067zXZ':
        #    self.pkgsuffix = 'pkg.tar.xz'
        fn = open('/dev/null', 'wb')
        pipe = subprocess.Popen(['tar', '-O', '-xf', self.__path, '.PKGINFO'], stdout=subprocess.PIPE, stderr=fn).stdout
        for line in pipe.readlines():
            line = line.rstrip().split(' = ', 2)
            if len(line) == 2:
                if not line[0] in self.fields:
                    self.fields[line[0]] = []
                self.fields[line[0]].append(line[1])
        if self_provides:
            prv = '%s = %s' % (self.name(), self.fields['pkgver'][0])
            self.fields.setdefault('provides', []).append(prv)
        return self

    def vercmp(self, archq):
        res = cmp(int(self.epoch()), int(archq.epoch()))
        if res != 0:
            return res
        res = ArchQuery.rpmvercmp(self.version(), archq.version())
        if res != None:
            return res
        res = ArchQuery.rpmvercmp(self.release(), archq.release())
        return res

    def name(self):
        return self.fields['pkgname'][0] if 'pkgname' in self.fields else None

    def version(self):
        pkgver = self.fields['pkgver'][0] if 'pkgver' in self.fields else None
        if pkgver != None:
            pkgver = re.sub(r'[0-9]+:', '', pkgver, 1)
            pkgver = re.sub(r'-[^-]*$', '', pkgver)
        return pkgver

    def release(self):
        pkgver = self.fields['pkgver'][0] if 'pkgver' in self.fields else None
        if pkgver != None:
            m = re.search(r'-([^-])*$', pkgver)
            if m:
                return m.group(1)
        return None

    def epoch(self):
        pkgver = self.fields['pkgver'][0] if 'pkgver' in self.fields else None
        if pkgver != None:
            m = re.match(r'([0-9])+:', pkgver)
            if m:
                return m.group(1)
        return None

    def arch(self):
        return self.fields['arch'][0] if 'arch' in self.fields else None

    def description(self):
        return self.fields['pkgdesc'][0] if 'pkgdesc' in self.fields else None

    def path(self):
        return self.__path

    def provides(self):
        return self.fields['provides'] if 'provides' in self.fields else []

    def requires(self):
        return self.fields['depend'] if 'depend' in self.fields else []

    def conflicts(self):
        return self.fields['conflict'] if 'conflict' in self.fields else []

    def obsoletes(self):
        return self.fields['replaces'] if 'replaces' in self.fields else []

    def canonname(self):
        pkgver = self.fields['pkgver'][0] if 'pkgver' in self.fields else None
        return self.name() + '-' + pkgver + '-' + self.arch() + '.' + self.pkgsuffix

    def gettag(self, tag):
        # implement me, if needed
        return None

    @staticmethod
    def query(filename, all_tags = False, *extra_tags):
        f = open(filename, 'rb')
        archq = ArchQuery(f)
        archq.read(all_tags, *extra_tags)
        f.close()
        return archq

    @staticmethod
    def rpmvercmp(ver1, ver2):
        """
        implementation of RPM's version comparison algorithm
        (as described in lib/rpmvercmp.c)
        """
        if ver1 == ver2:
            return 0
        res = 0
        while res == 0:
            # remove all leading non alphanumeric chars
            ver1 = re.sub('^[^a-zA-Z0-9]*', '', ver1)
            ver2 = re.sub('^[^a-zA-Z0-9]*', '', ver2)
            if not (len(ver1) and len(ver2)):
                break
            # check if we have a digits segment
            mo1 = re.match('(\d+)', ver1)
            mo2 = re.match('(\d+)', ver2)
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
        if epoch:
            if release:
                return '%s-%s:%s-%s-%s.arch' % (name, epoch, version, release, arch)
            else:
                return '%s-%s:%s-%s.arch' % (name, epoch, version, arch)
        if release:
            return '%s-%s-%s-%s.arch' % (name, version, release, arch)
        else:
            return '%s-%s-%s.arch' % (name, version, arch)


if __name__ == '__main__':
    import sys
    try:
        archq = ArchQuery.query(sys.argv[1])
    except ArchError as e:
        print(e.msg)
        sys.exit(2)
    print(archq.name(), archq.version(), archq.release(), archq.arch())
    print(archq.canonname())
    print(archq.description())
    print('##########')
    print('\n'.join(archq.provides()))
    print('##########')
    print('\n'.join(archq.requires()))
