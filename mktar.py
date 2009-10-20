#!/usr/bin/python
# tar up svn snapshot. run with -r to produce a release

import subprocess
import os
import sys
from osc import core

release = False
v = core.__version__
if (len(sys.argv) > 1 and sys.argv[1] == '-r'):
    release = True

if release:
    if (v.endswith('_SVN')):
        v=v[:-4]
    print "don't forget to increase version in osc/core.py after release"
else:
    v += subprocess.Popen(["svnversion", "."], stdout=subprocess.PIPE).stdout.read().strip()

d = "osc-" + v
f = d+".tar.bz2"
subprocess.check_call(["svn", "export", ".", d])
if release:
    # TODO: create tag for release
    subprocess.check_call(["sed", "-ie", "/^__version__/s/_SVN//", d+"/osc/core.py"])
subprocess.check_call(["tar", "--force-local", "--owner=root", "--group=root", "-cjf", f, d])
subprocess.call(["rm", "-rf", d]) # XXX how to do this in python properly?
print f
