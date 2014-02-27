import osc.commandline
import osc.core
import osc.oscerr
import os
import re
import sys
from common import GET, POST, OscTestCase, addExpectedRequest, EXPECTED_REQUESTS


FIXTURES_DIR = os.path.join(os.getcwd(), 'prdiff_fixtures')
API_URL  = 'http://localhost/'
UPSTREAM = 'some:project'
BRANCH   = 'home:user:branches:' + UPSTREAM

def rdiff_url(pkg, oldprj, newprj):
    return API_URL + 'source/%s/%s?unified=1&opackage=%s&oproject=%s&cmd=diff&expand=1&tarlimit=0&filelimit=0' % \
        (newprj, pkg, pkg, oldprj.replace(':', '%3A'))

def request_url(prj):
    return API_URL + 'search/request?match=%%28state%%2F%%40name%%3D%%27new%%27+or+state%%2F%%40name%%3D%%27review%%27%%29+and+%%28action%%2Ftarget%%2F%%40project%%3D%%27%s%%27+or+submit%%2Ftarget%%2F%%40project%%3D%%27%s%%27+or+action%%2Fsource%%2F%%40project%%3D%%27%s%%27+or+submit%%2Fsource%%2F%%40project%%3D%%27%s%%27%%29' % \
        tuple([prj.replace(':', '%3A')] * 4)

def GET_PROJECT_PACKAGES(*projects):
    def decorator(test_method):
        def wrapped_test_method(*args):
            for project in projects:
                addExpectedRequest('GET', API_URL + 'source/' + project,
                                   file='%s/directory' % project)
            test_method(*args)
        # "rename" method otherwise we cannot specify a TestCaseClass.testName
        # cmdline arg when using unittest.main()
        wrapped_test_method.__name__ = test_method.__name__
        return wrapped_test_method
    return decorator

def POST_RDIFF(oldprj, newprj):
    def decorator(test_method):
        def wrapped_test_method(*args):
            addExpectedRequest('POST', rdiff_url('common-one',   oldprj, newprj), exp='', text='')
            addExpectedRequest('POST', rdiff_url('common-two',   oldprj, newprj), exp='', file='common-two-diff')
            addExpectedRequest('POST', rdiff_url('common-three', oldprj, newprj), exp='', text='')
            test_method(*args)
        # "rename" method otherwise we cannot specify a TestCaseClass.testName
        # cmdline arg when using unittest.main()
        wrapped_test_method.__name__ = test_method.__name__
        return wrapped_test_method
    return decorator

def suite():
    import unittest
    return unittest.makeSuite(TestProjectDiff)

