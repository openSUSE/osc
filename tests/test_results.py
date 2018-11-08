import osc.commandline
from common import GET, OscTestCase
import os
import sys

def suite():
    import unittest
    return unittest.makeSuite(TestResults)

class TestResults(OscTestCase):
    def setUp(self):
        OscTestCase.setUp(self, copytree=False)

    def _get_fixtures_name(self):
        return 'results_fixtures'

    def _get_fixtures_dir(self):
        return os.path.join(os.path.dirname(__file__), self._get_fixtures_name())

    def _run_osc(self, *args):
        """Runs osc, returning (exit value, captured STDOUT as a string)."""
        cli = osc.commandline.Osc()
        argv = ['osc', '--no-keyring', '--no-gnome-keyring']
        argv.extend(args)
        exit = cli.main(argv=argv)
        return (exit, sys.stdout.getvalue())

    def _get_fixture(self, filename):
        return open(os.path.join(self._get_fixtures_dir(), filename), 'r').read()

    @GET('http://localhost/build/testproject/_result', file='result.xml')
    def testPrjresultsXml(self):
        _, out = self._run_osc('prjresults', '--xml', 'testproject')
        self.assertEqualMultiline(out, self._get_fixture('result.xml')+'\n')

    @GET('http://localhost/build/testproject/_result', file='result.xml')
    def testPrjresultsSuccess(self):
        exit, _ = self._run_osc('prjresults', '--xml', 'testproject')
        self.assertEqual(exit, None)

    @GET('http://localhost/build/testproject/_result', file='result-false.xml')
    def testPrjresultsFailure(self):
        exit, out = self._run_osc('prjresults', '--xml', 'testproject')
        self.assertEqual(exit, 3)
        self.assertEqualMultiline(out, self._get_fixture('result-false.xml')+'\n')

    @GET('http://localhost/build/testproject/_result', file='result.xml')
    def testPrjresults(self):
        _, out = self._run_osc('prjresults', 'testproject', '--hide-legend')
        self.assertEqualMultiline(out, self._get_fixture('result.txt')+'\n')

    @GET('http://localhost/build/testproject/_result', file='result-dirty.xml')
    @GET('http://localhost/build/testproject/_result?oldstate=c57e2ee592dbbf26ebf19cc4f1bc1e83', file='result.xml')
    def testPrjresultsWatchXml(self):
        _, out = self._run_osc('prjresults', '--watch', '--xml', 'testproject')
        self.assertEqualMultiline(out, self._get_fixture('result-dirty.xml')+'\n'+self._get_fixture('result.xml')+'\n')

    @GET('http://localhost/build/testproject/_result', file='result-dirty.xml')
    @GET('http://localhost/build/testproject/_result?oldstate=c57e2ee592dbbf26ebf19cc4f1bc1e83', file='result.xml')
    def testPrjresultsWatch(self):
        _, out = self._run_osc('prjresults', '--watch', 'testproject', '--hide-legend')
        self.assertEqualMultiline(out, self._get_fixture('result-dirty.txt')+'\n'+self._get_fixture('result.txt')+'\n')

    @GET('http://localhost/build/testproject/_result?package=python-MarkupSafe&multibuild=1&locallink=1', file='result.xml')
    def testResults(self):
        _, out = self._run_osc('results', '--xml', 'testproject', 'python-MarkupSafe')
        self.assertEqualMultiline(out, self._get_fixture('result.xml'))

    @GET('http://localhost/build/testproject/_result?package=python-MarkupSafe&multibuild=1&locallink=1', file='result-dirty.xml')
    @GET('http://localhost/build/testproject/_result?package=python-MarkupSafe&oldstate=c57e2ee592dbbf26ebf19cc4f1bc1e83&multibuild=1&locallink=1', file='result.xml')
    def testResultsWatch(self):
        _, out = self._run_osc('results', '--watch', '--xml', 'testproject', 'python-MarkupSafe')
        self.assertEqualMultiline(out, self._get_fixture('result-dirty.xml')+self._get_fixture('result.xml'))

if __name__ == '__main__':
    import unittest
    unittest.main()

