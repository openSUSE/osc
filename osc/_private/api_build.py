import csv
import io
import time

from . import api


class BuildHistory:
    def __init__(
        self,
        apiurl: str,
        project: str,
        package: str,
        repository: str,
        arch: str,
        limit: int = 0,
    ):
        self.apiurl = apiurl
        self.project = project
        self.package = package
        self.repository = repository
        self.arch = arch
        self._limit = int(limit)
        self.entries = self._get_entries()

    def _get_entries(self):
        url_path = [
            "build",
            self.project,
            self.repository,
            self.arch,
            self.package,
            "_history",
        ]
        url_query = {}
        if self._limit and self._limit > 0:
            url_query["limit"] = self._limit

        root = api.get(self.apiurl, url_path, url_query)

        result = []
        nodes = api.find_nodes(root, "buildhistory", "entry")
        for node in nodes:
            item = {
                "rev": node.get("rev"),
                "srcmd5": node.get("srcmd5"),
                "ver_rel": node.get("versrel"),
                "build_count": int(node.get("bcnt")),
                "time": time.strftime("%Y-%m-%d %H:%M:%S", time.gmtime(int(node.get("time")))),
            }

            # duration may not always be available
            duration = node.get("duration")
            if duration:
                item["duration"] = int(duration)

            result.append(item)
        return result

    def to_csv(self):
        out = io.StringIO()
        header = ["time", "srcmd5", "rev", "ver_rel", "build_count", "duration"]
        writer = csv.DictWriter(out, fieldnames=header, quoting=csv.QUOTE_ALL)
        writer.writeheader()
        for i in self.entries:
            writer.writerow(i)
        return out.getvalue()

    def to_text_table(self):
        from ..core import build_table

        header = ("TIME", "SRCMD5", "VER-REL.BUILD#", "REV", "DURATION")
        data = []
        for i in self.entries:
            item = (
                i["time"],
                i["srcmd5"],
                f"{i['ver_rel']}.{i['build_count']}",
                i["rev"],
                i.get("duration", ""),
            )
            data.extend(item)

        return "\n".join(build_table(len(header), data, header))
