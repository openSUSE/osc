import os
import unittest

import osc.core
import osc.oscerr

from .common import GET, PUT, OscTestCase


FIXTURES_DIR = os.path.join(os.path.dirname(__file__), 'setlinkrev_fixtures')


def suite():
    return unittest.defaultTestLoader.loadTestsFromTestCase(TestSetLinkRev)


class TestSetLinkRev(OscTestCase):
    def setUp(self):
        super().setUp(copytree=False)

    def _get_fixtures_dir(self):
        return FIXTURES_DIR

    @GET('http://localhost/source/osctest/simple/_link', file='simple_link')
    @GET('http://localhost/source/srcprj/srcpkg?rev=latest', file='simple_filesremote')
    @PUT('http://localhost/source/osctest/simple/_link?comment=Set+link+revision+to+42',
         exp='<link package="srcpkg" project="srcprj" rev="42" />', text='dummytext')
    def test_simple1(self):
        """a simple set_link_rev call without revision"""
        osc.core.set_link_rev('http://localhost', 'osctest', 'simple')

    @GET('http://localhost/source/osctest/simple/_link', file='simple_link')
    @PUT('http://localhost/source/osctest/simple/_link?comment=Set+link+revision+to+42',
         exp='<link package="srcpkg" project="srcprj" rev="42" />', text='dummytext')
    def test_simple2(self):
        """a simple set_link_rev call with revision"""
        osc.core.set_link_rev('http://localhost', 'osctest', 'simple', '42')

    @GET('http://localhost/source/osctest/simple/_link', file='noproject_link')
    @GET('http://localhost/source/osctest/srcpkg?rev=latest&expand=1', file='expandedsrc_filesremote')
    @PUT('http://localhost/source/osctest/simple/_link?comment=Set+link+revision+to+eeeeeeeeeeeeeeeeeeeeeeeeeeeeeeee',
         exp='<link package="srcpkg" rev="eeeeeeeeeeeeeeeeeeeeeeeeeeeeeeee" vrev="1" />', text='dummytext')
    def test_expandedsrc(self):
        """expand src package"""
        osc.core.set_link_rev('http://localhost', 'osctest', 'simple', expand=True)

    @GET('http://localhost/source/osctest/simple/_link', file='link_with_rev')
    @GET('http://localhost/source/srcprj/srcpkg?rev=latest', file='simple_filesremote')
    @PUT('http://localhost/source/osctest/simple/_link?comment=Set+link+revision+to+42',
         exp='<link package="srcpkg" project="srcprj" rev="42" />', text='dummytext')
    def test_existingrev(self):
        """link already has a rev attribute, update it to current version"""
        # we could also avoid the superfluous PUT
        osc.core.set_link_rev('http://localhost', 'osctest', 'simple')

    @GET('http://localhost/source/osctest/simple/_link', file='link_with_rev')
    @GET('http://localhost/source/srcprj/srcpkg?rev=latest&expand=1', file='expandedsrc_filesremote')
    @PUT('http://localhost/source/osctest/simple/_link?comment=Set+link+revision+to+eeeeeeeeeeeeeeeeeeeeeeeeeeeeeeee',
         exp='<link package="srcpkg" project="srcprj" rev="eeeeeeeeeeeeeeeeeeeeeeeeeeeeeeee" vrev="1" />',
         text='dummytext')
    def test_expandexistingrev(self):
        """link already has a rev attribute, update it to current version"""
        osc.core.set_link_rev('http://localhost', 'osctest', 'simple', expand=True)

    @GET('http://localhost/source/osctest/simple/_link', file='simple_link')
    @GET('http://localhost/source/srcprj/srcpkg?rev=latest&expand=1', text='conflict in file merge', code=400)
    def test_linkerror(self):
        """link is broken"""
        from urllib.error import HTTPError
        # the backend returns status 400 if we try to expand a broken _link
        self.assertRaises(HTTPError, osc.core.set_link_rev, 'http://localhost', 'osctest', 'simple', expand=True)

    @GET('http://localhost/source/osctest/simple/_link', file='rev_link')
    @PUT('http://localhost/source/osctest/simple/_link?comment=Unset+link+revision',
         exp='<link package="srcpkg" project="srcprj" />', text='dummytext')
    def test_deleterev(self):
        """delete rev attribute from link xml"""
        osc.core.set_link_rev('http://localhost', 'osctest', 'simple', revision=None)

    @GET('http://localhost/source/osctest/simple/_link', file='md5_rev_link')
    @PUT('http://localhost/source/osctest/simple/_link?comment=Unset+link+revision',
         exp='<link package="srcpkg" project="srcprj" />', text='dummytext')
    def test_deleterev_md5(self):
        """delete rev and vrev attribute from link xml"""
        osc.core.set_link_rev('http://localhost', 'osctest', 'simple', revision=None)

    @GET('http://localhost/source/osctest/simple/_link', file='simple_link')
    @PUT('http://localhost/source/osctest/simple/_link?comment=Unset+link+revision',
         exp='<link package="srcpkg" project="srcprj" />', text='dummytext')
    def test_deleterevnonexistent(self):
        """delete non existent rev attribute from link xml"""
        osc.core.set_link_rev('http://localhost', 'osctest', 'simple', revision=None)


if __name__ == '__main__':
    unittest.main()
