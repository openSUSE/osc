import unittest

from osc.gitea_api import GitDiffGenerator


class GitDiffGeneratorTest(unittest.TestCase):

    def test_add_file(self):
        base = GitDiffGenerator()
        head = GitDiffGenerator()

        head.set_file("new-file", "text")

        expected = """
--- /dev/null
+++ b/new-file
@@ -0,0 +1 @@
+text

""".lstrip()
        actual = "\n".join(base.diff(head))
        self.assertEqual(expected, actual)

    def test_remove_file(self):
        base = GitDiffGenerator()
        head = GitDiffGenerator()

        base.set_file("removed-file", "text")

        expected = """
--- a/removed-file
+++ /dev/null
@@ -1 +0,0 @@
-text

""".lstrip()
        actual = "\n".join(base.diff(head))
        self.assertEqual(expected, actual)

    def test_modify_file(self):
        base = GitDiffGenerator()
        head = GitDiffGenerator()

        base.set_file("modify-file", "old-value")
        head.set_file("modify-file", "new-value")

        expected = """
--- a/modify-file
+++ b/modify-file
@@ -1 +1 @@
-old-value
+new-value

""".lstrip()
        actual = "\n".join(base.diff(head))
        self.assertEqual(expected, actual)

    def test_add_submodule(self):
        base = GitDiffGenerator()
        head = GitDiffGenerator()

        head.create_gitmodules_entry(
            path="package", url="../../pool/package", branch="factory"
        )
        head.set_submodule_commit("package", "aabbcc")

        expected = """
--- a/.gitmodules
+++ b/.gitmodules
@@ -0,0 +1,4 @@
+[submodule "package"]
+	path = package
+	url = ../../pool/package
+	branch = factory
--- /dev/null
+++ b/package
@@ -0,0 +1 @@
+Subproject commit aabbcc

""".lstrip()
        actual = "\n".join(base.diff(head))
        self.assertEqual(expected, actual)

    def test_remove_submodule(self):
        base = GitDiffGenerator()
        head = GitDiffGenerator()

        base.create_gitmodules_entry(
            path="package", url="../../pool/package", branch="factory"
        )
        base.set_submodule_commit("package", "aabbcc")

        expected = """
--- a/.gitmodules
+++ b/.gitmodules
@@ -1,4 +0,0 @@
-[submodule "package"]
-	path = package
-	url = ../../pool/package
-	branch = factory
--- a/package
+++ /dev/null
@@ -1 +0,0 @@
-Subproject commit aabbcc

""".lstrip()
        actual = "\n".join(base.diff(head))
        self.assertEqual(expected, actual)

    def test_modify_submodule(self):
        gitmodules_str = """
[submodule "package"]
	path = package
	url = ../../pool/package
	branch = factory
"""

        base = GitDiffGenerator(gitmodules_str)
        head = GitDiffGenerator(gitmodules_str)

        base.set_submodule_commit("package", "aabbcc")
        head.set_submodule_commit("package", "dddeeff")

        expected = """
--- a/package
+++ b/package
@@ -1 +1 @@
-Subproject commit aabbcc
+Subproject commit dddeeff

""".lstrip()
        actual = "\n".join(base.diff(head))
        self.assertEqual(expected, actual)
