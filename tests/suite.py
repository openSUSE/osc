import unittest
import test_update
import test_addfiles
import test_deletefiles
import test_revertfiles
import test_difffiles

suite = unittest.TestSuite()
suite.addTests(test_addfiles.suite())
suite.addTests(test_deletefiles.suite())
suite.addTests(test_revertfiles.suite())
suite.addTests(test_update.suite())
suite.addTests(test_difffiles.suite())
unittest.TextTestRunner(verbosity=1).run(suite)
