import unittest

from osc.core import Request


class TestRequest(unittest.TestCase):
    def test_eq(self):
        req1 = Request()
        req1.reqid = 1
        req2 = Request()
        req2.reqid = 1
        self.assertEqual(req1, req2)

    def test_lt(self):
        req1 = Request()
        req1.reqid = 1
        req2 = Request()
        req2.reqid = 2
        self.assertTrue(req1 < req2)

    def test_gt(self):
        req1 = Request()
        req1.reqid = 2
        req2 = Request()
        req2.reqid = 1
        self.assertTrue(req1 > req2)

    def test_sort(self):
        req1 = Request()
        req1.reqid = 2
        req2 = Request()
        req2.reqid = 1
        requests = [req1, req2]
        requests.sort()
        self.assertEqual(requests[0].reqid, 1)
        self.assertEqual(requests[1].reqid, 2)


if __name__ == "__main__":
    unittest.main()
