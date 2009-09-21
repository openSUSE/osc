import ar
import re
import tarfile
import packagequery

class DebError(packagequery.PackageError):
    pass

class DebQuery(packagequery.PackageQuery):
    def __init__(self, fh):
        self.__file = fh
        self.filename_suffix = 'deb'
        self.fields = {}

    def read(self):
        arfile = ar.Ar(fh = self.__file)
        arfile.read()
        debbin = arfile.get_file('debian-binary')
        if debbin is None:
            raise DebError('no debian binary')
        if debbin.read() != '2.0\n':
            raise DebError('invalid debian binary format')
        control = arfile.get_file('control.tar.gz')
        if control is None:
            raise DebError('missing control.tar.gz')
        tar = tarfile.open(fileobj = control)
        try:
            control = tar.extractfile('./control')
        except KeyError:
            raise DebError('missing \'control\' file in control.tar.gz')
        self.__parse_control(control)

    def __parse_control(self, control):
        data = control.readline().strip()
        while data:
            field, val = re.split(':\s*', data.strip(), 1)
            data = control.readline()
            while data and re.match('\s+', data):
                val += '\n' + data.strip()
                data = control.readline().rstrip()
            # a hyphen is not allowed in dict keys
            self.fields[field.replace('-', '_').lower()] = val
        versrel = self.fields['version'].rsplit('-', 1)
        if len(versrel) == 2:
            self.fields['version'] = versrel[0]
            self.fields['release'] = versrel[1]
        else:
            self.fields['release'] = None
        self.fields['provides'] = [ i.strip() for i in re.split(',\s*', self.fields.get('provides', '')) if i ]
        self.fields['depends'] = [ i.strip() for i in re.split(',\s*', self.fields.get('depends', '')) if i ]
        self.fields['pre_depends'] = [ i.strip() for i in re.split(',\s*', self.fields.get('pre_depends', '')) if i ]
        # add self provides entry
        self.fields['provides'].append('%s = %s' % (self.name(), '-'.join(versrel)))

    def vercmp(self, debq):
        # XXX: just a dummy - the implementation will follow soon
        return 0

    def name(self):
        return self.fields['package']

    def version(self):
        return self.fields['version']

    def release(self):
        return self.fields['release']

    def arch(self):
        return self.fields['architecture']

    def description(self):
        return self.fields['description']

    def provides(self):
        return self.fields['provides']

    def requires(self):
        return self.fields['depends']

    def getTag(self, num):
        return self.fields.get(num, None)

    @staticmethod
    def query(filename):
        f = open(filename, 'rb')
        debq = DebQuery(f)
        debq.read()
        f.close()
        return debq

if __name__ == '__main__':
    import sys
    try:
        debq = DebQuery.query(sys.argv[1])
    except DebError, e:
        print e.msg
        sys.exit(2)
    print debq.name(), debq.version(), debq.release(), debq.arch()
    print debq.description()
    print '##########'
    print '\n'.join(debq.provides())
    print '##########'
    print '\n'.join(debq.requires())
