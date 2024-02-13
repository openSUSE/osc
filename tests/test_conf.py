import os
import shutil
import tempfile
import unittest

import osc.conf

from .common import patch


OSCRC = """
[general]
apiurl = https://api.opensuse.org
user = Admin
pass = opensuse
passx = unused
sshkey = ~/.ssh/id_rsa.pub
packagecachedir = /var/tmp/osbuild-packagecache
su-wrapper = sudo
build-cmd = /usr/bin/build
build-type = kvm
build-root = /var/tmp/build-root/%(repo)s-%(arch)s
build-uid = 1000:1000
build-device = /dev/null
build-memory = 1024
build-shell-after-fail = 0
build-swap = /tmp/build-swap
build-vmdisk-rootsize = 10240
build-vmdisk-swapsize = 512
build-vmdisk-filesystem = ext4
build-vm-user = abuild
build-kernel = /boot/vmlinuz
build-initrd = /boot/initrd
download-assets-cmd = /usr/lib/build/download_assets
build-jobs = 4
builtin_signature_check = 1
icecream = 0
ccache = 0
sccache = 0
sccache_uri = file:///var/tmp/osbuild-sccache
buildlog_strip_time = 0
debug = 0
http_debug = 0
http_full_debug = 0
http_retries = 3
quiet = 0
verbose = 0
no_preinstallimage = 0
traceback = 0
post_mortem = 0
use_keyring = 0
cookiejar = ~/.local/state/osc/cookiejar
no_verify = 0
disable_hdrmd5_check = 0
do_package_tracking = 1
extra-pkgs = vim strace
build_repository = openSUSE_Factory
getpac_default_project = openSUSE:Factory
checkout_no_colon = 0
project_separator = :
checkout_rooted = 0
exclude_glob = .osc CVS .svn .* _linkerror *~ #*# *.orig *.bak *.changes.vctmp.*
print_web_links = 0
request_list_days = 0
check_filelist = 1
check_for_request_on_action = 1
submitrequest_on_accept_action = cleanup
request_show_interactive = 0
request_show_source_buildstatus = 0
review_inherit_group = 0
submitrequest_accepted_template = bla bla
submitrequest_declined_template = bla bla
linkcontrol = 0
include_request_from_project = 1
local_service_run = 1
include_files = incl *.incl
exclude_files = excl *.excl
maintained_attribute = OBS:Maintained
maintenance_attribute = OBS:MaintenanceProject
maintained_update_project_attribute = OBS:UpdateProject
show_download_progress = 0
vc-cmd = /usr/lib/build/vc
status_mtime_heuristic = 0
plugin-option = plugin-general-option

[https://api.opensuse.org]
credentials_mgr_class=osc.credentials.PlaintextConfigFileCredentialsManager
user = Admin
pass = opensuse
passx = unused
aliases = obs
http_headers = 
    Authorization: Basic QWRtaW46b3BlbnN1c2U=
    X-Foo: Bar
realname = The Administrator
email = admin@example.com
cafile = /path/to/custom_cacert.pem
capath = /path/to/custom_cacert.d/
sslcertck = 1
trusted_prj = openSUSE:* SUSE:*
downloadurl = http://example.com/
sshkey = ~/.ssh/id_rsa.pub
disable_hdrmd5_check = 0
plugin-option = plugin-host-option
"""


