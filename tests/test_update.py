import unittest
import urllib2
import osc.core
import osc.oscerr
import StringIO
import shutil
import tempfile
import os
import sys
from xml.etree import cElementTree as ET
FIXTURES_DIR = os.path.join(os.getcwd(), 'update_fixtures')
EXPECTED_REQUESTS = []

class RequestWrongOrder(Exception):
    """issued if an unexpected request is issued to urllib2"""
    def __init__(self, url, exp_url, method, exp_method):
        Exception.__init__(self)
        self.url = url
        self.exp_url = exp_url
        self.method = method
        self.exp_method = exp_method

    def __str__(self):
        return '%s, %s, %s, %s' % (self.url, self.exp_url, self.method, self.exp_method)

def get_response(url, **kwargs):
    f = None
    if not kwargs.has_key('text') and kwargs.has_key('file'):
        f = StringIO.StringIO(open(os.path.join(FIXTURES_DIR, kwargs['file']), 'r').read())
    elif kwargs.has_key('text') and not kwargs.has_key('file'):
        f = StringIO.StringIO(kwargs['text'])
    else:
        raise RuntimeError('either specify text or file')
    resp = urllib2.addinfourl(f, '', url)
    resp.code = 200
    resp.msg = ''
    return resp

def mock_GET(fullurl, **kwargs):
    return get_response(fullurl, **kwargs)

class MyHTTPHandler(urllib2.HTTPHandler):
    def __init__(self, exp_requests):
        self.exp_requests = exp_requests

    def http_open(self, req):
        r = self.exp_requests.pop(0)
        if req.get_full_url() != r[1] and req.get_method() == r[0]:
            raise RequestWrongOrder(req.get_full_url(), r[1], req.get_method(), r[0])
        if req.get_method() == 'GET':
            return mock_GET(r[1], **r[2])

def GET(fullurl, **kwargs):
    def decorate(test_method):
        def wrapped_test_method(*args):
            addExpectedRequest('GET', fullurl, **kwargs)
            test_method(*args)
        return wrapped_test_method
    return decorate

def addExpectedRequest(method, url, **kwargs):
    global EXPECTED_REQUESTS
    EXPECTED_REQUESTS.append((method, url, kwargs))

