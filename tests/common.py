import io
import os
import shutil
import sys
import tempfile
import unittest
from unittest.mock import patch
from urllib.request import HTTPHandler, addinfourl, build_opener
from urllib.parse import urlparse, parse_qs
from xml.etree import ElementTree as ET

import urllib3.response

import osc.conf
import osc.core


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

        if components != components2 or \
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
        super().__init__()
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


EXPECTED_REQUESTS = []


# HACK: Fix "ValueError: I/O operation on closed file." error in tests on openSUSE Leap 15.2.
#       The problem seems to appear only in the tests, possibly some interaction with MockHTTPConnectionPool.
#       Porting 753fbc03 to urllib3 in openSUSE Leap 15.2 would fix the problem.
urllib3.response.HTTPResponse.__iter__ = lambda self: iter(self._fp)


class MockHTTPConnectionPool:
    def __init__(self, host, port=None, **conn_kw):
        pass

    def urlopen(self, method, url, body=None, headers=None, retries=None, **response_kw):
        global EXPECTED_REQUESTS
        request = EXPECTED_REQUESTS.pop(0)

        url = f"http://localhost{url}"

        if not urlcompare(request["url"], url) or request["method"] != method:
            raise RequestWrongOrder(request["url"], url, request["method"], method)

        if method in ("POST", "PUT"):
            if 'exp' not in request and 'expfile' in request:
                with open(request['expfile'], 'rb') as f:
                    exp = f.read()
            elif 'exp' in request and 'expfile' not in request:
                exp = request['exp'].encode('utf-8')
            else:
                raise RuntimeError('Specify either `exp` or `expfile`')

            body = body or b""
            if hasattr(body, "read"):
                # if it is a file-like object, read it
                body = body.read()
            if hasattr(body, "encode"):
                # if it can be encoded to bytes, do it
                body = body.encode("utf-8")

            if body != exp:
                # We do not have a notion to explicitly mark xml content. In case
                # of xml, we do not care about the exact xml representation (for
                # now). Hence, if both, data and exp, are xml and are "equal",
                # everything is fine (for now); otherwise, error out
                # (of course, this is problematic if we want to ensure that XML
                # documents are bit identical...)
                if not xml_equal(body, exp):
                    raise RequestDataMismatch(url, repr(body), repr(exp))

        if 'exception' in request:
            raise request["exception"]

        if 'text' not in request and 'file' in request:
            with open(request['file'], 'rb') as f:
                data = f.read()
        elif 'text' in request and 'file' not in request:
            data = request['text'].encode('utf-8')
        else:
            raise RuntimeError('Specify either `text` or `file`')

        response = urllib3.response.HTTPResponse(body=data, status=request.get("code", 200))
        response._fp = io.BytesIO(data)

        return response


def urldecorator(method, url, **kwargs):
    def decorate(test_method):
        def wrapped_test_method(self):
            # put all args into a single dictionary
            kwargs["method"] = method
            kwargs["url"] = url

            # prepend fixtures dir to `file`
            if "file" in kwargs:
                kwargs["file"] = os.path.join(self._get_fixtures_dir(), kwargs["file"])

            # prepend fixtures dir to `expfile`
            if "expfile" in kwargs:
                kwargs["expfile"] = os.path.join(self._get_fixtures_dir(), kwargs["expfile"])

            EXPECTED_REQUESTS.append(kwargs)

            test_method(self)

        # mock connection pool, but only just once
        if not hasattr(test_method, "_MockHTTPConnectionPool"):
            wrapped_test_method = patch('urllib3.HTTPConnectionPool', MockHTTPConnectionPool)(wrapped_test_method)
            wrapped_test_method._MockHTTPConnectionPool = True

        wrapped_test_method.__name__ = test_method.__name__
        return wrapped_test_method
    return decorate


def GET(path, **kwargs):
    return urldecorator('GET', path, **kwargs)


def PUT(path, **kwargs):
    return urldecorator('PUT', path, **kwargs)


def POST(path, **kwargs):
    return urldecorator('POST', path, **kwargs)


def DELETE(path, **kwargs):
    return urldecorator('DELETE', path, **kwargs)


class OscTestCase(unittest.TestCase):
    def setUp(self, copytree=True):
        global EXPECTED_REQUESTS
        EXPECTED_REQUESTS = []
        os.chdir(os.path.dirname(__file__))
        oscrc = os.path.join(self._get_fixtures_dir(), 'oscrc')
        osc.conf.get_config(override_conffile=oscrc, override_no_keyring=True)
        os.environ['OSC_CONFIG'] = oscrc

        self.tmpdir = tempfile.mkdtemp(prefix='osc_test')
        if copytree:
            shutil.copytree(os.path.join(self._get_fixtures_dir(), 'osctest'), os.path.join(self.tmpdir, 'osctest'))
        self.stdout = sys.stdout
        sys.stdout = io.StringIO()

    def tearDown(self):
        sys.stdout = self.stdout
        try:
            shutil.rmtree(self.tmpdir)
        except:
            pass
        os.environ.pop("OSC_CONFIG", "")
        self.assertTrue(len(EXPECTED_REQUESTS) == 0)

    def _get_fixtures_dir(self):
        raise NotImplementedError('subclasses should implement this method')

    def _get_fixture(self, filename):
        path = os.path.join(self._get_fixtures_dir(), filename)
        with open(path) as f:
            return f.read()

    def _change_to_pkg(self, name):
        os.chdir(os.path.join(self.tmpdir, 'osctest', name))

    def _check_list(self, fname, exp):
        fname = os.path.join('.osc', fname)
        self.assertFileContentEqual(fname, exp)

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
        with open(os.path.join('.osc', '_files')) as f:
            files_act = f.read()
        with open(fname) as f:
            files_exp = f.read()
        self.assertXMLEqual(files_act, files_exp)
        root = ET.fromstring(files_act)
        for i in root.findall('entry'):
            if i.get('name') in skipfiles:
                continue
            self.assertTrue(os.path.exists(os.path.join('.osc', 'sources', i.get('name'))))
            self.assertEqual(osc.core.dgst(os.path.join('.osc', 'sources', i.get('name'))), i.get('md5'))

    def assertFilesEqual(self, first, second):
        self.assertTrue(os.path.exists(first))
        self.assertTrue(os.path.exists(second))
        with open(first) as f1, open(second) as f2:
            self.assertEqual(f1.read(), f2.read())

    def assertFileContentEqual(self, file_path, expected_content):
        self.assertTrue(os.path.exists(file_path))
        with open(file_path) as f:
            self.assertEqual(f.read(), expected_content)

    def assertFileContentNotEqual(self, file_path, expected_content):
        self.assertTrue(os.path.exists(file_path))
        with open(file_path) as f:
            self.assertNotEqual(f.read(), expected_content)

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
            end_delim = "\n" + (" >8 ".join(["-----"] * 8)) + "\n\n"
            self.assertEqual(got, exp,
                             "got:" + start_delim + got + end_delim +
                             "expected:" + start_delim + exp + end_delim)
