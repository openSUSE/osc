#!/usr/bin/env python3


import distutils.core
import gzip
import os
import setuptools
from distutils.command import build, install_data

import osc.commandline
import osc.core


class build_osc(build.build):
    """
    Custom build command which generates man page.
    """

    def build_man_page(self):
        """
        """
        try:
            os.makedirs(self.build_base)
        except OSError:
            pass
        man_path = os.path.join(self.build_base, 'osc.1.gz')
        distutils.log.info('generating %s' % man_path)
        outfile = gzip.open(man_path, 'wt')
        osccli = osc.commandline.Osc(stdout=outfile)
        # FIXME: we cannot call the main method because osc expects an ~/.oscrc
        # file (this would break builds in environments like the obs)
        # osccli.main(argv = ['osc','man'])
        osccli.optparser = osccli.get_optparser()
        osccli.do_man(None)
        outfile.close()

    def run(self):
        super().run()
        self.build_man_page()


# take a potential build-base option into account (for instance, if osc is
# build and installed like this:
# python setup.py build --build-base=<dir> ... install ...)
class install_data(install_data.install_data):
    def initialize_options(self):
        super().initialize_options()
        self.built_data = None

    def finalize_options(self):
        super().finalize_options()
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


data_files = []
data_files.append((os.path.join('share', 'man', 'man1'), ['osc.1.gz']))

with open("README.md") as fh:
    lines = fh.readlines()
    while lines:
        line = lines[0].strip()
        if not line or line.startswith("["):
            # skip leading empty lines
            # skip leading lines with links to badges
            lines.pop(0)
            continue
        break
    long_description = "".join(lines)

cmdclass = {
    'build': build_osc,
    'install_data': install_data
}

# keep build deps minimal and be tolerant to missing sphinx
# that is not needed during package build
try:
    import sphinx.setup_command
    cmdclass['build_doc'] = sphinx.setup_command.BuildDoc
except ImportError:
    pass


setuptools.setup(
    name='osc',
    version=osc.core.__version__,
    description='openSUSE commander',
    long_description=long_description,
    long_description_content_type="text/plain",
    author='openSUSE project',
    author_email='opensuse-buildservice@opensuse.org',
    license='GPLv2+',
    platforms=['Linux', 'MacOS X', 'FreeBSD'],
    keywords=['openSUSE', 'SUSE', 'RPM', 'build', 'buildservice'],
    url='http://en.opensuse.org/openSUSE:OSC',
    download_url='https://github.com/openSUSE/osc',
    packages=['osc', 'osc.util'],
    data_files=data_files,
    install_requires=['cryptography', 'urllib3'],
    extras_require={
       'RPM signature verification': ['rpm'],
    },
    entry_points={
      'console_scripts': [
          'osc=osc.babysitter:main'
          ],
    },
    classifiers=[
        "Development Status :: 5 - Production/Stable",
        "Environment :: Console",
        "Intended Audience :: Developers",
        "Intended Audience :: Information Technology",
        "Intended Audience :: System Administrators",
        "License :: OSI Approved :: GNU General Public License v2 or later (GPLv2+)",
        "Operating System :: MacOS :: MacOS X",
        "Operating System :: POSIX :: BSD :: FreeBSD",
        "Operating System :: POSIX :: Linux",
        "Programming Language :: Python",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.6",
        "Programming Language :: Python :: 3.7",
        "Programming Language :: Python :: 3.8",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
        "Topic :: Software Development :: Build Tools",
        "Topic :: System :: Archiving :: Packaging",
    ],
    # Override certain command classes with our own ones
    cmdclass=cmdclass,
    test_suite="tests",
)
