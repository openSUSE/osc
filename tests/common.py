import unittest
import osc.core
import shutil
import tempfile
import os
import sys
try:
    # Works up to Python 3.8, needed for Python < 3.3 (inc 2.7)
    from xml.etree import cElementTree as ET
except ImportError:
    # will import a fast implementation from 3.3 onwards, needed
    # for 3.9+
    from xml.etree import ElementTree as ET
EXPECTED_REQUESTS = []

try:
    #python 2.x
    from cStringIO import StringIO
    from urllib2 import HTTPHandler, addinfourl, build_opener
    from urlparse import urlparse, parse_qs
except ImportError:
    from io import StringIO
    from urllib.request import HTTPHandler, addinfourl, build_opener
    from urllib.parse import urlparse, parse_qs

from io import BytesIO

def urlcompare(url, *args):
    """compare all components of url except query string - it is converted to
    dict, therefor different ordering does not makes url's different, as well
    as quoting of a query string"""

    components = urlparse(url)
    query_args = parse_qs(components.query)
    components = components._replace(query=None)

    if not args:
        return False

    for url in args:
        components2 = urlparse(url)
        query_args2 = parse_qs(components2.query)
        components2 = components2._replace(query=None)

        if  components != components2 or \
            query_args != query_args2:
            return False

    return True


def xml_equal(actual, exp):
    try:
        actual_xml = ET.fromstring(actual)
        exp_xml = ET.fromstring(exp)
    except ET.ParseError:
        return False
    todo = [(actual_xml, exp_xml)]
    while todo:
        actual_xml, exp_xml = todo.pop(0)
        if actual_xml.tag != exp_xml.tag:
            return False
        if actual_xml.attrib != exp_xml.attrib:
            return False
        if actual_xml.text != exp_xml.text:
            return False
        if actual_xml.tail != exp_xml.tail:
            return False
        if len(actual_xml) != len(exp_xml):
            return False
        todo.extend(list(zip(actual_xml, exp_xml)))
    return True


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

class MyHTTPHandler(HTTPHandler):
    def __init__(self, exp_requests, fixtures_dir):
        HTTPHandler.__init__(self)
        self.__exp_requests = exp_requests
        self.__fixtures_dir = fixtures_dir

    def http_open(self, req):
        r = self.__exp_requests.pop(0)
        if not urlcompare(req.get_full_url(), r[1]) or req.get_method() != r[0]:
            raise RequestWrongOrder(req.get_full_url(), r[1], req.get_method(), r[0])
        if req.get_method() in ('GET', 'DELETE'):
            return self.__mock_GET(r[1], **r[2])
        elif req.get_method() in ('PUT', 'POST'):
            return self.__mock_PUT(req, **r[2])

    def __mock_GET(self, fullurl, **kwargs):
        return self.__get_response(fullurl, **kwargs)

    def __mock_PUT(self, req, **kwargs):
        exp = kwargs.get('exp', None)
        if exp is not None and 'expfile' in kwargs:
            raise RuntimeError('either specify exp or expfile')
        elif 'expfile' in kwargs:
            exp = open(os.path.join(self.__fixtures_dir, kwargs['expfile']), 'rb').read()
        elif exp is None:
            raise RuntimeError('exp or expfile required')
        else:
            # for now, assume exp is a str
            exp = exp.encode('utf-8')
        # use req.data instead of req.get_data() for python3 compatiblity
        data = req.data
        if hasattr(data, 'read'):
            data = data.read()
        if data != exp:
            # We do not have a notion to explicitly mark xml content. In case
            # of xml, we do not care about the exact xml representation (for
            # now). Hence, if both, data and exp, are xml and are "equal",
            # everything is fine (for now); otherwise, error out
            # (of course, this is problematic if we want to ensure that XML
            # documents are bit identical...)
            if not xml_equal(data, exp):
                raise RequestDataMismatch(req.get_full_url(), repr(data), repr(exp))
        return self.__get_response(req.get_full_url(), **kwargs)

    def __get_response(self, url, **kwargs):
        f = None
        if 'exception' in kwargs:
            raise kwargs['exception']
        if 'text' not in kwargs and 'file' in kwargs:
            f = BytesIO(open(os.path.join(self.__fixtures_dir, kwargs['file']), 'rb').read())
        elif 'text' in kwargs and 'file' not in kwargs:
            f = BytesIO(kwargs['text'].encode('utf-8'))
        else:
            raise RuntimeError('either specify text or file')
        resp = addinfourl(f, {}, url)
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
        os.chdir(os.path.dirname(__file__))
        oscrc = os.path.join(self._get_fixtures_dir(), 'oscrc')
        osc.core.conf.get_config(override_conffile=oscrc,
                                 override_no_keyring=True, override_no_gnome_keyring=True)
        os.environ['OSC_CONFIG'] = oscrc

        self.tmpdir = tempfile.mkdtemp(prefix='osc_test')
        if copytree:
            shutil.copytree(os.path.join(self._get_fixtures_dir(), 'osctest'), os.path.join(self.tmpdir, 'osctest'))
        global EXPECTED_REQUESTS
        EXPECTED_REQUESTS = []
        osc.core.conf._build_opener = lambda u: build_opener(MyHTTPHandler(EXPECTED_REQUESTS, self._get_fixtures_dir()))
        self.stdout = sys.stdout
        sys.stdout = StringIO()

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
        with open(os.path.join('.osc', '_files'), 'r') as f:
            files_act = f.read()
        with open(fname, 'r') as f:
            files_exp = f.read()
        self.assertXMLEqual(files_act, files_exp)
        root = ET.fromstring(files_act)
        for i in root.findall('entry'):
            if i.get('name') in skipfiles:
                continue
            self.assertTrue(os.path.exists(os.path.join('.osc', 'sources', i.get('name'))))
            self.assertEqual(osc.core.dgst(os.path.join('.osc', 'sources', i.get('name'))), i.get('md5'))

    def assertXMLEqual(self, act, exp):
        if xml_equal(act, exp):
            return
        # ok, xmls are different, hence, assertEqual is expected to fail
        # (we just use it in order to get a "nice" error message)
        self.assertEqual(act, exp)
        # not reached (unless assertEqual is overridden in an incompatible way)
        raise RuntimeError('assertEqual assumptions violated')

    def assertEqualMultiline(self, got, exp):
        if (got + exp).find('\n') == -1:
            self.assertEqual(got, exp)
        else:
            start_delim = "\n" + (" 8< ".join(["-----"] * 8)) + "\n"
            end_delim   = "\n" + (" >8 ".join(["-----"] * 8)) + "\n\n"
            self.assertEqual(got, exp,
                             "got:"      + start_delim + got + end_delim +
                             "expected:" + start_delim + exp + end_delim)
