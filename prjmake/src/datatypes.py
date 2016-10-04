# Copyright (C) 2016 Ericsson AB
# This program is free software; it may be used, copied, modified
# and distributed under the terms of the GNU General Public Licence,
# either version 2, or version 3 (at your option).
#

class OBSPackage:
    _pkgdir = None
    _name = None
    _specfile = None
    _specfile_md5sum = None
    _project = None

    def __eq__(self, other):
        if type(other) is str:
            return self._pkgdir == other
        elif isinstance(other, OBSPackage):
            return self._pkgdir == other._pkgdir
        else:
            return False

    def __hash__(self):
        return hash(self._pkgdir)

    def __str__(self):
        return self._name

    def from_json(self, json):
        self._pkgdir = json['pkgdir']
        self._name = json['name']
        self._specfile = json['specfile']
        self._specfile_md5sum = json['specfile_md5sum']
        self._project = json['project']

# vim: et ts=4 sw=4
