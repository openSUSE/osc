#   This library is free software; you can redistribute it and/or
#   modify it under the terms of the GNU Lesser General Public
#   License as published by the Free Software Foundation; either
#   version 2.1 of the License, or (at your option) any later version.
#
#   This library is distributed in the hope that it will be useful,
#   but WITHOUT ANY WARRANTY; without even the implied warranty of
#   MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU
#   Lesser General Public License for more details.
#
#   You should have received a copy of the GNU Lesser General Public
#   License along with this library; if not, write to the
#      Free Software Foundation, Inc.,
#      59 Temple Place, Suite 330,
#      Boston, MA  02111-1307  USA

# this is basically a copy of python-urlgrabber's TextMeter class,
# with support added for dynamical sizing according to screen size.
# it uses getScreenWidth() scrapped from smart.
# 2007-04-24, poeml

from __future__ import print_function

import progressbar as pb
import sys, os

class TextMeter(object):
    def __init__(self):
        pass

    def start(self, basename, size=None):
        if size == None:
            widgets = [basename + ': ', pb.AnimatedMarker(), ' ' , pb.Timer()]
            self.bar = pb.ProgressBar(widgets=widgets, maxval=pb.UnknownLength)
        else:
            widgets = [basename + ': ', pb.Percentage(), pb.Bar(), ' ', pb.ETA()]
            self.bar = pb.ProgressBar(widgets=widgets, maxval=size)
        self.bar.start()

    def update(self, amount_read):
        self.bar.update(amount_read)

    def end(self):
        self.bar.finish()

# vim: sw=4 et
