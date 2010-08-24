import unittest
import test_update
import test_addfiles
import test_deletefiles

suite = unittest.TestSuite()
suite.addTests(test_addfiles.suite())
suite.addTests(test_deletefiles.suite())
suite.addTests(test_update.suite())
unittest.TextTestRunner(verbosity=1).run(suite)
