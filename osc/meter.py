# Copyright (C) 2018 SUSE Linux.  All rights reserved.
# This program is free software; it may be used, copied, modified
# and distributed under the terms of the GNU General Public Licence,
# either version 2, or (at your option) any later version.

try:
    import progressbar as pb
    have_pb_module = True
except ImportError:
    have_pb_module = False


class PBTextMeter(object):

    def start(self, basename, size=None):
        if size is None:
            widgets = [basename + ': ', pb.AnimatedMarker(), ' ', pb.Timer()]
            self.bar = pb.ProgressBar(widgets=widgets, maxval=pb.UnknownLength)
        else:
            widgets = [basename + ': ', pb.Percentage(), pb.Bar(), ' ',
                       pb.ETA()]
            self.bar = pb.ProgressBar(widgets=widgets, maxval=size)
        self.bar.start()

    def update(self, amount_read):
        self.bar.update(amount_read)

    def end(self):
        self.bar.finish()

class NoPBTextMeter(object):
    def start(self, *args, **kwargs):
        print('Please install the progressbar module...')

    def update(self, *args, **kwargs):
        pass

    def end(self, *args, **kwargs):
        pass

if have_pb_module:
    TextMeter = PBTextMeter
else:
    TextMeter = NoPBTextMeter
# vim: sw=4 et
