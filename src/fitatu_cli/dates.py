import argparse
from datetime import date, datetime, timedelta


def parse_date(value: str) -> date:
    if value == "today":
        return date.today()
    if value == "yesterday":
        return date.today() - timedelta(days=1)
    try:
        return datetime.strptime(value, "%Y-%m-%d").date()
    except ValueError:
        raise argparse.ArgumentTypeError(
            f"Invalid date '{value}'. Use today, yesterday or YYYY-MM-DD."
        ) from None


def add_date_argument(parser: argparse._ActionsContainer) -> None:
    parser.add_argument(
        "date",
        nargs="?",
        default=date.today(),
        type=parse_date,
        help="today | yesterday | YYYY-MM-DD (default: today)",
    )


def add_range_arguments(parser: argparse.ArgumentParser, default: date | None) -> None:
    help = "today | yesterday | YYYY-MM-DD"
    if default:
        help += " (default: today)"
    for flag, dest in (("--from", "start"), ("--to", "end")):
        parser.add_argument(
            flag, dest=dest, metavar="DATE", default=default, type=parse_date, help=help
        )


def timestamp(moment: datetime) -> str:
    """Local time as Fitatu's diary writes take it."""
    return f"{moment:%Y-%m-%d %H:%M:%S}"
