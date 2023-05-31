import base64
import fcntl
import inspect
import os
import re
import shutil
import subprocess
import ssl
import sys
import tempfile
import time
import warnings

import http.client
import http.cookiejar
import urllib.parse
import urllib.request
import urllib3.exceptions
import urllib3.poolmanager
import urllib3.response
import urllib3.util

from . import __version__
from . import conf
from . import oscerr
from . import oscssl
from .util.helper import decode_it


# print only the first occurrence of matching warnings, regardless of location
warnings.filterwarnings("once", category=urllib3.exceptions.InsecureRequestWarning)


class MockRequest:
    """
    Mock a request object for `cookiejar.extract_cookies()`
    and `cookiejar.add_cookie_header()`.
    """

    def __init__(self, url, headers):
        self.url = url
        self.headers = headers
        self.unverifiable = False
        self.type = "https"

    def get_full_url(self):
        return self.url

    def get_header(self, header_name, default=None):
        return self.headers.get(header_name, default)

    def has_header(self, header_name):
        return header_name in self.headers

    def add_unredirected_header(self, key, val):
        # modifies the `headers` variable that was passed to object's constructor
        self.headers[key] = val


def enable_http_debug(config):
    if not int(config["http_debug"]) and not int(config["http_full_debug"]):
        http.client.print = lambda *args, **kwargs: None
        return

    # HACK: override HTTPResponse's init to increase debug level
    old_HTTPResponse__init__ = http.client.HTTPResponse.__init__

    def new_HTTPResponse__init__(self, *args, **kwargs):
        old_HTTPResponse__init__(self, *args, **kwargs)
        self.debuglevel = 1
    http.client.HTTPResponse.__init__ = new_HTTPResponse__init__

    # increase HTTPConnection debug level
    http.client.HTTPConnection.debuglevel = 1

    # HACK: because HTTPResponse's debug data uses print(),
    # let's inject custom print() function to that module
    def new_print(*args, file=None):
        if not int(config["http_full_debug"]) and args:
            # hide private data (authorization and cookies) when full debug is not enabled
            if args[:2] == ("header:", "Set-Cookie:"):
                return
            if args[0] == "send:":
                args = list(args)
                # (?<=...) - '...' must be present before the pattern (positive lookbehind assertion)
                args[1] = re.sub(r"(?<=\\r\\n)authorization:.*?\\r\\n", "", args[1], re.I)
                args[1] = re.sub(r"(?<=\\r\\n)Cookie:.*?\\r\\n", "", args[1], re.I)
        print("DEBUG:", *args, file=sys.stderr)
    http.client.print = new_print


def get_proxy_manager(env):
    proxy_url = os.environ.get(env, None)

    if not proxy_url:
        return

    proxy_purl = urllib3.util.parse_url(proxy_url)

    # rebuild proxy url in order to remove auth because ProxyManager would fail on it
    if proxy_purl.port:
        proxy_url = f"{proxy_purl.scheme}://{proxy_purl.host}:{proxy_purl.port}"
    else:
        proxy_url = f"{proxy_purl.scheme}://{proxy_purl.host}"

    proxy_headers = urllib3.make_headers(
        user_agent=f"osc/{__version__}",
    )

    proxy_basic_auth = urllib.parse.unquote(proxy_purl.auth)
    proxy_basic_auth = proxy_basic_auth.encode("utf-8")
    proxy_basic_auth = base64.b64encode(proxy_basic_auth).decode()
    proxy_headers["Proxy-Authorization"] = f"Basic {proxy_basic_auth:s}"

    manager = urllib3.ProxyManager(proxy_url, proxy_headers=proxy_headers)
    return manager


# Instantiate on first use in `http_request()`.
# Each `apiurl` requires a differently configured pool
# (incl. trusted keys for example).
CONNECTION_POOLS = {}


# Pool manager for requests outside apiurls.
POOL_MANAGER = urllib3.PoolManager()


# Proxy manager for HTTP connections.
HTTP_PROXY_MANAGER = get_proxy_manager("HTTP_PROXY")


# Proxy manager for HTTPS connections.
HTTPS_PROXY_MANAGER = get_proxy_manager("HTTPS_PROXY")


