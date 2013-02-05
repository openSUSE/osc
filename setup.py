#!/usr/bin/env python

from distutils.core import setup
import distutils.command.build
import distutils.command.install_data
import os.path
import osc.core
import sys
from osc import commandline
from osc import babysitter
# optional support for py2exe
try:
    import py2exe
    HAVE_PY2EXE = True
except:
    HAVE_PY2EXE = False


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
        osccli = commandline.Osc(stdout=outfile)
        # FIXME: we cannot call the main method because osc expects an ~/.oscrc
        # file (this would break builds in environments like the obs)
        #osccli.main(argv = ['osc','man'])
        osccli.optparser = osccli.get_optparser()
        osccli.do_man(None)
        outfile.close()

    def run(self):
        super(build_osc, self).run()
        self.build_man_page()

addparams = {}
if HAVE_PY2EXE:
    addparams['console'] = [{'script': 'osc-wrapper.py', 'dest_base': 'osc', 'icon_resources': [(1, 'osc.ico')]}]
    addparams['zipfile'] = 'shared.lib'
    addparams['options'] = {'py2exe': {'optimize': 0, 'compressed': True, 'packages': ['xml.etree', 'StringIO', 'gzip']}}

data_files = []
if sys.platform[:3] != 'win':
    data_files.append((os.path.join('share', 'man', 'man1'), [os.path.join('build', 'osc.1.gz')]))

setup(name='osc',
      version = osc.core.__version__,
      description = 'openSUSE commander',
      long_description = 'Command-line client for the openSUSE Build Service, which allows to access repositories in the openSUSE Build Service in similar way as Subversion repositories.',
      author = 'openSUSE project',
      author_email = 'opensuse-buildservice@opensuse.org',
      license = 'GPL',
      platforms = ['Linux', 'Mac OSX', 'Windows XP/2000/NT', 'Windows 95/98/ME', 'FreeBSD'],
      keywords = ['openSUSE', 'SUSE', 'RPM', 'build', 'buildservice'],
      url = 'http://en.opensuse.org/openSUSE:OSC',
      download_url = 'https://github.com/openSUSE/osc',
      packages = ['osc', 'osc.util'],
      scripts = ['osc_hotshot.py', 'osc-wrapper.py'],
      data_files = data_files,

      # Override certain command classes with our own ones
      cmdclass = {
        'build': build_osc,
        },
      **addparams
     )
