#!/usr/bin/env python

import hotshot, hotshot.stats
import tempfile
import os, sys

from osc import commandline
from osc.core import init_basicauth


if __name__ == '__main__':

    (o, filename) = tempfile.mkstemp(prefix = 'osc_profiledata_', dir = '/dev/shm')
    del o

    try:

        prof = hotshot.Profile(filename)
        
        init_basicauth()
        prof.runcall(commandline.main)
        print 'run complete. analyzing.'
        prof.close()

        stats = hotshot.stats.load(filename)
        stats.strip_dirs()
        stats.sort_stats('time', 'calls')
        stats.print_stats(20)

        del stats

    finally:
        os.unlink(filename)
