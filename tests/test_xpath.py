import unittest

from osc.util.xpath import XPathQuery as Q


class TestQuery(unittest.TestCase):
    def test_noop(self):
        q = Q(name="foo")
        self.assertEqual(str(q), "@name='foo'")

    def test_not(self):
        q = Q(name__not="foo")
        self.assertEqual(str(q), "not(@name='foo')")

    def test_eq(self):
        q = Q(name__eq="foo")
        self.assertEqual(str(q), "@name='foo'")

    def test_not_eq(self):
        q = Q(name__not__eq="foo")
        self.assertEqual(str(q), "not(@name='foo')")

    def test_contains(self):
        q = Q(name__contains="foo")
        self.assertEqual(str(q), "contains(@name, 'foo')")

    def test_and(self):
        q1 = Q(name="foo")
        q2 = Q(name="bar")
        q = q1 & q2
        self.assertEqual(str(q), "@name='foo' and @name='bar'")

        q3 = Q(name="baz")
        q = q & q3
        self.assertEqual(str(q), "@name='foo' and @name='bar' and @name='baz'")

    def test_or(self):
        q1 = Q(name="foo")
        q2 = Q(name="bar")
        q = q1 | q2
        self.assertEqual(str(q), "@name='foo' or @name='bar'")

        q3 = Q(name="baz")
        q = q | q3
        self.assertEqual(str(q), "@name='foo' or @name='bar' or @name='baz'")

    def test_and_or(self):
        q1 = Q(name="foo")
        q2 = Q(name="bar")
        q = q1 & q2
        self.assertEqual(str(q), "@name='foo' and @name='bar'")

        q3 = Q(name="baz")
        q = q | q3
        self.assertEqual(str(q), "(@name='foo' and @name='bar') or @name='baz'")

        q4 = Q(name="xyz")
        q = q | q4
        self.assertEqual(str(q), "(@name='foo' and @name='bar') or @name='baz' or @name='xyz'")

    def test_or_and(self):
        q1 = Q(name="foo")
        q2 = Q(name="bar")
        q = q1 | q2
        self.assertEqual(str(q), "@name='foo' or @name='bar'")

        q3 = Q(name="baz")
        q = q & q3
        self.assertEqual(str(q), "(@name='foo' or @name='bar') and @name='baz'")

        q4 = Q(name="xyz")
        q = q & q4
        self.assertEqual(str(q), "(@name='foo' or @name='bar') and @name='baz' and @name='xyz'")

    def test_and_or_and(self):
        q1 = Q(name="foo")
        q2 = Q(name="bar")
        q3 = Q(name="baz")
        q4 = Q(name="xyz")
        q = (q1 & q2) | (q3 & q4)
        self.assertEqual(str(q), "(@name='foo' and @name='bar') or (@name='baz' and @name='xyz')")

    def test_or_and_or(self):
        q1 = Q(name="foo")
        q2 = Q(name="bar")
        q3 = Q(name="baz")
        q4 = Q(name="xyz")
        q = (q1 | q2) & (q3 | q4)
        self.assertEqual(str(q), "(@name='foo' or @name='bar') and (@name='baz' or @name='xyz')")

    def test_multiple_kwargs(self):
        q = Q(name1="foo", name2="bar")
        self.assertEqual(str(q), "@name1='foo' and @name2='bar'")

    def test_eq_list(self):
        q = Q(name=["foo", "bar", "baz"])
        self.assertEqual(str(q), "@name='foo' or @name='bar' or @name='baz'")

    def test_not_eq_list(self):
        q = Q(name__not=["foo", "bar", "baz"])
        self.assertEqual(str(q), "not(@name='foo') and not(@name='bar') and not(@name='baz')")

    def test_review_state(self):
        q = Q(state__name=["new"])
        self.assertEqual(str(q), "state[@name='new']")


if __name__ == "__main__":
    unittest.main()
