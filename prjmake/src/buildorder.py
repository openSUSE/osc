# Copyright (C) 2016 Ericsson AB
# This program is free software; it may be used, copied, modified
# and distributed under the terms of the GNU General Public Licence,
# either version 2, or version 3 (at your option).
#

import os
import sys
import copy
from oscpluginprjmake import settings
from exceptions import NotImplementedError
try:
    from lxml import etree as ET
except ImportError:
    from xml.etree import ElementTree as ET

# Return 1 if pkg and otherpkg depend on each other, ie.
# pkg depends and reverse depends on otherpkg. Otherwise
# return 0.
def detect_circular_dep(pkg, otherpkg, deps, rdeps):
    if deps.has_key(pkg) and rdeps.has_key(otherpkg):
        if otherpkg in deps[pkg] and otherpkg in rdeps[pkg]:
            return 1
    return 0

# The purpose of this class is to calculate a dependency tree
# and a correct build order based on that dependency tree. There
# are two ways the build order is determined:
#
# 1: Dependency tree is built using the changed packages (can be all
# packages) as initial leaves for the tree. This results in the minimal
# possible dependency tree based on what packages changed. Build order
# is resolved by using DFS on the tree for every package in the tree.
#
# 2: A full dependency tree is built. Build order is resolved by using DFS
# on the desired package. This way only the packages needed for the desired
# package are built.
#
# For both cases the implementation in this class is the same, the way these
# functions are called makes the difference.
class BuildOrder:

    _sts = None

    def __init__(_self, prjmake_sts):
        _self._sts = prjmake_sts

    # Return 1 if this package depends on other pkg, otherwise return 0.
    # Note: this function assumes the working directory (workdir) is only
    # handled by it
    def has_dependency(_self, this, other):
        mode = _self._sts.get('buildorder_calc_mode')
        if mode == 'buildinfo':
            return _self.has_dependency_bi(this, other)
        elif mode == 'builddepinfo':
            return _self.has_dependency_bdi(this, other)
        else:
            raise StandardError('Unknown buildorder_calc_mode "%s"' % mode)

    # Uses buildinfos to deduce buildorder
    def has_dependency_bi(_self, this, other):
        bidir = _self._sts.get('buildinfodir')

        if this._specfile_md5sum is not None:
            bifile_this = os.path.join(bidir, '%s.%s.bi' %
                (this, this._specfile_md5sum))
        else:
            bifile_this = os.path.join(bidir, '%s.bi' % this)

        if other._specfile_md5sum is not None:
            bifile_other = os.path.join(bidir, '%s.%s.bi' %
                (other, other._specfile_md5sum))
        else:
            bifile_other = os.path.join(bidir, '%s.bi' % other)

        try:
            xml_this = ET.parse(bifile_this)
        except IOError:
            print('File not found: %s' % bifile_this)
            sys.exit(1)
        except:
            # We have to use generic except due to different exceptions in
            # lxml and etree.
            print('Corrupted buildinfo file: %s' % bifile_this)
            sys.exit(1)
        try:
            xml_other = ET.parse(bifile_other)
        except IOError:
            print('File not found: %s' % bifile_this)
            sys.exit(1)
        except:
            # We have to use generic except due to different exceptions in
            # lxml and etree.
            print('Corrupted buildinfo file: %s' % bifile_other)
            sys.exit(1)
        if xml_this.find('error') is not None:
            print('%s - %s' % (this._name, xml_this.find('error').text))
            sys.exit(1)
        if xml_other.find('error') is not None:
            print('%s - %s' % (other._name, xml_other.find('error').text))
            sys.exit(1)
        for package in xml_other.findall('subpack'):
            for bdep in xml_this.findall('bdep'):
                if (bdep.get('name') == package.text and
                    _self._sts.get('repo') == bdep.get('repository')):
                    return 1
        return 0

    # Uses builddepinfo from OBS api to deduce buildorder
    def has_dependency_bdi(_self, this, other):
        bidir = _self._sts.get('buildinfodir')

        bdifile_this = os.path.join(bidir, '%s.bdi' % this)
        bdifile_other = os.path.join(bidir, '%s.bdi' % other)
        try:
            xml_this = ET.parse(bdifile_this).find('package')
            if xml_this is None:
                # Local packages return empty bdi. TODO fix this when
                # we get new api functionality in OBS.
                return 0
        except IOError:
            print 'File not found: %s' % bifile_this
            sys.exit(1)
        except:
            # We have to use generic except due to different exceptions in
            # lxml and etree.
            print 'Unable to parse builddepinfo file: %s' % bdifile_this
            sys.exit(1)
        try:
            xml_other = ET.parse(bdifile_other).find('package')
            if xml_other is None:
                # See above
                return 0
        except IOError:
            print 'File not found: %s' % bifile_other
            sys.exit(1)
        except:
            # We have to use generic except due to different exceptions in
            # lxml and etree.
            print 'Unable to parse builddepinfo file: %s' % bdifile_other
            sys.exit(1)

        for subpkg in xml_other.findall('subpkg'):
            for pkgdep in xml_this.findall('pkgdep'):
                if pkgdep.text == subpkg.text:
                    return 1

        return 0

    # Build dependency graph for the list of packages given
    def build_dep_graph(_self):
        deps = dict()
        rdeps = dict()
        visited = dict()

        pkgs_changed = copy.copy(_self._sts.get('pkgs_changed'))
        packages = _self._sts.get('packages')
        for pkg in pkgs_changed:
            visited[pkg]=1

        for pkg in pkgs_changed:
            for otherpkg in packages:
                if pkg == otherpkg:
                    continue
                if _self.has_dependency(otherpkg, pkg):
                    if not deps.has_key(otherpkg):
                        deps[otherpkg] = [pkg]
                    else:
                        deps[otherpkg].append(pkg)
                    if not rdeps.has_key(pkg):
                        rdeps[pkg] = [otherpkg]
                    else:
                        rdeps[pkg].append(otherpkg)
                    if not visited.has_key(otherpkg):
                        pkgs_changed.append(otherpkg)
                        visited[otherpkg]=1
                    # Detect circular dependency
                    if detect_circular_dep(pkg, otherpkg, deps, rdeps):
                        print "Circular dependency detected:"
                        print "%s and %s require each other" % (pkg, otherpkg)
                        sys.exit(1)
        return deps

    # Standard DFS algorithm to determine correct build order
    def dfs(_self, pkg, buildorder, visited, deps):
        if visited.has_key(pkg):
            return
        if deps.has_key(pkg):
            for bdep in deps[pkg]:
                _self.dfs(bdep, buildorder, visited, deps)

        buildorder.append(pkg)
        visited[pkg]=1

    # Calculate build order for given dependency graph
    def calc_buildorder(_self, deps, packages):
        buildorder = []
        visited = dict()
        for pkg in packages:
            _self.dfs(pkg, buildorder, visited, deps)
        return buildorder

    # Parse build order from builddepinfo (view=order)
    # instead of calculating it.
    def parse_builddepinfo(_self, builddepinfo):
        try:
            xml_bdi = ET.fromstring(builddepinfo)
            buildorder = []
            for pkg in xml_bdi.findall('package'):
                buildorder += [pkg.get('name')]
            return buildorder
        except:
            # We have to use generic except due to different exceptions in
            # lxml and etree.
            print 'Unable to parse builddepinfo string: %s' % builddepinfo
            sys.exit(1)
# vim: et ts=4 sw=4
