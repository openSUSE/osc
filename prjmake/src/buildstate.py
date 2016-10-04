# Copyright (c) 2016 Ericsson AB
# This program is free software; it may be used, copied, modified
# and distributed under the terms of the GNU General Public Licence,
# either version 2, or version 3 (at your option).
#

import os
import sys
import json
from oscpluginprjmake import datatypes
from oscpluginprjmake import settings

def pkg_to_json(pkg):
    return {
        'pkgdir': pkg._pkgdir,
        'name': pkg._name,
        'specfile': pkg._specfile,
        'specfile_md5sum': pkg._specfile_md5sum,
        'project': pkg._project
    }

class State:

    settings = None
    buildorder = None
    index = None

    def save(_self, statefile):
        if _self.settings is None:
            print("Unable to save state, settings not defined")
            sys.exit(1)
        if _self.buildorder is None:
            print("Unable to save state, buildorder not defined")
            sys.exit(1)
        if _self.index is None:
            print("Unable to save state, index not defined")
            sys.exit(1)

        statejson = {
            'index': _self.index,
            'buildorder': _self.buildorder,
            'settings': _self.settings._map
        }
        try:
            f = open(statefile, 'w+')
            f.write(json.dumps(statejson, default=pkg_to_json))
            f.close()
        except IOError as e:
            print(e)
            sys.exit(1)

    def load(_self, statefile):
        try:
            f = open(statefile)
            statejson = json.load(f)
            f.close()
        except IOError as e:
            print(e)
            sys.exit(1)
        _self.index = statejson['index']
        _self.buildorder = []
        for p in statejson['buildorder']:
            pkg = datatypes.OBSPackage()
            pkg.from_json(p)
            _self.buildorder += [pkg]
        _self.settings = settings.Settings()
        _self.settings._map = statejson['settings']

    def delete(_self, statefile):
        if os.path.exists(statefile):
            os.remove(statefile)

# vim: et sw=4 ts=4
