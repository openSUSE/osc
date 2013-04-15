import osc.core
import osc.oscerr
import os
from common import GET, PUT, OscTestCase
FIXTURES_DIR = os.path.join(os.getcwd(), 'setlinkrev_fixtures')

def suite():
    import unittest
    return unittest.makeSuite(TestSetLinkRev)

class TestSetLinkRev(OscTestCase):
    def setUp(self):
        OscTestCase.setUp(self, copytree=False)

    def _get_fixtures_dir(self):
        return FIXTURES_DIR

    @GET('http://localhost/source/osctest/simple/_link', file='simple_link')
    @GET('http://localhost/source/srcprj/srcpkg?rev=latest', file='simple_filesremote')
    @PUT('http://localhost/source/osctest/simple/_link',
         exp='<link package="srcpkg" project="srcprj" rev="42" />', text='dummytext')
    def test_simple1(self):
        """a simple set_link_rev call without revision"""
        osc.core.set_link_rev('http://localhost', 'osctest', 'simple')

    @GET('http://localhost/source/osctest/simple/_link', file='simple_link')
    @PUT('http://localhost/source/osctest/simple/_link',
         exp='<link package="srcpkg" project="srcprj" rev="42" />', text='dummytext')
    def test_simple2(self):
        """a simple set_link_rev call with revision"""
        osc.core.set_link_rev('http://localhost', 'osctest', 'simple', '42')

    @GET('http://localhost/source/osctest/simple/_link', file='noproject_link')
    @GET('http://localhost/source/osctest/srcpkg?rev=latest&expand=1', file='expandedsrc_filesremote')
    @PUT('http://localhost/source/osctest/simple/_link',
         exp='<link package="srcpkg" rev="eeeeeeeeeeeeeeeeeeeeeeeeeeeeeeee" vrev="1" />', text='dummytext')
    def test_expandedsrc(self):
        """expand src package"""
        osc.core.set_link_rev('http://localhost', 'osctest', 'simple', expand=True)

    @GET('http://localhost/source/osctest/simple/_link', file='simple_link')
    @GET('http://localhost/source/srcprj/srcpkg?linkrev=base&rev=latest&expand=1', file='baserev_filesremote')
    @PUT('http://localhost/source/osctest/simple/_link',
         exp='<link package="srcpkg" project="srcprj" rev="abcdeeeeeeeeeeeeeeeeeeeeeeeeeeee" vrev="1" />', text='dummytext')
    def test_baserev(self):
        """expanded baserev revision"""
        osc.core.set_link_rev('http://localhost', 'osctest', 'simple', baserev=True)

    @GET('http://localhost/source/osctest/simple/_link', file='simple_link')
    @GET('http://localhost/source/srcprj/srcpkg?rev=latest&expand=1', text='conflict in file merge', code=404)
    def test_linkerror(self):
        """link is broken"""
        try:
            from urllib.error import HTTPError
        except ImportError:
            from urllib2 import HTTPError
        # the backend returns status 404 if we try to expand a broken _link
        self.assertRaises(HTTPError, osc.core.set_link_rev, 'http://localhost', 'osctest', 'simple', expand=True)

    @GET('http://localhost/source/osctest/simple/_link', file='rev_link')
    @PUT('http://localhost/source/osctest/simple/_link',
         exp='<link package="srcpkg" project="srcprj" />', text='dummytext')
    def test_deleterev(self):
        """delete rev attribute from link xml"""
        osc.core.set_link_rev('http://localhost', 'osctest', 'simple', revision=None)

    @GET('http://localhost/source/osctest/simple/_link', file='simple_link')
    @PUT('http://localhost/source/osctest/simple/_link',
         exp='<link package="srcpkg" project="srcprj" />', text='dummytext')
    def test_deleterevnonexistent(self):
        """delete non existent rev attribute from link xml"""
        osc.core.set_link_rev('http://localhost', 'osctest', 'simple', revision=None)

if __name__ == '__main__':
    import unittest
    unittest.main()
