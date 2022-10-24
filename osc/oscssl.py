import binascii
import os
import socket
import ssl
import subprocess
import sys
import tempfile
import typing

from cryptography import x509
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives import serialization
from urllib3.util.ssl_ import create_urllib3_context

from . import oscerr


# based on openssl's include/openssl/x509_vfy.h.in
X509_V_ERR_DEPTH_ZERO_SELF_SIGNED_CERT = 18
X509_V_ERR_SELF_SIGNED_CERT_IN_CHAIN = 19


def create_ssl_context():
    """
    Create a ssl context with disabled weak crypto.

    Relatively safe defaults are set in urllib3 already,
    but we restrict crypto even more.
    """
    ssl_context = create_urllib3_context()
    # we consider anything older than TLSv1_2 insecure
    if sys.version_info[:2] <= (3, 6):
        # deprecated since py3.7
        ssl_context.options |= ssl.OP_NO_TLSv1
        ssl_context.options |= ssl.OP_NO_TLSv1_1
    else:
        # raise minimum version if too low
        if ssl_context.minimum_version < ssl.TLSVersion.TLSv1_2:
            ssl_context.minimum_version = ssl.TLSVersion.TLSv1_2
    return ssl_context


class CertVerificationError(oscerr.OscBaseError):
    def __str__(self):
        args_str = [str(i) for i in self.args]
        return "Certificate Verification Error: " + "\n".join(args_str)


class TrustedCertStore:
    def __init__(self, ssl_context, host, port):
        self.ssl_context = ssl_context
        self.host = host
        self.port = port or 443

        if not self.host:
            raise ValueError("Empty `host`")

        self.dir_path = os.path.expanduser("~/.config/osc/trusted-certs")
        if not os.path.isdir(self.dir_path):
            try:
                os.makedirs(self.dir_path, mode=0o700)
            except FileExistsError:
                pass

        file_name = f"{self.host}_{self.port}"
        self.pem_path = os.path.join(self.dir_path, f"{file_name}.pem")
        if os.path.isfile(self.pem_path):
            # load permanently trusted certificate that is stored on disk
            with open(self.pem_path, "rb") as f:
                self.cert = x509.load_pem_x509_certificate(f.read())
            self.ssl_context.load_verify_locations(cafile=self.pem_path)
        else:
            self.cert = None

    def get_server_certificate(self):
        # The following code throws an exception on self-signed certs,
        # therefore we need to retrieve the cert differently.
        # pem = ssl.get_server_certificate((self.host, self.port))

        ssl_context = create_ssl_context()
        ssl_context.check_hostname = False
        ssl_context.verify_mode = ssl.CERT_NONE
        sock = ssl_context.wrap_socket(socket.socket(), server_hostname=self.host)
        sock.connect((self.host, self.port))
        der = sock.getpeercert(binary_form=True)
        pem = ssl.DER_cert_to_PEM_cert(der)
        cert = x509.load_pem_x509_certificate(pem.encode("utf-8"))
        return cert

    def trust_permanently(self, cert):
        """
        Permanently trust the certificate.
        Store it as a pem file in ~/.config/osc/trusted-certs.
        """
        self.cert = cert
        data = self.cert.public_bytes(serialization.Encoding.PEM)
        with open(self.pem_path, "wb") as f:
            f.write(data)
        self.ssl_context.load_verify_locations(cafile=self.pem_path)

    def trust_temporarily(self, cert):
        """
        Temporarily trust the certificate.
        """
        self.cert = cert
        tmp_dir = os.path.expanduser("~/.config/osc")
        data = self.cert.public_bytes(serialization.Encoding.PEM)
        with tempfile.NamedTemporaryFile(mode="wb+", dir=tmp_dir, prefix="temp_trusted_cert_") as f:
            f.write(data)
            f.flush()
            self.ssl_context.load_verify_locations(cafile=f.name)

    @staticmethod
    def _display_cert(cert):
        print("Subject:", cert.subject.rfc4514_string())
        print("Issuer:", cert.issuer.rfc4514_string())
        try:
            san_ext = cert.extensions.get_extension_for_oid(x509.ExtensionOID.SUBJECT_ALTERNATIVE_NAME)
            san_ext_value = typing.cast(x509.SubjectAlternativeName, san_ext.value)
            san_ext_dnsnames = san_ext_value.get_values_for_type(x509.DNSName)
        except x509.extensions.ExtensionNotFound:
            san_ext_dnsnames = ["(not available)"]
        for san in san_ext_dnsnames:
            print("subjectAltName:", san)
        print("Valid:", cert.not_valid_before, "->", cert.not_valid_after)
        print("Fingerprint(MD5):", binascii.hexlify(cert.fingerprint(hashes.MD5())).decode("utf-8"))
        print("Fingerprint(SHA1):", binascii.hexlify(cert.fingerprint(hashes.SHA1())).decode("utf-8"))

    def prompt_trust(self, cert, reason):
        if self.cert:
            # check if the certificate matches the already trusted certificate for the host and port
            if cert != self.cert:
                raise CertVerificationError([
                    "Remote host identification has changed",
                    "",
                    "WARNING: REMOTE HOST IDENTIFICATION HAS CHANGED!",
                    "IT IS POSSIBLE THAT SOMEONE IS DOING SOMETHING NASTY!",
                    "",
                    f"Offending certificate is at '{self.pem_path}'"
                ])
        else:
            # since there is no trusted certificate on disk,
            # let's display the server cert and give user options to trust it
            print("The server certificate failed verification")
            print()
            self._display_cert(cert)
            print(f"Reason: {reason}")

            while True:
                print("""
Would you like to
0 - quit (default)
1 - continue anyways
2 - trust the server certificate permanently
9 - review the server certificate
""")

                print("Enter choice [0129]: ", end="")
                r = input()
                if not r or r == "0":
                    raise CertVerificationError(["Untrusted certificate"])
                elif r == "1":
                    self.trust_temporarily(cert)
                    return
                elif r == "2":
                    self.trust_permanently(cert)
                    return
                elif r == "9":
                    # TODO: avoid calling openssl to convert pem to text
                    pem = cert.public_bytes(encoding=serialization.Encoding.PEM).decode("utf-8")
                    cmd = ["openssl", "x509", "-text"]
                    try:
                        cert_text = subprocess.check_output(cmd, input=pem, encoding="utf-8")
                        print(cert_text)
                    except FileNotFoundError:
                        print("ERROR: Unable to display certificate because the 'openssl' executable is not available", file=sys.stderr)