def http_request_wrap_file(func):
    """
    Turn file path into a file object and close it automatically
    by using a context manager.
    """
    def new_func(method, url, headers=None, data=None, file=None, retry_on_400: bool = True):
        if file:
            with open(file, "rb") as f:
                return func(method, url, headers, data, f, retry_on_400)
        else:
            return func(method, url, headers, data, file, retry_on_400)

    new_func.__name__ = func.__name__
    new_func.__doc__ = func.__doc__
    return new_func


@http_request_wrap_file
def http_request(method: str, url: str, headers=None, data=None, file=None, retry_on_400: bool = True):
    """
    Send a HTTP request to a server.

    Features:
    * Authentication ([apiurl]/{user,pass} in oscrc)
    * Session cookie support (~/.local/state/osc/cookiejar)
    * SSL certificate verification incl. managing trusted certs
    * SSL certificate verification bypass (if [apiurl]/sslcertck=0 in oscrc)
    * Expired SSL certificates are no longer accepted. Either prolong them or set sslcertck=0.
    * Proxy support (HTTPS_PROXY env, NO_PROXY is respected)
    * Retries (http_retries in oscrc)
    * Requests outside apiurl (incl. proxy support)
    * Connection debugging (-H/--http-debug, --http-full-debug)

    :param method: HTTP request method (such as GET, POST, PUT, DELETE).
    :param url: The URL to perform the request on.
    :param headers: Dictionary of custom headers to send.
    :param data: Data to send in the request body (conflicts with `file`).
    :param file: Path to a file to send as data in the request body (conflicts with `data`).
    :param retry_on_400: Whether to retry on receiving HTTP status code 400.
    """

    purl = urllib3.util.parse_url(url)
    apiurl = conf.extract_known_apiurl(url)
    headers = urllib3.response.HTTPHeaderDict(headers or {})

    # identify osc
    headers.update(urllib3.make_headers(user_agent=f"osc/{__version__}"))

    if data and file:
        raise RuntimeError('Specify either `data` or `file`')
    elif data:
        if hasattr(data, "encode"):
            data = data.encode("utf-8")
        content_length = len(data)
    elif file:
        content_length = os.fstat(file.fileno()).st_size
        data = file
    else:
        content_length = 0

    if content_length:
        headers.add("Content-Length", str(content_length))

    # handle requests that go outside apiurl
    # do not set auth cookie or auth credentials
    if not apiurl:
        if purl.scheme == "http" and HTTP_PROXY_MANAGER and not urllib.request.proxy_bypass(url):
            # connection through proxy
            manager = HTTP_PROXY_MANAGER
        elif purl.scheme == "https" and HTTPS_PROXY_MANAGER and not urllib.request.proxy_bypass(url):
            # connection through proxy
            manager = HTTPS_PROXY_MANAGER
        else:
            # direct connection
            manager = POOL_MANAGER

        response = manager.urlopen(method, url, body=data, headers=headers, preload_content=False)

        if response.status / 100 != 2:
            raise urllib.error.HTTPError(url, response.status, response.reason, response.headers, response)

        return response

    options = conf.config["api_host_options"][apiurl]

    global CONNECTION_POOLS
    pool = CONNECTION_POOLS.get(apiurl, None)
    if not pool:
        pool_kwargs = {}

        # urllib3.Retry() argument 'method_whitelist' got renamed to 'allowed_methods'
        sig = inspect.signature(urllib3.Retry)
        arg_names = list(sig.parameters.keys())
        if "allowed_methods" in arg_names:
            retries_kwargs = {"allowed_methods": None}
        else:
            retries_kwargs = {"method_whitelist": None}


        status_forcelist = (
            500,  # Internal Server Error
            502,  # Bad Gateway
            503,  # Service Unavailable
            504,  # Gateway Timeout
        )
        if retry_on_400:
            status_forcelist = (
                400,  # Bad Request; retry on 400: service in progress
            ) + status_forcelist

        pool_kwargs["retries"] = urllib3.Retry(
            total=int(conf.config["http_retries"]),
            backoff_factor=2,
            status_forcelist=status_forcelist,
            # don't raise because we want an actual response rather than a MaxRetryError with "too many <status_code> error responses" message
            raise_on_status=False,
            **retries_kwargs,
        )

        if purl.scheme == "https":
            ssl_context = oscssl.create_ssl_context()
            ssl_context.load_default_certs()
            pool_kwargs["ssl_context"] = ssl_context
            # turn cert verification off if sslcertck = 0

            # urllib3 v1
            pool_kwargs["cert_reqs"] = "CERT_REQUIRED" if options["sslcertck"] else "CERT_NONE"

            # urllib3 v2
            if options["sslcertck"]:
                ssl_context.check_hostname = True
                ssl_context.verify_mode = ssl.CERT_REQUIRED
            else:
                ssl_context.check_hostname = False
                ssl_context.verify_mode = ssl.CERT_NONE

        if purl.scheme == "http" and HTTP_PROXY_MANAGER and not urllib.request.proxy_bypass(url):
            # connection through HTTP proxy
            pool = HTTP_PROXY_MANAGER.connection_from_host(
                host=purl.host,
                port=purl.port,
                scheme=purl.scheme,
                pool_kwargs=pool_kwargs
            )
            HTTP_PROXY_MANAGER.request('GET', url)
        elif purl.scheme == "https" and HTTPS_PROXY_MANAGER and not urllib.request.proxy_bypass(url):
            # connection through HTTPS proxy
            pool = HTTPS_PROXY_MANAGER.connection_from_host(
                host=purl.host,
                port=purl.port,
                scheme=purl.scheme,
                pool_kwargs=pool_kwargs
            )
        elif purl.scheme == "https":
            # direct connection
            pool = urllib3.HTTPSConnectionPool(host=purl.host, port=purl.port, **pool_kwargs)
        else:
            pool = urllib3.HTTPConnectionPool(host=purl.host, port=purl.port, **pool_kwargs)

        if purl.scheme == "https":
            # inject ssl context instance into pool so we can use it later
            pool.ssl_context = ssl_context

            # inject trusted cert store instance into pool so we can use it later
            pool.trusted_cert_store = oscssl.TrustedCertStore(ssl_context, purl.host, purl.port)

        CONNECTION_POOLS[apiurl] = pool

    auth_handlers = [
        CookieJarAuthHandler(apiurl, os.path.expanduser(conf.config["cookiejar"])),
        SignatureAuthHandler(apiurl, options["user"], options["sshkey"], options["pass"]),
        BasicAuthHandler(apiurl, options["user"], options["pass"]),
    ]

    for handler in auth_handlers:
        # authenticate using a cookie (if available)
        success = handler.set_request_headers(url, headers)
        if success:
            break

    # Rails sends a html response if the header is not set
    # https://github.com/openSUSE/open-build-service/pull/13019
    headers.add("Accept", "application/xml")

    if method == "PUT" or (method == "POST" and (data or file)):
        headers.add("Content-Type", "application/xml; charset=utf-8")
    elif method == "POST":
        headers.add("Content-Type", "application/x-www-form-urlencoded")

    if purl.scheme == "http" and HTTP_PROXY_MANAGER:
        # HTTP proxy requires full URL with 'same host' checking off
        urlopen_url = url
        assert_same_host = False
    else:
        # everything else is fine with path only
        # join path and query, ignore the remaining args; args are (scheme, netloc, path, query, fragment)
        urlopen_url = urllib.parse.urlunsplit(("", "", purl.path, purl.query, ""))
        assert_same_host = True

    if int(conf.config['http_debug']):
        # use the hacked print() for consistency
        http.client.print(40 * '-')
        http.client.print(method, url)

    try:
        response = pool.urlopen(
            method, urlopen_url, body=data, headers=headers,
            preload_content=False, assert_same_host=assert_same_host
        )
    except urllib3.exceptions.MaxRetryError as e:
        if not isinstance(e.reason, urllib3.exceptions.SSLError):
            # re-raise exceptions that are not related to SSL
            raise
        # ssl.SSLCertVerificationError doesn't exist on python 3.6
        # ssl.CertificateError is an alias for ssl.SSLCertVerificationError on python 3.7+
        if isinstance(e.reason.args[0], ssl.CertificateError):
            self_signed_verify_codes = (
                oscssl.X509_V_ERR_DEPTH_ZERO_SELF_SIGNED_CERT,
                oscssl.X509_V_ERR_SELF_SIGNED_CERT_IN_CHAIN,
            )
            if e.reason.args[0].verify_code not in self_signed_verify_codes:
                # re-raise ssl exceptions that are not related to self-signed certs
                raise e.reason.args[0] from None
        else:
            # re-raise other than ssl exceptions
            raise e.reason.args[0] from None

        # get the untrusted certificated from server
        cert = pool.trusted_cert_store.get_server_certificate()

        # prompt user if we should trust the certificate
        pool.trusted_cert_store.prompt_trust(cert, reason=e.reason)

        if hasattr(data, 'seek'):
            data.seek(0)

        response = pool.urlopen(
            method, urlopen_url, body=data, headers=headers,
            preload_content=False, assert_same_host=assert_same_host
        )

    if response.status == 401:
        # session cookie has expired, re-authenticate
        for handler in auth_handlers:
            success = handler.set_request_headers_after_401(url, headers, response)
            if success:
                break
        if hasattr(data, 'seek'):
            data.seek(0)
        response = pool.urlopen(method, urlopen_url, body=data, headers=headers, preload_content=False)

    if response.status / 100 != 2:
        raise urllib.error.HTTPError(url, response.status, response.reason, response.headers, response)

    for handler in auth_handlers:
        handler.process_response(url, headers, response)

    return response


