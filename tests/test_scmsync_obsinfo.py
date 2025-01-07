import unittest

from osc.obs_api.scmsync_obsinfo import ScmsyncObsinfo


class TestScmsyncObsinfo(unittest.TestCase):
    def test_empty(self):
        self.assertRaises(TypeError, ScmsyncObsinfo.from_string, "")

    def test_mandatory(self):
        data = """
        mtime: 123
        commit: abcdef
        """
        info = ScmsyncObsinfo.from_string(data)
        self.assertEqual(info.mtime, 123)
        self.assertEqual(info.commit, "abcdef")
        self.assertEqual(info.url, None)

    def test_all(self):
        data = """
        mtime: 123
        commit: abcdef
        url: https://example.com
        revision: 1
        subdir: dirname
        projectscmsync: project
        """
        info = ScmsyncObsinfo.from_string(data)
        self.assertEqual(info.mtime, 123)
        self.assertEqual(info.commit, "abcdef")
        self.assertEqual(info.url, "https://example.com")
        self.assertEqual(info.revision, "1")
        self.assertEqual(info.subdir, "dirname")
        self.assertEqual(info.projectscmsync, "project")


if __name__ == "__main__":
    unittest.main()
