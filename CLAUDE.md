# fitatu-cli

Tracker: GitHub Issues

Synced with python-template at 2ace352.

This repository is public. Never commit real Fitatu data.

- Test fixtures and examples copied from real Fitatu responses must be anonymized
  before commit: replace food names, quantities, user IDs (`uid`), emails and tokens
  with made-up values. Keep only the fields the test needs.
- Tokens and passwords stay outside the repo. Never print them in logs or error
  messages.
- Command output pasted into issues or PRs follows the same rule.

## Agents

Agents are first-class users of this CLI. `skills/fitatu/SKILL.md` teaches an agent
when and how to run it. A change to a command, its output or its error messages
updates that file in the same pull request.

## Modules

Read commands are grouped by domain, one module per group. A command that changes
data on the service gets its own module, named `<group>_<verb>.py`, and imports
shared read helpers from its group. Time and date conversion lives in `dates.py`.

Commands follow gh's `<noun> <verb>` shape; `test_commands_are_nouns_with_standard_verbs`
in `tests/test_cli.py` holds the allowed verbs.

## Errors

An expected failure raises `FitatuCliError(problem, action)`; `main` prints it as one
stderr line, `fitatu: <What happened.> <What to do.>`, and exits 1. Argument errors
exit 2 with the same one-line shape.

## Testing

- Tests never touch the network. Pass a fake client to `main` through its
  `connect` argument.
- Fixtures are minimal hand-written dicts with made-up values, under the
  anonymization rule above.
- Each subcommand tests its happy path, its "missing field" path, and `--raw`
  where it exists.
- `uv run pytest` fails when branch coverage of `src/` drops below 90%.

## Checks

CI (`.github/workflows/ci.yml`) runs these on every pull request and push to `main`.

- `uv sync`
- `uv run mypy`
- `uv run pytest`
- `uv run ruff check`
- `uv run ruff format --check`
- `uv run typos`
- `uv run vulture`
- `uv run deptry src`
- `uv run zizmor .github`
- `uv run mutmut run` (score ≥ 80%, see below)

## Mutation testing

The CI `check` job runs `mutmut` on every pull request and push to `main` and fails
when the score (killed / (killed + survived + timeout + suspicious)) falls below 80%.
Run it locally with `uv run mutmut run`, then `uv run mutmut results` lists the
surviving mutants and `uv run mutmut show <name>` shows one.
