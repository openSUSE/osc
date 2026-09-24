import io
import unittest
from unittest.mock import patch

from osc.obs_api.token import Token


def _response(xml):
    return io.BytesIO(xml.encode("utf-8"))


CREATE_RESPONSE = (
    '<status code="ok">'
    "<summary>Ok</summary>"
    '<data name="token">obs_pat_testsecret</data>'
    '<data name="id">42</data>'
    "</status>"
)

OK_RESPONSE = '<status code="ok"><summary>Ok</summary></status>'


class TestApiTokenModel(unittest.TestCase):
    def test_parse_apitoken_entry(self):
        xml = (
            '<entry id="42" string="deadbeef" kind="apitoken" '
            'description="ci" enabled="true" />'
        )
        token = Token.from_string(xml)
        self.assertEqual(token.kind, Token.Kind.APITOKEN)
        self.assertEqual(token.id, 42)

    def test_human_readable_does_not_expose_hash_as_secret(self):
        xml = (
            '<entry id="42" string="deadbeef" kind="apitoken" '
            'description="ci" enabled="true" />'
        )
        token = Token.from_string(xml)
        text = token.to_human_readable_string()
        self.assertNotIn("deadbeef", text)
        self.assertIn("not retrievable", text)

    def test_cmd_create_api_token(self):
        with patch.object(
            Token, "xml_request", return_value=_response(CREATE_RESPONSE)
        ) as mock_request:
            token_id, secret = Token.cmd_create_api_token(
                "https://api.example.com", "user", description="ci"
            )
        self.assertEqual(token_id, "42")
        self.assertEqual(secret, "obs_pat_testsecret")
        # only the plaintext secret may leave this function; it is not logged
        args, kwargs = mock_request.call_args
        self.assertEqual(args[0], "POST")
        self.assertEqual(args[2], ["person", "user", "token"])
        self.assertEqual(args[3]["operation"], "apitoken")
        self.assertEqual(args[3]["description"], "ci")
        # no expiry -> no extra update request
        self.assertEqual(mock_request.call_count, 1)

    def test_cmd_create_api_token_with_expiry(self):
        with patch.object(
            Token,
            "xml_request",
            side_effect=[_response(CREATE_RESPONSE), _response(OK_RESPONSE)],
        ) as mock_request:
            token_id, secret = Token.cmd_create_api_token(
                "https://api.example.com",
                "user",
                expires_at="2027-01-01T00:00:00Z",
            )
        self.assertEqual(token_id, "42")
        self.assertEqual(secret, "obs_pat_testsecret")
        self.assertEqual(mock_request.call_count, 2)
        args, kwargs = mock_request.call_args
        self.assertEqual(args[0], "PUT")
        self.assertEqual(args[2], ["person", "user", "token", "42"])
        self.assertIn('expires_at="2027-01-01T00:00:00Z"', kwargs["data"])

    def test_cmd_create_api_token_missing_secret(self):
        with patch.object(Token, "xml_request", return_value=_response(OK_RESPONSE)):
            self.assertRaises(
                ValueError,
                Token.cmd_create_api_token,
                "https://api.example.com",
                "user",
            )

    def test_do_set_attributes_escapes_xml(self):
        with patch.object(
            Token, "xml_request", return_value=_response(OK_RESPONSE)
        ) as mock_request:
            Token.do_set_attributes(
                "https://api.example.com",
                "user",
                "42",
                description='a "quoted" description',
                enabled=False,
            )
        args, kwargs = mock_request.call_args
        self.assertEqual(args[0], "PUT")
        # quoteattr picks single quotes when the value contains double quotes
        self.assertIn("description='a \"quoted\" description'", kwargs["data"])
        self.assertIn('enabled="false"', kwargs["data"])


if __name__ == "__main__":
    unittest.main()