# pylint: disable=C0103,C0116
def http_GET(*args, **kwargs):
    return http_request("GET", *args, **kwargs)


# pylint: disable=C0103,C0116
def http_POST(*args, **kwargs):
    return http_request("POST", *args, **kwargs)


# pylint: disable=C0103,C0116
def http_PUT(*args, **kwargs):
    return http_request("PUT", *args, **kwargs)


# pylint: disable=C0103,C0116
def http_DELETE(*args, **kwargs):
    return http_request("DELETE", *args, **kwargs)


class AuthHandlerBase:
    def __init__(self, apiurl):
        self.apiurl = apiurl

    def _get_auth_schemes(self, response):
        """
        Extract all `www-authenticate` headers from `response` and return them
        in a dictionary: `{scheme: auth_method}`.
        """
        result = {}
        for auth_method in response.headers.get_all("www-authenticate", []):
            scheme = auth_method.split()[0].lower()
            result[scheme] = auth_method
        return result

    def set_request_headers(self, url, request_headers):
        """
        Modify request headers with auth headers.

        :param url: Request URL provides context for `request_headers` modifications
        :type  url: str
        :param request_headers: object to be modified
        :type  request_headers: urllib3.response.HTTPHeaderDict
        :return: `True` on if `request_headers` was modified, `False` otherwise
        """
        raise NotImplementedError

    def set_request_headers_after_401(self, url, request_headers, response):
        """
        Modify request headers with auth headers after getting 401 response.

        :param url: Request URL provides context for `request_headers` modifications
        :type  url: str
        :param request_headers: object to be modified
        :type  request_headers: urllib3.response.HTTPHeaderDict
        :param response: Response object provides context for `request_headers` modifications
        :type  response: urllib3.response.HTTPResponse
        :return: `True` on if `request_headers` was modified, `False` otherwise
        """
        raise NotImplementedError

    def process_response(self, url, request_headers, response):
        """
        Retrieve data from response, save cookies, etc.

        :param url: Request URL provides context for `request_headers` modifications
        :type  url: str
        :param request_headers: object to be modified
        :type  request_headers: urllib3.response.HTTPHeaderDict
        :param response: Response object provides context for `request_headers` modifications
        :type  response: urllib3.response.HTTPResponse
        """
        raise NotImplementedError


