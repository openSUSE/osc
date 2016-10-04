#!/usr/bin/env python
#
# Copyright (C) 2016 Ericsson AB
# This program is free software; it may be used, copied, modified
# and distributed under the terms of the GNU General Public Licence,
# either version 2, or version 3 (at your option).
#
from distutils.core import setup

setup(name='oscpluginprjmake',
    version='1.1',
    description='osc plugin for project level builds',
    author='Matias Hilden',
    author_email='matias.hilden@ericsson.com',
    package_dir={'oscpluginprjmake': 'src'},
    packages=['oscpluginprjmake']
)
