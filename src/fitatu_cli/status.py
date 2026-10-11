import argparse
from typing import Any

from fitatu_cli.client import Connect
from fitatu_cli.errors import FitatuCliError


def status(args: argparse.Namespace, connect: Connect) -> Any:
    response = connect().get_status()
    if args.raw:
        return response
    if response.get("state") is None:
        raise FitatuCliError("No status yet.", "Try again in a few minutes.")
    return {
        "state": response["state"],
        "updated_at": response.get("updatedAt"),
        "load": response.get("load"),
    }


def register(subparsers: "argparse._SubParsersAction[argparse.ArgumentParser]") -> None:
    status_parser = subparsers.add_parser("status", help="service status")
    status_parser.add_argument(
        "--raw", action="store_true", help="print the full service response"
    )
    status_parser.set_defaults(run=status)
