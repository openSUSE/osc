#!/usr/bin/python

import os
import sys
import time
import re
import unittest
import shutil
from textwrap import dedent

from osc import commandline

chdir = os.chdir
mkdir = os.mkdir

# here, all tests will happen... 
BASEDIR = os.path.join(os.getcwd(), 't')

PRJ = 'home:poeml'
PAC = 'test'
TESTPACDIR = os.path.join(PRJ, PAC)
startdir = os.getcwd()


def remove_revid(s):
    return re.sub('revision \d*', 'revision XX', s)


def checkout_and_clean(self):
    """check out the package and delete all files.
    leave behind the empty package dir"""
    runosc('co %s %s' % (PRJ, PAC))
    chdir(TESTPACDIR)

    files, err = runosc('ls %s %s' %(PRJ, PAC))
    files = files.strip().split('\n')
    if files != ['']:
        for file in files:
            runosc('rm %s' % file)
        runosc('ci')


class TestOsc(unittest.TestCase):
    
    def setUp(self):

        if not os.path.isabs(BASEDIR):
            sys.exit('BASEDIR must be absolute')

        shutil.rmtree(BASEDIR, ignore_errors=True)
        mkdir(BASEDIR)
        chdir(BASEDIR)



    #####################################################################

    def testUsermeta(self):
        expect = """<person>
  <login>poeml</login>
  <email>poeml@suse.de</email>
  <realname>Dr. Peter Poeml</realname>
  <watchlist>
    <project name="server:mail"/>
    <project name="frox"/>
    <project name="home:cthiel1"/>
    <project name="server:php"/>
    <project name="Apache"/>
    <project name="server:httpd-trunk"/>
    <project name="server:isc-dhcp"/>
    <project name="Subversion"/>
    <project name="Tidy"/>
    <project name="validators"/>
    <project name="zsh"/>
    <project name="Apache:Modules"/>
    <project name="home:poeml"/>
  </watchlist>
</person>
"""

        self.out, self.err = runosc('meta user poeml')
        self.assertEqual(self.err, '')
        self.assertEqual(self.out, expect)


    #####################################################################

    def testLs(self):
        self.out, self.err = runosc('ls')
        self.assertEqual(self.err, '')
        self.assert_('Apache' in self.out)
        self.assert_(PRJ in self.out)


    def testLsPrj(self):
        self.out, self.err = runosc('ls Apache')
        self.assertEqual(self.err, '')
        self.assert_('apache2' in self.out)


    def testLsPac(self):
        self.out, self.err = runosc('ls Apache apache2')
        self.assertEqual(self.err, '')
        self.assert_('favicon.ico' in self.out)

    #####################################################################

    def testMetaPrj(self):
        self.out, self.err = runosc('meta prj Apache')
        self.assertEqual(self.err, '')
        self.assert_('<project name="Apache">' in self.out)


    def testMetaPac(self):
        self.out, self.err = runosc('meta pkg Apache apache2')
        self.assertEqual(self.err, '')
        self.assert_('<package project="Apache" name="apache2">' in self.out)


    #####################################################################

    def testPlatforms(self):
        self.out, self.err = runosc('platforms')
        self.assertEqual(self.err, '')
        self.assert_('Factory/standard' in self.out)
        self.assert_('SUSE:SL-10.1/standard' in self.out)


    def testPlatformsPac(self):
        self.out, self.err = runosc('platforms Apache')
        self.assertEqual(self.err, '')
        self.assert_('openSUSE_Factory' in self.out)


    #####################################################################

    def testCommitMsg(self):
        """also tests the info and log commands"""

        checkout_and_clean(self)

        # ci -F

        touch('foo')
        runosc('add foo')
        open('msgfile', 'w').write('message from file')

        self.out, self.err = runosc('ci -F msgfile')
        self.assertEqual(self.err, '')

        self.out, self.err = runosc('info')
        self.assertEqual(self.err, '')
        self.assert_('Path: .\n' in self.out)
        self.assert_('Repository UUID' in self.out)
        self.assert_('Revision' in self.out)

        lastrev = self.out[self.out.find('Revision') + 10 :].strip()

        self.out, self.err = runosc('log -r %s' % lastrev)
        self.assertEqual(self.err, '')
        cl = self.out.splitlines()
        self.assertEqual(len(cl), 5)
        self.assert_(cl[1].startswith('r%s | poeml | ' % lastrev))
        self.assertEqual(cl[2], '')
        self.assertEqual(cl[3], 'message from file')

        # ci -m

        touch('bar')
        runosc('add bar')
        self.out, self.err = runosc('ci -m "message from commandline"')
        self.assertEqual(self.err, '')

        self.out, self.err = runosc('info')
        self.assertEqual(self.err, '')
        lastrev = self.out[self.out.find('Revision') + 10 :].strip()

        self.out, self.err = runosc('log -r %s' % lastrev)
        self.assertEqual(self.err, '')
        cl = self.out.splitlines()
        self.assertEqual(len(cl), 5)
        self.assert_(cl[1].startswith('r%s | poeml | ' % lastrev))
        self.assertEqual(cl[2], '')
        self.assertEqual(cl[3], 'message from commandline')




    #####################################################################

    def testMerge(self):

        wc1 = os.path.join(BASEDIR, TESTPACDIR)
        wc2 = os.path.join(BASEDIR, 'otherwc')

        checkout_and_clean(self)

        # from wc1, create and check in a file
        open('foo', 'w').write(dedent("""\
            ein
            blaues
            Haus
            """))
        runosc('add foo')
        runosc('ci')


        # create second working copy, and do a local modification
        mkdir(wc2)
        chdir(wc2)
        runosc('init %s %s' % (PRJ, PAC))
        runosc('up')
        open('foo', 'w').write(dedent("""\
            kein
            blaues
            Haus
            """))

        self.out, self.err = runosc('st')
        self.assertEqual(self.err, '')
        self.assertEqual(self.out, 'M    foo\n')

        # from wc1, commit a change 
        chdir(wc1)
        open('foo', 'a').write("""geht aus""")
        runosc('ci')

        # in wc2, update, and the change should be merged in
        chdir(wc2)
        self.out, self.err = runosc('up')
        self.assertEqual(self.err, '')
        self.assertEqual(remove_revid(self.out), 'G    foo\nAt revision XX.\n')

        self.out, self.err = runosc('st')
        self.assertEqual(self.err, '')
        self.assertEqual(self.out, 'M    foo\n')

        # successful merge is one thing, but checking the local modification 
        # makes sure that the store copy has been updated to the upstream revision
        self.out, self.err = runosc('diff')
        self.assertEqual(self.err, '')
        expected = dedent("""\
            Index: foo
            ===================================================================
            --- foo     (revision XX) 
            +++ foo     (working copy) 
            @@ -1,4 +1,4 @@
            -ein
            +kein
             blaues
             Haus
             geht aus
            \\ No newline at end of file
            """)
        self.assertEqual(remove_revid(self.out), expected)



    #####################################################################

    def testUpdateLocalMod(self):

        wc1 = os.path.join(BASEDIR, TESTPACDIR)
        wc2 = os.path.join(BASEDIR, 'otherwc')

        checkout_and_clean(self)

        # in wc1, create and check in two files
        touch('f1')
        touch('f2')
        runosc('add f1 f2')
        runosc('ci')


        # create second working copy, and do a local modification
        mkdir(wc2)
        chdir(wc2)
        runosc('init %s %s' % (PRJ, PAC))
        runosc('up')
        open('f2', 'w').write('foo')

        # from wc1, delete the files
        chdir(wc1)
        runosc('rm f1 f2')
        runosc('ci')

        # in wc2, update
        # f1 should be deleted
        # f2 should be kept
        chdir(wc2)
        self.out, self.err = runosc('up')
        self.assertEqual(self.err, '')
        self.assertEqual(remove_revid(self.out), 'D    f1\nD    f2\nAt revision XX.\n')

        self.out, self.err = runosc('st')
        self.assertEqual(self.err, '')
        self.assertEqual(self.out, '?    f2\n')


    #####################################################################

    def testCoPrj(self):
        self.out, self.err = runosc('co %s' % PRJ)
        self.assertEqual(self.err, '')
        self.assert_('A    %s/%s' %(PRJ, PAC) in self.out)


    def testCoPac(self):
        # check out package dir
        self.out, self.err = runosc('co %s %s' % (PRJ, PAC))
        self.assertEqual(self.err, '')
        self.assert_('A    %s/%s' %(PRJ, PAC) in self.out)

    def testCoPacAndDoStuff(self):
        checkout_and_clean(self)

        # check in a file
        # give an error if it doesn't exist
        self.out, self.err = runosc('add foo1')
        self.assertEqual(self.err, 'file \'foo1\' does not exist\n')
        self.assertEqual(self.out, '')

        touch('foo1')
        self.out, self.err = runosc('add foo1')
        self.assertEqual(self.err, '')
        self.assertEqual(self.out, 'A    foo1\n')

        self.out, self.err = runosc('ci -m msg')
        self.assertEqual(self.err, '')
        self.assertEqual(remove_revid(self.out), """Sending        foo1
Transmitting file data .
Committed revision XX.
""")


        # delete a file
        self.out, self.err = runosc('rm foo1')
        self.assertEqual(self.err, '')
        self.assertEqual(self.out, 'D    foo1\n')

        self.out, self.err = runosc('ci -m msg')
        self.assertEqual(self.err, '')
        self.assertEqual(remove_revid(self.out), """Deleting       foo1
Transmitting file data 
Committed revision XX.
""")


        # test 'status'
        touch('onlyinwc')
        self.out, self.err = runosc('st')
        self.assertEqual(self.err, '')
        self.assertEqual(self.out, '?    onlyinwc\n')

        touch('foo2')
        self.out, self.err = runosc('add foo2')
        self.out, self.err = runosc('st')
        self.assertEqual(self.err, '')
        self.assertEqual(self.out, '?    onlyinwc\nA    foo2\n')

        # status with an absolute directory as argument
        self.out, self.err = runosc('st %s' % os.getcwd())
        self.assertEqual(self.err, '')
        self.assertEqual(self.out, '?    %s/onlyinwc\nA    %s/foo2\n' % (os.getcwd(), os.getcwd()))

        # status with an absolute directory as argument
        self.out, self.err = runosc('st %s' % os.getcwd())
        self.assertEqual(self.err, '')
        self.assertEqual(self.out, '?    %s/onlyinwc\nA    %s/foo2\n' % (os.getcwd(), os.getcwd()))

        # status with a single file as argument
        reldir = os.path.basename(os.getcwd())
        self.out, self.err = runosc('st foo2')
        self.assertEqual(self.err, '')
        self.assertEqual(self.out, 'A    foo2\n')

        # check in a single argument
        self.out, self.err = runosc('ci -m msg foo2')
        self.assertEqual(self.err, '')
        self.assertEqual(remove_revid(self.out), """Sending        foo2
Transmitting file data .
Committed revision XX.
""")

        # clean up
        self.out, self.err = runosc('st')
        self.assertEqual(self.err, '')
        self.assertEqual(self.out, '?    onlyinwc\n')
        os.unlink('onlyinwc')


        # test 'addremove'
        touch('bar1')
        os.unlink('foo2')
        self.out, self.err = runosc('addremove')
        self.assertEqual(self.err, '')
        self.assertEqual(self.out, 'D    foo2\nA    bar1\n')
        self.out, self.err = runosc('ci')
        self.assertEqual(self.err, '')
        self.assertEqual(remove_revid(self.out), """Sending        bar1
Deleting       foo2
Transmitting file data .
""")
#Committed revision XX.



    #####################################################################

    # test commandline options

    def testCmdOptVersion(self):
        self.out, self.err = runosc('--version')
        self.assertEqual(self.err, '')
        from osc.core import get_osc_version
        self.assertEqual(self.out, '%s\n' % get_osc_version())

    def testCmdOptHelp(self):
        self.out, self.err = runosc('--help')
        self.assertEqual(self.err, '')
        self.assert_('OpenSUSE build service' in self.out)
        self.assert_('additional information' in self.out)

    def testCmdOptHelpCmd(self):
        self.out, self.err = runosc('help')
        self.assertEqual(self.err, '')
        self.assert_('OpenSUSE build service' in self.out)
        self.assert_('additional information' in self.out)

    # a global option
    def testCmdOptHelpOpt(self):
        self.out, self.err = runosc('help')
        self.assertEqual(self.err, '')
        self.assert_('-H, --http-debug' in self.out)

    # a subcommand option
    def testCmdOptHelpBuild(self):
        self.out, self.err = runosc('help build')
        self.assertEqual(self.err, '')
        self.assert_('build: Build a package' in self.out)
        self.assert_('--clean' in self.out)

    def testCmdOptDebugLs(self):
        self.out, self.err = runosc('-H ls')
        self.assertEqual(self.err, '')
        self.assert_("send: 'GET /source" in self.out)

    def testCmdOptApiOption(self):
        self.out, self.err = runosc('-A https://api.opensuse.org -H ls')
        self.assertEqual(self.err, '')
        self.assert_("reply: 'HTTP/1.1 200 OK" in self.out)






#####################################################################


def runosc(argstring):
    #time.sleep(1) # don't stress the server

    # we test the osc in this directory, not a system one
    return runcmd(os.path.join(startdir, 'osc-wrapper.py'), argstring)


def runcmd(cmd, argstring):
    child_stdin, child_stdout, child_stderr = os.popen3(cmd + ' ' + argstring)
    return child_stdout.read(), child_stderr.read()


def touch(filename):
    open(filename, 'w').close();


if __name__ == '__main__':

    #unittest.main()
    suite = unittest.makeSuite(TestOsc)
    unittest.TextTestRunner(verbosity=2).run(suite)
