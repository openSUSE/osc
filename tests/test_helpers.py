import signal
import sys
import unittest

from osc.util.helper import decode_it, decode_list, run_interactive


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


class TestRunInteractive(unittest.TestCase):
    @unittest.skipIf(sys.platform == "win32", "POSIX signals required")
    def test_sigint_ignored_while_child_runs(self):
        # the child simulates Ctrl-C in the terminal by sending SIGINT to osc
        code = "import os, signal; os.kill(os.getppid(), signal.SIGINT)"
        old_handler = signal.getsignal(signal.SIGINT)
        returncode = run_interactive([sys.executable, "-c", code])
        self.assertEqual(returncode, 0)
        self.assertIs(signal.getsignal(signal.SIGINT), old_handler)

    def test_returncode(self):
        returncode = run_interactive([sys.executable, "-c", "raise SystemExit(3)"])
        self.assertEqual(returncode, 3)


if __name__ == '__main__':
    unittest.main()
