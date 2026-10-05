# AGENTS.md — osc

`osc` is the command-line client for the Open Build Service (OBS).
`git-obs` is the command-line client for the Git Packaging Workflow on top of OBS.

## Project structure - osc

- `osc/commands/` - osc CLI commands.
- `osc/commandline.py` - CLI setup and legacy `do_*` commands. Do not add new ones.
- `osc/obs_api/` - typed OBS API objects.
- `osc/conf.py` - configuration and `oscrc` handling.
- `osc/core.py` - legacy API and implementation. Use and extend `obs_api` instead if applicable.
- `osc/credentials.py` - credential handling.
- `osc/oscerr.py` - osc-specific exception hierarchy.
- `osc/output/` - user-facing output, prompts and TTY handling.
- `osc/util/` - shared utilities.
- `osc/cmdln.py` - vendored framework. Do not modify.
- `osc/babysitter.py` - entry point; maps `oscerr.*` to messages and exit codes.
- `osc/_private/` - new internals. Prefer over the legacy `osc/core.py`.

## Project structure - git-obs

- `osc/commands_git/` - git-obs CLI commands.
- `osc/commandline_git.py` - CLI setup.
- `osc/gitea_api/` - typed Gitea API objects.
- `osc/gitea_api/conf.py` - configuration and `~/.config/tea/config.yml` handling.

## Development rules

- Minimal changes leading to the requested behavior.
- Python 3.6 is the floor. f-strings yes; no walrus, no `match`, no `X | Y`.
- Preferred line length <= 120.
- Use `oscerr.OscBaseError` subclasses for new osc-specific error conditions.
- Configuration descriptions are used to generate documentation.
- Use attributes of the configuration objects, avoid legacy dict interface.
- Keep imports lazy where practical; startup time matters.
- Preserve backwards compatibility, especially the public and plugin API.

## Adding a command

- Add module in `osc/commands/<name>.py` with a `Command` subclass.
- Modules are auto-discovered, no registration needed.
- Docstring is user-facing help: `help` (1 line), empty line, description.

## Handling input

- Use `osc.util.helper.raw_input()` for normal stdin input. EOF raises `oscerr.UserAbort`.
- Use `osc.output.input.get_user_input()` for choice prompts.

## Tests

- `tests` - unit tests
  - Run `python3 -m unittest` after `pip install -e .`.
  - Simple, fast, offline tests. Avoid mocking unless necessary.
  - `tests/common.py` - shared harness.
- `behave` - integration tests
  - Require an OBS/podman environment.
- Linters
  - Code is old and has many issues, focus on diffs to produce new clean code.
  - `darker --check --line-length=120 --formatter ruff .`
  - `ruff check .`
  - `pylint --errors-only osc`
