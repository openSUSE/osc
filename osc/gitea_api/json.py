import json


class GitObsJSONEncoder(json.JSONEncoder):
    def default(self, obj):
        from .common import GiteaModel

        if isinstance(obj, GiteaModel):
            return obj.dict()
        return super().default(obj)


def json_dumps(obj, **kwargs):
    kwargs["cls"] = GitObsJSONEncoder
    return json.dumps(obj, **kwargs)
