import argparse
import sys
from typing import Any

import pytest
from conftest import FakeClient

from fitatu_cli import login
from fitatu_cli.cli import CliParser, build_parser, main, round_floats
from fitatu_cli.errors import FitatuCliError


class RaisingClient:
    def __init__(self, error: BaseException) -> None:
        self.error = error

    def get(self, path: str) -> Any:
        raise self.error


@pytest.fixture
def read_command(monkeypatch: pytest.MonkeyPatch) -> None:
    """Adds a `status view` command with a `--raw` flag, the shape of a read
    command. Its text output is the `state` field."""
    register_login = login.register

    def register(
        subparsers: "argparse._SubParsersAction[argparse.ArgumentParser]",
    ) -> None:
        register_login(subparsers)
        status = subparsers.add_parser("status", help="service status")
        view = status.add_subparsers(required=True).add_parser(
            "view", help="show the service status"
        )
        view.add_argument(
            "--raw", action="store_true", help="print the full service response"
        )
        view.set_defaults(
            run=lambda args, connect: connect().get("/status"),
            text=lambda result: f"state: {result['state']}",
            parser=view,
        )

    monkeypatch.setattr(login, "register", register)


def test_help_exits_0(capsys: pytest.CaptureFixture[str]) -> None:
    with pytest.raises(SystemExit) as exit:
        main(["--help"])

    assert exit.value.code == 0
    help_text = " ".join(capsys.readouterr().out.split())
    assert "usage: fitatu" in help_text
    assert "{auth,day,food,recipe}" in help_text
    assert "auth log in to Fitatu" in help_text
    assert "--debug show the full traceback on errors" in help_text


@pytest.mark.usefixtures("read_command")
def test_subcommand_help_exits_0(capsys: pytest.CaptureFixture[str]) -> None:
    with pytest.raises(SystemExit) as exit:
        main(["status", "view", "--help"])

    assert exit.value.code == 0
    help_text = " ".join(capsys.readouterr().out.split())
    assert help_text.startswith("usage: fitatu status view")
    assert "--raw print the full service response" in help_text


STATUS_HELP = "Run 'fitatu status view --help' for all options."


@pytest.mark.usefixtures("read_command")
@pytest.mark.parametrize(
    ("argv", "message"),
    [
        (
            [],
            "No command given. Run 'fitatu <command>', one of: "
            "auth, status, day, food, recipe.",
        ),
        (["statu"], "Unknown command 'statu'. Did you mean 'status'?"),
        (
            ["xyz"],
            "Unknown command 'xyz'. Run 'fitatu <command>', one of: "
            "auth, status, day, food, recipe.",
        ),
        (
            ["status"],
            "No command given. Run 'fitatu status <command>', one of: view.",
        ),
        (["status", "vie"], "Unknown command 'vie'. Did you mean 'view'?"),
        (
            ["status", "view", "--rwa"],
            "Unknown option '--rwa' for 'fitatu status view'. Did you mean '--raw'? "
            f"{STATUS_HELP}",
        ),
        (
            ["status", "view", "--xyz"],
            f"Unknown option '--xyz' for 'fitatu status view'. {STATUS_HELP}",
        ),
        (
            ["status", "view", "extra"],
            f"Unexpected argument 'extra' for 'fitatu status view'. {STATUS_HELP}",
        ),
        (["status", "view", "--raw=1"], "Option '--raw' takes no value. Remove '=1'."),
        (
            ["--raw", "status", "view"],
            "Option '--raw' goes after the command. Run 'fitatu status view --raw'.",
        ),
        (
            ["status", "--raw", "view"],
            "Option '--raw' goes after the command. Run 'fitatu status view --raw'.",
        ),
        (
            ["--debug", "--raw=1", "status", "view"],
            "Option '--raw=1' goes after the command. "
            "Run 'fitatu --debug status view --raw=1'.",
        ),
    ],
)
def test_argument_error_exits_2_with_one_line(
    argv: list[str], message: str, capsys: pytest.CaptureFixture[str]
) -> None:
    with pytest.raises(SystemExit) as exit:
        main(argv, connect=FakeClient)

    assert exit.value.code == 2
    out = capsys.readouterr()
    assert out.err == f"fitatu: {message}\n"
    assert out.out == ""