class CookieJarAuthHandler(AuthHandlerBase):
    # Shared among instances, instantiate on first use, key equals to cookiejar path.
    COOKIEJARS = {}

    def __init__(self, apiurl, cookiejar_path):
        super().__init__(apiurl)
        self.cookiejar_path = cookiejar_path
        if self.cookiejar_path in self.COOKIEJARS:
            self.cookiejar_lock_path = None
        else:
            # Cookiejar hasn't been loaded yet, let's lock it to avoid
            # doing expensive signature auth in multiple processes.
            # This usually happens when a user runs multiple osc instances
            # from the command-line in parallel.
            self.cookiejar_lock_path = self.cookiejar_path + ".lock"
        self.cookiejar_lock_fd = None

    @property
    def _cookiejar(self):
        jar = self.COOKIEJARS.get(self.cookiejar_path, None)
        if not jar:
            try:
                os.makedirs(os.path.dirname(self.cookiejar_path), mode=0o700)
            except FileExistsError:
                pass
            jar = http.cookiejar.LWPCookieJar(self.cookiejar_path)
            if os.path.isfile(self.cookiejar_path):
                try:
                    jar.load()
                except http.cookiejar.LoadError:
                    pass
            self.COOKIEJARS[self.cookiejar_path] = jar
        return jar

    def _lock(self):
        if self.cookiejar_lock_path:
            try:
                os.makedirs(os.path.dirname(self.cookiejar_lock_path), mode=0o700)
            except FileExistsError:
                pass
            self.cookiejar_lock_fd = open(self.cookiejar_lock_path, "w")
            fcntl.flock(self.cookiejar_lock_fd, fcntl.LOCK_EX)

    def _unlock(self):
        if self.cookiejar_lock_path:
            self.cookiejar_lock_path = None
            fcntl.flock(self.cookiejar_lock_fd, fcntl.LOCK_UN)
            self.cookiejar_lock_fd.close()

    def set_request_headers(self, url, request_headers):
        self._lock()
        self._cookiejar.add_cookie_header(MockRequest(url, request_headers))
        if request_headers.get_all("cookie", None):
            # we have a valid cookie already -> unlock immediately
            self._unlock()
            return True
        return False

    def set_request_headers_after_401(self, url, request_headers, response):
        # can't do anything, we have tried setting a cookie already
        return False

    def process_response(self, url, request_headers, response):
        if response.headers.get_all("set-cookie", None):
            self._cookiejar.extract_cookies(response, MockRequest(url, response.headers))
            self._cookiejar.save()
        self._unlock()


