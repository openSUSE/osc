# Copyright (C) 2016 Ericsson AB
# This program is free software; it may be used, copied, modified
# and distributed under the terms of the GNU General Public Licence,
# either version 2, or version 3 (at your option).
#

import copy
from exceptions import StandardError

class Settings:
    _map = {}
    _lists = ['packages', 'pkgs_changed', 'makeopts', 'buildopts', 'excludes']

    def set(_self, key, value):
        if key in _self._lists:
            _self._map[key] = copy.copy(value)
        else:
            _self._map[key] = value

    def get(_self, key):
        if not _self._map.has_key(key):
            raise StandardError('%s not set' % key)
        return _self._map[key]

# vim: et ts=4 sw=4
