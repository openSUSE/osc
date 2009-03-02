#!/usr/bin/env python

from distutils.core import setup

setup(name='osc',
      version='0.7',
      description='opensuse commander',
      author='openSUSE project',
      author_email='opensuse-buildservice@opensuse.org',
      license='GPL',
      url='https://forgesvn1.novell.com/svn/opensuse/trunk/buildservice/src/clientlib/python/osc/',

      packages=['osc'],
      scripts=['osc_hotshot.py', 'osc-wrapper.py'],

     )

