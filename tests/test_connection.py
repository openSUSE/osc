import os
import unittest
from unittest.mock import MagicMock, patch

import urllib3.response

from osc import connection


class TestConnectionProxyBypass(unittest.TestCase):
    @patch.dict(
        os.environ,
        {"no_proxy": "10.0.0.1,internal.example.com", "https_proxy": "http://proxy.example.com:8080"},
    )
    @patch("osc.connection.HTTPS_PROXY_MANAGER")
    @patch("osc.connection.POOL_MANAGER")
    def test_no_proxy_bypass_outside_apiurl(self, mock_pool_manager, mock_proxy_manager):
        mock_response = MagicMock()
        mock_response.status = 200
        mock_pool_manager.urlopen.return_value = mock_response

        with patch("osc.connection.conf.extract_known_apiurl", return_value=None):
            connection.http_request("GET", "https://10.0.0.1/test")

        mock_pool_manager.urlopen.assert_called_once()
        mock_proxy_manager.urlopen.assert_not_called()

    @patch.dict(
        os.environ,
        {"no_proxy": "10.0.0.1,internal.example.com", "https_proxy": "http://proxy.example.com:8080"},
    )
    @patch("osc.connection.HTTPS_PROXY_MANAGER")
    @patch("osc.connection.urllib3.HTTPSConnectionPool")
    def test_no_proxy_bypass_for_apiurl(self, mock_https_pool, mock_proxy_manager):
        connection.CONNECTION_POOLS.clear()
        mock_pool = MagicMock()
        mock_https_pool.return_value = mock_pool
        mock_pool.urlopen.return_value.status = 200
        mock_pool.urlopen.return_value.headers = urllib3.response.HTTPHeaderDict()
        mock_pool.urlopen.return_value.data = b"<status/>"

        mock_options = MagicMock()
        mock_options.http_headers = {}
        opts_dict = {
            "http_headers": {},
            "sslcertck": False,
            "cafile": None,
            "capath": None,
            "user": "testuser",
            "sshkey": None,
            "pass": "testpass",
        }
        mock_options.__getitem__.side_effect = opts_dict.get

        with patch("osc.connection.conf.extract_known_apiurl", return_value="https://10.0.0.1"), \
             patch("osc.connection.conf.config", {
                 "http_retries": "1",
                 "http_debug": "0",
                 "http_full_debug": "0",
                 "cookiejar": "/tmp/test_cookiejar",
                 "api_host_options": {"https://10.0.0.1": mock_options},
             }), \
             patch.object(connection.CookieJarAuthHandler, "set_request_headers", return_value=True), \
             patch.object(connection.CookieJarAuthHandler, "process_response"):
            connection.http_request("GET", "https://10.0.0.1/test")

        mock_https_pool.assert_called_once()
        mock_proxy_manager.connection_from_host.assert_not_called()
