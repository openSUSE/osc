from ..util.models import *  # pylint: disable=wildcard-import,unused-wildcard-import


class BlockModes(str, Enum):
    ALL = "all"
    LOCAL = "local"
    NEVER = "never"


class BoolString(str, Enum):
    TRUE = "true"
    FALSE = "false"


class BuildArch(str, Enum):
    NOARCH = "noarch"
    AARCH64 = "aarch64"
    AARCH64_ILP32 = "aarch64_ilp32"
    ARMV4L = "armv4l"
    ARMV5L = "armv5l"
    ARMV6L = "armv6l"
    ARMV7L = "armv7l"
    ARMV5EL = "armv5el"
    ARMV6EL = "armv6el"
    ARMV7EL = "armv7el"
    ARMV7HL = "armv7hl"
    ARMV8EL = "armv8el"
    HPPA = "hppa"
    M68K = "m68k"
    I386 = "i386"
    I486 = "i486"
    I586 = "i586"
    I686 = "i686"
    ATHLON = "athlon"
    IA64 = "ia64"
    K1OM = "k1om"
    LOONGARCH64 = "loongarch64"
    MIPS = "mips"
    MIPSEL = "mipsel"
    MIPS32 = "mips32"
    MIPS64 = "mips64"
    MIPS64EL = "mips64el"
    PPC = "ppc"
    PPC64 = "ppc64"
    PPC64P7 = "ppc64p7"
    PPC64LE = "ppc64le"
    RISCV64 = "riscv64"
    S390 = "s390"
    S390X = "s390x"
    SH4 = "sh4"
    SPARC = "sparc"
    SPARC64 = "sparc64"
    SPARC64V = "sparc64v"
    SPARCV8 = "sparcv8"
    SPARCV9 = "sparcv9"
    SPARCV9V = "sparcv9v"
    X86_64 = "x86_64"
    LOCAL = "local"


class LinkedbuildModes(str, Enum):
    OFF = "off"
    LOCALDEP = "localdep"
    ALLDIRECT = "alldirect"
    ALL = "all"


class LocalRole(str, Enum):
    MAINTAINER = "maintainer"
    BUGOWNER = "bugowner"
    REVIEWER = "reviewer"
    DOWNLOADER = "downloader"
    READER = "reader"


class ObsRatings(str, Enum):
    LOW = "low"
    MODERATE = "moderate"
    IMPORTANT = "important"
    CRITICAL = "critical"


class RebuildModes(str, Enum):
    TRANSITIVE = "transitive"
    DIRECT = "direct"
    LOCAL = "local"


class ReleaseTriggers(str, Enum):
    MANUAL = "manual"
    MAINTENANCE = "maintenance"
    OBSGENDIFF = "obsgendiff"


class RequestStates(str, Enum):
    REVIEW = "review"
    NEW = "new"
    ACCEPTED = "accepted"
    DECLINED = "declined"
    REVOKED = "revoked"
    SUPERSEDED = "superseded"
    DELETED = "deleted"
