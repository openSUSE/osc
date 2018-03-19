#!/usr/bin/env python

from distutils.core import setup
import distutils.core
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
        man_path = os.path.join(self.build_base, 'osc.1.gz')
        distutils.log.info('generating %s' % man_path)
        outfile = gzip.open(man_path, 'wt')
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


# Support for documentation (sphinx)
class build_docs(distutils.core.Command):
    description = 'builds documentation using sphinx'
    user_options = []

    def initialize_options(self):
        self.built_docs = None

    def finalize_options(self):
        self.set_undefined_options('build', ('build_base', 'built_docs'))

    def run(self):
        # metadata contains information supplied in setup()
        metadata = self.distribution.metadata
        # package_dir may be None, in that case use the current directory.
        src_dir = (self.distribution.package_dir or {'': ''})['']
        src_dir = os.path.join(os.getcwd(),  src_dir)
        import sphinx
        sphinx.main(['runme', 
                    '-D', 'version=%s' % metadata.get_version(), 
                    os.path.join('docs',), os.path.join(self.built_docs, 'docs')])


# take a potential build-base option into account (for instance, if osc is
# build and installed like this:
# python setup.py build --build-base=<dir> ... install ...)
class install_data(distutils.command.install_data.install_data, object):
    def initialize_options(self):
        super(install_data, self).initialize_options()
        self.built_data = None

    def finalize_options(self):
        super(install_data, self).finalize_options()
        self.set_undefined_options('build', ('build_base', 'built_data'))
        data_files = []
        for f in self.data_files:
            # f is either a str or a (dir, files) pair
            # (see distutils.command.install_data.install_data.run)
            if isinstance(f, str):
                data_files.append(os.path.join(self.built_data, f))
            else:
                data_files.append((f[0], [os.path.join(self.built_data, i) for i in f[1]]))
        self.data_files = data_files


addparams = {}
if HAVE_PY2EXE:
    addparams['console'] = [{'script': 'osc-wrapper.py', 'dest_base': 'osc', 'icon_resources': [(1, 'osc.ico')]}]
    addparams['zipfile'] = 'shared.lib'
    addparams['options'] = {'py2exe': {'optimize': 0, 'compressed': True, 'packages': ['xml.etree', 'StringIO', 'gzip']}}

data_files = []
if sys.platform[:3] != 'win':
    data_files.append((os.path.join('share', 'man', 'man1'), ['osc.1.gz']))

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
        'build_docs' : build_docs,
        'install_data': install_data
        },
      **addparams
     )
