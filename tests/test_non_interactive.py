import argparse
import contextlib
import io
import os
import shutil
import tempfile
import unittest
import unittest.mock

from osc import conf, oscerr
from osc.commandline import Osc, OscMainCommand
from osc.util import helper


class NonInteractiveTestBase(unittest.TestCase):
    """Set/restore the resolved non_interactive flag (no mutable helper state)."""

    def setUp(self):
        self._prev_config = conf.config
        conf.config = conf.Options()
        conf.config["non_interactive"] = False

    def tearDown(self):
        conf.config = self._prev_config

    def enable_non_interactive(self):
        conf.config["non_interactive"] = True


class TestRawInputNonInteractive(NonInteractiveTestBase):
    def test_interactive_reads_stdin(self):
        with unittest.mock.patch("builtins.input", return_value="y") as m:
            self.assertEqual(helper.raw_input("Proceed? "), "y")
            m.assert_called_once_with("Proceed? ")

    def test_interactive_eof_is_user_abort(self):
        with unittest.mock.patch("builtins.input", side_effect=EOFError):
            self.assertRaises(oscerr.UserAbort, helper.raw_input, "Proceed? ")

    def test_non_interactive_raises(self):
        self.enable_non_interactive()
        with self.assertRaises(oscerr.NonInteractiveInput) as ctx:
            helper.raw_input("Proceed? (y/n) ")
        self.assertIn("Proceed? (y/n)", str(ctx.exception))
        self.assertIn("non-interactive", str(ctx.exception))

    def test_non_interactive_includes_hint(self):
        self.enable_non_interactive()
        with self.assertRaises(oscerr.NonInteractiveInput) as ctx:
            helper.raw_input("Proceed? ", hint="Use --force to proceed without prompting.")
        self.assertIn("--force", str(ctx.exception))

    def test_non_interactive_error_is_osc_base_error(self):
        # babysitter.run() turns OscBaseError into exit code 1
        self.assertTrue(issubclass(oscerr.NonInteractiveInput, oscerr.OscBaseError))

    def test_hint_is_keyword_only(self):
        with self.assertRaises(TypeError):
            helper.raw_input("a", "b")

    def test_non_interactive_returns_default_without_prompting(self):
        self.enable_non_interactive()
        with unittest.mock.patch("builtins.input") as m:
            # simulates Enter: the documented default applies, nothing is read
            self.assertEqual(helper.raw_input("Proceed? (y/N) ", default=""), "")
            m.assert_not_called()

    def test_non_interactive_default_none_still_raises(self):
        self.enable_non_interactive()
        with self.assertRaises(oscerr.NonInteractiveInput):
            helper.raw_input("Proceed? ", default=None, hint="Use --force.")

    def test_is_non_interactive_reflects_config(self):
        self.assertFalse(helper.is_non_interactive())
        self.enable_non_interactive()
        self.assertTrue(helper.is_non_interactive())


