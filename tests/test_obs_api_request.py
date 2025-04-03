import os
import unittest

from osc import obs_api

from .common import GET
from .common import OscTestCase


FIXTURES_DIR = os.path.join(os.path.dirname(__file__), "fixtures", "packages")


class TestRequest(OscTestCase):
    def _get_fixtures_dir(self):
        return FIXTURES_DIR

    @GET("http://localhost/search/request?match=state[@name='new'+or+@name='review'+or+@name='declined']", text="<collection/>")
    def test_search_default(self):
        obs_api.Request.search("http://localhost")

    @GET("http://localhost/search/request?match=@id='1'+or+@id='2'", text="<collection/>")
    def test_search_request_ids(self):
        obs_api.Request.search("http://localhost", states=[], request_ids=["1", "2"])

    @GET("http://localhost/search/request?match=source[@project='foo'+or+@project='bar']+or+target[@project='foo'+or+@project='bar']", text="<collection/>")
    def test_search_projects(self):
        obs_api.Request.search("http://localhost", states=[], projects=["foo", "bar"])

    @GET("http://localhost/search/request?match=source[@package='foo'+or+@package='bar']+or+target[@package='foo'+or+@package='bar']", text="<collection/>")
    def test_search_packages(self):
        obs_api.Request.search("http://localhost", states=[], packages=["foo", "bar"])

    @GET("http://localhost/search/request?match=source[@project='foo'+or+@project='bar']", text="<collection/>")
    def test_search_source_projects(self):
        obs_api.Request.search("http://localhost", states=[], source_projects=["foo", "bar"])

    @GET("http://localhost/search/request?match=source[@packages='foo'+or+@packages='bar']", text="<collection/>")
    def test_search_source_packages(self):
        obs_api.Request.search("http://localhost", states=[], source_packages=["foo", "bar"])

    @GET("http://localhost/search/request?match=target[@project='foo'+or+@project='bar']", text="<collection/>")
    def test_search_target_projects(self):
        obs_api.Request.search("http://localhost", states=[], target_projects=["foo", "bar"])

    @GET("http://localhost/search/request?match=target[@packages='foo'+or+@packages='bar']", text="<collection/>")
    def test_search_target_packages(self):
        obs_api.Request.search("http://localhost", states=[], target_packages=["foo", "bar"])

    @GET("http://localhost/search/request?match=@creator='foo'+or+@creator='bar'", text="<collection/>")
    def test_search_creators(self):
        obs_api.Request.search("http://localhost", states=[], creators=["foo", "bar"])

    @GET("http://localhost/search/request?match=state[@who='foo'+or+@who='bar']+or+history[@who='foo'+or+@who='bar']", text="<collection/>")
    def test_search_who(self):
        obs_api.Request.search("http://localhost", states=[], who=["foo", "bar"])

    @GET("http://localhost/search/request?match=state[@name='new'+or+@name='review']", text="<collection/>")
    def test_search_states(self):
        obs_api.Request.search("http://localhost", states=["new", "review"])

    @GET("http://localhost/search/request?match=action[@type='submit'+or+@type='delete']", text="<collection/>")
    def test_search_types(self):
        obs_api.Request.search("http://localhost", states=[], types=["submit", "delete"])

    @GET("http://localhost/search/request?match=target[not(@project='foo')]+and+target[not(@project='bar')]", text="<collection/>")
    def test_search_exclude_target_projects(self):
        obs_api.Request.search("http://localhost", states=[], exclude_target_projects=["foo", "bar"])

    @GET("http://localhost/search/request?match=&withhistory=1", text="<collection/>")
    def test_search_with_history(self):
        obs_api.Request.search("http://localhost", states=[], with_history=True)

    @GET("http://localhost/search/request?match=&withfullhistory=1", text="<collection/>")
    def test_search_with_full_history(self):
        obs_api.Request.search("http://localhost", states=[], with_full_history=True)


if __name__ == "__main__":
    unittest.main()
