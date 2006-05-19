#!/usr/bin/env python

# this wrapper exists so it can be put into /usr/bin, but still allows the 
# python module to be called within the source directory during development

from osc import commandline
from osc.core import init_basicauth

init_basicauth()
commandline.main()