@pytest.mark.usefixtures("read_command")
def test_reads_sys_argv_by_default(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setattr(sys, "argv", ["fitatu", "--raw", "status", "view"])

    with pytest.raises(SystemExit):
        main(connect=FakeClient)

    assert capsys.readouterr().err == (
        "fitatu: Option '--raw' goes after the command. "
        "Run 'fitatu status view --raw'.\n"
    )


@pytest.mark.parametrize(
    ("argv", "message"),
    [
        (
            ["login"],
            "Unknown command 'login'. Run 'fitatu <command>', one of: "
            "auth, day, food, recipe.",
        ),
        (
            ["day", "2026-07-05"],
            "Unknown command '2026-07-05'. "
            "Run 'fitatu day <command>', one of: view, list.",
        ),
        (
            ["day", "--from", "2026-07-05"],
            "Unknown command '2026-07-05'. "
            "Run 'fitatu day <command>', one of: view, list.",
        ),
        (["day"], "No command given. Run 'fitatu day <command>', one of: view, list."),
        (["auth"], "No command given. Run 'fitatu auth <command>', one of: login."),
    ],
)
def test_old_command_name_exits_2(
    argv: list[str], message: str, capsys: pytest.CaptureFixture[str]
) -> None:
    with pytest.raises(SystemExit) as exit:
        main(argv, connect=FakeClient)

    assert exit.value.code == 2
    assert capsys.readouterr().err == f"fitatu: {message}\n"


VERBS = {"list", "view", "create", "edit", "delete", "set", "login", "search"}


def off_convention(parser: CliParser) -> list[str]:
    """Commands that break gh's `<noun> <verb>` shape: a top-level command that is
    not a group, or a subcommand whose name is not in VERBS."""
    wrong = []
    for noun, group in parser.commands.items():
        verbs = group.commands if isinstance(group, CliParser) else {}
        if not verbs:
            wrong.append(noun)
        wrong += [f"{noun} {verb}" for verb in verbs if verb not in VERBS]
    return wrong


def test_commands_are_nouns_with_standard_verbs() -> None:
    assert off_convention(build_parser()) == []


def test_off_convention_names_a_bare_command_and_an_unknown_verb() -> None:
    parser = CliParser(prog="fitatu")
    commands = parser.add_subparsers()
    commands.add_parser("login")
    day = commands.add_parser("day").add_subparsers()
    day.add_parser("view")
    day.add_parser("show")

    assert off_convention(parser) == ["login", "day show"]


def parse_error(parser: CliParser, argv: list[str], capsys: Any) -> str:
    with pytest.raises(SystemExit) as exit:
        parser.parse_args(argv)

    assert exit.value.code == 2
    err: str = capsys.readouterr().err
    assert err.count("\n") == 1
    return err


def test_missing_argument_generic_message(capsys: pytest.CaptureFixture[str]) -> None:
    parser = CliParser(prog="fitatu demo")
    parser.add_argument("name")

    assert parse_error(parser, [], capsys) == (
        "fitatu: Missing name for 'fitatu demo'. Run 'fitatu demo --help'.\n"
    )


def test_option_needs_value(capsys: pytest.CaptureFixture[str]) -> None:
    parser = CliParser(prog="fitatu demo")
    parser.add_argument("--limit")

    assert parse_error(parser, ["--limit"], capsys) == (
        "fitatu: Option '--limit' needs a value. Run 'fitatu demo --help'.\n"
    )


def test_type_error_message_is_kept(capsys: pytest.CaptureFixture[str]) -> None:
    def positive(value: str) -> int:
        raise argparse.ArgumentTypeError(f"Invalid --limit '{value}'. Use 1 or more.")

    parser = CliParser(prog="fitatu demo")
    parser.add_argument("--limit", type=positive)

    assert parse_error(parser, ["--limit", "0"], capsys) == (
        "fitatu: Invalid --limit '0'. Use 1 or more.\n"
    )


def test_invalid_choice_on_subcommand_generic_message(
    capsys: pytest.CaptureFixture[str],
) -> None:
    parser = CliParser(prog="fitatu")
    demo = parser.add_subparsers().add_parser("demo")
    demo.add_argument("--unit", choices=["kg", "lb"])

    err = parse_error(parser, ["demo", "--unit", "st"], capsys)

    # Python 3.12 patch releases differ in how they quote the choices.
    assert err.startswith("fitatu: Argument --unit: invalid choice: 'st' (choose")
    assert err.endswith("). Run 'fitatu demo --help'.\n")


def test_parser_without_commands_lists_none() -> None:
    parser = CliParser(prog="fitatu")

    assert parser.commands == {}
    assert parser.listed == []


@pytest.mark.usefixtures("read_command")
def test_prints_text_by_default(capsys: pytest.CaptureFixture[str]) -> None:
    client = FakeClient(get={"state": "ok", "load": 0.5})

    assert main(["status", "view"], connect=lambda: client) == 0
    assert capsys.readouterr().out == "state: ok\n"


@pytest.mark.usefixtures("read_command")
@pytest.mark.parametrize("flag", ["--json", "--raw"])
def test_prints_json_indented_by_2(
    flag: str, capsys: pytest.CaptureFixture[str]
) -> None:
    client = FakeClient(get={"x": [1]})

    assert main(["status", "view", flag], connect=lambda: client) == 0
    assert capsys.readouterr().out == '{\n  "x": [\n    1\n  ]\n}\n'


UNEXPECTED = (
    "Rerun with --debug and report it at "
    "https://github.com/PatrykPodworski/fitatu-cli/issues."
)


@pytest.mark.usefixtures("read_command")
@pytest.mark.parametrize(
    ("error", "message"),
    [
        (FitatuCliError("Not ready.", "Wait."), "Not ready. Wait."),
        (
            RuntimeError("first line\nsecond line with fake-secret"),
            f"Unexpected error (RuntimeError: first line). {UNEXPECTED}",
        ),
        (
            RuntimeError("x" * 200),
            f"Unexpected error (RuntimeError: {'x' * 86}). {UNEXPECTED}",
        ),
        (
            ConnectionError("Max retries exceeded with url: /sso?ticket=fake (no)"),
            "Unexpected error (ConnectionError: Max retries exceeded with url: "
            f"/sso?… (no)). {UNEXPECTED}",
        ),
        (
            PermissionError("401 for Authorization: Bearer fake.token"),
            "Unexpected error (PermissionError: 401 for Authorization: Bearer …). "
            f"{UNEXPECTED}",
        ),
        (KeyError("x"), f"Unexpected error (KeyError: 'x'). {UNEXPECTED}"),
    ],
)
def test_error_exits_1_with_message(
    error: Exception, message: str, capsys: pytest.CaptureFixture[str]
) -> None:
    client: Any = RaisingClient(error)

    assert main(["status", "view"], connect=lambda: client) == 1
    out = capsys.readouterr()
    assert out.err == f"fitatu: {message}\n"
    assert out.out == ""


@pytest.mark.usefixtures("read_command")
def test_debug_reraises_unexpected_error() -> None:
    client: Any = RaisingClient(KeyError("x"))

    with pytest.raises(KeyError):
        main(["--debug", "status", "view"], connect=lambda: client)


@pytest.mark.usefixtures("read_command")
def test_debug_reraises_expected_error() -> None:
    client: Any = RaisingClient(FitatuCliError("Not ready.", "Wait."))

    with pytest.raises(FitatuCliError) as error:
        main(["--debug", "status", "view"], connect=lambda: client)

    assert str(error.value) == "Not ready. Wait."


@pytest.mark.usefixtures("read_command")
def test_keyboard_interrupt_is_not_caught() -> None:
    client: Any = RaisingClient(KeyboardInterrupt())

    with pytest.raises(KeyboardInterrupt):
        main(["status", "view"], connect=lambda: client)


@pytest.mark.usefixtures("read_command")
def test_summary_rounds_floats_raw_does_not(
    capsys: pytest.CaptureFixture[str],
) -> None:
    client = FakeClient(get={"state": "ok", "load": 0.800000011920929})

    assert main(["status", "view", "--json"], connect=lambda: client) == 0
    assert '"load": 0.8\n' in capsys.readouterr().out
    assert main(["status", "view", "--raw"], connect=lambda: client) == 0
    assert '"load": 0.800000011920929\n' in capsys.readouterr().out


def test_round_floats_walks_dicts_and_lists() -> None:
    value = {
        "a": 0.800000011920929,
        "b": [4056.409912109375, {"c": 124.0}],
        "d": 7,
        "e": "x",
        "f": None,
        "g": True,
    }

    result = round_floats(value)

    assert result == {
        "a": 0.8,
        "b": [4056.41, {"c": 124.0}],
        "d": 7,
        "e": "x",
        "f": None,
        "g": True,
    }
    assert result["g"] is True
