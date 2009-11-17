# Copyright (C) 2009 Novell Inc.
# This program is free software; it may be used, copied, modified
# and distributed under the terms of the GNU General Public Licence,
# either version 2, or (at your option) any later version.

import M2Crypto.httpslib
from M2Crypto.SSL.Checker import SSLVerificationError
from M2Crypto import m2, SSL

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
        self.set_options(m2.SSL_OP_ALL | m2.SSL_OP_NO_SSLv2) # m2crypto does this for us but better safe than sorry
        self.verrs = None
        #self.set_info_callback() # debug
        self.set_verify(SSL.verify_peer | SSL.verify_fail_if_no_peer_cert, depth=9, callback=lambda ok, store: verify_cb(self, ok, store))


class myHTTPSConnection(M2Crypto.httpslib.HTTPSConnection):
    
    appname = 'generic'

    def __init__(self, *args, **kwargs):
        M2Crypto.httpslib.origHTTPSConnection.__init__(self, *args, **kwargs)

    def connect(self, *args):
        r = M2Crypto.httpslib.origHTTPSConnection.connect(self, *args)
	ctx = self.sock.ctx
	verrs = ctx.verrs
	ctx.verrs = None
        cert = self.sock.get_peer_cert()
        if not cert:
            self.close()
            raise SSLVerificationError("server did not present a certificate")

        # XXX: should be check if the certificate is known anyways?
        # Maybe it changed to something valid.
        if not self.sock.verify_ok():

            tc = TrustedCertStore(self.host, self.port, self.appname, cert)

            if tc.is_known():

                if tc.is_trusted(): # ok, same cert as the stored one
                    return
                else:
                    print "WARNING: REMOTE HOST IDENTIFICATION HAS CHANGED!"
                    print "IT IS POSSIBLE THAT SOMEONE IS DOING SOMETHING NASTY!"
                    print "offending certificate is at '%s'" % tc.file
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
                    self.close()
                    raise SSLVerificationError("Untrusted Certificate")
                elif r == '1':
                    tc.trust_tmp()
                    return
                elif r == '2':
                    tc.trust_always()
                    return
                elif r == '9':
                    print cert.as_text()

# XXX: do we really need to override m2crypto's httpslib to be able
# to check certificates after connect?
M2Crypto.httpslib.origHTTPSConnection = M2Crypto.httpslib.HTTPSConnection
M2Crypto.httpslib.HTTPSConnection = myHTTPSConnection

# vim: syntax=python sw=4 et