class TestPreflightHelpers(NonInteractiveTestBase):
    """Unit tests for the command-level pre-flight helpers."""

    def test_require_interactive_is_noop(self):
        # must not raise even when options are missing
        helper.require_non_interactive_options("osc whatever", [(None, "--missing")])

    def test_require_names_all_missing_options(self):
        self.enable_non_interactive()
        with self.assertRaises(oscerr.NonInteractiveInput) as ctx:
            helper.require_non_interactive_options(
                "osc whatever", [(None, "--first"), ("", "--second"), ("ok", "--third")]
            )
        msg = str(ctx.exception)
        self.assertIn("--first", msg)
        self.assertIn("--second", msg)
        self.assertNotIn("--third", msg)
        self.assertIn("osc whatever", msg)

    def test_require_passes_when_complete(self):
        self.enable_non_interactive()
        helper.require_non_interactive_options("osc whatever", [("x", "--first")])

    def test_require_empty_is_noop(self):
        self.enable_non_interactive()
        helper.require_non_interactive_options("osc whatever", [])

    def test_require_any_names_all_alternatives(self):
        self.enable_non_interactive()
        with self.assertRaises(oscerr.NonInteractiveInput) as ctx:
            helper.require_any_non_interactive_options("osc whatever", [(None, "--aaa"), ("", "--bbb")])
        self.assertIn("--aaa or --bbb", str(ctx.exception))

    def test_require_any_passes_when_one_given(self):
        self.enable_non_interactive()
        helper.require_any_non_interactive_options("osc whatever", [(None, "--aaa"), ("x", "--bbb")])

    def test_require_any_interactive_is_noop(self):
        helper.require_any_non_interactive_options("osc whatever", [(None, "--aaa")])

    def test_refuse_interactive_is_noop(self):
        helper.refuse_non_interactive("some prompt", hint="Do it this way instead.")

    def test_refuse_hint_is_required(self):
        # every refusal must name the alternative; there is no default hint
        self.enable_non_interactive()
        with self.assertRaises(TypeError):
            helper.refuse_non_interactive("some prompt")

    def test_refuse_custom_hint(self):
        self.enable_non_interactive()
        with self.assertRaises(oscerr.NonInteractiveInput) as ctx:
            helper.refuse_non_interactive("some prompt", hint="Do it this way instead.")
        self.assertIn("Do it this way instead.", str(ctx.exception))


class TestGetUserInputNonInteractive(NonInteractiveTestBase):
    def test_non_interactive_returns_default_without_prompting(self):
        self.enable_non_interactive()
        from osc.output import get_user_input

        with unittest.mock.patch("builtins.input") as m:
            reply = get_user_input(
                "Do it?",
                answers={"y": "yes", "n": "no"},
                default_answer="y",
            )
            self.assertEqual(reply, "y")
            m.assert_not_called()

    def test_non_interactive_no_default_returns_none(self):
        self.enable_non_interactive()
        from osc.output import get_user_input

        with unittest.mock.patch("builtins.input") as m:
            reply = get_user_input("Do it?", answers={"y": "yes", "n": "no"})
            self.assertIsNone(reply)
            m.assert_not_called()

    def test_interactive_eof_is_user_abort(self):
        from osc.output import get_user_input

        with unittest.mock.patch("builtins.input", side_effect=EOFError):
            self.assertRaises(oscerr.UserAbort, get_user_input, "Do it?", answers={"y": "yes"})


class TestNonInteractiveFlag(unittest.TestCase):
    def _main(self):
        from osc.commandline import Command

        class TestCommand(Command):
            name = "test-cmd"

        class TestMainCommand(OscMainCommand):
            name = "osc-test"

        main = TestMainCommand()
        main.load_command(TestCommand, "test.osc.commands")
        return main

    def test_flag_defaults_to_none(self):
        # absent flag preserves env/oscrc instead of forcing False
        args = self._main().parse_args([])
        self.assertIsNone(args.non_interactive)

    def test_flag_parsed(self):
        args = self._main().parse_args(["--non-interactive"])
        self.assertTrue(args.non_interactive)


OSCRC_LOCALHOST = """
[general]
apiurl = https://localhost

[https://localhost]
user=Admin
pass=opensuse
""".lstrip()


