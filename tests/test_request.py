import os
import unittest
from xml.etree import ElementTree as ET

import osc.core
import osc.oscerr

from .common import OscTestCase


FIXTURES_DIR = os.path.join(os.path.dirname(__file__), 'request_fixtures')


def suite():
    return unittest.defaultTestLoader.loadTestsFromTestCase(TestRequest)


class TestRequest(OscTestCase):
    def _get_fixtures_dir(self):
        return FIXTURES_DIR

    def setUp(self):
        super().setUp(copytree=False)

    def test_createsr(self):
        """create a simple submitrequest"""
        r = osc.core.Request()
        r.add_action('submit', src_project='foo', src_package='bar', src_rev='42',
                     tgt_project='foobar', tgt_package='bar')
        self.assertEqual(r.actions[0].type, 'submit')
        self.assertEqual(r.actions[0].src_project, 'foo')
        self.assertEqual(r.actions[0].src_package, 'bar')
        self.assertEqual(r.actions[0].src_rev, '42')
        self.assertEqual(r.actions[0].tgt_project, 'foobar')
        self.assertEqual(r.actions[0].tgt_package, 'bar')
        self.assertTrue(r.actions[0].opt_sourceupdate is None)
        self.assertTrue(r.actions[0].opt_updatelink is None)
        self.assertTrue(len(r.statehistory) == 0)
        self.assertTrue(len(r.reviews) == 0)
        self.assertRaises(AttributeError, getattr, r.actions[0], 'doesnotexist')
        exp = """<request>
  <action type="submit">
    <source package="bar" project="foo" rev="42" />
    <target package="bar" project="foobar" />
  </action>
</request>"""
        self.assertXMLEqual(exp, r.to_str())

    def test_createsr_with_option(self):
        """create a submitrequest with option"""
        """create a simple submitrequest"""
        r = osc.core.Request()
        r.add_action('submit', src_project='foo', src_package='bar',
                     tgt_project='foobar', tgt_package='bar', opt_sourceupdate='cleanup', opt_updatelink='1')
        self.assertEqual(r.actions[0].type, 'submit')
        self.assertEqual(r.actions[0].src_project, 'foo')
        self.assertEqual(r.actions[0].src_package, 'bar')
        self.assertEqual(r.actions[0].tgt_project, 'foobar')
        self.assertEqual(r.actions[0].tgt_package, 'bar')
        self.assertEqual(r.actions[0].opt_sourceupdate, 'cleanup')
        self.assertEqual(r.actions[0].opt_updatelink, '1')
        self.assertTrue(r.actions[0].src_rev is None)
        self.assertTrue(len(r.statehistory) == 0)
        self.assertTrue(len(r.reviews) == 0)
        self.assertRaises(AttributeError, getattr, r.actions[0], 'doesnotexist')
        exp = """<request>
  <action type="submit">
    <source package="bar" project="foo" />
    <target package="bar" project="foobar" />
    <options>
      <sourceupdate>cleanup</sourceupdate>
      <updatelink>1</updatelink>
    </options>
  </action>
</request>"""
        self.assertXMLEqual(exp, r.to_str())

    def test_createsr_missing_tgt_package(self):
        """create a submitrequest with missing target package"""
        r = osc.core.Request()
        r.add_action('submit', src_project='foo', src_package='bar',
                     tgt_project='foobar')
        self.assertEqual(r.actions[0].type, 'submit')
        self.assertEqual(r.actions[0].src_project, 'foo')
        self.assertEqual(r.actions[0].src_package, 'bar')
        self.assertEqual(r.actions[0].tgt_project, 'foobar')
        self.assertTrue(len(r.statehistory) == 0)
        self.assertTrue(len(r.reviews) == 0)
        self.assertTrue(r.actions[0].tgt_package is None)
        self.assertRaises(AttributeError, getattr, r.actions[0], 'doesnotexist')
        exp = """<request>
  <action type="submit">
    <source package="bar" project="foo" />
    <target project="foobar" />
  </action>
</request>"""
        self.assertXMLEqual(exp, r.to_str())

    def test_createsr_invalid_argument(self):
        """create a submitrequest with invalid action argument"""
        r = osc.core.Request()
        self.assertRaises(osc.oscerr.WrongArgs, r.add_action, 'submit', src_project='foo', src_invalid='bar')

    def test_create_request_invalid_type(self):
        """create a request with an invalid action type"""
        r = osc.core.Request()
        self.assertRaises(osc.oscerr.WrongArgs, r.add_action, 'invalid', foo='bar')

    def test_create_add_role_person(self):
        """create an add_role request (person element)"""
        r = osc.core.Request()
        r.add_action('add_role', tgt_project='foo', tgt_package='bar', person_name='user', person_role='reader')
        self.assertEqual(r.actions[0].type, 'add_role')
        self.assertEqual(r.actions[0].tgt_project, 'foo')
        self.assertEqual(r.actions[0].tgt_package, 'bar')
        self.assertEqual(r.actions[0].person_name, 'user')
        self.assertEqual(r.actions[0].person_role, 'reader')
        self.assertTrue(r.actions[0].group_name is None)
        self.assertTrue(r.actions[0].group_role is None)
        exp = """<request>
  <action type="add_role">
    <target package="bar" project="foo" />
    <person name="user" role="reader" />
  </action>
</request>"""
        self.assertXMLEqual(exp, r.to_str())

    def test_create_add_role_group(self):
        """create an add_role request (group element)"""
        r = osc.core.Request()
        r.add_action('add_role', tgt_project='foo', tgt_package='bar', group_name='group', group_role='reviewer')
        self.assertEqual(r.actions[0].type, 'add_role')
        self.assertEqual(r.actions[0].tgt_project, 'foo')
        self.assertEqual(r.actions[0].tgt_package, 'bar')
        self.assertEqual(r.actions[0].group_name, 'group')
        self.assertEqual(r.actions[0].group_role, 'reviewer')
        self.assertTrue(r.actions[0].person_name is None)
        self.assertTrue(r.actions[0].person_role is None)
        self.assertTrue(len(r.statehistory) == 0)
        self.assertTrue(len(r.reviews) == 0)
        exp = """<request>
  <action type="add_role">
    <target package="bar" project="foo" />
    <group name="group" role="reviewer" />
  </action>
</request>"""
        self.assertXMLEqual(exp, r.to_str())

    def test_create_add_role_person_group(self):
        """create an add_role request (person+group element)"""
        r = osc.core.Request()
        r.add_action('add_role', tgt_project='foo', tgt_package='bar', person_name='user', person_role='reader',
                     group_name='group', group_role='reviewer')
        self.assertEqual(r.actions[0].type, 'add_role')
        self.assertEqual(r.actions[0].tgt_project, 'foo')
        self.assertEqual(r.actions[0].tgt_package, 'bar')
        self.assertEqual(r.actions[0].person_name, 'user')
        self.assertEqual(r.actions[0].person_role, 'reader')
        self.assertEqual(r.actions[0].group_name, 'group')
        self.assertEqual(r.actions[0].group_role, 'reviewer')
        self.assertTrue(len(r.statehistory) == 0)
        self.assertTrue(len(r.reviews) == 0)
        exp = """<request>
  <action type="add_role">
    <target package="bar" project="foo" />
    <person name="user" role="reader" />
    <group name="group" role="reviewer" />
  </action>
</request>"""
        self.assertXMLEqual(exp, r.to_str())

    def test_create_set_bugowner_project(self):
        """create a set_bugowner request for a project"""
        r = osc.core.Request()
        r.add_action('set_bugowner', tgt_project='foobar', person_name='buguser')
        self.assertEqual(r.actions[0].type, 'set_bugowner')
        self.assertEqual(r.actions[0].tgt_project, 'foobar')
        self.assertEqual(r.actions[0].person_name, 'buguser')
        self.assertTrue(r.actions[0].tgt_package is None)
        self.assertTrue(len(r.statehistory) == 0)
        self.assertTrue(len(r.reviews) == 0)
        exp = """<request>
  <action type="set_bugowner">
    <target project="foobar" />
    <person name="buguser" />
  </action>
</request>"""
        self.assertXMLEqual(exp, r.to_str())

    def test_create_set_bugowner_package(self):
        """create a set_bugowner request for a package"""
        r = osc.core.Request()
        r.add_action('set_bugowner', tgt_project='foobar', tgt_package='baz', person_name='buguser')
        self.assertEqual(r.actions[0].type, 'set_bugowner')
        self.assertEqual(r.actions[0].tgt_project, 'foobar')
        self.assertEqual(r.actions[0].tgt_package, 'baz')
        self.assertEqual(r.actions[0].person_name, 'buguser')
        self.assertTrue(len(r.statehistory) == 0)
        self.assertTrue(len(r.reviews) == 0)
        exp = """<request>
  <action type="set_bugowner">
    <target package="baz" project="foobar" />
    <person name="buguser" />
  </action>
</request>"""
        self.assertXMLEqual(exp, r.to_str())

    def test_create_delete_project(self):
        """create a delete request for a project"""
        r = osc.core.Request()
        r.add_action('delete', tgt_project='foo')
        self.assertEqual(r.actions[0].type, 'delete')
        self.assertEqual(r.actions[0].tgt_project, 'foo')
        self.assertTrue(r.actions[0].tgt_package is None)
        self.assertTrue(len(r.statehistory) == 0)
        self.assertTrue(len(r.reviews) == 0)
        exp = """<request>
  <action type="delete">
    <target project="foo" />
  </action>
</request>"""
        self.assertXMLEqual(exp, r.to_str())

    def test_create_delete_package(self):
        """create a delete request for a package"""
        r = osc.core.Request()
        r.add_action('delete', tgt_project='foo', tgt_package='deleteme')
        self.assertEqual(r.actions[0].type, 'delete')
        self.assertEqual(r.actions[0].tgt_project, 'foo')
        self.assertEqual(r.actions[0].tgt_package, 'deleteme')
        self.assertTrue(len(r.statehistory) == 0)
        self.assertTrue(len(r.reviews) == 0)
        exp = """<request>
  <action type="delete">
    <target package="deleteme" project="foo" />
  </action>
</request>"""
        self.assertXMLEqual(exp, r.to_str())

    def test_create_change_devel(self):
        """create a change devel request"""
        r = osc.core.Request()
        r.add_action('change_devel', src_project='foo', src_package='bar', tgt_project='devprj', tgt_package='devpkg')
        self.assertEqual(r.actions[0].type, 'change_devel')
        self.assertEqual(r.actions[0].src_project, 'foo')
        self.assertEqual(r.actions[0].src_package, 'bar')
        self.assertEqual(r.actions[0].tgt_project, 'devprj')
        self.assertEqual(r.actions[0].tgt_package, 'devpkg')
        self.assertTrue(len(r.statehistory) == 0)
        self.assertTrue(len(r.reviews) == 0)
        exp = """<request>
  <action type="change_devel">
    <source package="bar" project="foo" />
    <target package="devpkg" project="devprj" />
  </action>
</request>"""
        self.assertXMLEqual(exp, r.to_str())

    def test_action_from_xml1(self):
        """create action from xml"""
        xml = """<action type="add_role">
  <target package="bar" project="foo" />
  <person name="user" role="reader" />
  <group name="group" role="reviewer" />
</action>"""
        action = osc.core.Action.from_xml(ET.fromstring(xml))
        self.assertEqual(action.type, 'add_role')
        self.assertEqual(action.tgt_project, 'foo')
        self.assertEqual(action.tgt_package, 'bar')
        self.assertEqual(action.person_name, 'user')
        self.assertEqual(action.person_role, 'reader')
        self.assertEqual(action.group_name, 'group')
        self.assertEqual(action.group_role, 'reviewer')
        self.assertXMLEqual(xml, action.to_str())

    def test_action_from_xml2(self):
        """create action from xml"""
        xml = """<action type="submit">
  <source package="bar" project="foo" />
  <target package="bar" project="foobar" />
  <options>
    <sourceupdate>cleanup</sourceupdate>
    <updatelink>1</updatelink>
  </options>
</action>"""
        action = osc.core.Action.from_xml(ET.fromstring(xml))
        self.assertEqual(action.type, 'submit')
        self.assertEqual(action.src_project, 'foo')
        self.assertEqual(action.src_package, 'bar')
        self.assertEqual(action.tgt_project, 'foobar')
        self.assertEqual(action.tgt_package, 'bar')
        self.assertEqual(action.opt_sourceupdate, 'cleanup')
        self.assertEqual(action.opt_updatelink, '1')
        self.assertTrue(action.src_rev is None)
        self.assertXMLEqual(xml, action.to_str())

    def test_action_from_xml3(self):
        """create action from xml (with acceptinfo element)"""
        xml = """<action type="submit">
  <source package="bar" project="testprj" />
  <target package="baz" project="foobar" />
  <acceptinfo rev="5" srcmd5="aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa" xsrcmd5="ffffffffffffffffffffffffffffffff" />
</action>"""
        action = osc.core.Action.from_xml(ET.fromstring(xml))
        self.assertEqual(action.type, 'submit')
        self.assertEqual(action.src_project, 'testprj')
        self.assertEqual(action.src_package, 'bar')
        self.assertEqual(action.tgt_project, 'foobar')
        self.assertEqual(action.tgt_package, 'baz')
        self.assertTrue(action.opt_sourceupdate is None)
        self.assertTrue(action.opt_updatelink is None)
        self.assertTrue(action.src_rev is None)
        self.assertEqual(action.acceptinfo_rev, '5')
        self.assertEqual(action.acceptinfo_srcmd5, 'aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa')
        self.assertEqual(action.acceptinfo_xsrcmd5, 'ffffffffffffffffffffffffffffffff')
        self.assertTrue(action.acceptinfo_osrcmd5 is None)
        self.assertTrue(action.acceptinfo_oxsrcmd5 is None)
        self.assertXMLEqual(xml, action.to_str())

    def test_action_from_xml_unknown_type(self):
        """try to create action from xml with unknown type"""
        xml = '<action type="foo"><source package="bar" project="foo" /></action>'
        self.assertRaises(osc.oscerr.WrongArgs, osc.core.Action.from_xml, ET.fromstring(xml))

    def test_read_request1(self):
        """read in a request"""
        xml = self._get_fixture('test_read_request1.xml')
        r = osc.core.Request()
        r.read(ET.fromstring(xml))
        self.assertEqual(r.reqid, '42')
        self.assertEqual(r.actions[0].type, 'submit')
        self.assertEqual(r.actions[0].src_project, 'foo')
        self.assertEqual(r.actions[0].src_package, 'bar')
        self.assertEqual(r.actions[0].src_rev, '1')
        self.assertEqual(r.actions[0].tgt_project, 'foobar')
        self.assertEqual(r.actions[0].tgt_package, 'bar')
        self.assertTrue(r.actions[0].opt_sourceupdate is None)
        self.assertTrue(r.actions[0].opt_updatelink is None)
        self.assertEqual(r.actions[1].type, 'delete')
        self.assertEqual(r.actions[1].tgt_project, 'deleteme')
        self.assertTrue(r.actions[1].tgt_package is None)
        self.assertEqual(r.state.name, 'accepted')
        self.assertEqual(r.state.when, '2010-12-27T01:36:29')
        self.assertEqual(r.state.who, 'user1')
        self.assertEqual(r.state.approver, None)
        self.assertEqual(r.state.comment, '')
        self.assertEqual(r.statehistory[0].when, '2010-12-13T13:02:03')
        self.assertEqual(r.statehistory[0].who, 'creator')
        self.assertEqual(r.statehistory[0].comment, 'foobar')
        self.assertEqual(r.title, 'title of the request')
        self.assertEqual(r.description, 'this is a\nvery long\ndescription')
        self.assertTrue(len(r.statehistory) == 1)
        self.assertTrue(len(r.reviews) == 0)
        self.assertXMLEqual(xml, r.to_str())

    def test_read_request2(self):
        """read in a request (with reviews)"""
        xml = self._get_fixture('test_read_request2.xml')
        r = osc.core.Request()
        r.read(ET.fromstring(xml))
        self.assertEqual(r.reqid, '123')
        self.assertEqual(r.actions[0].type, 'submit')
        self.assertEqual(r.actions[0].src_project, 'xyz')
        self.assertEqual(r.actions[0].src_package, 'abc')
        self.assertTrue(r.actions[0].src_rev is None)
        self.assertEqual(r.actions[0].opt_sourceupdate, 'cleanup')
        self.assertEqual(r.actions[0].opt_updatelink, '1')
        self.assertEqual(r.actions[1].type, 'add_role')
        self.assertEqual(r.actions[1].tgt_project, 'home:foo')
        self.assertEqual(r.actions[1].person_name, 'bar')
        self.assertEqual(r.actions[1].person_role, 'maintainer')
        self.assertEqual(r.actions[1].group_name, 'groupxyz')
        self.assertEqual(r.actions[1].group_role, 'reader')
        self.assertTrue(r.actions[1].tgt_package is None)
        self.assertEqual(r.state.name, 'review')
        self.assertEqual(r.state.when, '2010-12-27T01:36:29')
        self.assertEqual(r.state.approver, 'someone')
        self.assertEqual(r.state.who, 'abc')
        self.assertEqual(r.state.comment, '')
        self.assertEqual(r.reviews[0].state, 'new')
        self.assertEqual(r.reviews[0].by_group, 'group1')
        self.assertEqual(r.reviews[0].when, '2010-12-28T00:11:22')
        self.assertEqual(r.reviews[0].who, 'abc')
        self.assertEqual(r.reviews[0].comment, 'review start')
        self.assertTrue(r.reviews[0].by_user is None)
        self.assertEqual(r.statehistory[0].when, '2010-12-11T00:00:00')
        self.assertEqual(r.statehistory[0].who, 'creator')
        self.assertEqual(r.statehistory[0].comment, '')
        self.assertEqual(r.creator, 'creator')
        self.assertTrue(len(r.statehistory) == 1)
        self.assertTrue(len(r.reviews) == 1)
        self.assertXMLEqual(xml, r.to_str())

    def test_read_request3(self):
        """read in a request (with an "empty" comment+description)"""
        xml = """<request creator="xyz" id="2">
  <action type="set_bugowner">
    <target project="foo" />
    <person name="buguser" />
  </action>
  <state name="new" when="2010-12-28T12:36:29" who="xyz">
    <comment></comment>
  </state>
  <description></description>
</request>"""
        r = osc.core.Request()
        r.read(ET.fromstring(xml))
        self.assertEqual(r.reqid, '2')
        self.assertEqual(r.actions[0].type, 'set_bugowner')
        self.assertEqual(r.actions[0].tgt_project, 'foo')
        self.assertEqual(r.actions[0].person_name, 'buguser')
        self.assertEqual(r.state.name, 'new')
        self.assertEqual(r.state.when, '2010-12-28T12:36:29')
        self.assertEqual(r.state.who, 'xyz')
        self.assertEqual(r.state.comment, '')
        self.assertEqual(r.description, '')
        self.assertTrue(len(r.statehistory) == 0)
        self.assertTrue(len(r.reviews) == 0)
        self.assertEqual(r.creator, 'xyz')
        exp = """<request creator="xyz" id="2">
  <action type="set_bugowner">
    <target project="foo" />
    <person name="buguser" />
  </action>
  <state name="new" when="2010-12-28T12:36:29" who="xyz" />
</request>"""

        self.assertXMLEqual(exp, r.to_str())

    def test_request_list_view1(self):
        """test the list_view method"""
        xml = self._get_fixture('test_request_list_view1.xml')
        exp = """\
    62  State:new        By:Admin        When:2010-12-29T14:57:25
        Created by: Admin
        set_bugowner:    buguser                                            foo
        add_role:        person: xyz as maintainer, group: group1 as reader foobar
        add_role:        person: abc as reviewer                            foo/bar
        change_devel:    foo/bar                                            developed in devprj/devpkg
        submit:          srcprj/srcpackage ->                               tgtprj/tgtpackage
        submit:          foo/bar ->                                         baz
        delete:                                                             deleteme
        delete:                                                             foo/bar\n"""
        r = osc.core.Request()
        r.read(ET.fromstring(xml))
        self.assertEqual(exp, r.list_view())

    def test_request_list_view2(self):
        """test the list_view method (with history elements and description)"""
        xml = self._get_fixture('test_request_list_view2.xml')
        r = osc.core.Request()
        r.read(ET.fromstring(xml))
        exp = """\
    21  State:accepted   By:foobar       When:2010-12-29T16:37:45
        Created by: foobar
        set_bugowner:    buguser                                            foo
        From: Created Request: user -> Review Approved: foobar
        Descr: This is a simple request with a lot of ... ... text and other
               stuff. This request also contains a description. This is useful
               to describe the request. blabla blabla\n"""
        self.assertEqual(exp, r.list_view())

    def test_request_str1(self):
        """test the __str__ method"""
        xml = self._get_fixture('test_request_str1.xml')
        r = osc.core.Request()
        r = osc.core.Request()
        r.read(ET.fromstring(xml))
        self.assertEqual(r.creator, 'creator')
        exp = """\
Request:    123
Created by: creator

Actions:
  submit:       xyz/abc(cleanup) -> foo ***update link***
  add_role:     person: bar as maintainer, group: groupxyz as reader home:foo

Message:
  just a samll description
  in order to describe this
  request - blablabla
  test.

State:
  review                                                        2010-12-27T01:36:29 abc
    | currently in review

Review:
  accepted   Group: group1                                      2010-12-29T00:11:22 abc
    | accepted
  new        Group: group1                                      2010-12-28T00:11:22 abc
    | review start

History:
  2010-12-12T00:00:00 creator                        revoked
  2010-12-11T00:00:00 creator                        new"""
        self.assertEqual(exp, str(r))

    def test_request_str2(self):
        """test the __str__ method"""
        xml = """\
<request creator="creator" id="98765">
  <action type="change_devel">
    <source project="devprj" package="devpkg" />
    <target project="foo" package="bar" />
  </action>
  <action type="delete">
    <target project="deleteme" />
  </action>
  <state name="new" when="2010-12-29T00:11:22" who="creator" />
</request>"""
        r = osc.core.Request()
        r.read(ET.fromstring(xml))
        self.assertEqual(r.creator, 'creator')
        exp = """\
Request:    98765
Created by: creator

Actions:
  change_devel: foo/bar developed in devprj/devpkg
  delete:       deleteme

Message:
  <no message>

State:
  new                                                           2010-12-29T00:11:22 creator"""
        self.assertEqual(exp, str(r))

    def test_legacy_request(self):
        """load old-style submitrequest"""
        xml = """\
<request creator="olduser" id="1234" type="submit">
  <submit>
    <source package="baz" project="foobar" />
    <target package="baz" project="foo" />
  </submit>
  <state name="new" when="2010-12-30T02:11:22" who="olduser" />
</request>"""
        r = osc.core.Request()
        r.read(ET.fromstring(xml))
        self.assertEqual(r.reqid, '1234')
        self.assertEqual(r.actions[0].type, 'submit')
        self.assertEqual(r.actions[0].src_project, 'foobar')
        self.assertEqual(r.actions[0].src_package, 'baz')
        self.assertEqual(r.actions[0].tgt_project, 'foo')
        self.assertEqual(r.actions[0].tgt_package, 'baz')
        self.assertTrue(r.actions[0].opt_sourceupdate is None)
        self.assertTrue(r.actions[0].opt_updatelink is None)
        self.assertEqual(r.state.name, 'new')
        self.assertEqual(r.state.when, '2010-12-30T02:11:22')
        self.assertEqual(r.state.who, 'olduser')
        self.assertEqual(r.state.comment, '')
        self.assertEqual(r.creator, 'olduser')
        exp = """\
<request creator="olduser" id="1234">
  <action type="submit">
    <source package="baz" project="foobar" />
    <target package="baz" project="foo" />
  </action>
  <state name="new" when="2010-12-30T02:11:22" who="olduser" />
</request>"""
        self.assertXMLEqual(exp, r.to_str())

    def test_get_actions(self):
        """test get_actions method"""
        xml = self._get_fixture('test_request_list_view1.xml')
        r = osc.core.Request()
        r.read(ET.fromstring(xml))
        sr_actions = r.get_actions('submit')
        self.assertTrue(len(sr_actions) == 2)
        for i in sr_actions:
            self.assertEqual(i.type, 'submit')
        self.assertTrue(len(r.get_actions('submit', 'delete', 'change_devel')) == 5)
        self.assertTrue(len(r.get_actions()) == 8)


if __name__ == '__main__':
    unittest.main()
