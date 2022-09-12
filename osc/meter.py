# Copyright (C) 2018 SUSE Linux.  All rights reserved.
# This program is free software; it may be used, copied, modified
# and distributed under the terms of the GNU General Public Licence,
# either version 2, or (at your option) any later version.


import signal

try:
    import progressbar as pb
    have_pb_module = True
except ImportError:
    have_pb_module = False


class PBTextMeter:

    def start(self, basename, size=None):
        if size is None:
            widgets = [basename + ': ', pb.AnimatedMarker(), ' ', pb.Timer()]
            self.bar = pb.ProgressBar(widgets=widgets, maxval=pb.UnknownLength)
        else:
            widgets = [basename + ': ', pb.Bar(), ' ', pb.ETA()]
            if size:
                # if size is 0, using pb.Percentage will result in
                # a ZeroDivisionException
                widgets.insert(1, pb.Percentage())
            self.bar = pb.ProgressBar(widgets=widgets, maxval=size)
        # When a signal handler is set, it resets SA_RESTART flag
        # - see signal.siginterrupt() python docs.
        # ProgressBar's constructor sets signal handler for SIGWINCH.
        # So let's make sure that it doesn't interrupt syscalls in osc.
        signal.siginterrupt(signal.SIGWINCH, False)
        self.bar.start()

    def update(self, amount_read):
        self.bar.update(amount_read)

    def end(self):
        self.bar.finish()


class NoPBTextMeter:
    _complained = False

    def start(self, basename, size=None):
        if not self._complained:
            print('Please install the progressbar module')
            NoPBTextMeter._complained = True
        print('Processing: %s' % basename)

    def update(self, *args, **kwargs):
        pass

    def end(self, *args, **kwargs):
        pass


def create_text_meter(*args, **kwargs):
    use_pb_fallback = kwargs.pop('use_pb_fallback', True)
    if have_pb_module or use_pb_fallback:
        return TextMeter(*args, **kwargs)
    return None


if have_pb_module:
    TextMeter = PBTextMeter
else:
    TextMeter = NoPBTextMeter
# vim: sw=4 et
