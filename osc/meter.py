# Copyright (C) 2018 SUSE Linux.  All rights reserved.
# This program is free software; it may be used, copied, modified
# and distributed under the terms of the GNU General Public Licence,
# either version 2, or (at your option) any later version.


import signal
import sys
from abc import ABC
from abc import abstractmethod
from typing import Optional

try:
    import progressbar as pb
    have_pb_module = True
    using_pb_progressbar2 = tuple(map(int, pb.__version__.split('.'))) >= (3, 1)
except ImportError:
    have_pb_module = False


class TextMeterBase(ABC):
    @abstractmethod
    def start(self, basename: str, size: Optional[int] = None):
        pass

    @abstractmethod
    def update(self, amount_read: int):
        pass

    @abstractmethod
    def end(self):
        pass


class PBTextMeter(TextMeterBase):
    def __init__(self):
        self.bar: pb.ProgressBar

    def start(self, basename: str, size: Optional[int] = None):
        if size is None:
            widgets = [f"{basename} ", pb.AnimatedMarker(), ' ', pb.Timer()]
            self.bar = pb.ProgressBar(widgets=widgets, maxval=pb.UnknownLength)
        else:
            widgets = [f"{basename} ", pb.Bar(), ' ', pb.ETA()]
            if size:
                # if size is 0, using pb.Percentage will result in
                # a ZeroDivisionException
                widgets[3:3] = [pb.Percentage(), " "]
            self.bar = pb.ProgressBar(widgets=widgets, maxval=size)
        # When a signal handler is set, it resets SA_RESTART flag
        # - see signal.siginterrupt() python docs.
        # ProgressBar's constructor sets signal handler for SIGWINCH.
        # So let's make sure that it doesn't interrupt syscalls in osc.
        signal.siginterrupt(signal.SIGWINCH, False)
        self.bar.start()

    def update(self, amount_read: int):
        self.bar.update(amount_read)

    def end(self):
        # replace marker (ticks) and left+right borders of the bar with spaces
        # to hide it from output after completion
        for i in self.bar.widgets:
            if not isinstance(i, pb.Bar):
                continue
            if using_pb_progressbar2:
                i.marker = lambda _progress, _data, _width: " "
                i.left = lambda _progress, _data, _width: " "
                i.right = lambda _progress, _data, _width: " "
            else:
                i.marker = " "
                i.left = " "
                i.right = " "

        self.bar.finish()


class SimpleTextMeter(TextMeterBase):
    def start(self, basename: str, size: Optional[int] = None):
        print(basename, file=sys.stderr)

    def update(self, amount_read: int):
        pass

    def end(self):
        pass


class NoTextMeter(TextMeterBase):
    def start(self, basename: str, size: Optional[int] = None):
        pass

    def update(self, amount_read: int):
        pass

    def end(self):
        pass


def create_text_meter(*args, **kwargs) -> TextMeterBase:
    from .conf import config

    use_pb_fallback = kwargs.pop("use_pb_fallback", False)

    meter_class: TextMeterBase
    if config.quiet:
        meter_class = NoTextMeter
    elif not have_pb_module or not config.show_download_progress or not sys.stdout.isatty() or use_pb_fallback:
        meter_class = SimpleTextMeter
    else:
        meter_class = PBTextMeter

    return meter_class(*args, **kwargs)


# vim: sw=4 et