class TestProjectDiff(OscTestCase):
    diff_hdr = 'Index: %s\n==================================================================='
    def _get_fixtures_dir(self):
        return FIXTURES_DIR

    def _change_to_tmpdir(self, *args):
        os.chdir(os.path.join(self.tmpdir, *args))

    def _run_prdiff(self, *args):
        """Runs osc prdiff, returning captured STDOUT as a string."""
        cli = osc.commandline.Osc()
        argv = ['osc', '--no-keyring', '--no-gnome-keyring', 'prdiff']
        argv.extend(args)
        cli.main(argv=argv)
        return sys.stdout.getvalue()


    def testPrdiffTooManyArgs(self):
        def runner():
            self._run_prdiff('one', 'two', 'superfluous-arg')
        self.assertRaises(osc.oscerr.WrongArgs, runner)


    @GET_PROJECT_PACKAGES(UPSTREAM, BRANCH)
    @POST_RDIFF(UPSTREAM, BRANCH)
    @POST(rdiff_url('only-in-new', UPSTREAM, BRANCH), exp='', text='')
    def testPrdiffZeroArgs(self):
        exp = """identical: common-one
differs:   common-two
identical: common-three
identical: only-in-new
"""
        def runner():
            self._run_prdiff()

        os.chdir('/tmp')
        self.assertRaises(osc.oscerr.WrongArgs, runner)

        self._change_to_tmpdir(FIXTURES_DIR, UPSTREAM)
        self.assertRaises(osc.oscerr.WrongArgs, runner)

        self._change_to_tmpdir(FIXTURES_DIR, BRANCH)
        out = self._run_prdiff()
        self.assertEqualMultiline(out, exp)


    @GET_PROJECT_PACKAGES(UPSTREAM, BRANCH)
    @POST_RDIFF(UPSTREAM, BRANCH)
    @POST(rdiff_url('only-in-new', UPSTREAM, BRANCH), exp='', text='')
    def testPrdiffOneArg(self):
        self._change_to_tmpdir()
        exp = """identical: common-one
differs:   common-two
identical: common-three
identical: only-in-new
"""
        out = self._run_prdiff('home:user:branches:some:project')
        self.assertEqualMultiline(out, exp)


    @GET_PROJECT_PACKAGES('old:prj', 'new:prj')
    @POST_RDIFF('old:prj', 'new:prj')
    def testPrdiffTwoArgs(self):
        self._change_to_tmpdir()
        exp = """identical: common-one
differs:   common-two
identical: common-three
"""
        out = self._run_prdiff('old:prj', 'new:prj')
        self.assertEqualMultiline(out, exp)


    @GET_PROJECT_PACKAGES('old:prj', 'new:prj')
    @POST_RDIFF('old:prj', 'new:prj')
    def testPrdiffOldOnly(self):
        self._change_to_tmpdir()
        exp = """identical: common-one
differs:   common-two
identical: common-three
old only:  only-in-old
"""
        out = self._run_prdiff('--show-not-in-new', 'old:prj', 'new:prj')
        self.assertEqualMultiline(out, exp)


    @GET_PROJECT_PACKAGES('old:prj', 'new:prj')
    @POST_RDIFF('old:prj', 'new:prj')
    def testPrdiffNewOnly(self):
        self._change_to_tmpdir()
        exp = """identical: common-one
differs:   common-two
identical: common-three
new only:  only-in-new
"""
        out = self._run_prdiff('--show-not-in-old', 'old:prj', 'new:prj')
        self.assertEqualMultiline(out, exp)


    @GET_PROJECT_PACKAGES('old:prj', 'new:prj')
    @POST_RDIFF('old:prj', 'new:prj')
    def testPrdiffDiffstat(self):
        self._change_to_tmpdir()
        exp = """identical: common-one
differs:   common-two

 common-two |    1 +
 1 file changed, 1 insertion(+)

identical: common-three
"""
        out = self._run_prdiff('--diffstat', 'old:prj', 'new:prj')
        self.assertEqualMultiline(out, exp)


    @GET_PROJECT_PACKAGES('old:prj', 'new:prj')
    @POST_RDIFF('old:prj', 'new:prj')
    def testPrdiffUnified(self):
        self._change_to_tmpdir()
        exp = """identical: common-one
differs:   common-two

Index: common-two
===================================================================
--- common-two\t2013-01-18 19:18:38.225983117 +0000
+++ common-two\t2013-01-18 19:19:27.882082325 +0000
@@ -1,4 +1,5 @@
 line one
 line two
 line three
+an extra line
 last line

identical: common-three
"""
        out = self._run_prdiff('--unified', 'old:prj', 'new:prj')
        self.assertEqualMultiline(out, exp)


    @GET_PROJECT_PACKAGES('old:prj', 'new:prj')
    @POST(rdiff_url('common-two',   'old:prj', 'new:prj'), exp='', file='common-two-diff')
    @POST(rdiff_url('common-three', 'old:prj', 'new:prj'), exp='', text='')
    def testPrdiffInclude(self):
        self._change_to_tmpdir()
        exp = """differs:   common-two
identical: common-three
"""
        out = self._run_prdiff('--include', 'common-t',
                               'old:prj', 'new:prj')
        self.assertEqualMultiline(out, exp)


    @GET_PROJECT_PACKAGES('old:prj', 'new:prj')
    @POST(rdiff_url('common-two',   'old:prj', 'new:prj'), exp='', file='common-two-diff')
    @POST(rdiff_url('common-three', 'old:prj', 'new:prj'), exp='', text='')
    def testPrdiffExclude(self):
        self._change_to_tmpdir()
        exp = """differs:   common-two
identical: common-three
"""
        out = self._run_prdiff('--exclude', 'one', 'old:prj', 'new:prj')
        self.assertEqualMultiline(out, exp)


    @GET_PROJECT_PACKAGES('old:prj', 'new:prj')
    @POST(rdiff_url('common-two',   'old:prj', 'new:prj'), exp='', file='common-two-diff')
    def testPrdiffIncludeExclude(self):
        self._change_to_tmpdir()
        exp = """differs:   common-two
"""
        out = self._run_prdiff('--include', 'common-t',
                               '--exclude', 'three',
                               'old:prj', 'new:prj')
        self.assertEqualMultiline(out, exp)


    @GET_PROJECT_PACKAGES(UPSTREAM, BRANCH)
    @GET(request_url(UPSTREAM), exp='', file='request')
    @POST(rdiff_url('common-one',   UPSTREAM, BRANCH), exp='', text='')
    @POST(rdiff_url('common-two',   UPSTREAM, BRANCH), exp='', file='common-two-diff')
    @POST(rdiff_url('common-three', UPSTREAM, BRANCH), exp='', file='common-two-diff')
    @POST(rdiff_url('only-in-new',  UPSTREAM, BRANCH), exp='', text='')
    def testPrdiffRequestsMatching(self):
        self._change_to_tmpdir()
        exp = """identical: common-one
differs:   common-two

148023  State:new        By:user         When:2013-01-11T11:04:14
        submit:          home:user:branches:some:project/common-two@7 ->    some:project
        Descr: - Fix it to work - Improve support for something

differs:   common-three
identical: only-in-new
"""
        out = self._run_prdiff('--requests', UPSTREAM, BRANCH)
        self.assertEqualMultiline(out, exp)


    # Reverse the direction of the diff.
    @GET_PROJECT_PACKAGES(BRANCH, UPSTREAM)
    @GET(request_url(BRANCH), exp='', file='no-requests')
    @POST(rdiff_url('common-one',   BRANCH, UPSTREAM), exp='', text='')
    @POST(rdiff_url('common-two',   BRANCH, UPSTREAM), exp='', file='common-two-diff')
    @POST(rdiff_url('common-three', BRANCH, UPSTREAM), exp='', file='common-two-diff')
    @POST(rdiff_url('only-in-new',  BRANCH, UPSTREAM), exp='', text='')
    def testPrdiffRequestsSwitched(self):
        self._change_to_tmpdir()
        exp = """identical: common-one
differs:   common-two
differs:   common-three
identical: only-in-new
"""
        out = self._run_prdiff('--requests', BRANCH, UPSTREAM)
        self.assertEqualMultiline(out, exp)



if __name__ == '__main__':
    import unittest
    unittest.main()
