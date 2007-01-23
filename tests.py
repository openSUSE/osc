#!/usr/bin/python

import os, sys, time
import unittest
import shutil

from osc import commandline

PRJ = 'home:poeml'
PAC = 'test'
testpacdir = os.path.join(PRJ, PAC)
testdir = 't'

class TestOsc(unittest.TestCase):
    
    def setUp(self):
        os.chdir(oldpwd)
        self.wd = testdir
        shutil.rmtree(self.wd, ignore_errors=True)
        os.mkdir(self.wd)

        pass


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

    def testCoPrj(self):
        os.chdir(self.wd)
        self.out, self.err = runosc('co %s' % PRJ)
        self.assertEqual(self.err, '')
        self.assert_('A    %s/%s' %(PRJ, PAC) in self.out)


    def testCoPac(self):
        # check out package dir
        os.chdir(self.wd)
        self.out, self.err = runosc('co %s %s' % (PRJ, PAC))
        self.assertEqual(self.err, '')
        self.assert_('A    %s/%s' %(PRJ, PAC) in self.out)

        # work in the package dir
        os.chdir(testpacdir)


        # delete all existing files
        self.upstream_files, err = runosc('ls %s %s' %(PRJ, PAC))
        self.upstream_files = self.upstream_files.strip().split('\n')
        if self.upstream_files != ['']:
            for file in self.upstream_files:
                self.out, self.err = runosc('rm %s' % file)
                self.assertEqual(self.err, '')
                self.assert_('D    %s' % file in self.out)
            self.out, self.err = runosc('ci')


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
    time.sleep(1) # don't stress the server
    return runcmd(os.path.join(oldpwd, 'osc-wrapper.py'), argstring)


def runcmd(cmd, argstring):
    child_stdin, child_stdout, child_stderr = os.popen3(cmd + ' ' + argstring)
    return child_stdout.read(), child_stderr.read()


def touch(filename):
    open(filename, 'w').close();


if __name__ == '__main__':

    #unittest.main()
    oldpwd = os.getcwd()
    suite = unittest.makeSuite(TestOsc)
    unittest.TextTestRunner(verbosity=2).run(suite)
