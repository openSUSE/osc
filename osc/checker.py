from __future__ import print_function

from tempfile import mkdtemp
import os
from shutil import rmtree
import rpm
import base64

class KeyError(Exception):
    def __init__(self, key, *args):
        Exception.__init__(self)
        self.args = args
        self.key = key
    def __str__(self):
        return ''+self.key+' :'+' '.join(self.args)

class Checker:
    def __init__(self):
        self.dbdir = mkdtemp(prefix='oscrpmdb')
        self.imported = {}
        rpm.addMacro('_dbpath', self.dbdir)
        self.ts = rpm.TransactionSet()
        self.ts.initDB()
        self.ts.openDB()
        self.ts.setVSFlags(0)
        #self.ts.Debug(1)

    def readkeys(self, keys=[]):
        rpm.addMacro('_dbpath', self.dbdir)
        for key in keys:
            try:
                self.readkey(key)
            except KeyError as e:
                print(e)

        if not len(self.imported):
            raise KeyError('', "no key imported")

        rpm.delMacro("_dbpath")

# python is an idiot
#    def __del__(self):
#        self.cleanup()

    def cleanup(self):
        self.ts.closeDB()
        rmtree(self.dbdir)

    def readkey(self, file):
        if file in self.imported:
            return

        fd = open(file, "r")
        line = fd.readline()
        if line and line[0:14] == "-----BEGIN PGP":
            line = fd.readline()
            while line and line != "\n":
                line = fd.readline()
            if not line:
                raise KeyError(file, "not a pgp public key")
        else:
            raise KeyError(file, "not a pgp public key")

        key = ''
        line = fd.readline()
        crc = None
        while line:
            if line[0:12] == "-----END PGP":
                break
            line = line.rstrip()
            if (line[0] == '='):
                crc = line[1:]
                line = fd.readline()
                break
            else:
                key += line
                line = fd.readline()
        fd.close()
        if not line or line[0:12] != "-----END PGP":
            raise KeyError(file, "not a pgp public key")

        # TODO: compute and compare CRC, see RFC 2440

        bkey = base64.b64decode(key)

        r = self.ts.pgpImportPubkey(bkey)
        if r != 0:
            raise KeyError(file, "failed to import pubkey")
        self.imported[file] = 1

    def check(self, pkg):
        # avoid errors on non rpm
        if pkg[-4:] != '.rpm': return
        fd = os.open(pkg, os.O_RDONLY)
        hdr = self.ts.hdrFromFdno(fd)
        os.close(fd)

if __name__ == "__main__":
    import sys
    keyfiles = []
    pkgs = []
    for arg in sys.argv[1:]:
        if arg[-4:] == '.rpm':
            pkgs.append(arg)
        else:
            keyfiles.append(arg)

    checker = Checker()
    try:
        checker.readkeys(keyfiles)
        for pkg in pkgs:
            checker.check(pkg)
    except Exception as e:
        checker.cleanup()
        raise e

# vim: sw=4 et
