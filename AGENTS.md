# AGENTS.md — osc (openSUSE Commander)

Notes for AI agents working on this codebase. osc is the command-line client
for the Open Build Service (OBS).

## Python floor

Python **3.6** is the minimum supported version (`setup.cfg`
classifiers). f-strings are fine; no walrus operator, no `match`, no
`X | Y` annotations. `typing_extensions` is a conditional dependency for
<3.8 (used once, in `osc/core.py`).

## Layout

- `osc/babysitter.py` — entry point (`osc = osc.babysitter:main`). `run()`
  is the global exception handler mapping `oscerr.*` to messages/exit codes.
- `osc/commandline.py` — `OscMainCommand` (argparse) + the legacy `Osc`
  class with 96 `do_*` commands (11k lines, being migrated away).
- `osc/commands/` — new-style subcommands as argparse `Command` classes.
  **New commands go here; do not extend the legacy `do_*` methods.**
- `osc/commands_git/`, `osc/commandline_git.py`, `osc/gitea_api/` —
  the separate `git-obs` tool.
- `osc/conf.py` — the configuration system (see below).
- `osc/core.py` — legacy workhorse (Package/Project/Request). Being
  reimplemented cleanly in `osc/_private/`; use `_private` for new internals.
- `osc/obs_api/` — new typed object model (`Project`, `Package`).
- `osc/output/` — user-facing output: `input.py` (prompts), `output.py`
  (pager, `print_msg`), `tty.py`.
- `osc/util/helper.py` — **stateless** utilities (`raw_input` stdin funnel,
  `decode_it`, `format_table`). No configuration, no module-global state.
- `osc/oscerr.py` — exception hierarchy; all user-facing errors derive
  from `oscerr.OscBaseError`. New failure modes get a new subclass.
- `osc/credentials.py` — pluggable credential managers (config, keyring,
  transient). Passwords use the `Password` type, never plain strings in
  `Options`.
- `osc/cmdln.py` — vendored cmdln framework (do not modify lightly).

## Configuration system (`osc/conf.py`)

Config is a hand-rolled model framework (`osc/util/models.py`:
`BaseModel`/`Field`), not a dict:

- `Options` — ~100 global options, each a class attribute:
  ```python
  quiet: bool = Field(
      default=False,
      description=textwrap.dedent("""…"""),
  )  # type: ignore[assignment]
  ```
- `HostOptions` — per-`[apiurl]` section options.
- `OscOptions` adds dict-compat shims so `conf.config["quiet"]` works.

**Adding a new global option is one `Field(...)`** on `Options` with
`default=` and `description=` (the description renders into the Sphinx
docs via `_model_to_rst`). The ini key, `OSC_<NAME>` env var, `--setopt
name=value`, type coercion, and unknown-key errors all derive
automatically. Unknown `[general]` keys are **errors**, not warnings.

**Precedence** (documented in `get_config()`'s docstring), highest first:
explicit `override_*` kwargs > working-copy store apiurl > `OSC_*` env >
oscrc file > defaults.

`get_config()` runs once, from `OscMainCommand.post_parse_args()`
(`osc/commandline.py`). **Design rule: persistent user-facing knobs are
config options; ephemeral per-invocation switches are argparse flags**
mapped to `get_config()` `override_*` kwargs (follow the
`--quiet` → `override_quiet` pattern at `conf.py:1910`). Precedent for
both coexisting: `request_show_interactive` config option +
`--interactive` per-command flag, consulted as
`conf.config['request_show_interactive']` in `commandline.py`.

## Prompting

All stdin reads funnel through `osc/util/helper.py::raw_input()`
(EOF → `oscerr.UserAbort`). Choice prompts: `osc/output/input.py::
get_user_input()`. Passwords: `getpass.getpass` in `credentials.py` /
`conf.py`.

There is **no global "may I prompt" gate** — each site decides locally.
The established idiom for non-interactive paths is a per-call
`interactive=True` parameter (see `build.py::check_trusted_projects`),
not a module global. Output-layer modules already read
`conf.config[...]` directly (e.g. `osc/output/output.py` reads
`conf.config["verbose"]`), so consulting config at the prompt layer via
a lazy import is consistent.

## Conventions

- **Lazy imports everywhere** (`import-outside-toplevel` is disabled
  repo-wide in pylint config). Startup latency is a first-class concern;
  keep module import time low.
- Line length 120 (ruff format + pylint agree).
- Docstrings are user docs: a command's first docstring line becomes its
  help text; `Field(description=…)` becomes oscrc documentation.
- Interactive config-file creation lives in
  `conf.interactive_config_setup()`; `post_parse_args` retries
  `get_config()` after it.
- Backwards compatibility is enforced by CI: a pylint job runs 6
  downstream plugin repos against both master and the PR and diffs the
  logs — breaking the plugin API shows up there.

## Tests

- Framework: **`unittest`**, run with `python3 -m unittest` (after
  `pip install -e .`). Each `tests/test_*.py` ends with
  `if __name__ == '__main__': unittest.main()`.
- `tests/common.py` — shared offline harness (fixture-backed fake HTTP).
- Config tests: build an oscrc from a string fixture, call
  `osc.conf.get_config(override_conffile=…)`, assert on
  `osc.conf.config[...]` (see `tests/test_conf.py`).
- `behave/` — integration tests needing a live OBS server container;
  not runnable without podman.

## CI (`.github/workflows/`)

- `tests.yaml` — unittests on ubuntu-latest plus a distro container
  matrix (Fedora, Leap, Tumbleweed, SLE, CentOS Stream, Debian, Ubuntu)
  because `rpm` is not on PyPI; coverage → Codecov; then `behave`.
- `linters.yaml` — `mypy osc` (failures tolerated), `darker --check`
  (ruff format, changed lines only), `graylint` (`ruff check`),
  `pylint --errors-only`, and the plugin-compat job described above.
- `build-install.yaml` — build/install smoke test across distros.
