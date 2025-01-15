import copy
import http.client
import json
import time
import urllib.parse
from typing import Optional

import urllib3
import urllib3.exceptions
import urllib3.response

from .conf import Login


class GiteaHTTPResponse:
    """
    A ``urllib3.response.HTTPResponse`` wrapper
    that ensures compatibility with older versions of urllib3.
    """

    def __init__(self, response: urllib3.response.HTTPResponse):
        self.__dict__["_response"] = response

    def __getattr__(self, name):
        return getattr(self._response, name)

    def json(self):
        if hasattr(self._response, "json"):
            return self._response.json()
        return json.loads(self._response.data)


class Connection:
    def __init__(self, login: Login, alternative_port: Optional[int] = None):
        """
        :param login: ``Login`` object with Gitea url and credentials.
        :param alternative_port: Use an alternative port for the connection. This is needed for testing when gitea runs on a random port.
        """
        self.login = login

        parsed_url = urllib.parse.urlparse(self.login.url, scheme="https")
        if parsed_url.scheme == "http":
            ConnectionClass = urllib3.connection.HTTPConnection
        elif parsed_url.scheme == "https":
            ConnectionClass = urllib3.connection.HTTPSConnection
        else:
            raise ValueError(f"Unsupported scheme in Gitea url '{self.login.url}'")

        self.host = parsed_url.hostname
        assert self.host is not None
        self.port = alternative_port if alternative_port else parsed_url.port
        self.conn = ConnectionClass(host=self.host, port=self.port)

        # retries; variables are named according to urllib3
        self.retry_count = 3
        self.retry_backoff_factor = 2
        self.retry_status_forcelist = (
            500,  # Internal Server Error
            502,  # Bad Gateway
            503,  # Service Unavailable
            504,  # Gateway Timeout
        )

        if hasattr(self.conn, "set_cert"):
            # needed to avoid: AttributeError: 'HTTPSConnection' object has no attribute 'assert_hostname'. Did you mean: 'server_hostname'?
            self.conn.set_cert()

    def makeurl(self, *path: str, query: Optional[dict] = None):
        """
        Return relative url prefixed with "/api/v1/" followed with concatenated ``*path``.
        """
        url_path = ["", "api", "v1"] + [urllib.parse.quote(i, safe="/:") for i in path]
        url_path_str = "/".join(url_path)

        if query is None:
            query = {}
        query = copy.deepcopy(query)

        for key in list(query):
            value = query[key]

            if value in (None, [], ()):
                # remove items with value equal to None or [] or ()
                del query[key]
            elif isinstance(value, bool):
                # convert boolean values to "0" or "1"
                query[key] = str(int(value))

        url_query_str = urllib.parse.urlencode(query, doseq=True)
        return urllib.parse.urlunsplit(("", "", url_path_str, url_query_str, ""))

    def request(self, method, url, json_data: Optional[dict] = None) -> GiteaHTTPResponse:
        """
        Make a request and return ``GiteaHTTPResponse``.
        """
        headers = {
            "Content-Type": "application/json",
        }
        if self.login.token:
            headers["Authorization"] = f"token {self.login.token}"

        if json_data:
            json_data = dict(((key, value) for key, value in json_data.items() if value is not None))

        body = json.dumps(json_data) if json_data else None

        for retry in range(1 + self.retry_count):
            # 1 regular request + ``self.retry_count`` retries
            try:
                self.conn.request(method, url, body, headers)
                response = self.conn.getresponse()

                if response.status not in self.retry_status_forcelist:
                    # we are happy with the response status -> use the response
                    break

                if retry >= self.retry_count:
                    # we have reached maximum number of retries -> use the response
                    break

            except (urllib3.exceptions.HTTPError, ConnectionResetError):
                if retry >= self.retry_count:
                    raise

            # {backoff factor} * (2 ** ({number of previous retries}))
            time.sleep(self.retry_backoff_factor * (2 ** retry))
            self.conn.close()

        if isinstance(response, http.client.HTTPResponse):
            result = GiteaHTTPResponse(urllib3.response.HTTPResponse.from_httplib(response))
        else:
            result = GiteaHTTPResponse(response)

        if not hasattr(response, "status"):
            from .exceptions import GiteaException  # pylint: disable=import-outside-toplevel,cyclic-import

            raise GiteaException(result)

        if response.status // 100 != 2:
            from .exceptions import GiteaException  # pylint: disable=import-outside-toplevel,cyclic-import

            raise GiteaException(result)

        return result
