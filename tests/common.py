import unittest
import urllib2
import osc.core
import StringIO
import shutil
import tempfile
import os
import sys
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

class MyHTTPHandler(urllib2.HTTPHandler):
    def __init__(self, exp_requests, fixtures_dir):
        urllib2.HTTPHandler.__init__(self)
        self.__exp_requests = exp_requests
        self.__fixtures_dir = fixtures_dir

    def http_open(self, req):
        r = self.__exp_requests.pop(0)
        if req.get_full_url() != r[1] and req.get_method() == r[0]:
            raise RequestWrongOrder(req.get_full_url(), r[1], req.get_method(), r[0])
        if req.get_method() == 'GET':
            return self.__mock_GET(r[1], **r[2])

    def __mock_GET(self, fullurl, **kwargs):
        return self.__get_response(fullurl, **kwargs)

    def __get_response(self, url, **kwargs):
        f = None
        if not kwargs.has_key('text') and kwargs.has_key('file'):
            f = StringIO.StringIO(open(os.path.join(self.__fixtures_dir, kwargs['file']), 'r').read())
        elif kwargs.has_key('text') and not kwargs.has_key('file'):
            f = StringIO.StringIO(kwargs['text'])
        else:
            raise RuntimeError('either specify text or file')
        resp = urllib2.addinfourl(f, '', url)
        resp.code = 200
        resp.msg = ''
        return resp

def GET(fullurl, **kwargs):
    def decorate(test_method):
        def wrapped_test_method(*args):
            addExpectedRequest('GET', fullurl, **kwargs)
            test_method(*args)
        # "rename" method otherwise we cannot specify a TestCaseClass.testName
        # cmdline arg when using unittest.main()
        wrapped_test_method.__name__ = test_method.__name__
        return wrapped_test_method
    return decorate

def addExpectedRequest(method, url, **kwargs):
    global EXPECTED_REQUESTS
    EXPECTED_REQUESTS.append((method, url, kwargs))

class OscTestCase(unittest.TestCase):
    def setUp(self):
        osc.core.conf.get_config(override_conffile=os.path.join(self._get_fixtures_dir(), 'oscrc'))
        self.tmpdir = tempfile.mkdtemp(prefix='osc_test')
        shutil.copytree(os.path.join(self._get_fixtures_dir(), 'osctest'), os.path.join(self.tmpdir, 'osctest'))
        global EXPECTED_REQUESTS
        EXPECTED_REQUESTS = []
        urllib2.install_opener(urllib2.build_opener(MyHTTPHandler(EXPECTED_REQUESTS, self._get_fixtures_dir())))
        self.stdout = sys.stdout
        sys.stdout = StringIO.StringIO()

    def tearDown(self):
        self.assertTrue(len(EXPECTED_REQUESTS) == 0)
        sys.stdout = self.stdout
        try:
            shutil.rmtree(self.tmpdir)
        except:
            pass

    def _get_fixtures_dir(self):
        raise NotImplementedError('subclasses should implement this method')

    def _change_to_pkg(self, name):
        os.chdir(os.path.join(self.tmpdir, 'osctest', name))

    def _check_list(self, fname, exp):
        fname = os.path.join('.osc', fname)
        self.assertTrue(os.path.exists(fname))
        self.assertEqual(open(fname, 'r').read(), exp)

    def _check_status(self, p, fname, exp):
        self.assertEqual(p.status(fname), exp)
