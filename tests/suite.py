import os.path
import sys
import unittest

try:
    import xmlrunner # JUnit like XML reporting
    have_xmlrunner = True
except ImportError:
    have_xmlrunner = False

import test_update
import test_addfiles
import test_deletefiles
import test_revertfiles
import test_difffiles
import test_init_package
import test_init_project
import test_commit
import test_repairwc
import test_package_status
import test_project_status
import test_request
import test_setlinkrev
import test_prdiff
import test_conf

suite = unittest.TestSuite()
suite.addTests(test_addfiles.suite())
suite.addTests(test_deletefiles.suite())
suite.addTests(test_revertfiles.suite())
suite.addTests(test_update.suite())
suite.addTests(test_difffiles.suite())
suite.addTests(test_init_package.suite())
suite.addTests(test_init_project.suite())
suite.addTests(test_commit.suite())
suite.addTests(test_repairwc.suite())
suite.addTests(test_package_status.suite())
suite.addTests(test_project_status.suite())
suite.addTests(test_request.suite())
suite.addTests(test_setlinkrev.suite())
suite.addTests(test_prdiff.suite())
suite.addTests(test_conf.suite())

if have_xmlrunner:
    result = xmlrunner.XMLTestRunner(output=os.path.join(os.getcwd(), 'junit-xml-results')).run(suite)
else:
    result = unittest.TextTestRunner(verbosity=1).run(suite)
sys.exit(not result.wasSuccessful())
