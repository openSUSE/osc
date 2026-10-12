import os
from functools import wraps

import rpm

from . import packagequery

RPMTAG_OLDSUGGESTSNAME = getattr(rpm, "RPMTAG_OLDSUGGESTSNAME", 1156)
RPMTAG_OLDSUGGESTSFLAGS = getattr(rpm, "RPMTAG_OLDSUGGESTSFLAGS", 1158)
RPMTAG_OLDSUGGESTSVERSION = getattr(rpm, "RPMTAG_OLDSUGGESTSVERSION", 1157)
RPMSENSE_STRONG = getattr(rpm, "RPMSENSE_STRONG", 1 << 27)


def cmp(a, b):
    return (a > b) - (a < b)


def to_bytes(func):
    """Decorator to convert return values (str, list[str], or raw values) into bytes."""
    def _convert(val):
        if val is None:
            return None
        if isinstance(val, bytes):
            return val
        if isinstance(val, str):
            return val.encode("utf-8", errors="surrogateescape")
        return str(val).encode("utf-8")

    @wraps(func)
    def wrapper(*args, **kwargs):
        val = func(*args, **kwargs)
        if val is None:
            return None
        if isinstance(val, list):
            return [_convert(item) for item in val]
        return _convert(val)

    return wrapper


class RpmError(packagequery.PackageError):
    pass


class RpmHeaderError(RpmError):
    pass


class RpmHeaderEntry:
    def __init__(self, data):
        self.data = data