class TestNonInteractivePostParse(unittest.TestCase):
    def setUp(self):
        self._prev_config = conf.config
        # an earlier test module may have removed our cwd; anchor somewhere safe first
        os.chdir(tempfile.gettempdir())
        self._cwd = os.getcwd()
        self.tmpdir = tempfile.mkdtemp(prefix="osc_test")
        os.chdir(self.tmpdir)
        self.oscrc = os.path.join(self.tmpdir, "oscrc")
        with open(self.oscrc, "w") as f:
            f.write(OSCRC_LOCALHOST)

    def tearDown(self):
        conf.config = self._prev_config
        os.chdir(self._cwd)
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def _main(self):
        from osc.commandline import Command

        class TestCommand(Command):
            name = "test-cmd"

        class TestMainCommand(OscMainCommand):
            name = "osc-test"

        main = TestMainCommand()
        main.load_command(TestCommand, "test.osc.commands")
        return main

    def _post_parse(self, argv, env=None):
        main = self._main()
        environ = {"OSC_CONFIG": self.oscrc}
        environ.update(env or {})
        with unittest.mock.patch.dict(os.environ, environ):
            args = main.parse_args(argv)
            main.post_parse_args(args)
        return args

    def test_flag_resolves_into_config(self):
        self._post_parse(["--non-interactive"])
        self.assertTrue(conf.config["non_interactive"])

    def test_absent_flag_preserves_env(self):
        self._post_parse([], env={"OSC_NON_INTERACTIVE": "1"})
        self.assertTrue(conf.config["non_interactive"])

    def test_absent_flag_defaults_to_false(self):
        with unittest.mock.patch.dict(os.environ, {"OSC_CONFIG": self.oscrc}):
            # make sure no stray env var leaks in
            os.environ.pop("OSC_NON_INTERACTIVE", None)
            self._post_parse([])
        self.assertFalse(conf.config["non_interactive"])

    def test_cli_flag_wins_over_env(self):
        # --setopt non_interactive=false overrides OSC_NON_INTERACTIVE=1
        self._post_parse(
            ["--setopt", "non_interactive=false"],
            env={"OSC_NON_INTERACTIVE": "1"},
        )
        self.assertFalse(conf.config["non_interactive"])

    def test_no_config_non_interactive_fails_fast(self):
        main = self._main()
        args = main.parse_args(["--non-interactive", "test-cmd"])
        err = oscerr.NoConfigfile("/nonexistent/oscrc", "no config")
        with unittest.mock.patch("osc.conf.get_config", side_effect=err):
            with unittest.mock.patch("osc.conf.interactive_config_setup") as wizard:
                with self.assertRaises(oscerr.NonInteractiveInput) as ctx:
                    main.post_parse_args(args)
                self.assertIn("non-interactive", str(ctx.exception))
                wizard.assert_not_called()

    def test_no_config_interactive_runs_wizard(self):
        main = self._main()
        args = main.parse_args(["test-cmd"])
        err = oscerr.NoConfigfile("/nonexistent/oscrc", "no config")
        real_get_config = conf.get_config
        calls = []

        def fake_get_config(*a, **kwargs):
            calls.append(1)
            if len(calls) == 1:
                raise err
            return real_get_config(*a, **kwargs)

        with unittest.mock.patch("osc.conf.get_config", side_effect=fake_get_config):
            with unittest.mock.patch("osc.conf.interactive_config_setup") as wizard:
                with unittest.mock.patch.dict(os.environ, {"OSC_CONFIG": self.oscrc}):
                    main.post_parse_args(args)
        wizard.assert_called_once()
        self.assertFalse(conf.config["non_interactive"])


class TestIsNonInteractiveRequested(unittest.TestCase):
    def test_cli_flag(self):
        self.assertTrue(conf.is_non_interactive_requested(True))

    def test_no_request(self):
        with unittest.mock.patch.dict(os.environ, {}, clear=False):
            os.environ.pop("OSC_NON_INTERACTIVE", None)
            self.assertFalse(conf.is_non_interactive_requested(False, {}))

    def test_env_var(self):
        with unittest.mock.patch.dict(os.environ, {"OSC_NON_INTERACTIVE": "1"}):
            self.assertTrue(conf.is_non_interactive_requested(False, {}))

    def test_empty_env_var_is_not_a_request(self):
        with unittest.mock.patch.dict(os.environ, {"OSC_NON_INTERACTIVE": ""}):
            self.assertFalse(conf.is_non_interactive_requested(False, {}))

    def test_setopt(self):
        with unittest.mock.patch.dict(os.environ, {}, clear=False):
            os.environ.pop("OSC_NON_INTERACTIVE", None)
            self.assertTrue(conf.is_non_interactive_requested(False, {"non_interactive": "true"}))


