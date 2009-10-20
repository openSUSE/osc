#!/usr/bin/env python

import hotshot, hotshot.stats
import tempfile
import os, sys

from osc import commandline


if __name__ == '__main__':

    (fd, filename) = tempfile.mkstemp(prefix = 'osc_profiledata_', dir = '/dev/shm')
    f = os.fdopen(fd)

    try:

        prof = hotshot.Profile(filename)

        prof.runcall(commandline.main)
        print 'run complete. analyzing.'
        prof.close()

        stats = hotshot.stats.load(filename)
        stats.strip_dirs()
        stats.sort_stats('time', 'calls')
        stats.print_stats(20)

        del stats

    finally:
        f.close()
        os.unlink(filename)
