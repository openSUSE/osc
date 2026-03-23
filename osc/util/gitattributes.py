import copy
from typing import List, Optional


class GitAttributesRule:
    """
    A representation of .gitattributes rule with leading blank lines and comments
    """

    def __init__(
        self,
        pattern: Optional[str],
        attributes: Optional[str] = None,
        leading_lines: Optional[List[str]] = None,
    ):
        self.pattern = pattern
        self.attributes = attributes
        self.leading_lines = leading_lines or []

    def get_key(self):
        """
        Return a key identifying the rule.
        """
        if not self.pattern:
            return None
        return self.pattern.strip()

    def __str__(self):
        lines = []
        lines.extend(self.leading_lines)
        if self.pattern is not None:
            if self.attributes:
                lines.append(f"{self.pattern} {self.attributes}")
            else:
                lines.append(self.pattern)
        return "\n".join(lines)


class GitAttributes:
    def __init__(self, rules: List[GitAttributesRule]):
        self.rules = rules

    @classmethod
    def from_file(cls, path: str, *, missing_ok: bool = False) -> "GitAttributes":
        try:
            with open(path, "r", encoding="utf-8") as f:
                text = f.read()
        except FileNotFoundError:
            if not missing_ok:
                raise
            text = ""
        return cls.from_string(text)

    @classmethod
    def from_string(cls, text: str) -> "GitAttributes":
        rules = []

        if not text:
            return cls(rules)

        leading_lines = []
        for line in text.splitlines():
            stripped = line.strip()

            # empty lines and comments are collected as leading lines
            is_comment = stripped.startswith("#") and not line.startswith(r"\#")

            if not stripped or is_comment:
                leading_lines.append(line)
                continue

            # the current line contains a rule; split it and reset leading_lines
            parts = line.split(None, 1)
            pattern = parts[0]
            attributes = parts[1] if len(parts) > 1 else ""

            rule = GitAttributesRule(pattern, attributes, leading_lines)
            rules.append(rule)
            leading_lines = []

        # handle orphaned trailing empty lines and comments that are not associated to any rule
        if leading_lines:
            rule = GitAttributesRule(None, None, leading_lines)
            rules.append(rule)

        return cls(rules)

    def merge(self, other: "GitAttributes"):
        """
        Merge the ``other`` GitAttributes object into ``self``.
        Matching entries will have their comments and attributes updated.
        New entries will be appended.
        """
        # mapping to keep track of existing rule patterns in ``self`` for deduplication and updating
        self_rules_by_key = {i.get_key(): i for i in self.rules if i.get_key() is not None}

        for other_rule in other.rules:
            key = other_rule.get_key()
            if key is None:
                # ignore orphaned trailing comments from ``other``
                continue

            if key in self_rules_by_key:
                # update comments and attributes in the matching rule
                self_rules_by_key[key].leading_lines = other_rule.leading_lines[:]
                self_rules_by_key[key].attributes = other_rule.attributes
            else:
                new_rule = copy.deepcopy(other_rule)
                if self.rules and self.rules[-1].pattern is None:
                    # append before the orphaned empty lines and comments if they exist
                    self.rules.insert(-1, new_rule)
                else:
                    self.rules.append(new_rule)

                # add the new rule to the map to handle incoming duplicates properly
                self_rules_by_key[key] = new_rule

    def __str__(self):
        return "\n".join(str(i) for i in self.rules)

    def to_file(self, path: str):
        text = str(self)
        with open(path, "w", encoding="utf-8") as f:
            f.write(text)