class TestUpdate(unittest.TestCase):
    def setUp(self):
        osc.core.conf.get_config(override_conffile=os.path.join(FIXTURES_DIR, 'oscrc'))
        self.tmpdir = tempfile.mkdtemp(prefix='osc_test')
        shutil.copytree(os.path.join(FIXTURES_DIR, 'osctest'), os.path.join(self.tmpdir, 'osctest'))
        global EXPECTED_REQUESTS
        EXPECTED_REQUESTS = []
        urllib2.install_opener(urllib2.build_opener(MyHTTPHandler(EXPECTED_REQUESTS)))
        self.stdout = sys.stdout
        sys.stdout = StringIO.StringIO()

    def tearDown(self):
        sys.stdout = self.stdout
        try:
            shutil.rmtree(self.tmpdir)
        except:
            pass

    @GET('http://localhost/source/osctest/simple?rev=latest', file='testUpdateNoChanges_files')
    @GET('http://localhost/source/osctest/simple/_meta', file='meta.xml')
    def testUpdateNoChanges(self):
        """update without any changes (the wc is the most recent version)"""
        self.__change_to_pkg('simple')
        osc.core.Package('.').update()
        self.assertTrue(len(EXPECTED_REQUESTS) == 0)
        self.assertEqual(sys.stdout.getvalue(), 'At revision 1.\n')

    @GET('http://localhost/source/osctest/simple?rev=2', file='testUpdateNewFile_files')
    @GET('http://localhost/source/osctest/simple/upstream_added?rev=2', file='testUpdateNewFile_upstream_added')
    @GET('http://localhost/source/osctest/simple/_meta', file='meta.xml')
    def testUpdateNewFile(self):
        """a new file was added to the remote package"""
        self.__change_to_pkg('simple')
        osc.core.Package('.').update(rev=2)
        self.assertTrue(len(EXPECTED_REQUESTS) == 0)
        exp = 'A    upstream_added\nAt revision 2.\n'
        self.assertEqual(sys.stdout.getvalue(), exp)
        self.__check_digests('testUpdateNewFile_files')

    @GET('http://localhost/source/osctest/simple?rev=2', file='testUpdateNewFileLocalExists_files')
    def testUpdateNewFileLocalExists(self):
        """
        a new file was added to the remote package but the same (unversioned)
        file exists locally
        """
        self.__change_to_pkg('simple')
        self.assertRaises(osc.oscerr.PackageFileConflict, osc.core.Package('.').update, rev=2)
        self.assertTrue(len(EXPECTED_REQUESTS) == 0)

    @GET('http://localhost/source/osctest/simple?rev=2', file='testUpdateDeletedFile_files')
    @GET('http://localhost/source/osctest/simple/_meta', file='meta.xml')
    def testUpdateDeletedFile(self):
        """a file was deleted from the remote package"""
        self.__change_to_pkg('simple')
        osc.core.Package('.').update(rev=2)
        self.assertTrue(len(EXPECTED_REQUESTS) == 0)
        exp = 'D    foo\nAt revision 2.\n'
        self.assertEqual(sys.stdout.getvalue(), exp)
        self.__check_digests('testUpdateDeletedFile_files')
        self.assertFalse(os.path.exists('foo'))
        self.assertFalse(os.path.exists(os.path.join('.osc', 'foo')))

    @GET('http://localhost/source/osctest/simple?rev=2', file='testUpdateUpstreamModifiedFile_files')
    @GET('http://localhost/source/osctest/simple/foo?rev=2', file='testUpdateUpstreamModifiedFile_foo')
    @GET('http://localhost/source/osctest/simple/_meta', file='meta.xml')
    def testUpdateUpstreamModifiedFile(self):
        """a file was modified in the remote package (local file isn't modified)"""
        
        self.__change_to_pkg('simple')
        osc.core.Package('.').update(rev=2)
        self.assertTrue(len(EXPECTED_REQUESTS) == 0)
        exp = 'U    foo\nAt revision 2.\n'
        self.assertEqual(sys.stdout.getvalue(), exp)
        self.__check_digests('testUpdateUpstreamModifiedFile_files')

    @GET('http://localhost/source/osctest/conflict?rev=2', file='testUpdateConflict_files')
    @GET('http://localhost/source/osctest/conflict/merge?rev=2', file='testUpdateConflict_merge')
    @GET('http://localhost/source/osctest/conflict/_meta', file='meta.xml')
    def testUpdateConflict(self):
        """
        a file was modified in the remote package (local file is also modified 
        and a merge isn't possible)
        """
        self.__change_to_pkg('conflict')
        osc.core.Package('.').update(rev=2)
        self.assertTrue(len(EXPECTED_REQUESTS) == 0)
        exp = 'C    merge\nAt revision 2.\n'
        self.__check_digests('testUpdateConflict_files')
        self.assertEqual(sys.stdout.getvalue(), exp)
        self.assertEqual(open(os.path.join('.osc', '_in_conflict'), 'r').read(), 'merge\n')

    @GET('http://localhost/source/osctest/already_in_conflict?rev=2', file='testUpdateAlreadyInConflict_files')
    @GET('http://localhost/source/osctest/already_in_conflict/merge?rev=2', file='testUpdateAlreadyInConflict_merge')
    @GET('http://localhost/source/osctest/already_in_conflict/_meta', file='meta.xml')
    def testUpdateAlreadyInConflict(self):
        """
        a file was modified in the remote package (the local file is already in conflict)
        """
        self.__change_to_pkg('already_in_conflict')
        osc.core.Package('.').update(rev=2)
        self.assertTrue(len(EXPECTED_REQUESTS) == 0)
        exp = 'skipping \'merge\' (this is due to conflicts)\nAt revision 2.\n'
        self.assertEqual(sys.stdout.getvalue(), exp)
        self.__check_digests('testUpdateAlreadyInConflict_files')

    @GET('http://localhost/source/osctest/deleted?rev=2', file='testUpdateLocalDeletions_files')
    @GET('http://localhost/source/osctest/deleted/foo?rev=2', file='testUpdateLocalDeletions_foo')
    @GET('http://localhost/source/osctest/deleted/merge?rev=2', file='testUpdateLocalDeletions_merge')
    @GET('http://localhost/source/osctest/deleted/_meta', file='meta.xml')
    def testUpdateLocalDeletions(self):
        """
        the files 'foo' and 'merge' were modified in the remote package
        and marked for deletion in the local wc. Additionally the file
        'merge' was modified in the wc before deletion so the local file
        still exists (and a merge with the remote file is not possible)
        """
        self.__change_to_pkg('deleted')
        osc.core.Package('.').update(rev=2)
        self.assertTrue(len(EXPECTED_REQUESTS) == 0)
        exp = 'U    foo\nC    merge\nAt revision 2.\n'
        self.assertEqual(sys.stdout.getvalue(), exp)
        self.assertEqual(open(os.path.join('.osc', '_to_be_deleted'), 'r').read(), 'foo\n')
        self.assertEqual(open(os.path.join('.osc', '_in_conflict'), 'r').read(), 'merge\n')
        self.assertEqual(open('foo', 'r').read(), open(os.path.join('.osc', 'foo'), 'r').read())
        self.__check_digests('testUpdateLocalDeletions_files')

    @GET('http://localhost/source/osctest/restore?rev=latest', file='testUpdateRestore_files')
    @GET('http://localhost/source/osctest/restore/foo?rev=1', file='testUpdateRestore_foo')
    @GET('http://localhost/source/osctest/restore/_meta', file='meta.xml')
    def testUpdateRestore(self):
        """local file 'foo' was deleted with a non osc command and will be restored"""
        self.__change_to_pkg('restore')
        osc.core.Package('.').update()
        self.assertTrue(len(EXPECTED_REQUESTS) == 0)
        exp = 'Restored \'foo\'\nAt revision 1.\n'
        self.assertEqual(sys.stdout.getvalue(), exp)
        self.__check_digests('testUpdateRestore_files')

    @GET('http://localhost/source/osctest/limitsize?rev=latest', file='testUpdateLimitSizeNoChange_filesremote')
    @GET('http://localhost/source/osctest/limitsize/_meta', file='meta.xml')
    def testUpdateLimitSizeNoChange(self):
        """
        a new file was added to the remote package but isn't checked out because
        of the size constraint
        """
        self.__change_to_pkg('limitsize')
        osc.core.Package('.').update(limit_size=50)
        self.assertTrue(len(EXPECTED_REQUESTS) == 0)
        exp = 'D    bigfile\nAt revision 2.\n'
        self.assertEqual(sys.stdout.getvalue(), exp)
        self.assertFalse(os.path.exists(os.path.join('.osc', 'bigfile')))
        self.assertFalse(os.path.exists('bigfile'))
        self.__check_digests('testUpdateLimitSizeNoChange_files', 'bigfile')

    @GET('http://localhost/source/osctest/limitsize?rev=latest', file='testUpdateLimitSizeAddDelete_filesremote')
    @GET('http://localhost/source/osctest/limitsize/exists?rev=2', file='testUpdateLimitSizeAddDelete_exists')
    @GET('http://localhost/source/osctest/limitsize/_meta', file='meta.xml')
    def testUpdateLimitSizeAddDelete(self):
        """
        a new file (exists) was added to the remote package with
        size < limit_size and one file (nochange) was deleted from the
        remote package (local file 'nochange' is modified). Additionally
        files which didn't change are removed the local wc due to the
        size constraint.
        """
        self.__change_to_pkg('limitsize')
        osc.core.Package('.').update(limit_size=10)
        self.assertTrue(len(EXPECTED_REQUESTS) == 0)
        exp = 'A    exists\nD    bigfile\nD    foo\nD    merge\nD    nochange\nAt revision 2.\n'
        self.assertEqual(sys.stdout.getvalue(), exp)
        self.assertFalse(os.path.exists(os.path.join('.osc', 'bigfile')))
        self.assertFalse(os.path.exists('bigfile'))
        self.assertFalse(os.path.exists(os.path.join('.osc', 'foo')))
        self.assertFalse(os.path.exists('foo'))
        self.assertFalse(os.path.exists(os.path.join('.osc', 'merge')))
        self.assertFalse(os.path.exists('merge'))
        # exists because local version is modified
        self.assertTrue(os.path.exists('nochange'))

        self.__check_digests('testUpdateLimitSizeAddDelete_files', 'bigfile', 'foo', 'merge', 'nochange')

    # tests to recover from an aborted/broken update

    @GET('http://localhost/source/osctest/simple/foo?rev=2', file='testUpdateResume_foo')
    @GET('http://localhost/source/osctest/simple/merge?rev=2', file='testUpdateResume_merge')
    @GET('http://localhost/source/osctest/simple/_meta', file='meta.xml')
    @GET('http://localhost/source/osctest/simple?rev=2', file='testUpdateResume_files')
    @GET('http://localhost/source/osctest/simple/_meta', file='meta.xml')
    def testUpdateResume(self):
        """resume an aborted update"""
        self.__change_to_pkg('resume')
        osc.core.Package('.').update(rev=2)
        self.assertTrue(len(EXPECTED_REQUESTS) == 0)
        exp = 'resuming broken update...\nU    foo\nU    merge\nAt revision 2.\nAt revision 2.\n'
        self.assertEqual(sys.stdout.getvalue(), exp)
        self.assertFalse(os.path.exists(os.path.join('.osc', '_in_update')))
        self.__check_digests('testUpdateResume_files')

    @GET('http://localhost/source/osctest/simple/foo?rev=1', file='testUpdateResumeDeletedFile_foo')
    @GET('http://localhost/source/osctest/simple/merge?rev=1', file='testUpdateResumeDeletedFile_merge')
    @GET('http://localhost/source/osctest/simple/_meta', file='meta.xml')
    @GET('http://localhost/source/osctest/simple?rev=1', file='testUpdateResumeDeletedFile_files')
    @GET('http://localhost/source/osctest/simple/_meta', file='meta.xml')
    def testUpdateResumeDeletedFile(self):
        """
        resume an aborted update (the file 'added' was already deleted in the first update
        run). It's marked as deleted again (this is due to an expected issue with the update
        code)
        """
        self.__change_to_pkg('resume_deleted')
        osc.core.Package('.').update(rev=1)
        self.assertTrue(len(EXPECTED_REQUESTS) == 0)
        exp = 'resuming broken update...\nD    added\nU    foo\nU    merge\nAt revision 1.\nAt revision 1.\n'
        self.assertEqual(sys.stdout.getvalue(), exp)
        self.assertFalse(os.path.exists(os.path.join('.osc', '_in_update')))
        self.__check_digests('testUpdateResumeDeletedFile_files')

    def __expected_requests(self, *args):
        self.assertTrue(len(self.exp_requests) == 0)
        for i in args:
            self.exp_requests.append(i)

    def __change_to_pkg(self, name):
        os.chdir(os.path.join(self.tmpdir, 'osctest', name))

    def __check_digests(self, fname, *skipfiles):
        fname = os.path.join(FIXTURES_DIR, fname)
        self.assertEqual(open(os.path.join('.osc', '_files'), 'r').read(), open(fname, 'r').read())
        root = ET.parse(fname).getroot()
        for i in root.findall('entry'):
            if i.get('name') in skipfiles:
                continue
            self.assertTrue(os.path.exists(os.path.join('.osc', i.get('name'))))
            self.assertEqual(osc.core.dgst(os.path.join('.osc', i.get('name'))), i.get('md5'))

if __name__ == '__main__':
    unittest.main()
