# Copyright (C) 2009 Novell Inc.
# This program is free software; it may be used, copied, modified
# and distributed under the terms of the GNU General Public Licence,
# either version 2, or (at your option) any later version.

from __future__ import print_function

from M2Crypto.SSL.Checker import SSLVerificationError
from M2Crypto import m2, SSL, httpslib
import M2Crypto.m2urllib2
import socket
import sys
import inspect

try:
    from urllib.parse import urlparse, splithost, splitport, splittype, urldefrag
    from urllib.request import addinfourl
    from http.client import HTTPSConnection
except ImportError:
    #python 2.x
    from urlparse import urlparse, urldefrag
    from urllib import addinfourl, splithost, splitport, splittype
    from httplib import HTTPSConnection

from .core import raw_input

class TrustedCertStore:
    _tmptrusted = {}

    def __init__(self, host, port, app, cert):

        self.cert = cert
        self.host = host
        if self.host == None:
            raise Exception("empty host")
        if port:
            self.host += "_%d" % port
        import os
        self.dir = os.path.expanduser('~/.config/%s/trusted-certs' % app)
        self.file = self.dir + '/%s.pem' % self.host

    def is_known(self):
        if self.host in self._tmptrusted:
            return True

        import os
        if os.path.exists(self.file):
            return True
        return False

    def is_trusted(self):
        import os
        if self.host in self._tmptrusted:
            cert = self._tmptrusted[self.host]
        else:
            if not os.path.exists(self.file):
                return False
            from M2Crypto import X509
            cert = X509.load_cert(self.file)
        if self.cert.as_pem() == cert.as_pem():
            return True
        else:
            return False

    def trust_tmp(self):
        self._tmptrusted[self.host] = self.cert

    def trust_always(self):
        self.trust_tmp()
        from M2Crypto import X509
        import os
        if not os.path.exists(self.dir):
            os.makedirs(self.dir)
        self.cert.save_pem(self.file)


# verify_cb is called for each error once
# we only collect the errors and return suceess
# connection will be aborted later if it needs to
def verify_cb(ctx, ok, store):
    if not ctx.verrs:
        ctx.verrs = ValidationErrors()

    try:
        if not ok:
            ctx.verrs.record(store.get_current_cert(), store.get_error(), store.get_error_depth())
        return 1

    except Exception as e:
        print(e, file=sys.stderr)
        return 0

class FailCert:
    def __init__(self, cert):
        self.cert = cert
        self.errs = []

class ValidationErrors:

    def __init__(self):
        self.chain_ok = True
        self.cert_ok = True
        self.failures = {}

    def record(self, cert, err, depth):
        #print "cert for %s, level %d fail(%d)" % ( cert.get_subject().commonName, depth, err )
        if depth == 0:
            self.cert_ok = False
        else:
            self.chain_ok = False

        if not depth in self.failures:
            self.failures[depth] = FailCert(cert)
        else:
            if self.failures[depth].cert.get_fingerprint() != cert.get_fingerprint():
                raise Exception("Certificate changed unexpectedly. This should not happen")
        self.failures[depth].errs.append(err)

    def show(self, out):
        for depth in self.failures.keys():
            cert = self.failures[depth].cert
            print("*** certificate verify failed at depth %d" % depth, file=out)
            print("Subject: ", cert.get_subject(), file=out)
            print("Issuer:  ", cert.get_issuer(), file=out)
            print("Valid: ", cert.get_not_before(), "-", cert.get_not_after(), file=out)
            print("Fingerprint(MD5):  ", cert.get_fingerprint('md5'), file=out)
            print("Fingerprint(SHA1): ", cert.get_fingerprint('sha1'), file=out)

            for err in self.failures[depth].errs:
                reason = "Unknown"
                try:
                    import M2Crypto.Err
                    reason = M2Crypto.Err.get_x509_verify_error(err)
                except:
                    pass
                print("Reason:", reason, file=out)

    # check if the encountered errors could be ignored
    def could_ignore(self):
        if not 0 in self.failures:
            return True

        nonfatal_errors = [
                m2.X509_V_ERR_UNABLE_TO_GET_ISSUER_CERT_LOCALLY,
                m2.X509_V_ERR_SELF_SIGNED_CERT_IN_CHAIN,
                m2.X509_V_ERR_DEPTH_ZERO_SELF_SIGNED_CERT,
                m2.X509_V_ERR_CERT_UNTRUSTED,
                m2.X509_V_ERR_UNABLE_TO_VERIFY_LEAF_SIGNATURE,

                m2.X509_V_ERR_CERT_NOT_YET_VALID,
                m2.X509_V_ERR_CERT_HAS_EXPIRED,
                m2.X509_V_OK,
                ]

        canignore = True
        for err in self.failures[0].errs:
            if not err in nonfatal_errors:
                canignore = False
                break

        return canignore

