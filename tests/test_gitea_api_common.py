import unittest

from osc.gitea_api import dt_sanitize


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


if __name__ == "__main__":
    unittest.main()
