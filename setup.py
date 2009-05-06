#!/usr/bin/env python

from distutils.core import setup
import osc.core

setup(name='osc',
      version=osc.core.__version__,
      description='openSUSE (buildsystem) commander',
      long_description='Commandline client for the openSUSE Build Service, which allows to access repositories in the openSUSE Build Service in similar way as Subversion repositories.',
      author='openSUSE project',
      author_email='opensuse-buildservice@opensuse.org',
      license='GPL',
      platforms = ['Linux'],
      keywords = ['openSUSE', 'SUSE', 'RPM', 'build', 'buildservice'],
      url='https://forgesvn1.novell.com/svn/opensuse/trunk/buildservice/src/clientlib/python/osc/',

      packages=['osc', 'osc.util'],
      scripts=['osc_hotshot.py', 'osc-wrapper.py'],

     )

