import os
import sys
import unittest

import urllib3.exceptions

import osc.commandline
import osc.core

from .common import GET, OscTestCase


def suite():
    return unittest.defaultTestLoader.loadTestsFromTestCase(TestResults)


class TestResults(OscTestCase):
    def setUp(self):
        super().setUp(copytree=False)

    def _get_fixtures_name(self):
        return 'results_fixtures'

    def _get_fixtures_dir(self):
        return os.path.join(os.path.dirname(__file__), self._get_fixtures_name())

    @GET("http://localhost/build/testproject/_result", file="result.xml", timeout=osc.core.RESULTS_TIMEOUT)
    def testPrjresults(self):
        out = self._run_osc('prjresults', '--xml', 'testproject')
        self.assertEqualMultiline(out, self._get_fixture('result.xml') + '\n')

    @GET("http://localhost/build/testproject/_result", file="result-dirty.xml", timeout=osc.core.RESULTS_TIMEOUT)
    @GET(
        "http://localhost/build/testproject/_result?oldstate=c57e2ee592dbbf26ebf19cc4f1bc1e83",
        file="result.xml",
        timeout=osc.core.RESULTS_TIMEOUT,
    )
    def testPrjresultsWatch(self):
        out = self._run_osc('prjresults', '--watch', '--xml', 'testproject')
        self.assertEqualMultiline(out, self._get_fixture('result-dirty.xml') + '\n' + self._get_fixture('result.xml') + '\n')

    @GET(
        "http://localhost/build/testproject/_result?package=python-MarkupSafe&multibuild=1&locallink=1",
        file="result.xml",
        timeout=osc.core.RESULTS_TIMEOUT,
    )
    def testResults(self):
        out = self._run_osc('results', '--xml', 'testproject', 'python-MarkupSafe')
        self.assertEqualMultiline(out, self._get_fixture('result.xml'))

    @GET(
        "http://localhost/build/testproject/_result?package=python-MarkupSafe&multibuild=1&locallink=1",
        file="result-dirty.xml",
        timeout=osc.core.RESULTS_TIMEOUT,
    )
    @GET(
        "http://localhost/build/testproject/_result?package=python-MarkupSafe&oldstate=c57e2ee592dbbf26ebf19cc4f1bc1e83&multibuild=1&locallink=1",
        file="result.xml",
        timeout=osc.core.RESULTS_TIMEOUT,
    )
    def testResultsWatch(self):
        out = self._run_osc('results', '--watch', '--xml', 'testproject', 'python-MarkupSafe')
        self.assertEqualMultiline(out, self._get_fixture('result-dirty.xml') + self._get_fixture('result.xml'))

    @GET(
        "http://localhost/build/testproject/_result?package=python-MarkupSafe&multibuild=1&locallink=1",
        file="result-dirty.xml",
        timeout=osc.core.RESULTS_TIMEOUT,
    )
    @GET(
        "http://localhost/build/testproject/_result?package=python-MarkupSafe&oldstate=c57e2ee592dbbf26ebf19cc4f1bc1e83&multibuild=1&locallink=1",
        body_exception=urllib3.exceptions.ReadTimeoutError(None, None, "Read timed out."),
        timeout=osc.core.RESULTS_TIMEOUT,
    )
    @GET(
        "http://localhost/build/testproject/_result?package=python-MarkupSafe&oldstate=c57e2ee592dbbf26ebf19cc4f1bc1e83&multibuild=1&locallink=1",
        body_exception=urllib3.exceptions.ProtocolError("Connection broken", ConnectionResetError()),
        timeout=osc.core.RESULTS_TIMEOUT,
    )
    @GET(
        "http://localhost/build/testproject/_result?package=python-MarkupSafe&oldstate=c57e2ee592dbbf26ebf19cc4f1bc1e83&multibuild=1&locallink=1",
        file="result.xml",
        timeout=osc.core.RESULTS_TIMEOUT,
    )
    def testResultsWatchBrokenBody(self):
        out = self._run_osc("results", "--watch", "--xml", "testproject", "python-MarkupSafe")
        self.assertEqualMultiline(out, self._get_fixture("result-dirty.xml") + self._get_fixture("result.xml"))


if __name__ == '__main__':
    unittest.main()
