import unittest
from osc.util.gitattributes import GitAttributes


class TestGitAttributes(unittest.TestCase):
    def test_simple_parsing(self):
        content = """\
# Binary files
*.png binary
*.jpg filter=lfs diff=lfs merge=lfs -text
"""
        gitattributes = GitAttributes.from_string(content)
        rules = gitattributes.rules
        # One rule per line
        self.assertEqual(len(rules), 2)
        self.assertEqual(rules[0].pattern, "*.png")
        self.assertEqual(rules[0].attributes, "binary")
        self.assertEqual(rules[0].leading_lines, ["# Binary files"])
        self.assertEqual(rules[1].pattern, "*.jpg")
        self.assertEqual(rules[1].attributes, "filter=lfs diff=lfs merge=lfs -text")
        self.assertEqual(rules[1].leading_lines, [])

    def test_empty_line_preservation(self):
        content = """\
# Header
rule1 attr1


# Footer
rule2 attr2"""
        gitattributes = GitAttributes.from_string(content)
        rules = gitattributes.rules
        self.assertEqual(len(rules), 2)
        r1 = rules[0]
        r2 = rules[1]

        self.assertEqual(r1.pattern, "rule1")
        self.assertEqual(r1.attributes, "attr1")
        self.assertEqual(r1.leading_lines, ["# Header"])

        self.assertEqual(r2.pattern, "rule2")
        self.assertEqual(r2.attributes, "attr2")
        # It should have the leading empty lines and comment captured
        self.assertEqual(r2.leading_lines, ["", "", "# Footer"])

        expected = """\


# Footer
rule2 attr2"""
        self.assertEqual(str(r2), expected)

    def test_merging_blocks(self):
        base_text = """\
# Section 1
rule1 attr1

# Section 2
rule2 attr2"""
        overlay_text = """\
# Section 1
rule3 attr3

# New Section
rule4 attr4"""

        base = GitAttributes.from_string(base_text)
        overlay = GitAttributes.from_string(overlay_text)

        base.merge(overlay)
        merged = str(base)

        expected = """\
# Section 1
rule1 attr1

# Section 2
rule2 attr2
# Section 1
rule3 attr3

# New Section
rule4 attr4"""
        self.assertEqual(merged, expected)

    def test_escaped_characters(self):
        # Escaped # should be treated as a rule, not a comment
        content = """\
\\#not_a_comment.txt attr
# Real comment
rule attr2"""
        gitattributes = GitAttributes.from_string(content)
        rules = gitattributes.rules
        self.assertEqual(len(rules), 2)
        self.assertEqual(rules[0].pattern, r"\#not_a_comment.txt")
        self.assertEqual(rules[1].pattern, "rule")
        self.assertEqual(rules[1].leading_lines, ["# Real comment"])

    def test_globs_and_attributes(self):
        content = """\
*.log text eol=lf
docs/**/*.pdf -text
"""
        gitattributes = GitAttributes.from_string(content)
        rules = gitattributes.rules
        # Each rule is a separate instance
        self.assertEqual(len(rules), 2)
        self.assertEqual(rules[0].pattern, "*.log")
        self.assertEqual(rules[0].attributes, "text eol=lf")
        self.assertEqual(rules[1].pattern, "docs/**/*.pdf")
        self.assertEqual(rules[1].attributes, "-text")

    def test_attribute_update(self):
        base_text = """\
# Old comment
rule1 old_attr"""
        overlay_text = """\
# New comment
rule1 new_attr"""

        base = GitAttributes.from_string(base_text)
        overlay = GitAttributes.from_string(overlay_text)

        base.merge(overlay)
        merged = str(base)

        expected = """\
# New comment
rule1 new_attr"""
        self.assertEqual(merged, expected)

    def test_no_attributes(self):
        content = "pattern_only"
        gitattributes = GitAttributes.from_string(content)
        rules = gitattributes.rules
        self.assertEqual(len(rules), 1)
        self.assertEqual(rules[0].pattern, "pattern_only")
        self.assertEqual(rules[0].attributes, "")


if __name__ == "__main__":
    unittest.main()
