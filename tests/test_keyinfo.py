import unittest

from osc import obs_api


class TestKeyinfo(unittest.TestCase):
    def test_empty_pubkey(self):
        ki = obs_api.Keyinfo()
        ki.pubkey_list = [{"value": "<pubkey>"}]

        expected = """
Type        : GPG public key
User ID     : 
Algorithm   : 
Key size    : 
Expires     : 
Fingerprint : 
<pubkey>""".strip()
        actual = ki.pubkey_list[0].to_human_readable_string()
        self.assertEqual(expected, actual)

    def test_empty_sslcert(self):
        ki = obs_api.Keyinfo()
        ki.sslcert_list = [{"value": "<pubkey>"}]

        expected = """
Type        : SSL certificate
Subject     : 
Key ID      : 
Serial      : 
Issuer      : 
Algorithm   : 
Key size    : 
Begins      : 
Expires     : 
Fingerprint : 
<pubkey>""".strip()
        actual = ki.sslcert_list[0].to_human_readable_string()
        self.assertEqual(expected, actual)


if __name__ == "__main__":
    unittest.main()
