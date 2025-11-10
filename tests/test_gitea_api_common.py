import os
import shutil
import unittest

from osc.gitea_api import dt_sanitize
from osc.gitea_api.common import TemporaryDirectory


class TestGiteaApiCommon(unittest.TestCase):
    def test_dt_sanitize(self):
        datetime_str = "1970-01-01T01:00:00+01:00"
        expected = "1970-01-01 00:00"
        actual = dt_sanitize(datetime_str)
        self.assertEqual(expected, actual)

        datetime_str = "1970-01-01T01:00:00-01:00"
        expected = "1970-01-01 02:00"
        actual = dt_sanitize(datetime_str)
        self.assertEqual(expected, actual)

        datetime_str = "1970-01-01T00:00:00Z"
        expected = "1970-01-01 00:00"
        actual = dt_sanitize(datetime_str)
        self.assertEqual(expected, actual)


    def test_TemporaryDirectory_delete(self):
        with TemporaryDirectory(delete=True) as temp_dir:
            pass
        self.assertFalse(os.path.isdir(temp_dir))

    def test_TemporaryDirectory_no_delete(self):
        with TemporaryDirectory(delete=False) as temp_dir:
            pass
        self.assertTrue(os.path.isdir(temp_dir))
        shutil.rmtree(temp_dir)


if __name__ == "__main__":
    unittest.main()
