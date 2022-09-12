import os
import re
import unittest

import osc.core
import osc.oscerr
from osc.util.helper import decode_list

from .common import GET, OscTestCase


FIXTURES_DIR = os.path.join(os.path.dirname(__file__), 'difffile_fixtures')


def suite():
    return unittest.defaultTestLoader.loadTestsFromTestCase(TestDiffFiles)


class TestDiffFiles(OscTestCase):
    diff_hdr = 'Index: %s\n==================================================================='

    def _get_fixtures_dir(self):
        return FIXTURES_DIR

    def testDiffUnmodified(self):
        """diff an unmodified file"""
        self._change_to_pkg('simple')
        p = osc.core.Package('.')
        p.todo = ['merge']
        self.__check_diff(p, '', None)

    def testDiffAdded(self):
        """diff an added file"""
        self._change_to_pkg('simple')
        p = osc.core.Package('.')
        p.todo = ['toadd1']
        exp = """%s
--- toadd1\t(revision 0)
+++ toadd1\t(revision 0)
@@ -0,0 +1,1 @@
+toadd1
""" % (TestDiffFiles.diff_hdr % 'toadd1')
        self.__check_diff(p, exp, None)

    def testDiffRemoved(self):
        """diff a removed file"""
        self._change_to_pkg('simple')
        p = osc.core.Package('.')
        p.todo = ['somefile']
        exp = """%s
--- somefile\t(revision 2)
+++ somefile\t(working copy)
@@ -1,1 +0,0 @@
-some content
""" % (TestDiffFiles.diff_hdr % 'somefile')
        self.__check_diff(p, exp, None)

    def testDiffMissing(self):
        """diff a missing file (missing files are ignored)"""
        self._change_to_pkg('simple')
        p = osc.core.Package('.')
        p.todo = ['missing']
        self.__check_diff(p, '', None)

    def testDiffReplaced(self):
        """diff a replaced file"""
        self._change_to_pkg('simple')
        p = osc.core.Package('.')
        p.todo = ['replaced']
        exp = """%s
--- replaced\t(revision 2)
+++ replaced\t(working copy)
@@ -1,1 +1,1 @@
-yet another file
+foo replaced
""" % (TestDiffFiles.diff_hdr % 'replaced')
        self.__check_diff(p, exp, None)

    def testDiffSkipped(self):
        """diff a skipped file (skipped files are ignored)"""
        self._change_to_pkg('simple')
        p = osc.core.Package('.')
        p.todo = ['skipped']
        self.__check_diff(p, '', None)

    def testDiffConflict(self):
        """diff a file which is in the conflict state"""
        self._change_to_pkg('simple')
        p = osc.core.Package('.')
        p.todo = ['foo']
        exp = """%s
--- foo\t(revision 2)
+++ foo\t(working copy)
@@ -1,1 +1,5 @@
+<<<<<<< foo.mine
+This is no test.
+=======
 This is a simple test.
+>>>>>>> foo.r2
""" % (TestDiffFiles.diff_hdr % 'foo')
        self.__check_diff(p, exp, None)

    def testDiffModified(self):
        """diff a modified file"""
        self._change_to_pkg('simple')
        p = osc.core.Package('.')
        p.todo = ['nochange']
        exp = """%s
--- nochange\t(revision 2)
+++ nochange\t(working copy)
@@ -1,1 +1,2 @@
-This file didn't change.
+This file didn't change but
+is modified.
""" % (TestDiffFiles.diff_hdr % 'nochange')
        self.__check_diff(p, exp, None)

    def testDiffUnversioned(self):
        """diff an unversioned file"""
        self._change_to_pkg('simple')
        p = osc.core.Package('.')
        p.todo = ['toadd2']
        self.assertRaises(osc.oscerr.OscIOError, self.__check_diff, p, '', None)

    def testDiffAddedMissing(self):
        """diff a file which has satus 'A' but the local file does not exist"""
        self._change_to_pkg('simple')
        p = osc.core.Package('.')
        p.todo = ['addedmissing']
        self.assertRaises(osc.oscerr.OscIOError, self.__check_diff, p, '', None)

    def testDiffMultipleFiles(self):
        """diff multiple files"""
        self._change_to_pkg('simple')
        p = osc.core.Package('.')
        p.todo = ['nochange', 'somefile']
        exp = """%s
--- nochange\t(revision 2)
+++ nochange\t(working copy)
@@ -1,1 +1,2 @@
-This file didn't change.
+This file didn't change but
+is modified.
%s
--- somefile\t(revision 2)
+++ somefile\t(working copy)
@@ -1,1 +0,0 @@
-some content
""" % (TestDiffFiles.diff_hdr % 'nochange', TestDiffFiles.diff_hdr % 'somefile')
        self.__check_diff(p, exp, None)

    def testDiffReplacedEmptyTodo(self):
        """diff a complete package"""
        self._change_to_pkg('replaced')
        p = osc.core.Package('.')
        exp = """%s
--- replaced\t(revision 2)
+++ replaced\t(working copy)
@@ -1,1 +1,1 @@
-yet another file
+foo replaced
""" % (TestDiffFiles.diff_hdr % 'replaced')
        self.__check_diff(p, exp, None)

    def testDiffBinaryAdded(self):
        """diff an added binary file"""
        self._change_to_pkg('binary')
        p = osc.core.Package('.')
        p.todo = ['binary_added']
        exp = """%s
Binary file 'binary_added' added.
""" % (TestDiffFiles.diff_hdr % 'binary_added')
        self.__check_diff(p, exp, None)

    def testDiffBinaryDeleted(self):
        """diff a deleted binary file"""
        self._change_to_pkg('binary')
        p = osc.core.Package('.')
        p.todo = ['binary_deleted']
        exp = """%s
Binary file 'binary_deleted' deleted.
""" % (TestDiffFiles.diff_hdr % 'binary_deleted')
        self.__check_diff(p, exp, None)

    def testDiffBinaryModified(self):
        """diff a modified binary file"""
        self._change_to_pkg('binary')
        p = osc.core.Package('.')
        p.todo = ['binary']
        exp = """%s
Binary file 'binary' has changed.
""" % (TestDiffFiles.diff_hdr % 'binary')
        self.__check_diff(p, exp, None)

    # diff with revision
    @GET('http://localhost/source/osctest/remote_simple_noadd?rev=3', file='testDiffRemoteNoChange_files')
    def testDiffRemoteNoChange(self):
        """diff against remote revision where no file changed"""
        self._change_to_pkg('remote_simple_noadd')
        p = osc.core.Package('.')
        self.__check_diff(p, '', 3)

    @GET('http://localhost/source/osctest/remote_simple?rev=3', file='testDiffRemoteModified_files')
    @GET('http://localhost/source/osctest/remote_simple/merge?rev=3', file='testDiffRemoteModified_merge')
    def testDiffRemoteModified(self):
        """diff against a remote revision with one modified file"""
        self._change_to_pkg('remote_simple')
        p = osc.core.Package('.')
        exp = """%s
--- merge\t(revision 3)
+++ merge\t(working copy)
@@ -1,3 +1,4 @@
 Is it
 possible to
 merge this file?
+I hope so...
%s
--- toadd1\t(revision 0)
+++ toadd1\t(revision 0)
@@ -0,0 +1,1 @@
+toadd1
""" % (TestDiffFiles.diff_hdr % 'merge', TestDiffFiles.diff_hdr % 'toadd1')
        self.__check_diff(p, exp, 3)

    @GET('http://localhost/source/osctest/remote_simple?rev=3', file='testDiffRemoteDeletedLocalAdded_files')
    def testDiffRemoteNotExistingLocalAdded(self):
        """
        a file which doesn't exist in a remote revision and
        has status A in the wc
        """
        self._change_to_pkg('remote_simple')
        p = osc.core.Package('.')
        exp = """%s
--- toadd1\t(revision 0)
+++ toadd1\t(revision 0)
@@ -0,0 +1,1 @@
+toadd1
""" % (TestDiffFiles.diff_hdr % 'toadd1')
        self.__check_diff(p, exp, 3)

    @GET('http://localhost/source/osctest/remote_simple_noadd?rev=3', file='testDiffRemoteExistingLocalNotExisting_files')
    @GET('http://localhost/source/osctest/remote_simple_noadd/foobar?rev=3', file='testDiffRemoteExistingLocalNotExisting_foobar')
    @GET('http://localhost/source/osctest/remote_simple_noadd/binary?rev=3', file='testDiffRemoteExistingLocalNotExisting_binary')
    def testDiffRemoteExistingLocalNotExisting(self):
        """
        a file doesn't exist in the local wc but exists
        in the remote revision
        """
        self._change_to_pkg('remote_simple_noadd')
        p = osc.core.Package('.')
        exp = """%s
--- foobar\t(revision 3)
+++ foobar\t(working copy)
@@ -1,2 +0,0 @@
-foobar
-barfoo
%s
Binary file 'binary' deleted.
""" % (TestDiffFiles.diff_hdr % 'foobar', TestDiffFiles.diff_hdr % 'binary')
        self.__check_diff(p, exp, 3)

    @GET('http://localhost/source/osctest/remote_localmodified?rev=3', file='testDiffRemoteUnchangedLocalModified_files')
    @GET('http://localhost/source/osctest/remote_localmodified/nochange?rev=3', file='testDiffRemoteUnchangedLocalModified_nochange')
    @GET('http://localhost/source/osctest/remote_localmodified/binary?rev=3', file='testDiffRemoteUnchangedLocalModified_binary')
    def testDiffRemoteUnchangedLocalModified(self):
        """remote revision didn't change, local file is modified"""
        self._change_to_pkg('remote_localmodified')
        p = osc.core.Package('.')
        exp = """%s
--- nochange\t(revision 3)
+++ nochange\t(working copy)
@@ -1,1 +1,2 @@
 This file didn't change.
+oh it does
%s
Binary file 'binary' has changed.
""" % (TestDiffFiles.diff_hdr % 'nochange', TestDiffFiles.diff_hdr % 'binary')
        self.__check_diff(p, exp, 3)

    @GET('http://localhost/source/osctest/remote_simple_noadd?rev=3', file='testDiffRemoteMissingLocalExisting_files')
    def testDiffRemoteMissingLocalExisting(self):
        """
        remote revision misses a file which exists in the local wc (state ' ')"""
        self._change_to_pkg('remote_simple_noadd')
        p = osc.core.Package('.')
        exp = """%s
--- foo\t(revision 0)
+++ foo\t(working copy)
@@ -0,0 +1,1 @@
+This is a simple test.
""" % (TestDiffFiles.diff_hdr % 'foo')
        self.__check_diff(p, exp, 3)

    @GET('http://localhost/source/osctest/remote_localdelete?rev=3', file='testDiffRemoteMissingLocalDeleted_files')
    def testDiffRemoteMissingLocalDeleted(self):
        """
        remote revision misses a file which is marked for
        deletion in the local wc
        """
        # empty diff is expected (svn does the same)
        self._change_to_pkg('remote_localdelete')
        p = osc.core.Package('.')
        self.__check_diff(p, '', 3)

    def __check_diff(self, p, exp, revision=None):
        got = ''
        for i in p.get_diff(revision):
            got += ''.join(decode_list(i))

        # When a hunk header refers to a single line in the "from"
        # file and/or the "to" file, e.g.
        #
        #   @@ -37,37 +41,43 @@
        #   @@ -37,39 +41,41 @@
        #   @@ -37,37 +41,41 @@
        #
        # some systems will avoid repeating the line number:
        #
        #   @@ -37 +41,43 @@
        #   @@ -37,39 +41 @@
        #   @@ -37 +41 @@
        #
        # so we need to canonise the output to avoid false negative
        # test failures.

        # TODO: Package.get_diff should return a consistent format
        #       (regardless of the used python version)
        def __canonise_diff(diff):
            # we cannot use re.M because python 2.6's re.sub does
            # not support a flags argument
            diff = [re.sub(r'^@@ -(\d+) ', '@@ -\\1,\\1 ', line)
                    for line in diff.split('\n')]
            diff = [re.sub(r'^(@@ -\d+,\d+) \+(\d+) ', '\\1 +\\2,\\2 ', line)
                    for line in diff]
            return '\n'.join(diff)

        got = __canonise_diff(got)
        exp = __canonise_diff(exp)
        self.assertEqualMultiline(got, exp)


if __name__ == '__main__':
    unittest.main()
