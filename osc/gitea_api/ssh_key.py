from typing import Optional

from .connection import Connection
from .connection import GiteaHTTPResponse


class SSHKey:
    @classmethod
    def get(cls, conn: Connection, id: int) -> GiteaHTTPResponse:
        """
        Get an authenticated user's public key by its ``id``.

        :param conn: Gitea ``Connection`` instance.
        :param id: key numeric id
        """
        url = conn.makeurl("user", "keys", str(id))
        return conn.request("GET", url)

    @classmethod
    def list(cls, conn: Connection) -> GiteaHTTPResponse:
        """
        List the authenticated user's public keys.

        :param conn: Gitea ``Connection`` instance.
        """
        q = {
            "limit": -1,
        }
        url = conn.makeurl("user", "keys", query=q)
        return conn.request("GET", url)

    @classmethod
    def _split_key(cls, key):
        import re
        return re.split(" +", key, maxsplit=2)

    @classmethod
    def _validate_key_format(cls, key):
        """
        Check that the public ssh key has the correct format:
            - must be a single line of text
            - it is possible to split it into <type> <key> <comment> parts
            - the <key> part is base64 encoded
        """
        import base64
        import binascii
        from .exceptions import InvalidSshPublicKey

        key = key.strip()
        if len(key.splitlines()) != 1:
            raise InvalidSshPublicKey()

        try:
            key_type, key_base64, key_comment = cls._split_key(key)
        except ValueError:
            raise InvalidSshPublicKey()

        try:
            base64.b64decode(key_base64)
        except binascii.Error:
            raise InvalidSshPublicKey()

    @classmethod
    def create(cls, conn: Connection, key: str, title: Optional[str] = None) -> GiteaHTTPResponse:
        """
        Create a public key.

        :param conn: Gitea ``Connection`` instance.
        :param key: An armored SSH key to add.
        :param title: Title of the key to add. Derived from the key if not specified.
        """
        url = conn.makeurl("user", "keys")

        cls._validate_key_format(key)

        if not title:
            title = cls._split_key(key)[2]

        data = {
            "key": key,
            "title": title,
        }
        return conn.request("POST", url, json_data=data)

    @classmethod
    def delete(cls, conn: Connection, id: int):
        """
        Delete a public key

        :param conn: Gitea ``Connection`` instance.
        :param id: Id of key to delete.
        """

        url = conn.makeurl("user", "keys", str(id))
        return conn.request("DELETE", url)

    @classmethod
    def to_human_readable_string(cls, data):
        from osc.output import KeyValueTable
        table = KeyValueTable()
        table.add("ID", f"{data['id']}", color="bold")
        table.add("Title", f"{data['title']}")
        table.add("Key", f"{data['key']}")
        return str(table)
