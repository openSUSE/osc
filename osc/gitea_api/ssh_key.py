from typing import List
from typing import Optional

from .connection import Connection
from .connection import GiteaHTTPResponse


class SSHKey:
    def __init__(self, data: dict, *, response: Optional[GiteaHTTPResponse] = None):
        self._data = data
        self._response = response

    @property
    def id(self) -> int:
        return self._data["id"]

    @property
    def key(self) -> str:
        return self._data["key"]

    @property
    def title(self) -> str:
        return self._data["title"]

    @classmethod
    def get(cls, conn: Connection, id: int) -> "SSHKey":
        """
        Get an authenticated user's public key by its ``id``.

        :param conn: Gitea ``Connection`` instance.
        :param id: key numeric id
        """
        url = conn.makeurl("user", "keys", str(id))
        response = conn.request("GET", url)
        obj = cls(response.json(), response=response)
        return obj

    @classmethod
    def list(cls, conn: Connection) -> List["SSHKey"]:
        """
        List the authenticated user's public keys.

        :param conn: Gitea ``Connection`` instance.
        """
        q = {
            "limit": -1,
        }
        url = conn.makeurl("user", "keys", query=q)
        response = conn.request("GET", url)
        obj_list = [cls(i, response=response) for i in response.json()]
        return obj_list

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
    def create(cls, conn: Connection, key: str, title: Optional[str] = None) -> "SSHKey":
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
        response = conn.request("POST", url, json_data=data)
        obj = cls(response.json(), response=response)
        return obj

    @classmethod
    def delete(cls, conn: Connection, id: int) -> GiteaHTTPResponse:
        """
        Delete a public key

        :param conn: Gitea ``Connection`` instance.
        :param id: Id of key to delete.
        """

        url = conn.makeurl("user", "keys", str(id))
        return conn.request("DELETE", url)

    def to_human_readable_string(self) -> str:
        from osc.output import KeyValueTable

        table = KeyValueTable()
        table.add("ID", f"{self.id}", color="bold")
        table.add("Title", f"{self.title}")
        table.add("Key", f"{self.key}")
        return str(table)
