import unittest
import urllib2
import osc.core
import StringIO
import shutil
import tempfile
import os
import sys
from xml.etree import cElementTree as ET
EXPECTED_REQUESTS = []

class RequestWrongOrder(Exception):
    """raised if an unexpected request is issued to urllib2"""
    def __init__(self, url, exp_url, method, exp_method):
        Exception.__init__(self)
        self.url = url
        self.exp_url = exp_url
        self.method = method
        self.exp_method = exp_method

    def __str__(self):
        return '%s, %s, %s, %s' % (self.url, self.exp_url, self.method, self.exp_method)

class RequestDataMismatch(Exception):
    """raised if POSTed or PUTed data doesn't match with the expected data"""
    def __init__(self, url, got, exp):
        self.url = url
        self.got = got
        self.exp = exp

    def __str__(self):
        return '%s, %s, %s' % (self.url, self.got, self.exp)

class MyHTTPHandler(urllib2.HTTPHandler):
    def __init__(self, exp_requests, fixtures_dir):
        urllib2.HTTPHandler.__init__(self)
        self.__exp_requests = exp_requests
        self.__fixtures_dir = fixtures_dir

    def http_open(self, req):
        r = self.__exp_requests.pop(0)
        if req.get_full_url() != r[1] or req.get_method() != r[0]:
            raise RequestWrongOrder(req.get_full_url(), r[1], req.get_method(), r[0])
        if req.get_method() in ('GET', 'DELETE'):
            return self.__mock_GET(r[1], **r[2])
        elif req.get_method() in ('PUT', 'POST'):
            return self.__mock_PUT(req, **r[2])

    def __mock_GET(self, fullurl, **kwargs):
        return self.__get_response(fullurl, **kwargs)

    def __mock_PUT(self, req, **kwargs):
        exp = kwargs.get('exp', None)
        if exp is not None and kwargs.has_key('expfile'):
            raise RuntimeError('either specify exp or expfile')
        elif kwargs.has_key('expfile'):
            exp = open(os.path.join(self.__fixtures_dir, kwargs['expfile']), 'r').read()
        elif exp is None:
            raise RuntimeError('exp or expfile required')
        if exp is not None:
            if req.get_data() != exp:
                raise RequestDataMismatch(req.get_full_url(), repr(req.get_data()), repr(exp))
        return self.__get_response(req.get_full_url(), **kwargs)

    def __get_response(self, url, **kwargs):
        f = None
        if kwargs.has_key('exception'):
            raise kwargs['exception']
        if not kwargs.has_key('text') and kwargs.has_key('file'):
            f = StringIO.StringIO(open(os.path.join(self.__fixtures_dir, kwargs['file']), 'r').read())
        elif kwargs.has_key('text') and not kwargs.has_key('file'):
            f = StringIO.StringIO(kwargs['text'])
        else:
            raise RuntimeError('either specify text or file')
        resp = urllib2.addinfourl(f, {}, url)
        resp.code = kwargs.get('code', 200)
        resp.msg = ''
        return resp

def urldecorator(method, fullurl, **kwargs):
    def decorate(test_method):
        def wrapped_test_method(*args):
            addExpectedRequest(method, fullurl, **kwargs)
            test_method(*args)
        # "rename" method otherwise we cannot specify a TestCaseClass.testName
        # cmdline arg when using unittest.main()
        wrapped_test_method.__name__ = test_method.__name__
        return wrapped_test_method
    return decorate

def GET(fullurl, **kwargs):
    return urldecorator('GET', fullurl, **kwargs)

def PUT(fullurl, **kwargs):
    return urldecorator('PUT', fullurl, **kwargs)

def POST(fullurl, **kwargs):
    return urldecorator('POST', fullurl, **kwargs)

def DELETE(fullurl, **kwargs):
    return urldecorator('DELETE', fullurl, **kwargs)

def addExpectedRequest(method, url, **kwargs):
    global EXPECTED_REQUESTS
    EXPECTED_REQUESTS.append((method, url, kwargs))

class OscTestCase(unittest.TestCase):
    def setUp(self, copytree=True):
        oscrc = os.path.join(self._get_fixtures_dir(), 'oscrc')
        osc.core.conf.get_config(override_conffile=oscrc,
                                 override_no_keyring=True, override_no_gnome_keyring=True)
        os.environ['OSC_CONFIG'] = oscrc

        self.tmpdir = tempfile.mkdtemp(prefix='osc_test')
        if copytree:
            shutil.copytree(os.path.join(self._get_fixtures_dir(), 'osctest'), os.path.join(self.tmpdir, 'osctest'))
        global EXPECTED_REQUESTS
        EXPECTED_REQUESTS = []
        osc.core.conf._build_opener = lambda u: urllib2.build_opener(MyHTTPHandler(EXPECTED_REQUESTS, self._get_fixtures_dir()))
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

    def _check_addlist(self, exp):
        self._check_list('_to_be_added', exp)

    def _check_deletelist(self, exp):
        self._check_list('_to_be_deleted', exp)

    def _check_conflictlist(self, exp):
        self._check_list('_in_conflict', exp)

    def _check_status(self, p, fname, exp):
        self.assertEqual(p.status(fname), exp)

    def _check_digests(self, fname, *skipfiles):
        fname = os.path.join(self._get_fixtures_dir(), fname)
        self.assertEqual(open(os.path.join('.osc', '_files'), 'r').read(), open(fname, 'r').read())
        root = ET.parse(fname).getroot()
        for i in root.findall('entry'):
            if i.get('name') in skipfiles:
                continue
            self.assertTrue(os.path.exists(os.path.join('.osc', i.get('name'))))
            self.assertEqual(osc.core.dgst(os.path.join('.osc', i.get('name'))), i.get('md5'))

    def assertEqualMultiline(self, got, exp):
        if (got + exp).find('\n') == -1:
            self.assertEqual(got, exp)
        else:
            start_delim = "\n" + (" 8< ".join(["-----"] * 8)) + "\n"
            end_delim   = "\n" + (" >8 ".join(["-----"] * 8)) + "\n\n"
            self.assertEqual(got, exp,
                             "got:"      + start_delim + got + end_delim +
                             "expected:" + start_delim + exp + end_delim)
