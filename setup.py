#!/usr/bin/env python

from distutils.core import setup

setup(name='osc',
      version='0.6',
      description='opensuse commander',
      author='Peter Poeml',
      author_email='poeml@suse.de',
      license='GPL',
      url='https://forgesvn1.novell.com/svn/opensuse/trunk/buildservice/src/clientlib/python/osc/',

      packages=['osc'],
      scripts=['osc_hotshot.py', 'osc-wrapper.py'],

     )

