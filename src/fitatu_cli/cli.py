"""`fitatu` entry point. A subcommand gets the parsed args and a `connect`
function, returns JSON-serializable data, and `main` prints it to stdout."""

import argparse
import difflib
import json
import re
import sys
from collections.abc import Mapping
from typing import Any, NoReturn, cast

from fitatu_cli import client, day, login
from fitatu_cli.client import Connect
from fitatu_cli.errors import ISSUES, FitatuCliError, reason

NAME = "fitatu"
REQUIRED = "the following arguments are required: "


class CliParser(argparse.ArgumentParser):
    """Reports an argument error on one stderr line, `fitatu: <problem> <action>`,
    instead of a usage block."""

    def __init__(self, **kwargs: Any) -> None:
        super().__init__(**{**kwargs, "allow_abbrev": False})

    @property
    def subparsers(
        self,
    ) -> "argparse._SubParsersAction[argparse.ArgumentParser] | None":
        for action in self._actions:
            if isinstance(action, argparse._SubParsersAction):
                return action
        return None

    @property
    def commands(self) -> Mapping[str, argparse.ArgumentParser]:
        return self.subparsers.choices if self.subparsers else {}

    @property
    def listed(self) -> list[str]:
        """The commands `--help` lists: those registered with a `help`."""
        if not self.subparsers:
            return []
        return [action.dest for action in self.subparsers._get_subactions()]

    def fail(self, message: str) -> NoReturn:
        self.exit(2, f"{NAME}: {message}\n")

    def error(self, message: str) -> NoReturn:
        self.fail(self.explain(message))

    def explain(self, message: str) -> str:
        detail = re.sub(r"^argument [^:]+: ", "", message)
        # argparse's own messages start lowercase; type functions raise final ones.
        if detail[0].isupper():
            return detail
        option = message.removeprefix("argument ").partition(":")[0]
        if detail == "expected one argument":
            return f"Option '{option}' needs a value. Run '{self.prog} --help'."
        if value := re.match(r"ignored explicit argument '(.*)'", detail):
            return f"Option '{option}' takes no value. Remove '={value[1]}'."
        if self.listed and (choice := re.match(r"invalid choice: '(.*?)'", detail)):
            name = choice[1]
            if match := difflib.get_close_matches(name, self.listed):
                return f"Unknown command '{name}'. Did you mean '{match[0]}'?"
            return f"Unknown command '{name}'. {self.run_command()}"
        if detail.startswith(REQUIRED):
            name = detail.removeprefix(REQUIRED)
            # argparse names the command argument by its metavar.
            if self.subparsers and name == self.subparsers.metavar:
                return f"No command given. {self.run_command()}"
            return f"Missing {name} for '{self.prog}'. Run '{self.prog} --help'."
        return f"{message[0].upper()}{message[1:]}. Run '{self.prog} --help'."

    def run_command(self) -> str:
        return f"Run '{self.prog} <command>', one of: {', '.join(self.listed)}."

    def reject(self, argv: list[str], args: argparse.Namespace, arg: str) -> NoReturn:
        """Reports an argument the parser of the parsed command did not consume."""
        command = args.command
        subparser = self.commands[command]
        prog = subparser.prog
        help = f"Run '{prog} --help' for all options."
        if not arg.startswith("-"):
            self.fail(f"Unexpected argument '{arg}' for '{prog}'. {help}")
        options = [
            option for action in subparser._actions for option in action.option_strings
        ]
        # The command's parser consumes its own options, so one left over came
        # before the command.
        if arg.partition("=")[0] in options:
            rest = list(argv)
            rest.remove(arg)
            rest.insert(rest.index(command) + 1, arg)
            self.fail(
                f"Option '{arg}' goes after the command. Run '{NAME} {' '.join(rest)}'."
            )
        problem = f"Unknown option '{arg}' for '{prog}'."
        if match := difflib.get_close_matches(arg, options):
            problem += f" Did you mean '{match[0]}'?"
        self.fail(f"{problem} {help}")


def round_floats(value: Any) -> Any:
    if isinstance(value, float):
        return round(value, 2)
    if isinstance(value, dict):
        return {key: round_floats(item) for key, item in value.items()}
    if isinstance(value, list):
        return [round_floats(item) for item in value]
    return value


def build_parser() -> CliParser:
    parser = CliParser(prog=NAME, description="Read your Fitatu food diary as JSON.")
    parser.add_argument(
        "--debug",
        action="store_true",
        help="show the full traceback on errors",
    )
    # Subparsers are CliParsers too; the cast matches the invariant type the
    # `register` functions take.
    subparsers = cast(
        "argparse._SubParsersAction[argparse.ArgumentParser]",
        parser.add_subparsers(dest="command", required=True),
    )
    login.register(subparsers)
    day.register(subparsers)
    subparsers.metavar = f"{{{','.join(parser.listed)}}}"
    return parser


def main(argv: list[str] | None = None, connect: Connect = client.connect) -> int:
    parser = build_parser()
    if argv is None:
        argv = sys.argv[1:]
    args, extras = parser.parse_known_args(argv)
    if extras:
        parser.reject(argv, args, extras[0])
    try:
        result = args.run(args, connect)
    except Exception as error:
        if args.debug:
            raise
        message = (
            str(error)
            if isinstance(error, FitatuCliError)
            else f"Unexpected error ({reason(error)}). "
            f"Rerun with --debug and report it at {ISSUES}."
        )
    else:
        if not getattr(args, "raw", False):
            result = round_floats(result)
        print(json.dumps(result, indent=2))
        return 0
    print(f"{NAME}: {message}", file=sys.stderr)
    return 1
