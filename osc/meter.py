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

from urlgrabber.progress import BaseMeter, format_time, format_number
import sys, os

def getScreenWidth():
    import termios, struct, fcntl
    s = struct.pack('HHHH', 0, 0, 0, 0)
    try:
        x = fcntl.ioctl(1, termios.TIOCGWINSZ, s)
    except IOError:
        return 80
    return struct.unpack('HHHH', x)[1]


class TextMeter(BaseMeter):
    def __init__(self, fo=sys.stderr, hide_finished=False):
        BaseMeter.__init__(self)
        self.fo = fo
        self.hide_finished = hide_finished
        try:
            width = int(os.environ['COLUMNS'])
        except (KeyError, ValueError):
            width = getScreenWidth()


        #self.unsized_templ = '\r%-60.60s    %5sB %s '
        self.unsized_templ = '\r%%-%s.%ss    %%5sB %%s ' % (width *2/5, width*3/5)
        #self.sized_templ = '\r%-45.45s %3i%% |%-15.15s| %5sB %8s '
        self.bar_length = width/5
        self.sized_templ = '\r%%-%s.%ss %%3i%%%% |%%-%s.%ss| %%5sB %%8s ' % (width*4/10, width*4/10, self.bar_length, self.bar_length)


    def _do_start(self, *args, **kwargs):
        BaseMeter._do_start(self, *args, **kwargs)
        self._do_update(0)

    def _do_update(self, amount_read, now=None):
        etime = self.re.elapsed_time()
        fetime = format_time(etime)
        fread = format_number(amount_read)
        #self.size = None
        if self.text is not None:
            text = self.text
        else:
            text = self.basename
        if self.size is None:
            out = self.unsized_templ % \
                  (text, fread, fetime)
        else:
            rtime = self.re.remaining_time()
            frtime = format_time(rtime)
            frac = self.re.fraction_read()
            bar = '='*int(self.bar_length * frac)

            out = self.sized_templ % \
                  (text, frac*100, bar, fread, frtime) + 'ETA '

        self.fo.write(out)
        self.fo.flush()

    def _do_end(self, amount_read, now=None):
        total_time = format_time(self.re.elapsed_time())
        total_size = format_number(amount_read)
        if self.text is not None:
            text = self.text
        else:
            text = self.basename
        if self.size is None:
            out = self.unsized_templ % \
                  (text, total_size, total_time)
        else:
            bar = '=' * self.bar_length
            out = self.sized_templ % \
                  (text, 100, bar, total_size, total_time) + '    '
        if self.hide_finished:
            self.fo.write('\r'+ ' '*len(out) + '\r')
        else:
            self.fo.write(out + '\n')
        self.fo.flush()

# vim: sw=4 et
