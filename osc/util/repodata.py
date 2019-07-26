"""Module for reading repodata directory (created with createrepo) for package
information instead of scanning individual rpms."""

# standard modules
import gzip
import os.path

# cElementTree can be standard or 3rd-party depending on python version
try:
    from xml.etree import cElementTree as ET
except ImportError:
    import cElementTree as ET

# project modules
import osc.util.rpmquery
import osc.util.packagequery

def namespace(name):
    return "{http://linux.duke.edu/metadata/%s}" % name

OPERATOR_BY_FLAGS = {
    "EQ" : "=",
    "LE" : "<=",
    "GE" : ">=",
    "LT" : "<",
    "GT" : ">"
}

def primaryPath(directory):
    """Returns path to the primary repository data file.

    @param directory repository directory that contains the repodata subdirectory
    @return str path to primary repository data file
    @raise IOError if repomd.xml contains no primary location
    """
    metaDataPath = os.path.join(directory, "repodata", "repomd.xml")
    elementTree = ET.parse(metaDataPath)
    root = elementTree.getroot()

    for dataElement in root:
        if dataElement.get("type") == "primary":
            locationElement = dataElement.find(namespace("repo") + "location")
            # even though the repomd.xml file is under repodata, the location a
            # attribute is relative to parent directory (directory).
            primaryPath = os.path.join(directory, locationElement.get("href"))
            break
    else:
        raise IOError("'%s' contains no primary location" % metaDataPath)

    return primaryPath

def queries(directory):
    """Returns a list of RepoDataQueries constructed from the repodata under
    the directory.

    @param directory path to a repository directory (parent directory of
                     repodata directory)
    @return list of RepoDataQueryResult instances
    @raise IOError if repomd.xml contains no primary location
    """
    path = primaryPath(directory)

    gunzippedPrimary = gzip.GzipFile(path)
    elementTree = ET.parse(gunzippedPrimary)
    root = elementTree.getroot()

    packageQueries = []
    for packageElement in root:
        packageQuery = RepoDataQueryResult(directory, packageElement)
        packageQueries.append(packageQuery)

    return packageQueries

class RepoDataQueryResult(osc.util.packagequery.PackageQueryResult):
    """PackageQueryResult that reads in data from the repodata directory files."""

    def __init__(self, directory, element):
        """Creates a RepoDataQueryResult from the a package Element under a metadata
        Element in a primary.xml file.

        @param directory repository directory path.  Used to convert relative
                         paths to full paths.
        @param element package Element
        """
        self.__directory = os.path.abspath(directory)
        self.__element = element

    def __formatElement(self):
        return self.__element.find(namespace("common") + "format")

    def __parseEntry(self, element):
        entry = element.get("name")
        flags = element.get("flags")

        if flags is not None:
            version = element.get("ver")
            operator = OPERATOR_BY_FLAGS[flags]
            entry += " %s %s" % (operator, version)

            release = element.get("rel")
            if release is not None:
                entry += "-%s" % release

        return entry

    def __parseEntryCollection(self, collection):
        formatElement = self.__formatElement()
        collectionElement = formatElement.find(namespace("rpm") + collection)

        entries = []
        if collectionElement is not None:
            for entryElement in collectionElement.findall(namespace("rpm") +
                                                          "entry"):
                entry = self.__parseEntry(entryElement)
                entries.append(entry)

        return entries

    def __versionElement(self):
        return self.__element.find(namespace("common") + "version")

    def arch(self):
        return self.__element.find(namespace("common") + "arch").text

    def description(self):
        return self.__element.find(namespace("common") + "description").text

    def distribution(self):
        return None

    def epoch(self):
        return self.__versionElement().get("epoch")

    def name(self):
        return self.__element.find(namespace("common") + "name").text

    def path(self):
        locationElement = self.__element.find(namespace("common") + "location")
        relativePath = locationElement.get("href")
        absolutePath = os.path.join(self.__directory, relativePath)

        return absolutePath

    def provides(self):
        return self.__parseEntryCollection("provides")

    def release(self):
        return self.__versionElement().get("rel")

    def requires(self):
        return self.__parseEntryCollection("requires")

    def conflicts(self):
        return self.__parseEntryCollection('conflicts')

    def obsoletes(self):
        return self.__parseEntryCollection('obsoletes')

    def recommends(self):
        return self.__parseEntryCollection('recommends')

    def suggests(self):
        return self.__parseEntryCollection('suggests')

    def supplements(self):
        return self.__parseEntryCollection('supplements')

    def enhances(self):
        return self.__parseEntryCollection('enhances')

    def canonname(self):
        if self.release() is None:
            release = None
        else:
            release = self.release().encode()
        return osc.util.rpmquery.RpmQuery.filename(self.name().encode(), None,
            self.version().encode(), release, self.arch().encode())

    def gettag(self, tag):
        # implement me, if needed
        return None

    def vercmp(self, other):
        res = osc.util.rpmquery.RpmQuery.rpmvercmp(str(self.epoch()).encode(), str(other.epoch()).encode())
        if res != 0:
            return res
        res = osc.util.rpmquery.RpmQuery.rpmvercmp(self.version().encode(), other.version().encode())
        if res != 0:
            return res
        res = osc.util.rpmquery.RpmQuery.rpmvercmp(self.release().encode(), other.release().encode())
        return res

    def version(self):
        return self.__versionElement().get("ver")
