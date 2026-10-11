import argparse

from fitatu_cli import auth
from fitatu_cli.client import Connect


def login(_args: argparse.Namespace, connect: Connect) -> dict[str, str]:
    connect().login()
    return {"session": str(auth.session_path())}


def register(subparsers: "argparse._SubParsersAction[argparse.ArgumentParser]") -> None:
    auth_parser = subparsers.add_parser("auth", help="log in to Fitatu")
    login_parser = auth_parser.add_subparsers(required=True).add_parser(
        "login",
        help="log in as FITATU_EMAIL with the Keychain password, save the session",
    )
    login_parser.set_defaults(run=login, parser=login_parser)
