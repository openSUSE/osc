from ..util.models import *  # pylint: disable=wildcard-import,unused-wildcard-import


class KeyinfoSslcert(XmlModel):
    XML_TAG = "sslcert"

    keyid: Optional[str] = Field(
        xml_attribute=True,
    )

    serial: Optional[str] = Field(
        xml_attribute=True,
    )

    issuer: Optional[str] = Field(
        xml_attribute=True,
    )

    subject: Optional[str] = Field(
        xml_attribute=True,
    )

    algo: Optional[str] = Field(
        xml_attribute=True,
    )

    keysize: Optional[str] = Field(
        xml_attribute=True,
    )

    begins: Optional[int] = Field(
        xml_attribute=True,
    )

    expires: Optional[int] = Field(
        xml_attribute=True,
    )

    fingerprint: Optional[str] = Field(
        xml_attribute=True,
    )

    value: str = Field(
        xml_set_text=True,
    )

    def get_begins_str(self) -> str:
        import datetime

        if self.begins is None:
            return ""

        return datetime.datetime.fromtimestamp(self.begins).strftime("%Y-%m-%d %H:%M:%S")

    def get_expires_str(self) -> str:
        import datetime

        if self.expires is None:
            return ""

        return datetime.datetime.fromtimestamp(self.expires).strftime("%Y-%m-%d %H:%M:%S")

    def to_human_readable_string(self) -> str:
        """
        Render the object as a human readable string.
        """
        from ..output import KeyValueTable
        table = KeyValueTable()
        table.add("Type", "SSL certificate")
        table.add("Subject", self.subject, color="bold")
        table.add("Key ID", self.keyid)
        table.add("Serial", self.serial)
        table.add("Issuer", self.issuer)
        table.add("Algorithm", self.algo)
        table.add("Key size", self.keysize)
        table.add("Begins", self.get_begins_str())
        table.add("Expires", self.get_expires_str())
        table.add("Fingerprint", self.fingerprint)
        return f"{table}\n{self.value}"
