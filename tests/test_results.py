import os
import sys
import unittest

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

    @GET('http://localhost/build/testproject/_result', file='result.xml')
    def testPrjresults(self):
        out = self._run_osc('prjresults', '--xml', 'testproject')
        self.assertEqualMultiline(out, self._get_fixture('result.xml') + '\n')

    @GET('http://localhost/build/testproject/_result', file='result-dirty.xml')
    @GET('http://localhost/build/testproject/_result?oldstate=c57e2ee592dbbf26ebf19cc4f1bc1e83', file='result.xml')
    def testPrjresultsWatch(self):
        out = self._run_osc('prjresults', '--watch', '--xml', 'testproject')
        self.assertEqualMultiline(out, self._get_fixture('result-dirty.xml') + '\n' + self._get_fixture('result.xml') + '\n')

    @GET('http://localhost/build/testproject/_result?package=python-MarkupSafe&multibuild=1&locallink=1', file='result.xml')
    def testResults(self):
        out = self._run_osc('results', '--xml', 'testproject', 'python-MarkupSafe')
        self.assertEqualMultiline(out, self._get_fixture('result.xml'))

    @GET('http://localhost/build/testproject/_result?package=python-MarkupSafe&multibuild=1&locallink=1', file='result-dirty.xml')
    @GET('http://localhost/build/testproject/_result?package=python-MarkupSafe&oldstate=c57e2ee592dbbf26ebf19cc4f1bc1e83&multibuild=1&locallink=1', file='result.xml')
    def testResultsWatch(self):
        out = self._run_osc('results', '--watch', '--xml', 'testproject', 'python-MarkupSafe')
        self.assertEqualMultiline(out, self._get_fixture('result-dirty.xml') + self._get_fixture('result.xml'))

    @GET(
        "http://localhost/build/testproject/_result?package=python-MarkupSafe&multibuild=1&locallink=1",
        file="result-publishing-error.xml",
    )
    def testResultsPublishingError(self):
        out = self._run_osc("results", "-v", "--format", "%(repo)s %(status)s", "testproject", "python-MarkupSafe")
        self.assertEqualMultiline(
            out,
            "succeeded_repo succeeded(unpublished)\n"
            "unresolvable_repo unresolvable: \n      nothing provides missing-dependency\n"
            "failed_repo failed\n"
            "broken_repo broken: package has no build description\n",
        )

    @GET(
        "http://localhost/build/testproject/_result?package=python-MarkupSafe&multibuild=1&locallink=1",
        file="result-publishing-error.xml",
    )
    def testResultsPublishingErrorCsv(self):
        out = self._run_osc(
            "results", "--csv", "--format", "repository,code,details", "testproject", "python-MarkupSafe"
        )
        self.assertEqualMultiline(
            out,
            '"succeeded_repo","succeeded",""\n'
            '"unresolvable_repo","unresolvable","nothing provides missing-dependency"\n'
            '"failed_repo","failed",""\n'
            '"broken_repo","broken","package has no build description"\n',
        )


class TestResultXmlToDicts(unittest.TestCase):
    def test_repository_error_without_package_status(self):
        xml = """<resultlist>
          <result repository="repo" arch="x86_64" code="broken" details="invalid repository configuration" />
        </resultlist>"""
        result, is_multi = list(osc.core.result_xml_to_dicts(xml))[0]
        self.assertEqual(result["pkg"], "_repository")
        self.assertEqual(result["code"], "broken")
        self.assertEqual(result["details"], "invalid repository configuration")
        self.assertFalse(is_multi)

    def test_repository_error_with_unknown_package_status(self):
        xml = """<resultlist>
          <result repository="repo" arch="x86_64" code="broken" details="invalid repository configuration">
            <status package="package" code="unknown" />
          </result>
        </resultlist>"""
        result, is_multi = list(osc.core.result_xml_to_dicts(xml))[0]
        self.assertEqual(result["pkg"], "package")
        self.assertEqual(result["code"], "broken")
        self.assertEqual(result["details"], "repository: invalid repository configuration")
        self.assertFalse(is_multi)


if __name__ == '__main__':
    unittest.main()
