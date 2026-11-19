import unittest

import urllib3

from osc import oscerr
from osc.connection import BearerAuthHandler


class TestBearerAuthHandler(unittest.TestCase):
    apiurl = "https://api.example.com"

    def test_no_token_is_inert(self):
        handler = BearerAuthHandler(self.apiurl, None)
        headers = urllib3.response.HTTPHeaderDict()
        self.assertFalse(handler.set_request_headers(f"{self.apiurl}/foo", headers))
        self.assertNotIn("Authorization", headers)

    def test_token_sets_bearer_header(self):
        handler = BearerAuthHandler(self.apiurl, "secret-token")
        headers = urllib3.response.HTTPHeaderDict()
        self.assertTrue(handler.set_request_headers(f"{self.apiurl}/foo", headers))
        self.assertEqual(headers["Authorization"], "Bearer secret-token")

    def test_401_with_bearer_raises_without_fallback(self):
        handler = BearerAuthHandler(self.apiurl, "secret-token")
        headers = urllib3.response.HTTPHeaderDict({"Authorization": "Bearer secret-token"})
        self.assertRaises(
            oscerr.OscIOError,
            handler.set_request_headers_after_401,
            f"{self.apiurl}/foo",
            headers,
            None,
        )

    def test_401_error_message(self):
        handler = BearerAuthHandler(self.apiurl, "secret-token")
        headers = urllib3.response.HTTPHeaderDict({"Authorization": "Bearer secret-token"})
        try:
            handler.set_request_headers_after_401(f"{self.apiurl}/foo", headers, None)
            self.fail("OscIOError not raised")
        except oscerr.OscIOError as e:
            self.assertIn("401", e.msg)
            self.assertIn("not falling back to password authentication", e.msg)

    def test_401_without_bearer_falls_through(self):
        handler = BearerAuthHandler(self.apiurl, None)
        headers = urllib3.response.HTTPHeaderDict()
        self.assertFalse(
            handler.set_request_headers_after_401(f"{self.apiurl}/foo", headers, None)
        )

    def test_401_with_basic_header_falls_through(self):
        handler = BearerAuthHandler(self.apiurl, "secret-token")
        headers = urllib3.response.HTTPHeaderDict({"Authorization": "Basic dXNlcjpwYXNz"})
        self.assertFalse(
            handler.set_request_headers_after_401(f"{self.apiurl}/foo", headers, None)
        )

    def test_process_response_is_noop(self):
        handler = BearerAuthHandler(self.apiurl, "secret-token")
        headers = urllib3.response.HTTPHeaderDict()
        self.assertIsNone(handler.process_response(f"{self.apiurl}/foo", headers, None))


if __name__ == "__main__":
    unittest.main()
