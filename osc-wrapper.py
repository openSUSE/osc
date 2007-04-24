#!/usr/bin/env python

# this wrapper exists so it can be put into /usr/bin, but still allows the 
# python module to be called within the source directory during development

import sys
from osc import commandline

osc = commandline.Osc()
sys.exit( osc.main() )