class TestExampleConfig(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.mkdtemp(prefix="osc_test_")
        self.oscrc = os.path.join(self.tmpdir, "oscrc")
        with open(self.oscrc, "w", encoding="utf-8") as f:
            f.write(OSCRC)
        osc.conf.get_config(override_conffile=self.oscrc)
        self.config = osc.conf.config

    def tearDown(self):
        shutil.rmtree(self.tmpdir)

    def test_invalid_attribute(self):
        self.assertRaises(AttributeError, setattr, self.config, "new_attribute", "123")

    def test_apiurl(self):
        self.assertEqual(self.config["apiurl"], "https://api.opensuse.org")

    def test_user(self):
        self.assertEqual(self.config["user"], "Admin")

    def test_pass(self):
        self.assertEqual(self.config["pass"], "opensuse")

    def test_passx(self):
        self.assertEqual(self.config["passx"], "unused")

    def test_sshkey(self):
        self.assertEqual(self.config["sshkey"], "~/.ssh/id_rsa.pub")

    def test_packagecachedir(self):
        self.assertEqual(self.config["packagecachedir"], "/var/tmp/osbuild-packagecache")

    def test_su_wrapper(self):
        self.assertEqual(self.config["su-wrapper"], "sudo")

    def test_build_cmd(self):
        self.assertEqual(self.config["build-cmd"], "/usr/bin/build")

    def test_build_type(self):
        self.assertEqual(self.config["build-type"], "kvm")

    def test_build_root(self):
        self.assertEqual(self.config["build-root"], "/var/tmp/build-root/%(repo)s-%(arch)s")

    def test_build_uid(self):
        self.assertEqual(self.config["build-uid"], "1000:1000")

    def test_build_device(self):
        self.assertEqual(self.config["build-device"], "/dev/null")

    def test_build_memory(self):
        self.assertEqual(self.config["build-memory"], 1024)

    def test_build_shell_after_fail(self):
        self.assertEqual(self.config["build-shell-after-fail"], False)

    def test_build_swap(self):
        self.assertEqual(self.config["build-swap"], "/tmp/build-swap")

    def test_build_vmdisk_rootsize(self):
        self.assertEqual(self.config["build-vmdisk-rootsize"], 10240)

    def test_build_vmdisk_swapsize(self):
        self.assertEqual(self.config["build-vmdisk-swapsize"], 512)

    def test_build_vmdisk_filesystem(self):
        self.assertEqual(self.config["build-vmdisk-filesystem"], "ext4")

    def test_build_vm_user(self):
        self.assertEqual(self.config["build-vm-user"], "abuild")

    def test_build_kernel(self):
        self.assertEqual(self.config["build-kernel"], "/boot/vmlinuz")

    def test_build_initrd(self):
        self.assertEqual(self.config["build-initrd"], "/boot/initrd")

    def test_download_assets_cmd(self):
        self.assertEqual(self.config["download-assets-cmd"], "/usr/lib/build/download_assets")

    def test_build_jobs(self):
        self.assertEqual(self.config["build-jobs"], 4)

    def test_builtin_signature_check(self):
        self.assertEqual(self.config["builtin_signature_check"], True)

    def test_icecream(self):
        self.assertEqual(self.config["icecream"], 0)

    def test_ccache(self):
        self.assertEqual(self.config["ccache"], False)

    def test_sccache(self):
        self.assertEqual(self.config["sccache"], False)

    def test_sccache_uri(self):
        self.assertEqual(self.config["sccache_uri"], "file:///var/tmp/osbuild-sccache")

    def test_buildlog_strip_time(self):
        self.assertEqual(self.config["buildlog_strip_time"], False)

    def test_debug(self):
        self.assertEqual(self.config["debug"], False)

    def test_http_debug(self):
        self.assertEqual(self.config["http_debug"], False)

    def test_http_full_debug(self):
        self.assertEqual(self.config["http_full_debug"], False)

    def test_http_retries(self):
        self.assertEqual(self.config["http_retries"], 3)

    def test_quiet(self):
        self.assertEqual(self.config["quiet"], False)

    def test_verbose(self):
        self.assertEqual(self.config["verbose"], False)

    def test_no_preinstallimage(self):
        self.assertEqual(self.config["no_preinstallimage"], False)

    def test_traceback(self):
        self.assertEqual(self.config["traceback"], False)

    def test_post_mortem(self):
        self.assertEqual(self.config["post_mortem"], False)

    def test_use_keyring(self):
        self.assertEqual(self.config["use_keyring"], False)

    def test_cookiejar(self):
        self.assertEqual(self.config["cookiejar"], "~/.local/state/osc/cookiejar")

    def test_no_verify(self):
        self.assertEqual(self.config["no_verify"], False)

    def test_disable_hdrmd5_check(self):
        self.assertEqual(self.config["disable_hdrmd5_check"], False)

    def test_do_package_tracking(self):
        self.assertEqual(self.config["do_package_tracking"], True)

    def test_extra_pkgs(self):
        self.assertEqual(self.config["extra-pkgs"], ["vim", "strace"])

    def test_build_repository(self):
        self.assertEqual(self.config["build_repository"], "openSUSE_Factory")

    def test_getpac_default_project(self):
        self.assertEqual(self.config["getpac_default_project"], "openSUSE:Factory")

    def test_checkout_no_colon(self):
        self.assertEqual(self.config["checkout_no_colon"], False)

    def test_project_separator(self):
        self.assertEqual(self.config["project_separator"], ":")

    def test_checkout_rooted(self):
        self.assertEqual(self.config["checkout_rooted"], False)

    def test_exclude_glob(self):
        self.assertEqual(
            self.config["exclude_glob"],
            [
                ".osc",
                "CVS",
                ".svn",
                ".*",
                "_linkerror",
                "*~",
                "#*#",
                "*.orig",
                "*.bak",
                "*.changes.vctmp.*",
            ],
        )

    def test_print_web_links(self):
        self.assertEqual(self.config["print_web_links"], False)

    def test_request_list_days(self):
        self.assertEqual(self.config["request_list_days"], 0)

    def test_check_filelist(self):
        self.assertEqual(self.config["check_filelist"], True)

    def test_check_for_request_on_action(self):
        self.assertEqual(self.config["check_for_request_on_action"], True)

    def test_submitrequest_on_accept_action(self):
        self.assertEqual(self.config["submitrequest_on_accept_action"], "cleanup")

    def test_request_show_interactive(self):
        self.assertEqual(self.config["request_show_interactive"], False)

    def test_request_show_source_buildstatus(self):
        self.assertEqual(self.config["request_show_source_buildstatus"], False)

    def test_review_inherit_group(self):
        self.assertEqual(self.config["review_inherit_group"], False)

    def test_submitrequest_accepted_template(self):
        self.assertEqual(self.config["submitrequest_accepted_template"], "bla bla")

    def test_submitrequest_declined_template(self):
        self.assertEqual(self.config["submitrequest_declined_template"], "bla bla")

    def test_linkcontrol(self):
        self.assertEqual(self.config["linkcontrol"], False)

    def test_include_request_from_project(self):
        self.assertEqual(self.config["include_request_from_project"], True)

    def test_local_service_run(self):
        self.assertEqual(self.config["local_service_run"], True)

    def test_exclude_files(self):
        self.assertEqual(self.config["exclude_files"], ["excl", "*.excl"])

    def test_include_files(self):
        self.assertEqual(self.config["include_files"], ["incl", "*.incl"])

    def test_maintained_attribute(self):
        self.assertEqual(self.config["maintained_attribute"], "OBS:Maintained")

    def test_maintenance_attribute(self):
        self.assertEqual(self.config["maintenance_attribute"], "OBS:MaintenanceProject")

    def test_maintained_update_project_attribute(self):
        self.assertEqual(self.config["maintained_update_project_attribute"], "OBS:UpdateProject")

    def test_show_download_progress(self):
        self.assertEqual(self.config["show_download_progress"], False)

    def test_vc_cmd(self):
        self.assertEqual(self.config["vc-cmd"], "/usr/lib/build/vc")

    def test_status_mtime_heuristic(self):
        self.assertEqual(self.config["status_mtime_heuristic"], False)

    def test_host_option_user(self):
        host_options = self.config["api_host_options"][self.config["apiurl"]]
        self.assertEqual(host_options["user"], "Admin")

    def test_host_option_pass(self):
        host_options = self.config["api_host_options"][self.config["apiurl"]]
        self.assertEqual(host_options["pass"], "opensuse")

    def test_host_option_http_headers(self):
        host_options = self.config["api_host_options"][self.config["apiurl"]]
        self.assertEqual(
            host_options["http_headers"],
            [
                ("Authorization", "Basic QWRtaW46b3BlbnN1c2U="),
                ("X-Foo", "Bar"),
            ],
        )

    def test_host_option_realname(self):
        host_options = self.config["api_host_options"][self.config["apiurl"]]
        self.assertEqual(host_options["realname"], "The Administrator")

    def test_host_option_email(self):
        host_options = self.config["api_host_options"][self.config["apiurl"]]
        self.assertEqual(host_options["email"], "admin@example.com")

    def test_host_option_sslcertck(self):
        host_options = self.config["api_host_options"][self.config["apiurl"]]
        self.assertEqual(host_options["sslcertck"], True)

    def test_host_option_cafile(self):
        host_options = self.config["api_host_options"][self.config["apiurl"]]
        self.assertEqual(host_options["cafile"], "/path/to/custom_cacert.pem")

    def test_host_option_capath(self):
        host_options = self.config["api_host_options"][self.config["apiurl"]]
        self.assertEqual(host_options["capath"], "/path/to/custom_cacert.d/")

    def test_host_option_sshkey(self):
        host_options = self.config["api_host_options"][self.config["apiurl"]]
        self.assertEqual(host_options["sshkey"], "~/.ssh/id_rsa.pub")

    def test_host_option_credentials_mgr_class(self):
        host_options = self.config["api_host_options"][self.config["apiurl"]]
        self.assertEqual(
            host_options["credentials_mgr_class"],
            "osc.credentials.PlaintextConfigFileCredentialsManager",
        )

    def test_host_option_allow_http(self):
        host_options = self.config["api_host_options"][self.config["apiurl"]]
        self.assertEqual(host_options["allow_http"], False)

    def test_host_option_trusted_prj(self):
        host_options = self.config["api_host_options"][self.config["apiurl"]]
        self.assertEqual(host_options["trusted_prj"], ["openSUSE:*", "SUSE:*"])

    def test_host_option_downloadurl(self):
        host_options = self.config["api_host_options"][self.config["apiurl"]]
        self.assertEqual(host_options["downloadurl"], "http://example.com/")

    def test_host_option_disable_hdrmd5_check(self):
        host_options = self.config["api_host_options"][self.config["apiurl"]]
        self.assertEqual(host_options["disable_hdrmd5_check"], False)

    def test_extra_fields(self):
        self.assertEqual(self.config["plugin-option"], "plugin-general-option")
        self.assertEqual(self.config._extra_fields, {"plugin-option": "plugin-general-option"})

        self.config["new-option"] = "value"
        self.assertEqual(self.config["new-option"], "value")
        self.assertEqual(self.config._extra_fields, {"plugin-option": "plugin-general-option", "new-option": "value"})

        host_options = self.config["api_host_options"][self.config["apiurl"]]
        self.assertEqual(host_options["plugin-option"], "plugin-host-option")
        self.assertEqual(host_options._extra_fields, {"plugin-option": "plugin-host-option"})

        host_options["new-option"] = "value"
        self.assertEqual(host_options["new-option"], "value")
        self.assertEqual(host_options._extra_fields, {"plugin-option": "plugin-host-option", "new-option": "value"})

    def test_apiurl_aliases(self):
        expected = {"https://api.opensuse.org": "https://api.opensuse.org", "obs": "https://api.opensuse.org"}
        self.assertEqual(self.config.apiurl_aliases, expected)
        self.assertEqual(self.config["apiurl_aliases"], expected)


class TestOverrides(unittest.TestCase):
    def test_verbose(self):
        self.options = osc.conf.Options()
        self.assertEqual(self.options.quiet, False)
        self.assertEqual(self.options.verbose, False)

        self.options.quiet = True
        self.options.verbose = True
        self.assertEqual(self.options.quiet, True)
        # ``verbose`` is forced to ``False`` by the ``quiet`` option
        self.assertEqual(self.options.verbose, False)

        self.options.quiet = False
        self.assertEqual(self.options.quiet, False)
        self.assertEqual(self.options.verbose, True)

    def test_http_debug(self):
        self.options = osc.conf.Options()
        self.assertEqual(self.options.http_debug, False)
        self.assertEqual(self.options.http_full_debug, False)

        self.options.http_full_debug = True
        # ``http_debug`` forced to ``True`` by the ``http_full_debug`` option
        self.assertEqual(self.options.http_debug, True)
        self.assertEqual(self.options.http_full_debug, True)


class TestFromParent(unittest.TestCase):
    def setUp(self):
        self.options = osc.conf.Options()
        self.host_options = osc.conf.HostOptions(apiurl="https://example.com", username="Admin", _parent=self.options)
        self.options.api_host_options[self.host_options.apiurl] = self.host_options

    def test_disable_hdrmd5_check(self):
        self.assertEqual(self.options.disable_hdrmd5_check, False)
        self.assertEqual(self.host_options.disable_hdrmd5_check, False)

        self.options.disable_hdrmd5_check = True

        self.assertEqual(self.options.disable_hdrmd5_check, True)
        self.assertEqual(self.host_options.disable_hdrmd5_check, True)

        self.host_options.disable_hdrmd5_check = False

        self.assertEqual(self.options.disable_hdrmd5_check, True)
        self.assertEqual(self.host_options.disable_hdrmd5_check, False)

    def test_email(self):
        self.assertEqual(self.options.email, None)
        self.assertEqual(self.host_options.email, None)

        self.options.email = "user@example.com"

        self.assertEqual(self.options.email, "user@example.com")
        self.assertEqual(self.host_options.email, "user@example.com")

        self.host_options.email = "another-user@example.com"

        self.assertEqual(self.options.email, "user@example.com")
        self.assertEqual(self.host_options.email, "another-user@example.com")


class TestConf(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.mkdtemp(prefix="osc_test_")

    def tearDown(self):
        shutil.rmtree(self.tmpdir)

    def test_write_initial_config(self):
        conffile = os.path.join(self.tmpdir, "oscrc")
        entries = {
            "user": "Admin",
            "pass": "opensuse",
            "apiurl": "https://example.com",
        }
        osc.conf.write_initial_config(conffile, entries)

    def test_api_host_options(self):
        # test that instances do not share any references leaked from the defaults
        conf1 = osc.conf.Options()
        conf2 = osc.conf.Options()

        self.assertEqual(conf1, conf2)  # models are compared by their contents now
        self.assertNotEqual(id(conf1), id(conf2))
        self.assertNotEqual(id(conf1.api_host_options), id(conf2.api_host_options))


class TestCredentialsFromEnv(unittest.TestCase):
    def setUp(self):
        osc.conf.config = None
        self.oscrc = ""

    @patch.dict(os.environ, {"OSC_APIURL": "https://example.com"}, clear=True)
    def test_new_apiurl(self):
        # missing user
        self.assertRaises(
            osc.oscerr.ConfigMissingCredentialsError,
            osc.conf.get_config,
            override_conffile=self.oscrc,
        )

    @patch.dict(
        os.environ,
        {"OSC_APIURL": "https://example.com", "OSC_USERNAME": "user"},
        clear=True,
    )
    def test_new_apiurl_username(self):
        # missing password
        self.assertRaises(
            osc.oscerr.ConfigMissingCredentialsError,
            osc.conf.get_config,
            override_conffile=self.oscrc,
        )

    @patch.dict(
        os.environ,
        {
            "OSC_APIURL": "https://example.com",
            "OSC_USERNAME": "user",
            "OSC_PASSWORD": "secret",
        },
        clear=True,
    )
    def test_new_apiurl_username_password(self):
        # missing password
        osc.conf.get_config(override_conffile=self.oscrc)
        conf = osc.conf.config
        host_options = conf["api_host_options"][conf["apiurl"]]
        self.assertEqual(conf.apiurl, "https://example.com")
        self.assertEqual(host_options.apiurl, "https://example.com")
        self.assertEqual(host_options.username, "user")
        self.assertEqual(host_options.password, "secret")
        self.assertEqual(host_options.credentials_mgr_class, None)

    @patch.dict(
        os.environ,
        {
            "OSC_APIURL": "https://example.com",
            "OSC_USERNAME": "user",
            "OSC_PASSWORD": "secret",
        },
        clear=True,
    )
    def test_new_apiurl_username_password(self):
        # missing password
        osc.conf.get_config(override_conffile=self.oscrc)
        conf = osc.conf.config
        host_options = conf["api_host_options"][conf["apiurl"]]
        self.assertEqual(conf.apiurl, "https://example.com")
        self.assertEqual(host_options.apiurl, "https://example.com")
        self.assertEqual(host_options.username, "user")
        self.assertEqual(host_options.password, "secret")
        self.assertEqual(host_options.credentials_mgr_class, None)

    @patch.dict(
        os.environ,
        {
            "OSC_APIURL": "https://example.com",
            "OSC_USERNAME": "user",
            "OSC_PASSWORD": "secret",
            "OSC_CREDENTIALS_MGR_CLASS": "osc.credentials.PlaintextConfigFileCredentialsManager",
        },
        clear=True,
    )
    def test_new_apiurl_username_password_credmgr(self):
        # missing password
        osc.conf.get_config(override_conffile=self.oscrc)
        conf = osc.conf.config
        host_options = conf["api_host_options"][conf.apiurl]
        self.assertEqual(conf.apiurl, "https://example.com")
        self.assertEqual(host_options.apiurl, "https://example.com")
        self.assertEqual(host_options.username, "user")
        self.assertEqual(host_options.password, "secret")
        self.assertEqual(host_options.credentials_mgr_class, "osc.credentials.PlaintextConfigFileCredentialsManager")


class TestHostOptionsFromEnv(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.mkdtemp(prefix="osc_test_")
        self.oscrc = os.path.join(self.tmpdir, "oscrc")
        with open(self.oscrc, "w", encoding="utf-8") as f:
            f.write(OSCRC)
        osc.conf.get_config(override_conffile=self.oscrc)
        self.config = osc.conf.config

    def tearDown(self):
        shutil.rmtree(self.tmpdir)

    @patch.dict(
        os.environ,
        {
            "OSC_HOST_OBS_USERNAME": "user",
            "OSC_HOST_OBS_PASSWORD": "secret",
            "OSC_HOST_OBS_CREDENTIALS_MGR_CLASS": "osc.credentials.PlaintextConfigFileCredentialsManager",
            "OSC_HOST_OBS_REALNAME": "User",
            "OSC_HOST_OBS_EMAIL": "user@example.com",
        },
        clear=True,
    )
    def test_host_options(self):
        osc.conf.get_config(override_conffile=self.oscrc)
        conf = osc.conf.config
        host_options = conf["api_host_options"][conf["apiurl"]]
        self.assertEqual(conf.apiurl, "https://api.opensuse.org")
        self.assertEqual(host_options.apiurl, "https://api.opensuse.org")
        self.assertEqual(host_options.username, "user")
        self.assertEqual(host_options.password, "secret")
        self.assertEqual(host_options.credentials_mgr_class, "osc.credentials.PlaintextConfigFileCredentialsManager")
        self.assertEqual(host_options.realname, "User")
        self.assertEqual(host_options.email, "user@example.com")

    @patch.dict(
        os.environ,
        {
            "OSC_HOST_OBS_USERNAME": "user",
            "OSC_HOST_OBS_PASSWORD": "secret",
            "OSC_HOST_OBS_CREDENTIALS_MGR_CLASS": "osc.credentials.PlaintextConfigFileCredentialsManager",
            "OSC_HOST_OBS_REALNAME": "User",
            "OSC_HOST_OBS_EMAIL": "user@example.com",
            "OSC_USERNAME": "USER",
            "OSC_PASSWORD": "SECRET",
            "OSC_CREDENTIALS_MGR_CLASS": "osc.credentials.TransientCredentialsManager",
        },
        clear=True,
    )
    def test_host_options_overrides(self):
        # thest if OSC_{USERNAME,PASSWORD,CREDENTIALS_MGR_CLASS} prevail over OSC_HOST_* options
        osc.conf.get_config(override_conffile=self.oscrc)
        conf = osc.conf.config
        host_options = conf["api_host_options"][conf["apiurl"]]
        self.assertEqual(conf.apiurl, "https://api.opensuse.org")
        self.assertEqual(host_options.apiurl, "https://api.opensuse.org")
        self.assertEqual(host_options.username, "USER")
        self.assertEqual(host_options.password, "SECRET")
        self.assertEqual(host_options.credentials_mgr_class, "osc.credentials.TransientCredentialsManager")
        self.assertEqual(host_options.realname, "User")
        self.assertEqual(host_options.email, "user@example.com")


if __name__ == "__main__":
    unittest.main()
