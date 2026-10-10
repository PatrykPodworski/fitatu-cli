import argparse
from datetime import date, timedelta

import pytest

from fitatu_cli.cli import CliParser
from fitatu_cli.dates import add_date_argument, add_range_arguments


def parse(*argv: str) -> date:
    parser = argparse.ArgumentParser()
    add_date_argument(parser)
    day: date = parser.parse_args(argv).date
    return day


def test_date_defaults_to_today() -> None:
    assert parse() == date.today()


def test_date_today() -> None:
    assert parse("today") == date.today()


def test_date_yesterday() -> None:
    assert parse("yesterday") == date.today() - timedelta(days=1)


def test_date_iso() -> None:
    assert parse("2026-07-05") == date(2026, 7, 5)


@pytest.mark.parametrize("value", ["tomorrow", "2026-13-01"])
def test_invalid_date_exits_2_with_one_line(
    value: str, capsys: pytest.CaptureFixture[str]
) -> None:
    parser = CliParser(prog="fitatu demo")
    add_date_argument(parser)

    with pytest.raises(SystemExit) as exit:
        parser.parse_args([value])

    assert exit.value.code == 2
    assert capsys.readouterr().err == (
        f"fitatu: Invalid date '{value}'. Use today, yesterday or YYYY-MM-DD.\n"
    )


def test_range_parses_from_and_to() -> None:
    parser = argparse.ArgumentParser()
    add_range_arguments(parser, None)

    args = parser.parse_args(["--from", "2026-07-01", "--to", "yesterday"])

    assert (args.start, args.end) == (
        date(2026, 7, 1),
        date.today() - timedelta(days=1),
    )


@pytest.mark.parametrize(
    ("default", "help"),
    [
        (None, "--from DATE today | yesterday | YYYY-MM-DD --to"),
        (
            date(2026, 7, 5),
            "--from DATE today | yesterday | YYYY-MM-DD (default: today)",
        ),
    ],
)
def test_range_defaults_and_help(default: date | None, help: str) -> None:
    parser = argparse.ArgumentParser()
    add_range_arguments(parser, default)

    args = parser.parse_args([])

    assert (args.start, args.end) == (default, default)
    assert help in " ".join(parser.format_help().split())
