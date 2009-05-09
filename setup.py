#!/usr/bin/env python

from distutils.core import setup
import distutils.command.build
import distutils.command.install_data
import os.path
import osc.core
from osc import commandline
from osc import babysitter

class build_osc(distutils.command.build.build, object):
    """
    Custom build command which generates man page.
    """

    def build_man_page(self):
        """
        """
        import gzip
        man_path = os.path.join('build', 'osc.1.gz')
        distutils.log.info('generating %s' % man_path)
        outfile = gzip.open(man_path, 'w')
        osccli = commandline.Osc(stdout = outfile)
        osccli.main(argv = ['osc','man'])
        outfile.close()

    def run(self):
        super(build_osc, self).run()
        self.build_man_page()

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
      data_files=[(os.path.join('share','man','man1'), [os.path.join('build', 'osc.1.gz')])],

      # Override certain command classes with our own ones
      cmdclass = {
        'build': build_osc,
        },
     )

