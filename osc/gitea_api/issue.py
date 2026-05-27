from .common import GiteaModel


class Issue(GiteaModel):
    @property
    def number(self) -> int:
        return self._data["number"]

    @property
    def html_url(self) -> str:
        return self._data["html_url"]

    @classmethod
    def create(cls, conn, owner, repo, title, body, ref=None):
        url = conn.makeurl("repos", owner, repo, "issues")
        data = {
            "title": title,
            "body": body,
        }
        if ref:
            data["ref"] = ref
        response = conn.request("POST", url, json_data=data)
        return cls(response.json(), response=response)

    def add_labels(self, conn, owner, repo, labels):
        url = conn.makeurl("repos", owner, repo, "issues", str(self.number), "labels")
        conn.request("POST", url, json={"labels": labels})