def _request_opts(**kwargs):
    opts = argparse.Namespace(
        all=False,
        brief=False,
        bugowner=False,
        days=None,
        diff=False,
        edit=False,
        exclude_target_project=None,
        force=False,
        group=None,
        incoming=False,
        interactive=False,
        involved_projects=False,
        keep_packages_locked=False,
        message=None,
        mine=False,
        no_devel=False,
        no_pager=False,
        non_interactive=False,
        or_revoke=False,
        package=None,
        project=None,
        source_buildstatus=False,
        state=None,
        superseded_request=None,
        target_package_filter=None,
        type=None,
        user=None,
    )
    for key, value in kwargs.items():
        setattr(opts, key, value)
    return opts


class TestRequestPreflightNonInteractive(NonInteractiveTestBase):
    """--non-interactive pre-validates request commands before any work happens."""

    def setUp(self):
        super().setUp()
        self.enable_non_interactive()

    def _osc(self):
        osc_self = unittest.mock.Mock()
        osc_self.get_api_url.return_value = "https://localhost"
        return osc_self

    def test_approvenew_refused_before_any_work(self):
        osc_self = self._osc()
        with self.assertRaises(oscerr.NonInteractiveInput) as ctx:
            Osc.do_request(osc_self, "request", _request_opts(), "approvenew", "myproject")
        self.assertIn("approvenew", str(ctx.exception))
        osc_self.get_api_url.assert_not_called()

    def test_state_commands_require_message_upfront(self):
        for cmd in ("accept", "decline", "reopen", "revoke", "wipe", "supersede"):
            with self.subTest(cmd=cmd):
                osc_self = self._osc()
                with self.assertRaises(oscerr.NonInteractiveInput) as ctx:
                    Osc.do_request(osc_self, "request", _request_opts(), cmd, "123")
                self.assertIn("-m/--message", str(ctx.exception))
                osc_self.get_api_url.assert_not_called()

    def test_accept_with_message_passes_preflight(self):
        request = unittest.mock.Mock()
        request.state.name = "new"
        request.actions = []
        request.get_actions.return_value = []
        request.reqid = "123"
        request.creator = "user"
        osc_self = self._osc()
        with (
            unittest.mock.patch("osc.core.get_request", return_value=request),
            unittest.mock.patch("osc.core.change_request_state", return_value="<ok/>") as change_state,
            contextlib.redirect_stdout(io.StringIO()),
        ):
            Osc.do_request(osc_self, "request", _request_opts(message="msg"), "accept", "123")
        change_state.assert_called_once()

    def test_show_edit_refused_with_alternative(self):
        osc_self = self._osc()
        with self.assertRaises(oscerr.NonInteractiveInput) as ctx:
            Osc.do_request(osc_self, "request", _request_opts(edit=True), "show", "123")
        self.assertIn("--edit", str(ctx.exception))
        osc_self.get_api_url.assert_not_called()

    def test_interactive_approvenew_not_refused(self):
        conf.config["non_interactive"] = False
        result = unittest.mock.Mock()
        result.actions = []
        result.state.name = "new"
        result.state.when = "2026-01-01T00:00:00"
        result.list_view.return_value = "123 new"
        osc_self = self._osc()
        fake_config = {
            "request_list_days": "0",
            "request_show_interactive": "",
            "request_show_source_buildstatus": "",
            "non_interactive": False,
        }
        with (
            unittest.mock.patch("osc.core.get_request_collection", return_value=[result]),
            unittest.mock.patch("osc.conf.config", fake_config),
            unittest.mock.patch("sys.stdin") as stdin,
            contextlib.redirect_stdout(io.StringIO()),
        ):
            stdin.read.return_value = "n"
            # pre-flight did not fire: the command proceeded into the
            # interactive confirmation, which aborts on "n"
            with self.assertRaises(oscerr.UserAbort):
                Osc.do_request(osc_self, "request", _request_opts(), "approvenew", "myproject")


if __name__ == "__main__":
    unittest.main()
