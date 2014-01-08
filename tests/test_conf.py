from osc.conf import passx_encode, passx_decode
from common import OscTestCase

import os

FIXTURES_DIR = os.path.join(os.getcwd(), 'conf_fixtures')

def suite():
    import unittest
    return unittest.makeSuite(TestConf)

class TestConf(OscTestCase):
    def _get_fixtures_dir(self):
        return FIXTURES_DIR

    def setUp(self):
        return super(TestConf, self).setUp(copytree=False)
    
    def testPassxEncodeDecode(self):
        
        passwd = "J0e'sPassword!@#"
        passx = passx_encode(passwd)
        #base64.b64encode(passwd.encode('bz2'))
        passx27 = "QlpoOTFBWSZTWaDg4dQAAAKfgCiAQABAEEAAJgCYgCAAMQAACEyYmTyei67AsYSDSaLuSKcKEhQcHDqA"
        
        self.assertEqual(passwd, passx_decode(passx))
        self.assertEqual(passwd, passx_decode(passx27))
        self.assertEqual(passx, passx27)

if __name__ == '__main__':
    import unittest
    unittest.main()
