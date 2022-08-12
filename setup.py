#!/usr/bin/env python3


import setuptools

import osc.core


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
