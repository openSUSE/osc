import unittest
from unittest.mock import patch

import osc.conf
from osc.meter import NoTextMeter
from osc.meter import PBTextMeter
from osc.meter import SimpleTextMeter
from osc.meter import create_text_meter


class TestCreateTextMeter(unittest.TestCase):
    def setUp(self):
        osc.conf.config = osc.conf.Options()
        osc.conf.config.quiet = False
        osc.conf.config.show_download_progress = True

    def test_quiet_uses_no_meter(self):
        osc.conf.config.quiet = True
        self.assertIsInstance(create_text_meter(), NoTextMeter)

    def test_show_download_progress_disabled_uses_simple_meter(self):
        osc.conf.config.show_download_progress = False
        with patch("sys.stdout.isatty", return_value=True):
            self.assertIsInstance(create_text_meter(), SimpleTextMeter)

    def test_non_tty_uses_simple_meter(self):
        with patch("sys.stdout.isatty", return_value=False):
            self.assertIsInstance(create_text_meter(), SimpleTextMeter)

    def test_use_pb_fallback_uses_simple_meter(self):
        with patch("sys.stdout.isatty", return_value=True):
            self.assertIsInstance(create_text_meter(use_pb_fallback=True), SimpleTextMeter)

    def test_default_uses_pb_meter(self):
        with patch("sys.stdout.isatty", return_value=True):
            self.assertIsInstance(create_text_meter(), PBTextMeter)
