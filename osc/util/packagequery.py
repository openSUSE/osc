import sys

from .helper import decode_it


class PackageError(Exception):
    """base class for all package related errors"""

    def __init__(self, fname, msg):
        super().__init__()
        self.fname = fname
        self.msg = msg


class PackageQueries(dict):
    """Dict of package name keys and package query values.  When assigning a
    package query, to a name, the package is evaluated to see if it matches the
    wanted architecture and if it has a greater version than the current value.
    """

    # map debian and rpm arches to common obs arches
    architectureMap = {'i386': ['i586', 'i686'], 'amd64': ['x86_64'], 'ppc64el': ['ppc64le'], 'armv6hl': ['armv6l'], 'armv7hl': ['armv7l']}

    def __init__(self, wanted_architecture):
        self.wanted_architecture = wanted_architecture
        super().__init__()

    def add(self, query):
        """Adds package query to dict if it is of the correct architecture and
        is newer (has a greater version) than the currently assigned package.

        :param query: a PackageQuery
        """
        self.__setitem__(query.name(), query)

    def __setitem__(self, name, query):
        if decode_it(name) != decode_it(query.name()):
            raise ValueError("key '%s' does not match "
                             "package query name '%s'" % (name, query.name()))

        architecture = decode_it(query.arch())

        if (architecture in [self.wanted_architecture, 'noarch', 'all', 'any']
            or self.wanted_architecture in self.architectureMap.get(architecture,
                                                                    [])):
            current_query = self.get(name)

            # if current query does not exist or is older than this new query
            if current_query is None or current_query.vercmp(query) <= 0:
                super().__setitem__(name, query)


class PackageQuery:
    """abstract base class for all package types"""

    def read(self, all_tags=False, *extra_tags):
        """Returns a PackageQueryResult instance"""
        raise NotImplementedError

    # Hmmm... this should be a module function (inherting this stuff
    # does not make much sense) (the same is true for the queryhdrmd5 method)
    @staticmethod
    def query(filename, all_tags=False, extra_rpmtags=(), extra_debtags=(), self_provides=True):
        f = open(filename, 'rb')
        magic = f.read(7)
        f.seek(0)
        extra_tags = ()
        pkgquery = None
        if magic[:4] == b'\xed\xab\xee\xdb':
            from . import rpmquery
            pkgquery = rpmquery.RpmQuery(f)
            extra_tags = extra_rpmtags
        elif magic == b'!<arch>':
            from . import debquery
            pkgquery = debquery.DebQuery(f)
            extra_tags = extra_debtags
        elif magic[:5] == b'<?xml':
            f.close()
            return None
        # arch tar ball compressed with gz, xz or zst
        elif magic[:5] == b'\375\067zXZ' or magic[:2] == b'\037\213' or magic[:4] == b'(\xb5/\xfd':
            from . import archquery
            pkgquery = archquery.ArchQuery(f)
        else:
            raise PackageError(filename, 'unsupported package type. magic: \'%s\'' % magic)
        pkgqueryresult = pkgquery.read(all_tags, self_provides, *extra_tags)
        f.close()
        return pkgqueryresult

    @staticmethod
    def queryhdrmd5(filename):
        f = open(filename, 'rb')
        magic = f.read(7)
        f.seek(0)
        if magic[:4] == b'\xed\xab\xee\xdb':
            from . import rpmquery
            f.close()
            return rpmquery.RpmQuery.queryhdrmd5(filename)
        return None


class PackageQueryResult:
    """abstract base class that represents the result of a package query"""

    def name(self):
        raise NotImplementedError

    def version(self):
        raise NotImplementedError

    def release(self):
        raise NotImplementedError

    def epoch(self):
        raise NotImplementedError

    def arch(self):
        raise NotImplementedError

    def description(self):
        raise NotImplementedError

    def path(self):
        raise NotImplementedError

    def provides(self):
        raise NotImplementedError

    def requires(self):
        raise NotImplementedError

    def conflicts(self):
        raise NotImplementedError

    def obsoletes(self):
        raise NotImplementedError

    def recommends(self):
        raise NotImplementedError

    def suggests(self):
        raise NotImplementedError

    def supplements(self):
        raise NotImplementedError

    def enhances(self):
        raise NotImplementedError

    def gettag(self, tag):
        raise NotImplementedError

    def vercmp(self, pkgquery):
        raise NotImplementedError

    def canonname(self):
        raise NotImplementedError

    def evr(self):
        evr = self.version()

        if self.release():
            evr += b"-" + self.release()

        epoch = self.epoch()
        if epoch is not None and epoch != 0:
            evr = epoch + b":" + evr
        return evr


def cmp(a, b):
    return (a > b) - (a < b)


if __name__ == '__main__':
    try:
        pkgq = PackageQuery.query(sys.argv[1])
    except PackageError as e:
        print(e.msg)
        sys.exit(2)
    print(pkgq.name())
    print(pkgq.version())
    print(pkgq.release())
    print(pkgq.description())
    print('##########')
    print('\n'.join(pkgq.provides()))
    print('##########')
    print('\n'.join(pkgq.requires()))
