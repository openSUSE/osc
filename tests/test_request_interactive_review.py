import io
import unittest
from contextlib import redirect_stderr, redirect_stdout
from unittest.mock import patch

from osc import core


class TestRequestInteractiveReview(unittest.TestCase):
    apiurl = 'https://api.example.com'
    results = b'''<resultlist>
      <result project="source" repository="standard" arch="x86_64">
        <status package="foo" code="succeeded"/>
        <status package="foo:test" code="failed"/>
        <status package="foo:disabled" code="disabled"/>
        <status package="foo:excluded" code="excluded"/>
      </result>
      <result project="source" repository="standard" arch="aarch64">
        <status package="foo:test" code="building"/>
      </result>
      <result project="source" repository="broken" arch="x86_64" code="broken"/>
    </resultlist>'''

    def setUp(self):
        self.request = core.Request()
        self.request.reqid = '123'
        self.request.add_action('submit', src_project='source', src_package='foo',
                                tgt_project='target', tgt_package='foo')
        # Request rendering and comments are unrelated to log selection.
        self.patchers = [
            patch.object(core.Request, '__str__', return_value='request 123'),
            patch.object(core, 'print_comments'),
            patch.object(core, 'run_pager'),
        ]
        for patcher in self.patchers:
            patcher.start()
            self.addCleanup(patcher.stop)

    def review(self, replies):
        output = io.StringIO()
        with patch.object(core, 'raw_input', side_effect=replies), \
                redirect_stdout(output), redirect_stderr(io.StringIO()):
            core.request_interactive_review(self.apiurl, self.request)
        return output.getvalue()

    def test_buildlog_flavor(self):
        with patch.object(core, 'get_package_results', return_value=iter([self.results])) as results, \
                patch.object(core, 'print_buildlog') as buildlog:
            output = self.review(['bl', '1', 's'])
        results.assert_called_once_with(self.apiurl, 'source', 'foo', multibuild=True)
        self.assertEqual(buildlog.call_args.args,
                         (self.apiurl, 'source', 'foo:test', 'standard', 'x86_64'))
        self.assertIn('(0) source/foo/standard/x86_64', output)
        self.assertIn('(1) source/foo:test/standard/x86_64', output)
        self.assertIn('(2) source/foo:test/standard/aarch64', output)
        self.assertNotIn('foo:disabled', output)
        self.assertNotIn('foo:excluded', output)
        self.assertNotIn('/broken/', output)

    def test_buildlog_base_package(self):
        results_xml = b'''<resultlist><result repository="standard" arch="x86_64">
          <status package="foo" code="succeeded"/>
        </result></resultlist>'''
        with patch.object(core, 'get_package_results', return_value=iter([results_xml])), \
                patch.object(core, 'print_buildlog') as buildlog:
            self.review(['bl', '0', 's'])
        self.assertEqual(buildlog.call_args.args,
                         (self.apiurl, 'source', 'foo', 'standard', 'x86_64'))

    def test_rpmlint_flavor(self):
        with patch.object(core, 'get_package_results', return_value=iter([self.results])), \
                patch.object(core, 'get_rpmlint_log', return_value='lint log') as lintlog:
            self.review(['li', '1', 's'])
        lintlog.assert_called_once_with(self.apiurl, proj='source', pkg='foo:test',
                                        repo='standard', arch='x86_64')

    def test_empty_results(self):
        with patch.object(core, 'get_package_results', return_value=iter([b'<resultlist/>'])), \
                patch.object(core, 'print_buildlog') as buildlog:
            output = self.review(['bl', 's'])
        self.assertIn('No repos', output)
        buildlog.assert_not_called()

    def test_multiple_actions(self):
        self.request.add_action('submit', src_project='other', src_package='bar',
                                tgt_project='target', tgt_package='bar')
        other_results = b'''<resultlist><result repository="ports" arch="aarch64">
          <status package="bar:test" code="failed"/>
        </result></resultlist>'''
        with patch.object(core, 'get_package_results',
                          side_effect=[iter([self.results]), iter([other_results])]), \
                patch.object(core, 'print_buildlog') as buildlog:
            self.review(['bl', '3', 's'])
        self.assertEqual(buildlog.call_args.args,
                         (self.apiurl, 'other', 'bar:test', 'ports', 'aarch64'))

    def test_missing_buildlog(self):
        error = core.HTTPError('https://api.example.com', 404, 'Not Found', {}, None)
        with patch.object(core, 'get_package_results', return_value=iter([self.results])), \
                patch.object(core, 'print_buildlog', side_effect=error):
            output = self.review(['bl', '1', 's'])
        self.assertIn('No build log for standard/x86_64', output)

    def test_buildstatus_includes_multibuild(self):
        with patch.object(core, 'get_results', return_value=['foo:test failed']) as results:
            output = self.review(['b', 's'])
        results.assert_called_once_with(self.apiurl, 'source', 'foo', multibuild=True)
        self.assertIn('foo:test failed', output)


if __name__ == '__main__':
    unittest.main()