class RpmQuery(packagequery.PackageQuery, packagequery.PackageQueryResult):
    def __init__(self, fh):
        self.__file = fh
        self.__path = os.path.abspath(fh.name) if hasattr(fh, "name") else ""
        self.filename_suffix = "rpm"
        self.header = None

    def read(self, all_tags=False, self_provides=True, *extra_tags, **extra_kw):
        ts = rpm.TransactionSet()
        ts.setVSFlags(rpm._RPMVSF_NOSIGNATURES)
        close_fd = False
        fd = None
        try:
            if hasattr(self.__file, "fileno"):
                try:
                    fd = self.__file.fileno()
                    if hasattr(self.__file, "seek"):
                        self.__file.seek(0)
                except (OSError, AttributeError):
                    fd = None
            if fd is None:
                if self.__path and os.path.isfile(self.__path):
                    fd = os.open(self.__path, os.O_RDONLY)
                    close_fd = True
                else:
                    raise RpmError(self.__path, "file descriptor or path not accessible")
            try:
                self.header = ts.hdrFromFdno(fd)
            except rpm.error as e:
                raise RpmError(self.__path, str(e))
        except OSError as e:
            raise RpmError(self.__path, str(e))
        finally:
            if close_fd and fd is not None:
                os.close(fd)

        if self.header is None:
            raise RpmHeaderError(self.__path, "failed to read rpm header")
        return self

    @to_bytes
    def _reqprov(self, tag, flagstag, vertag, strong=None):
        """
        Format RPM dependency tuples (name, flags, version) into formatted byte strings.

        :param tag: RPM tag for dependency names.
        :param flagstag: RPM tag for dependency flags.
        :param vertag: RPM tag for dependency versions.
        :param strong: Legacy compatibility filter for the obsolete RPMTAG_OLDSUGGESTS* tags
                       (used in SUSE packages circa 2005-2007 prior to RPM 4.4 weak dependencies).
                       In that format, recommends and suggests shared the same tags:
                       - If strong is True: filters for "Recommends" (RPMSENSE_STRONG bit set).
                       - If strong is False: filters for "Suggests" (RPMSENSE_STRONG bit unset).
                       - If strong is None: no sense filtering is performed (standard dependencies).
        """
        pnames = self.header[tag]
        if not pnames:
            return []
        pflags = self.header[flagstag] or []
        pvers = self.header[vertag] or []
        target_strong = RPMSENSE_STRONG if strong else 0
        res = []
        for name, flags, ver in zip(pnames, pflags, pvers):
            if isinstance(name, bytes):
                name = name.decode("utf-8", errors="surrogateescape")
            if isinstance(ver, bytes):
                ver = ver.decode("utf-8", errors="surrogateescape")
            if strong is not None and (flags & RPMSENSE_STRONG) != target_strong:
                continue
            # RPMSENSE_SENSEMASK = 15 but ignore RPMSENSE_SERIAL (= 1 << 0) therefore use 14
            if flags & 14:
                name += " "
                if flags & (1 << 2):  # GREATER
                    name += ">"
                elif flags & (1 << 1):  # LESS
                    name += "<"
                if flags & (1 << 3):  # EQUAL
                    name += "="
                name += f" {ver}"
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

    @to_bytes
    def name(self):
        return self.header[rpm.RPMTAG_NAME]

    @to_bytes
    def version(self):
        return self.header[rpm.RPMTAG_VERSION]

    @to_bytes
    def release(self):
        return self.header[rpm.RPMTAG_RELEASE]

    def epoch(self):
        epoch = self.header[rpm.RPMTAG_EPOCH]
        if epoch is None:
            return 0
        return int(epoch)

    @to_bytes
    def arch(self):
        return self.header[rpm.RPMTAG_ARCH]

    @to_bytes
    def summary(self):
        return self.header[rpm.RPMTAG_SUMMARY]

    @to_bytes
    def description(self):
        return self.header[rpm.RPMTAG_DESCRIPTION]

    @to_bytes
    def url(self):
        return self.header[rpm.RPMTAG_URL]

    def path(self):
        return self.__path

    def provides(self):
        return self._reqprov(rpm.RPMTAG_PROVIDENAME, rpm.RPMTAG_PROVIDEFLAGS, rpm.RPMTAG_PROVIDEVERSION)

    def requires(self):
        return self._reqprov(rpm.RPMTAG_REQUIRENAME, rpm.RPMTAG_REQUIREFLAGS, rpm.RPMTAG_REQUIREVERSION)

    def conflicts(self):
        return self._reqprov(rpm.RPMTAG_CONFLICTNAME, rpm.RPMTAG_CONFLICTFLAGS, rpm.RPMTAG_CONFLICTVERSION)

    def obsoletes(self):
        return self._reqprov(rpm.RPMTAG_OBSOLETENAME, rpm.RPMTAG_OBSOLETEFLAGS, rpm.RPMTAG_OBSOLETEVERSION)

    def recommends(self):
        res = self._reqprov(rpm.RPMTAG_RECOMMENDNAME, rpm.RPMTAG_RECOMMENDFLAGS, rpm.RPMTAG_RECOMMENDVERSION)
        if not res:
            res = self._reqprov(RPMTAG_OLDSUGGESTSNAME, RPMTAG_OLDSUGGESTSFLAGS, RPMTAG_OLDSUGGESTSVERSION, strong=True)
        return res

    def suggests(self):
        res = self._reqprov(rpm.RPMTAG_SUGGESTNAME, rpm.RPMTAG_SUGGESTFLAGS, rpm.RPMTAG_SUGGESTVERSION)
        if not res:
            res = self._reqprov(RPMTAG_OLDSUGGESTSNAME, RPMTAG_OLDSUGGESTSFLAGS, RPMTAG_OLDSUGGESTSVERSION, strong=False)
        return res

    def supplements(self):
        return self._reqprov(rpm.RPMTAG_SUPPLEMENTNAME, rpm.RPMTAG_SUPPLEMENTFLAGS, rpm.RPMTAG_SUPPLEMENTVERSION)

    def enhances(self):
        return self._reqprov(rpm.RPMTAG_ENHANCENAME, rpm.RPMTAG_ENHANCEFLAGS, rpm.RPMTAG_ENHANCEVERSION)

    def is_src(self):
        return self.header[rpm.RPMTAG_SOURCERPM] is None

    def is_nosrc(self):
        if not self.is_src():
            return False
        return bool(
            self.header[rpm.RPMTAG_NOSOURCE]
            or self.header[rpm.RPMTAG_NOPATCH]
        )

    def gettag(self, num):
        val = self.header[num]
        if val is None:
            return None
        return RpmHeaderEntry(val)

    def canonname(self):
        if self.is_nosrc():
            arch = b"nosrc"
        elif self.is_src():
            arch = b"src"
        else:
            arch = self.arch()
        return RpmQuery.filename(self.name(), None, self.version(), self.release(), arch)

    @staticmethod
    def query(filename):
        with open(filename, "rb") as f:
            rpmq = RpmQuery(f)
            rpmq.read()
        return rpmq

    @staticmethod
    def queryhdrmd5(filename):
        try:
            with open(filename, "rb") as f:
                rpmq = RpmQuery(f)
                rpmq.read()
                val = rpmq.header[rpm.RPMTAG_SIGMD5]
                if val is None:
                    return None
                if isinstance(val, (bytes, bytearray)):
                    return val.hex()
                return str(val)
        except (OSError, RpmError, rpm.error):
            return None

    @staticmethod
    def rpmvercmp(v1, v2):
        if not v1:
            v1 = ""
        elif isinstance(v1, bytes):
            v1 = v1.decode("utf-8", errors="surrogateescape")

        if not v2:
            v2 = ""
        elif isinstance(v2, bytes):
            v2 = v2.decode("utf-8", errors="surrogateescape")

        if v1 == v2:
            return 0
        if not v1:
            return -1
        if not v2:
            return 1
        return rpm.labelCompare(("0", v1, "0"), ("0", v2, "0"))

    @staticmethod
    def filename(name, epoch, version, release, arch):
        return b"%s-%s-%s.%s.rpm" % (name, version, release, arch)