class mySSLContext(SSL.Context):

    def __init__(self):
        SSL.Context.__init__(self, 'sslv23')
        self.set_options(m2.SSL_OP_NO_SSLv2 | m2.SSL_OP_NO_SSLv3)
        self.set_cipher_list("ECDHE-RSA-AES128-SHA256:AES128-GCM-SHA256:RC4:HIGH:!MD5:!aNULL:!EDH")
        self.set_session_cache_mode(m2.SSL_SESS_CACHE_CLIENT)
        self.verrs = None
        #self.set_info_callback() # debug
        self.set_verify(SSL.verify_peer | SSL.verify_fail_if_no_peer_cert, depth=9, callback=lambda ok, store: verify_cb(self, ok, store))

class myHTTPSHandler(M2Crypto.m2urllib2.HTTPSHandler):
    handler_order = 499

    def __init__(self, *args, **kwargs):
        self.appname = kwargs.pop('appname', 'generic')
        M2Crypto.m2urllib2.HTTPSHandler.__init__(self, *args, **kwargs)

    # copied from M2Crypto.m2urllib2.HTTPSHandler
    # it's sole purpose is to use our myHTTPSHandler/myHTTPSProxyHandler class
    # ideally the m2urllib2.HTTPSHandler.https_open() method would be split into
    # "do_open()" and "https_open()" so that we just need to override
    # the small "https_open()" method...)
    def https_open(self, req):
        # https://docs.python.org/3.3/library/urllib.request.html#urllib.request.Request.get_host
        try:     # up to python-3.2
            host = req.get_host()
        except AttributeError:  # from python-3.3
            host = req.host
        if not host:
            raise M2Crypto.m2urllib2.URLError('no host given')

        # Our change: Check to see if we're using a proxy.
        # Then create an appropriate ssl-aware connection.
        full_url = req.get_full_url()
        target_host = urlparse(full_url)[1]

        if target_host != host:
            request_uri = urldefrag(full_url)[0]
            h = myProxyHTTPSConnection(host=host, appname=self.appname, ssl_context=self.ctx)
        else:
            try:     # up to python-3.2
                request_uri = req.get_selector()
            except AttributeError:  # from python-3.3
                request_uri = req.selector
            h = myHTTPSConnection(host=host, appname=self.appname, ssl_context=self.ctx)
        # End our change
        h.set_debuglevel(self._debuglevel)

        headers = dict(req.headers)
        headers.update(req.unredirected_hdrs)
        # We want to make an HTTP/1.1 request, but the addinfourl
        # class isn't prepared to deal with a persistent connection.
        # It will try to read all remaining data from the socket,
        # which will block while the server waits for the next request.
        # So make sure the connection gets closed after the (only)
        # request.
        headers["Connection"] = "close"
        try:
            h.request(req.get_method(), request_uri, req.data, headers)
            r = h.getresponse()
        except socket.error as err:  # XXX what error?
            raise M2Crypto.m2urllib2.URLError(err)

        # Pick apart the HTTPResponse object to get the addinfourl
        # object initialized properly.

        # Wrap the HTTPResponse object in socket's file object adapter
        # for Windows.  That adapter calls recv(), so delegate recv()
        # to read().  This weird wrapping allows the returned object to
        # have readline() and readlines() methods.
        r.recv = r.read
        if (sys.version_info < (3, 0)):
            fp = socket._fileobject(r, close=True)
        else:
            r._decref_socketios = lambda: None
            r.ssl = h.sock.ssl
            r._timeout = -1.0
            # hack to bypass python3 bug with 0 buffer size and
            # http/client.py readinto method for response class
            if r.length is not None and r.length == 0:
                r.readinto = lambda b: 0
            r.recv_into = r.readinto
            fp = socket.SocketIO(r, 'rb')

        resp = addinfourl(fp, r.msg, req.get_full_url())
        resp.code = r.status
        resp.msg = r.reason
        return resp


