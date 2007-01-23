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


def remove_revid(s):
    return re.sub('revision \d*', 'revision XX', s)


def checkout_and_clean(self):
    """check out the package and delete all files
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
  <source_backend>
    <host></host>
    <port></port>
  </source_backend>
  <rpm_backend>
    <host></host>
    <port></port>
  </rpm_backend>
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
    <project name="home:poeml"/>
    <project name="Apache:Modules"/>
  </watchlist>
</person>

"""

        self.out, self.err = runosc('usermeta poeml')
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
        self.out, self.err = runosc('meta Apache')
        self.assertEqual(self.err, '')
        self.assert_('<project name="Apache">' in self.out)


    def testMetaPac(self):
        self.out, self.err = runosc('meta Apache apache2')
        self.assertEqual(self.err, '')
        self.assert_('<package name="apache2" project="Apache">' in self.out)


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
            """)
        self.assertEqual(remove_revid(self.out), expected)



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
        self.assertEqual(self.err, '')
        self.assertEqual(self.out, 'file \'foo1\' does not exist\n')

        touch('foo1')
        self.out, self.err = runosc('add foo1')
        self.assertEqual(self.err, '')
        self.assertEqual(self.out, 'A    foo1\n')

        self.out, self.err = runosc('ci')
        self.assertEqual(self.err, '')
        self.assertEqual(self.out, """Sending        foo1
Transmitting file data .
""")


        # delete a file
        self.out, self.err = runosc('rm foo1')
        self.assertEqual(self.err, '')
        self.assertEqual(self.out, 'D    foo1\n')

        self.out, self.err = runosc('ci')
        self.assertEqual(self.err, '')
        self.assertEqual(self.out, """Deleting       foo1
Transmitting file data 
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
        self.out, self.err = runosc('ci foo2')
        self.assertEqual(self.err, '')
        self.assertEqual(self.out, """Sending        foo2
Transmitting file data .
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
        self.assertEqual(self.out, """Sending        bar1
Deleting       foo2
Transmitting file data .
""")








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
    startdir = os.getcwd()
    suite = unittest.makeSuite(TestOsc)
    unittest.TextTestRunner(verbosity=2).run(suite)
