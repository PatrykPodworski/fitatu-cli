"""The Fitatu session: a token cached in a session file, refreshed or replaced by
a fresh login with the Keychain password when it expires."""

import base64
import json
import os
import subprocess
import tempfile
from collections.abc import Callable
from pathlib import Path
from typing import Any, cast
from urllib.error import HTTPError

from fitatu_cli.errors import FitatuCliError, unreadable

Json = dict[str, Any]
Http = Callable[[str, dict[str, str], Json | None, str], Json]

API_BASE = "https://en-gb.fitatu.com"
# Fitatu's public web-client key: the web app ships it to every browser, and
# AndekQR/fitatu-mcp-unofficial and Jezue/fitatu_library publish it.
API_SECRET = "PYRXtfs88UDJMuCCrNpLV"  # noqa: S105
# Fitatu's public web-client UUID: the web app ships it in its bundle and every
# browser sends it. Fitatu rejects a login from a UUID it does not know.
APP_UUID = "64c2d1b0-c8ad-11e8-8956-0242ac120008"
HEADERS = {
    "API-Key": "FITATU-MOBILE-APP",
    "API-Secret": API_SECRET,
    "APP-UUID": APP_UUID,
    "APP-Locale": "en_GB",
    "APP-Location-Country": "UNKNOWN",
    "APP-OS": "FITATU-WEB",
    "APP-SearchLocale": "pl_PL",
    "APP-StorageLocale": "en_GB",
    "APP-Version": "4.7.3",
    "Accept": "application/json; version=v3",
    "Accept-Language": "en-US,en;q=0.9",
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/148.0.0.0 Safari/537.36"
    ),
}
# Seconds before `exp` at which a token counts as expired, so a request never
# starts with a token about to run out. Tokens live 3600 s (exp - iat, measured
# 2026-10-11).
MARGIN = 60


def session_path() -> Path:
    return Path(os.environ.get("FITATU_SESSION", "~/.fitatu/session.json")).expanduser()


def load() -> Json:
    """The saved session. A missing or unreadable file is no session, and a token
    that does not decode is left out, so the command refreshes or logs in."""
    try:
        # ValueError covers JSONDecodeError and UnicodeDecodeError.
        session = json.loads(session_path().read_text())
    except (FileNotFoundError, ValueError):
        return {}
    if not isinstance(session, dict):
        return {}
    if session.get("token"):
        try:
            claims(session["token"])
        # A payload without a dot raises IndexError; bad base64 or JSON raise
        # ValueError.
        except (IndexError, ValueError):
            del session["token"]
    return session


def save(session: Json) -> None:
    """Writes a private temporary file beside the session file and renames it
    over the session file, so a parallel reader or an interrupted save never
    leaves a partial session behind."""
    path = session_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    # mkstemp creates the file readable and writable by its owner only.
    descriptor, temporary = tempfile.mkstemp(dir=path.parent)
    try:
        with os.fdopen(descriptor, "w") as file:
            json.dump(session, file)
        os.replace(temporary, path)
    except BaseException:
        os.unlink(temporary)
        raise


def headers(session: Json) -> dict[str, str]:
    return HEADERS | {
        "API-Cluster": f"en-gb{session['uid']}",
        "Authorization": f"Bearer {session['token']}",
    }


def claims(token: str) -> Json:
    payload = token.split(".")[1]
    # JWT strips the base64 padding.
    padded = payload + "=" * (-len(payload) % 4)
    return cast(Json, json.loads(base64.urlsafe_b64decode(padded)))


def email() -> str:
    address = os.environ.get("FITATU_EMAIL")
    if not address:
        raise FitatuCliError(
            "FITATU_EMAIL is not set.",
            "Run 'export FITATU_EMAIL=you@example.com' with your Fitatu account email.",
        )
    return address


def password(address: str) -> str:
    try:
        keychain = subprocess.run(  # noqa: S603
            ["security", "find-generic-password", "-s", "fitatu", "-a", address, "-w"],  # noqa: S607
            capture_output=True,
            text=True,
        )
    except FileNotFoundError:
        raise FitatuCliError(
            "Logging in to Fitatu reads the password from the macOS Keychain, which "
            "is not available here.",
            "Copy a session file from a Mac that ran 'fitatu auth login' and point "
            "FITATU_SESSION at it."
            if "FITATU_SESSION" in os.environ
            else "Log in on a Mac and copy ~/.fitatu/session.json to this machine, "
            "or set FITATU_SESSION to a copied session file.",
        ) from None
    if keychain.returncode != 0:
        raise FitatuCliError(
            f"No Keychain password for account {address} (service 'fitatu').",
            f"Add it with 'security add-generic-password -s fitatu -a {address} -w'.",
        )
    return keychain.stdout.rstrip("\n")


def store(response: Json, address: str | None) -> Json:
    """Saves the session from a login or refresh response, with the email it
    logged in with when that is known."""
    token = response.get("token")
    if not token:
        raise unreadable()
    session = {"token": token, "uid": str(claims(token)["id"])}
    if address:
        session["email"] = address
    if response.get("refresh_token"):
        session["refresh_token"] = response["refresh_token"]
    save(session)
    return session


def login(http: Http) -> Json:
    address = email()
    secret = password(address)
    try:
        response = http(
            f"{API_BASE}/api/login",
            HEADERS,
            {"_username": address, "_password": secret},
            "POST",
        )
    except HTTPError as error:
        if error.code in (400, 401, 422):
            raise FitatuCliError(
                f"Fitatu rejected the login for {address}.",
                "Check the Keychain password for service 'fitatu'.",
            ) from None
        raise
    return store(response, address)


def session(http: Http, now: Callable[[], float]) -> Json:
    """A session with a token valid for at least MARGIN seconds. A session saved
    for another account than FITATU_EMAIL is replaced by a login; one without an
    email, from an older version or copied, is used as it is."""
    current = load()
    recorded = current.get("email")
    address = os.environ.get("FITATU_EMAIL")
    if recorded and address and recorded != address:
        return login(http)
    if current.get("token") and claims(current["token"])["exp"] - MARGIN > now():
        return current
    if current.get("refresh_token"):
        try:
            response = http(
                f"{API_BASE}/api/token/refresh",
                HEADERS,
                {"refresh_token": current["refresh_token"]},
                "POST",
            )
        except HTTPError:
            pass
        else:
            return store(response, recorded)
    return login(http)
