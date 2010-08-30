import osc.core
import osc.oscerr
import os
import sys
from common import GET, PUT, POST, DELETE, OscTestCase
from xml.etree import cElementTree as ET
FIXTURES_DIR = os.path.join(os.getcwd(), 'commit_fixtures')

def suite():
    import unittest
    return unittest.makeSuite(TestCommit)

rev_dummy = '<revision rev="upload">\n  <srcmd5>ffffffffffffffffffffffffffffffff</srcmd5>\n</revision>'

class TestCommit(OscTestCase):
    def _get_fixtures_dir(self):
        return FIXTURES_DIR

    @GET('http://localhost/source/osctest/simple?rev=latest', file='testSimple_filesremote')
    @PUT('http://localhost/source/osctest/simple/nochange?rev=upload',
         exp='This file didn\'t change but\nis modified.\n', text=rev_dummy)
    @POST('http://localhost/source/osctest/simple?comment=&cmd=commit&rev=upload&user=Admin', text='<revision rev="2" />',
          exp='')
    @GET('http://localhost/source/osctest/simple?rev=2', file='testSimple_cfilesremote')
    def test_simple(self):
        """a simple commit (only one modified file)"""
        self._change_to_pkg('simple')
        p = osc.core.Package('.')
        p.commit()
        exp = 'Sending    nochange\nTransmitting file data .\nCommitted revision 2.\n'
        self.assertEqual(sys.stdout.getvalue(), exp)
        self._check_digests('testSimple_cfilesremote')
        self.assertTrue(os.path.exists('nochange'))
        self.assertEqual(open('nochange', 'r').read(), open(os.path.join('.osc', 'nochange'), 'r').read())
        self._check_status(p, 'nochange', ' ')

    @GET('http://localhost/source/osctest/add?rev=latest', file='testAddfile_filesremote')
    @PUT('http://localhost/source/osctest/add/add?rev=upload',
         exp='added file\n', text=rev_dummy)
    @POST('http://localhost/source/osctest/add?comment=&cmd=commit&rev=upload&user=Admin', text='<revision rev="2" />',
          exp='')
    @GET('http://localhost/source/osctest/add?rev=2', file='testAddfile_cfilesremote')
    def test_addfile(self):
        """commit a new file"""
        self._change_to_pkg('add')
        p = osc.core.Package('.')
        p.commit()
        exp = 'Sending    add\nTransmitting file data .\nCommitted revision 2.\n'
        self.assertEqual(sys.stdout.getvalue(), exp)
        self._check_digests('testAddfile_cfilesremote')
        self.assertTrue(os.path.exists('add'))
        self.assertEqual(open('add', 'r').read(), open(os.path.join('.osc', 'add'), 'r').read())
        self.assertFalse(os.path.exists(os.path.join('.osc', '_to_be_added')))
        self._check_status(p, 'add', ' ')

    @GET('http://localhost/source/osctest/delete?rev=latest', file='testDeletefile_filesremote')
    @DELETE('http://localhost/source/osctest/delete/nochange?rev=upload', text='<status code="ok" />')
    @POST('http://localhost/source/osctest/delete?comment=&cmd=commit&rev=upload&user=Admin', text='<revision rev="2" />',
          exp='')
    @GET('http://localhost/source/osctest/delete?rev=2', file='testDeletefile_cfilesremote')
    def test_deletefile(self):
        """delete a file"""
        self._change_to_pkg('delete')
        osc.core.Package('.').commit()
        exp = 'Deleting    nochange\nTransmitting file data \nCommitted revision 2.\n'
        self.assertEqual(sys.stdout.getvalue(), exp)
        self._check_digests('testDeletefile_cfilesremote')
        self.assertFalse(os.path.exists('nochange'))
        self.assertFalse(os.path.exists(os.path.join('.osc', 'nochange')))
        self.assertFalse(os.path.exists(os.path.join('.osc', '_to_be_deleted')))

    @GET('http://localhost/source/osctest/conflict?rev=latest', file='testConflictfile_filesremote')
    def test_conflictfile(self):
        """package has a file which is in conflict state"""
        self._change_to_pkg('conflict')
        ret = osc.core.Package('.').commit()
        self.assertTrue(ret == 1)
        exp = 'Please resolve all conflicts before committing using "osc resolved FILE"!\n'
        self.assertEqual(sys.stdout.getvalue(), exp)
        self._check_digests('testConflictfile_filesremote')
        self._check_conflictlist('merge\n')

    @GET('http://localhost/source/osctest/nochanges?rev=latest', file='testNoChanges_filesremote')
    def test_nochanges(self):
        """package has no changes (which can be committed)"""
        self._change_to_pkg('nochanges')
        ret = osc.core.Package('.').commit()
        self.assertTrue(ret == 1)
        exp = 'nothing to do for package nochanges\n'
        self.assertEqual(sys.stdout.getvalue(), exp)

    @GET('http://localhost/source/osctest/multiple?rev=latest', file='testMultiple_filesremote')
    @DELETE('http://localhost/source/osctest/multiple/foo?rev=upload', text='<status code="ok" />')
    @DELETE('http://localhost/source/osctest/multiple/merge?rev=upload', text='<status code="ok" />')
    @PUT('http://localhost/source/osctest/multiple/add?rev=upload', exp='added file\n', text=rev_dummy)
    @PUT('http://localhost/source/osctest/multiple/add2?rev=upload', exp='add2\n', text=rev_dummy)
    @PUT('http://localhost/source/osctest/multiple/nochange?rev=upload', exp='This file did change.\n', text=rev_dummy)
    @POST('http://localhost/source/osctest/multiple?comment=&cmd=commit&rev=upload&user=Admin', text='<revision rev="2" />',
          exp='')
    @GET('http://localhost/source/osctest/multiple?rev=2', file='testMultiple_cfilesremote')
    def test_multiple(self):
        """a simple commit (only one modified file)"""
        self._change_to_pkg('multiple')
        p = osc.core.Package('.')
        p.commit()
        exp = 'Sending    add\nSending    add2\nDeleting    foo\nDeleting    ' \
            'merge\nSending    nochange\nTransmitting file data ...\nCommitted revision 2.\n'
        self.assertEqual(sys.stdout.getvalue(), exp)
        self._check_digests('testMultiple_cfilesremote')
        self.assertFalse(os.path.exists(os.path.join('.osc', '_to_be_added')))
        self.assertFalse(os.path.exists(os.path.join('.osc', '_to_be_deleted')))
        self.assertFalse(os.path.exists(os.path.join('.osc', 'foo')))
        self.assertFalse(os.path.exists(os.path.join('.osc', 'merge')))
        self.assertRaises(IOError, p.status, 'foo')
        self.assertRaises(IOError, p.status, 'merge')
        self._check_status(p, 'add', ' ')
        self._check_status(p, 'add2', ' ')
        self._check_status(p, 'nochange', ' ')

    @GET('http://localhost/source/osctest/multiple?rev=latest', file='testPartial_filesremote')
    @DELETE('http://localhost/source/osctest/multiple/foo?rev=upload', text='<status code="ok" />')
    @PUT('http://localhost/source/osctest/multiple/add?rev=upload', exp='added file\n', text=rev_dummy)
    @PUT('http://localhost/source/osctest/multiple/nochange?rev=upload', exp='This file did change.\n', text=rev_dummy)
    @POST('http://localhost/source/osctest/multiple?comment=&cmd=commit&rev=upload&user=Admin', text='<revision rev="2" />',
          exp='')
    @GET('http://localhost/source/osctest/multiple?rev=2', file='testPartial_cfilesremote')
    def test_partial(self):
        """commit only some files"""
        self._change_to_pkg('multiple')
        p = osc.core.Package('.')
        p.todo = ['foo', 'add', 'nochange']
        p.commit()
        exp = 'Sending    add\nDeleting    foo\n' \
            'Sending    nochange\nTransmitting file data ...\nCommitted revision 2.\n'
        self.assertTrue(sys.stdout.getvalue(), exp)
        self._check_digests('testPartial_cfilesremote')
        self._check_addlist('add2\n')
        self._check_deletelist('merge\n')
        self._check_status(p, 'add2', 'A')
        self._check_status(p, 'merge', 'D')
        self._check_status(p, 'add', ' ')
        self._check_status(p, 'nochange', ' ')
        self.assertRaises(IOError, p.status, 'foo')

    @GET('http://localhost/source/osctest/simple?rev=latest', file='testSimple_filesremote')
    @PUT('http://localhost/source/osctest/simple/nochange?rev=upload', exp='This file didn\'t change but\nis modified.\n',
        exception=IOError('test exception'), text=rev_dummy)
    @POST('http://localhost/source/osctest/simple?comment=&cmd=deleteuploadrev&rev=upload&user=Admin', text='<revision rev="2" />',
          exp='')
    def test_interrupt(self):
        """interrupt a commit"""
        self._change_to_pkg('simple')
        p = osc.core.Package('.')
        self.assertRaises(IOError, p.commit)
        exp = 'Sending    nochange\nTransmitting file data .'
        self.assertEqual(sys.stdout.getvalue(), exp)
        self._check_digests('testSimple_filesremote')
        self.assertTrue(os.path.exists('nochange'))
        self._check_status(p, 'nochange', 'M')

if __name__ == '__main__':
    import unittest
    unittest.main()