class BasicAuthHandler(AuthHandlerBase):
    def __init__(self, apiurl, user, password):
        super().__init__(apiurl)
        self.user = user
        self.password = password

    def set_request_headers(self, url, request_headers):
        return False

    def set_request_headers_after_401(self, url, request_headers, response):
        auth_schemes = self._get_auth_schemes(response)
        if "basic" not in auth_schemes:
            return False
        if not self.user or not self.password:
            return False

        basic_auth = f"{self.user:s}:{self.password:s}"
        basic_auth = basic_auth.encode("utf-8")
        basic_auth = base64.b64encode(basic_auth).decode()
        request_headers["Authorization"] = f"Basic {basic_auth:s}"

        return True

    def process_response(self, url, request_headers, response):
        pass


class SignatureAuthHandler(AuthHandlerBase):
    def __init__(self, apiurl, user, sshkey, basic_auth_password=None):
        super().__init__(apiurl)
        self.user = user
        self.sshkey = sshkey

        self.ssh_keygen_path = shutil.which("ssh-keygen")
        self.ssh_add_path = shutil.which("ssh-add")

        creds_mgr = conf.config["api_host_options"][self.apiurl].get("credentials_mgr_class", None)
        if creds_mgr == "osc.credentials.TransientCredentialsManager":
            self.basic_auth_password = False
        else:
            # value of `basic_auth_password` is only used as a hint if we should skip signature auth
            self.basic_auth_password = bool(basic_auth_password)

        self.temp_pubkey = None

    def list_ssh_agent_keys(self):
        if not self.ssh_add_path:
            return []
        cmd = [self.ssh_add_path, '-L']
        proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        stdout, _ = proc.communicate()
        if proc.returncode == 0 and stdout.strip():
            return stdout.strip().splitlines()
        else:
            return []

    @staticmethod
    def get_fingerprint(line):
        parts = line.strip().split(b" ")
        if len(parts) < 2:
            raise ValueError(f"Unable to retrieve ssh key fingerprint from line: {line}")
        return parts[1]

    def guess_keyfile(self):
        # `ssh-keygen -Y sign` requires a file with a key which is not available during ssh agent forwarding
        # that's why we need to list ssh-agent's keys and store the first one into a temp file
        keys_in_agent = self.list_ssh_agent_keys()
        if keys_in_agent:
            self.temp_pubkey = tempfile.NamedTemporaryFile()
            self.temp_pubkey.write(keys_in_agent[0])
            self.temp_pubkey.flush()
            return self.temp_pubkey.name

        sshdir = os.path.expanduser('~/.ssh')
        keyfiles = ('id_ed25519', 'id_ed25519_sk', 'id_rsa', 'id_ecdsa', 'id_ecdsa_sk', 'id_dsa')
        for keyfile in keyfiles:
            keyfile_path = os.path.join(sshdir, keyfile)
            if os.path.isfile(keyfile_path):
                return keyfile_path
        return None

    def ssh_sign(self, data, namespace, keyfile=None):
        try:
            data = bytes(data, 'utf-8')
        except:
            pass
        if not keyfile:
            keyfile = self.guess_keyfile()
        else:
            if '/' not in keyfile:
                keyfile = '~/.ssh/' + keyfile
            keyfile = os.path.expanduser(keyfile)

        cmd = [self.ssh_keygen_path, '-Y', 'sign', '-f', keyfile, '-n', namespace, '-q']
        proc = subprocess.Popen(cmd, stdin=subprocess.PIPE, stdout=subprocess.PIPE)
        stdout, _ = proc.communicate(data)

        if self.temp_pubkey:
            self.temp_pubkey.close()
            self.temp_pubkey = None

        if proc.returncode:
            raise oscerr.OscIOError(None, 'ssh-keygen signature creation failed: %d' % proc.returncode)

        signature = decode_it(stdout)
        match = re.match(r"\A-----BEGIN SSH SIGNATURE-----\n(.*)\n-----END SSH SIGNATURE-----", signature, re.S)
        if not match:
            raise oscerr.OscIOError(None, 'could not extract ssh signature')
        return base64.b64decode(match.group(1))

    def get_authorization(self, chal):
        realm = chal.get('realm', '')
        now = int(time.time())
        sigdata = "(created): %d" % now
        signature = self.ssh_sign(sigdata, realm, self.sshkey)
        signature = decode_it(base64.b64encode(signature))
        return 'keyId="%s",algorithm="ssh",headers="(created)",created=%d,signature="%s"' \
            % (self.user, now, signature)

    def add_signature_auth_header(self, req, auth):
        token, challenge = auth.split(' ', 1)
        chal = urllib.request.parse_keqv_list(filter(None, urllib.request.parse_http_list(challenge)))
        auth = self.get_authorization(chal)
        if not auth:
            return False
        auth_val = 'Signature %s' % auth
        req.add('Authorization', auth_val)
        return True

    def set_request_headers(self, url, request_headers):
        return False

    def set_request_headers_after_401(self, url, request_headers, response):
        auth_schemes = self._get_auth_schemes(response)

        if "signature" not in auth_schemes:
            # unsupported on server
            return False

        if not self.user:
            return False

        if self.basic_auth_password and "basic" in auth_schemes:
            # prefer basic auth, but only if password is set
            return False

        if not self.ssh_keygen_path:
            if conf.config["debug"]:
                msg = "Skipping signature auth because ssh-keygen is not available"
                print(msg, file=sys.stderr)
            return False

        if not self.sshkey_known():
            # ssh key not set, try to guess it
            self.sshkey = self.guess_keyfile()

        if not self.sshkey_known():
            # ssh key cannot be guessed
            return False

        return self.add_signature_auth_header(request_headers, auth_schemes["signature"])

    def process_response(self, url, request_headers, response):
        pass

    def sshkey_known(self):
        return self.sshkey is not None
