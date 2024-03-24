from ..util.models import *  # pylint: disable=wildcard-import,unused-wildcard-import


class KeyinfoPubkey(XmlModel):
    XML_TAG = "pubkey"

    keyid: str = Field(
        xml_attribute=True,
    )

    userid: str = Field(
        xml_attribute=True,
    )

    algo: str = Field(
        xml_attribute=True,
    )

    keysize: str = Field(
        xml_attribute=True,
    )

    expires: int = Field(
        xml_attribute=True,
    )

    fingerprint: str = Field(
        xml_attribute=True,
    )

    value: str = Field(
        xml_set_text=True,
    )

    def get_expires_str(self) -> str:
        import datetime
        return datetime.datetime.fromtimestamp(self.expires).strftime("%Y-%m-%d %H:%M:%S")

    def to_human_readable_string(self) -> str:
        """
        Render the object as a human readable string.
        """
        from ..output import KeyValueTable
        table = KeyValueTable()
        table.add("Type", "GPG public key")
        table.add("User ID", self.userid, color="bold")
        table.add("Algorithm", self.algo)
        table.add("Key size", self.keysize)
        table.add("Expires", self.get_expires_str())
        table.add("Fingerprint", self.fingerprint)
        return f"{table}\n{self.value}"
