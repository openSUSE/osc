from . import xml


class XPathQuery:
    """
    A query object that translates keyword arguments into a xpath query.
    The query objects can combined using `&` and `|` operators.

    Inspired with:
    https://docs.djangoproject.com/en/dev/topics/db/queries/#complex-lookups-with-q-objects
    """

    VALID_OPS = [
        "eq",
        "gt",
        "gteq",
        "lt",
        "lteq",
        "contains",
        "ends_with",
        "starts_with",
    ]

    def __init__(self, **kwargs):
        self.xpath = ""
        self.last_op = None

        for key, value in kwargs.items():
            if value is None:
                continue
            key, op, value, op_not = self._parse(key, value)
            self._apply(key, op, value, op_not)

    def __str__(self):
        return self.xpath

    def _parse(self, key, value):
        op = "eq"
        op_not = False

        parts = key.split("__")
        for valid_op in self.VALID_OPS:
            # there must always be a field name followed by 0+ operators
            # in this case there's only the name
            if len(parts) == 1:
                continue

            if parts[-2:] == ["not", valid_op]:
                op = parts[-1]
                op_not = True
                parts = parts[:-2]
                break
            elif parts[-1] == valid_op:
                op = parts[-1]
                parts = parts[:-1]
                break
            elif parts[-1] == "not":
                op_not = True
                parts = parts[:-1]
                break

        key = "__".join(parts)
        return key, op, value, op_not

    def _apply(self, key, op, value, op_not=False):
        if "__" in key:
            prefix, key = key.rsplit("__", 1)
            prefix = prefix.replace("__", "/")
        else:
            prefix = ""

        if isinstance(value, (list, tuple)):
            q = XPathQuery()
            for i in value:
                if op_not:
                    # translate name__not=["foo", "bar"] into XPathQuery(name__not="foo") & XPathQuery(name__not="bar")
                    q &= XPathQuery()._apply(key, op, i, op_not)
                else:
                    # translate name=["foo", "bar"] into XPathQuery(name="foo") | XPathQuery(name="bar")
                    q |= XPathQuery()._apply(key, op, i, op_not)

            if prefix:
                q.xpath = f"{prefix}[{q.xpath}]"

            self &= q
            return self

        if isinstance(value, bool):
            value = str(int(value))

        prefix = xml.xml_escape(prefix)
        key = xml.xml_escape(key)
        key = f"@{key}"
        value = xml.xml_escape(value)
        value = f"'{value}'"

        q = XPathQuery()
        if op == "eq":
            q.xpath = f"{key}={value}"
        elif op == "contains":
            q.xpath = f"contains({key}, {value})"
        else:
            raise ValueError(f"Invalid operator: {op}")

        if op_not:
            q.xpath = f"not({q.xpath})"

        if prefix:
            q.xpath = f"{prefix}[{q.xpath}]"

        self &= q
        return self

    @staticmethod
    def _imerge(q1, op, q2):
        """
        Merge `q2` into `q1`.
        """
        if not q1.xpath and not q2.xpath:
            return

        if not q1.xpath:
            q1.xpath = q2.xpath
            q1.last_op = q2.last_op
            return

        if not q2.xpath:
            return

        assert op is not None

        if q1.last_op not in (None, op):
            q1.xpath = f"({q1.xpath})"

        q1.xpath += f" {op} "

        if q2.last_op in (None, op):
            q1.xpath += f"{q2.xpath}"
        else:
            q1.xpath += f"({q2.xpath})"

        q1.last_op = op

    def __and__(self, other):
        result = XPathQuery()
        self._imerge(result, None, self)
        self._imerge(result, "and", other)
        return result

    def __iand__(self, other):
        self._imerge(self, "and", other)
        return self

    def __or__(self, other):
        result = XPathQuery()
        self._imerge(result, None, self)
        self._imerge(result, "or", other)
        return result

    def __ior__(self, other):
        self._imerge(self, "or", other)
        return self
