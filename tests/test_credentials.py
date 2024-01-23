import unittest

import osc.conf
from osc.credentials import ObfuscatedConfigFileCredentialsManager


class TestObfuscatedConfigFileCredentialsManager(unittest.TestCase):
    def test_decode_password(self):
        # obfuscated "opensuse"
        password_str = "QlpoOTFBWSZTWeTSblkAAAGBgAIBygAgADDACGNEHxaYXckU4UJDk0m5ZA=="
        password = osc.conf.Password(password_str)
        decoded = ObfuscatedConfigFileCredentialsManager.decode_password(password)
        self.assertEqual(decoded, "opensuse")


if __name__ == "__main__":
    unittest.main()
