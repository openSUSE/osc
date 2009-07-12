#!/usr/bin/env python

# this wrapper exists so it can be put into /usr/bin, but still allows the 
# python module to be called within the source directory during development


import sys, locale
# this is a hack to make osc work as expected with utf-8 characters, no matter
# how site.py is set...
reload(sys)
loc = locale.getdefaultlocale()[1]
if not loc:
    loc = sys.getdefaultencoding()
sys.setdefaultencoding(loc)
del sys.setdefaultencoding

from osc import commandline
from osc import babysitter

osccli = commandline.Osc()

r = babysitter.run(osccli)
sys.exit(r)