class myHTTPSConnection(M2Crypto.httpslib.HTTPSConnection):
    def __init__(self, *args, **kwargs):
        self.appname = kwargs.pop('appname', 'generic')
        M2Crypto.httpslib.HTTPSConnection.__init__(self, *args, **kwargs)

    def _connect(self, family):
        # workaround for old M2Crypto versions where the the
        # SSL.Connection.__init__ constructor has no "family" parameter
        kwargs = {}
        argspec = inspect.getargspec(SSL.Connection.__init__)
        if 'family' in argspec.args:
            kwargs['family'] = family
        elif family != socket.AF_INET:
            # old SSL.Connection classes implicitly use socket.AF_INET
            return False

        self.sock = SSL.Connection(self.ssl_ctx, **kwargs)
        if self.session:
            self.sock.set_session(self.session)
        if hasattr(self.sock, 'set_tlsext_host_name'):
            self.sock.set_tlsext_host_name(self.host)
        self.sock.connect((self.host, self.port))
        return True

    def connect(self):
        # based on M2Crypto.httpslib.HTTPSConnection.connect
        last_exc = None
        connected = False
        for addrinfo in socket.getaddrinfo(self.host, self.port,
                                           socket.AF_UNSPEC,
                                           socket.SOCK_STREAM,
                                           0, 0):
            try:
                connected = self._connect(addrinfo[0])
                if connected:
                    break
            except socket.error as e:
                last_exc = e
            finally:
                if not connected and self.sock is not None:
                    self.sock.close()
        if not connected:
            if last_exc is None:
                msg = 'getaddrinfo returned empty list or unsupported families'
                raise RuntimeError(msg)
            raise last_exc
        # ok we are connected, verify cert
        verify_certificate(self)

    def getHost(self):
        return self.host

    def getPort(self):
        return self.port

class myProxyHTTPSConnection(M2Crypto.httpslib.ProxyHTTPSConnection, HTTPSConnection):
    def __init__(self, *args, **kwargs):
        self.appname = kwargs.pop('appname', 'generic')
        M2Crypto.httpslib.ProxyHTTPSConnection.__init__(self, *args, **kwargs)

    def _start_ssl(self):
        M2Crypto.httpslib.ProxyHTTPSConnection._start_ssl(self)
        verify_certificate(self)

    def endheaders(self, *args, **kwargs):
        if self._proxy_auth is None:
            self._proxy_auth = self._encode_auth()
        HTTPSConnection.endheaders(self, *args, **kwargs)

    # broken in m2crypto: port needs to be an int
    def putrequest(self, method, url, skip_host=0, skip_accept_encoding=0):
        #putrequest is called before connect, so can interpret url and get
        #real host/port to be used to make CONNECT request to proxy
        proto, rest = splittype(url)
        if proto is None:
            raise ValueError("unknown URL type: %s" % url)
        #get host
        host, rest = splithost(rest)
        #try to get port
        host, port = splitport(host)
        #if port is not defined try to get from proto
        if port is None:
            try:
                port = self._ports[proto]
            except KeyError:
                raise ValueError("unknown protocol for: %s" % url)
        self._real_host = host
        self._real_port = int(port)
        M2Crypto.httpslib.HTTPSConnection.putrequest(self, method, url, skip_host, skip_accept_encoding)

    def getHost(self):
        return self._real_host

    def getPort(self):
        return self._real_port

def verify_certificate(connection):
    ctx = connection.sock.ctx
    verrs = ctx.verrs
    ctx.verrs = None
    cert = connection.sock.get_peer_cert()
    if not cert:
        connection.close()
        raise SSLVerificationError("server did not present a certificate")

    # XXX: should be check if the certificate is known anyways?
    # Maybe it changed to something valid.
    if not connection.sock.verify_ok():

        tc = TrustedCertStore(connection.getHost(), connection.getPort(), connection.appname, cert)

        if tc.is_known():

            if tc.is_trusted(): # ok, same cert as the stored one
                return
            else:
                print("WARNING: REMOTE HOST IDENTIFICATION HAS CHANGED!", file=sys.stderr)
                print("IT IS POSSIBLE THAT SOMEONE IS DOING SOMETHING NASTY!", file=sys.stderr)
                print("offending certificate is at '%s'" % tc.file, file=sys.stderr)
                raise SSLVerificationError("remote host identification has changed")

        # if http_debug is set we redirect sys.stdout to an StringIO
        # instance in order to do some header filtering (see conf module)
        # so we have to use the "original" stdout for printing
        out = getattr(connection, '_orig_stdout', sys.stdout)
        verrs.show(out)

        print(file=out)

        if not verrs.could_ignore():
            raise SSLVerificationError("Certificate validation error cannot be ignored")

        if not verrs.chain_ok:
            print("A certificate in the chain failed verification", file=out)
        if not verrs.cert_ok:
            print("The server certificate failed verification", file=out)

        while True:
            print("""
Would you like to
0 - quit (default)
1 - continue anyways
2 - trust the server certificate permanently
9 - review the server certificate
""", file=out)

            print("Enter choice [0129]: ", end='', file=out)
            r = raw_input()
            if not r or r == '0':
                connection.close()
                raise SSLVerificationError("Untrusted Certificate")
            elif r == '1':
                tc.trust_tmp()
                return
            elif r == '2':
                tc.trust_always()
                return
            elif r == '9':
                print(cert.as_text(), file=out)

# vim: sw=4 et
