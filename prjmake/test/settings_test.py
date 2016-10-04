# Copyright (c) 2016 Ericsson AB
# This program is free software; it may be used, copied, modified
# and distributed under the terms of the GNU General Public Licence,
# either version 2, or version 3 (at your option).
#

import unittest
from oscpluginprjmake import settings

def suite():
    return unittest.makeSuite(TestSettings)

class TestSettings(unittest.TestCase):

    sts = None

    def setUp(self):
        self.sts = settings.Settings()

    def test_set_normal(self):
        self.sts.set('key', 'value')
        self.assertEqual(self.sts.get('key'), 'value')

    def test_set_list(self):
        for key in self.sts._lists:
            value = [key, 'foobar']
            self.sts.set(key, value)
            self.assertEqual(self.sts.get(key), value)
            self.assertFalse(self.sts.get(key) is value)

    def test_get_invalid(self):
        try:
            self.sts.get('invalid')
            self.assertTrue(False)
        except StandardError as e:
            self.assertEqual(e.args, ('invalid not set',))

    def test_reference_mixup(self):
        list_a = ['a', 'b', 'c']
        list_b = ['d', 'e', 'f']
        self.sts.set('pkgs_changed', list_a)
        self.sts.set('packages', list_b)
        pkgs_changed = self.sts.get('pkgs_changed')
        packages_old = self.sts.get('packages')
        self.sts.set('packages', pkgs_changed)
        self.sts.set('packages', packages_old)
        self.assertEqual(list_a, self.sts.get('pkgs_changed'))
        self.assertEqual(list_b, self.sts.get('packages'))
        list_a[0] = 'foobar'
        self.assertTrue(list_a != self.sts.get('pkgs_changed'))

if __name__ == '__main__':
    unittest.main()

# vim: et ts=4 sw=4
