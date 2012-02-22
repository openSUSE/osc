class PackageError(Exception):
    """base class for all package related errors"""
    def __init__(self, fname, msg):
        Exception.__init__(self)
        self.fname = fname
        self.msg = msg

class PackageQueries(dict):
    """Dict of package name keys and package query values.  When assigning a
    package query, to a name, the package is evaluated to see if it matches the
    wanted architecture and if it has a greater version than the current value.
    """

    # map debian arches to common obs arches
    architectureMap = {'i386': ['i586', 'i686'], 'amd64': ['x86_64']}

    def __init__(self, wanted_architecture):
        self.wanted_architecture = wanted_architecture
        super(PackageQueries, self).__init__()

    def add(self, query):
        """Adds package query to dict if it is of the correct architecture and
        is newer (has a greater version) than the currently assigned package.

        @param a PackageQuery
        """
        self.__setitem__(query.name(), query)

    def __setitem__(self, name, query):
        if name != query.name():
            raise ValueError("key '%s' does not match "
                             "package query name '%s'" % (name, query.name()))

        architecture = query.arch()

        if (architecture in [self.wanted_architecture, 'noarch', 'all'] or
            self.wanted_architecture in self.architectureMap.get(architecture,
                                                                [])):
            current_query = self.get(name)

            # if current query does not exist or is older than this new query
            if current_query is None or current_query.vercmp(query) <= 0:
                super(PackageQueries, self).__setitem__(name, query)

class PackageQuery:
    """abstract base class for all package types"""
    def read(self, all_tags = False, *extra_tags):
        raise NotImplementedError

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

    def gettag(self):
        raise NotImplementedError

    def vercmp(self, pkgquery):
        raise NotImplementedError

    def canonname(self):
        raise NotImplementedError

    @staticmethod
    def query(filename, all_tags = False, extra_rpmtags = (), extra_debtags = ()):
        f = open(filename, 'rb')
        magic = f.read(7)
        f.seek(0)
        extra_tags = ()
        pkgquery = None
        if magic[:4] == '\xed\xab\xee\xdb':
            import rpmquery
            pkgquery = rpmquery.RpmQuery(f)
            extra_tags = extra_rpmtags
        elif magic == '!<arch>':
            import debquery
            pkgquery = debquery.DebQuery(f)
            extra_tags = extra_debtags
        elif magic[:5] == '<?xml':
	    f.close()
	    return None
        else:
            raise PackageError(filename, 'unsupported package type. magic: \'%s\'' % magic)
        pkgquery.read(all_tags, *extra_tags)
        f.close()
        return pkgquery

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
