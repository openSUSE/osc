# Copyright (C) 2009 Novell Inc.
# This program is free software; it may be used, copied, modified
# and distributed under the terms of the GNU General Public Licence,
# either version 2, or (at your option) any later version.

import M2Crypto.httpslib
from M2Crypto.SSL.Checker import SSLVerificationError
from M2Crypto import m2, SSL
import M2Crypto.m2urllib2
import urlparse
import socket
import urllib
import httplib
import sys

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

    except Exception, e:
        print e
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

    def show(self):
        for depth in self.failures.keys():
            cert = self.failures[depth].cert
            print "*** certificate verify failed at depth %d" % depth
            print "Subject: ", cert.get_subject()
            print "Issuer:  ", cert.get_issuer()
            print "Valid: ", cert.get_not_before(), "-", cert.get_not_after()
            print "Fingerprint(MD5):  ", cert.get_fingerprint('md5')
            print "Fingerprint(SHA1): ", cert.get_fingerprint('sha1')

            for err in self.failures[depth].errs:
                reason = "Unknown"
                try:
                    import M2Crypto.Err
                    reason = M2Crypto.Err.get_x509_verify_error(err)
                except:
                    pass
                print "Reason:", reason

    # check if the encountered errors could be ignored
    def could_ignore(self):
        if not 0 in self.failures:
            return True

        from M2Crypto import m2
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
    saved_session = None

    def __init__(self, *args, **kwargs):
        self.appname = kwargs.pop('appname', 'generic')
        M2Crypto.m2urllib2.HTTPSHandler.__init__(self, *args, **kwargs)

    # copied from M2Crypto.m2urllib2.HTTPSHandler
    # it's sole purpose is to use our myHTTPSHandler/myHTTPSProxyHandler class
    # ideally the m2urllib2.HTTPSHandler.https_open() method would be split into
    # "do_open()" and "https_open()" so that we just need to override
    # the small "https_open()" method...)
    def https_open(self, req):
        host = req.get_host()
        if not host:
            raise M2Crypto.m2urllib2.URLError('no host given: ' + req.get_full_url())

        # Our change: Check to see if we're using a proxy.
        # Then create an appropriate ssl-aware connection.
        full_url = req.get_full_url()
        target_host = urlparse.urlparse(full_url)[1]

        if (target_host != host):
            h = myProxyHTTPSConnection(host = host, appname = self.appname, ssl_context = self.ctx)
            # M2Crypto.ProxyHTTPSConnection.putrequest expects a fullurl
            selector = full_url
        else:
            h = myHTTPSConnection(host = host, appname = self.appname, ssl_context = self.ctx)
            selector = req.get_selector()
        # End our change
        h.set_debuglevel(self._debuglevel)
        if self.saved_session:
            h.set_session(self.saved_session)

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
            h.request(req.get_method(), selector, req.data, headers)
            s = h.get_session()
            if s:
                self.saved_session = s
            r = h.getresponse()
        except socket.error, err: # XXX what error?
            err.filename = full_url
            raise M2Crypto.m2urllib2.URLError(err)

        # Pick apart the HTTPResponse object to get the addinfourl
        # object initialized properly.

        # Wrap the HTTPResponse object in socket's file object adapter
        # for Windows.  That adapter calls recv(), so delegate recv()
        # to read().  This weird wrapping allows the returned object to
        # have readline() and readlines() methods.

        # XXX It might be better to extract the read buffering code
        # out of socket._fileobject() and into a base class.

        r.recv = r.read
        fp = socket._fileobject(r)

        resp = urllib.addinfourl(fp, r.msg, req.get_full_url())
        resp.code = r.status
        resp.msg = r.reason
        return resp

class myHTTPSConnection(M2Crypto.httpslib.HTTPSConnection):
    def __init__(self, *args, **kwargs):
        self.appname = kwargs.pop('appname', 'generic')
        M2Crypto.httpslib.HTTPSConnection.__init__(self, *args, **kwargs)

    def connect(self, *args):
        M2Crypto.httpslib.HTTPSConnection.connect(self, *args)
        verify_certificate(self)

    def getHost(self):
        return self.host

    def getPort(self):
        return self.port

class myProxyHTTPSConnection(M2Crypto.httpslib.ProxyHTTPSConnection, httplib.HTTPSConnection):
    def __init__(self, *args, **kwargs):
        self.appname = kwargs.pop('appname', 'generic')
        M2Crypto.httpslib.ProxyHTTPSConnection.__init__(self, *args, **kwargs)

    def _start_ssl(self):
        M2Crypto.httpslib.ProxyHTTPSConnection._start_ssl(self)
        verify_certificate(self)

    def endheaders(self, *args, **kwargs):
        if self._proxy_auth is None:
            self._proxy_auth = self._encode_auth()
        httplib.HTTPSConnection.endheaders(self, *args, **kwargs)        

    # broken in m2crypto: port needs to be an int
    def putrequest(self, method, url, skip_host=0, skip_accept_encoding=0):
        #putrequest is called before connect, so can interpret url and get
        #real host/port to be used to make CONNECT request to proxy
        proto, rest = urllib.splittype(url)
        if proto is None:
            raise ValueError, "unknown URL type: %s" % url
        #get host
        host, rest = urllib.splithost(rest)
        #try to get port
        host, port = urllib.splitport(host)
        #if port is not defined try to get from proto
        if port is None:
            try:
                port = self._ports[proto]
            except KeyError:
                raise ValueError, "unknown protocol for: %s" % url
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
                print >>sys.stderr, "WARNING: REMOTE HOST IDENTIFICATION HAS CHANGED!"
                print >>sys.stderr, "IT IS POSSIBLE THAT SOMEONE IS DOING SOMETHING NASTY!"
                print >>sys.stderr, "offending certificate is at '%s'" % tc.file
                raise SSLVerificationError("remote host identification has changed")

        verrs.show()

        print

        if not verrs.could_ignore():
            raise SSLVerificationError("Certificate validation error cannot be ignored")

        if not verrs.chain_ok:
            print "A certificate in the chain failed verification"
        if not verrs.cert_ok:
            print "The server certificate failed verification"

        while True:
            print """
Would you like to
0 - quit (default)
1 - continue anyways
2 - trust the server certificate permanently
9 - review the server certificate
"""

            r = raw_input("Enter choice [0129]: ")
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
                print cert.as_text()

# vim: sw=4 et
