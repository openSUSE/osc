import unittest
from osc.util.gitignore import GitIgnore


class TestGitIgnore(unittest.TestCase):
    def test_simple_parsing(self):
        content = """\
# Logs
*.log
debug.log
"""
        gitignore = GitIgnore.from_string(content)
        rules = gitignore.rules
        # One rule per line
        self.assertEqual(len(rules), 2)
        self.assertEqual(rules[0].rule, "*.log")
        self.assertEqual(rules[0].leading_lines, ["# Logs"])
        self.assertEqual(rules[1].rule, "debug.log")
        self.assertEqual(rules[1].leading_lines, [])

    def test_empty_line_preservation(self):
        content = """\
# Header
rule1


# Footer
rule2"""
        gitignore = GitIgnore.from_string(content)
        rules = gitignore.rules
        self.assertEqual(len(rules), 2)
        r1 = rules[0]
        r2 = rules[1]

        self.assertEqual(r1.rule, "rule1")
        self.assertEqual(r1.leading_lines, ["# Header"])

        self.assertEqual(r2.rule, "rule2")
        # It should have the leading empty lines and comment captured
        self.assertEqual(r2.leading_lines, ["", "", "# Footer"])

        expected = """\


# Footer
rule2"""
        self.assertEqual(str(r2), expected)

    def test_merging_blocks(self):
        base_text = """\
# Section 1
rule1

# Section 2
rule2"""
        overlay_text = """\
# Section 1
rule3

# New Section
rule4"""

        base = GitIgnore.from_string(base_text)
        overlay = GitIgnore.from_string(overlay_text)

        base.merge(overlay)
        merged = str(base)

        expected = """\
# Section 1
rule1

# Section 2
rule2
# Section 1
rule3

# New Section
rule4"""
        self.assertEqual(merged, expected)

    def test_escaped_characters(self):
        # Escaped # should be treated as a rule, not a comment
        content = """\
\\#not_a_comment.txt
# Real comment
rule"""
        gitignore = GitIgnore.from_string(content)
        rules = gitignore.rules
        self.assertEqual(len(rules), 2)
        self.assertEqual(rules[0].rule, r"\#not_a_comment.txt")
        self.assertEqual(rules[1].rule, "rule")
        self.assertEqual(rules[1].leading_lines, ["# Real comment"])

    def test_negation_and_globs(self):
        content = """\
*.log
!important.log
docs/**/*.pdf"""
        gitignore = GitIgnore.from_string(content)
        rules = gitignore.rules
        # Each rule is a separate instance
        self.assertEqual(len(rules), 3)
        self.assertEqual(rules[0].rule, "*.log")
        self.assertEqual(rules[1].rule, "!important.log")
        self.assertEqual(rules[2].rule, "docs/**/*.pdf")

    def test_no_comments_merging(self):
        base_text = """\
rule1
rule2"""
        overlay_text = """\
rule1
rule3"""

        base = GitIgnore.from_string(base_text)
        overlay = GitIgnore.from_string(overlay_text)

        base.merge(overlay)
        merged = str(base)

        expected = """\
rule1
rule2
rule3"""
        self.assertEqual(merged, expected)

    def test_comment_update(self):
        base_text = """\
# Old comment
rule1"""
        overlay_text = """\
# New comment
rule1"""

        base = GitIgnore.from_string(base_text)
        overlay = GitIgnore.from_string(overlay_text)

        base.merge(overlay)
        merged = str(base)

        expected = """\
# New comment
rule1"""
        self.assertEqual(merged, expected)


if __name__ == "__main__":
    unittest.main()
