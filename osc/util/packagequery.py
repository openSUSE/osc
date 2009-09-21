class PackageError(Exception):
    """base class for all package related errors"""
    def __init__(self, msg):
        Exception.__init__(self)
        self.msg = msg

class PackageQuery:
    """abstract base class for all package types"""
    def read(self):
        raise NotImplementedError

    def name(self):
        raise NotImplementedError

    def version(self):
        raise NotImplementedError

    def release(self):
        raise NotImplementedError

    def arch(self):
        raise NotImplementedError

    def description(self):
        raise NotImplementedError

    def provides(self):
        raise NotImplementedError

    def requires(self):
        raise NotImplementedError

    def getTag(self):
        raise NotImplementedError

    def vercmp(self, pkgq):
        raise NotImplementedError

    @staticmethod
    def query(filename):
        f = open(filename, 'rb')
        magic = f.read(7)
        f.seek(0)
        pkgq = None
        if magic[:4] == '\xed\xab\xee\xdb':
            import rpmquery
            pkgq = rpmquery.RpmQuery(f)
        elif magic == '!<arch>':
            import debquery
            pkgq = debquery.DebQuery(f)
        else:
            raise PackageError('unsupported package type. magic: \'%s\' (%s)' % (magic, filename))
        pkgq.read()
        f.close()
        return pkgq

if __name__ == '__main__':
    import sys
    try:
        pkgq = PackageQuery.query(sys.argv[1])
    except PackageError, e:
        print e.msg
        sys.exit(2)
    print pkgq.name()
    print pkgq.version()
    print pkgq.release()
    print pkgq.description()
    print '##########'
    print '\n'.join(pkgq.provides())
    print '##########'
    print '\n'.join(pkgq.requires())
