import unittest

from osc.util.helper import decode_it, decode_list


def suite():
    return unittest.defaultTestLoader.loadTestsFromTestCase(TestResults)


class TestResults(unittest.TestCase):
    def testDecodeList(self):
        strlist = ['Test1', 'Test2', 'Test3']
        mixlist = ['Test1', b'Test2', 'Test3']
        byteslist = [b'Test1', b'Test2', b'Test3']

        out = decode_list(strlist)
        self.assertListEqual(out, strlist)

        out = decode_list(mixlist)
        self.assertListEqual(out, strlist)

        out = decode_list(byteslist)
        self.assertListEqual(out, strlist)

    def testDecodeIt(self):
        bytes_obj = b'Test the decoding'
        string_obj = 'Test the decoding'

        out = decode_it(bytes_obj)
        self.assertEqual(out, string_obj)

        out = decode_it(string_obj)
        self.assertEqual(out, string_obj)


if __name__ == '__main__':
    unittest.main()
