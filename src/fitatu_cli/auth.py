"""The Fitatu session: a token cached in a session file, refreshed or replaced by
a fresh login with the Keychain password when it expires."""

import base64
import json
import os
import subprocess
from collections.abc import Callable
from pathlib import Path
from typing import Any, cast
from urllib.error import HTTPError

from fitatu_cli.errors import FitatuCliError, unreadable

Json = dict[str, Any]
Http = Callable[[str, dict[str, str], Json | None], Json]

API_BASE = "https://en-gb.fitatu.com"
# Fitatu's public web-client key: the web app ships it to every browser, and
# AndekQR/fitatu-mcp-unofficial and Jezue/fitatu_library publish it.
API_SECRET = "PYRXtfs88UDJMuCCrNpLV"  # noqa: S105
HEADERS = {
    "API-Key": "FITATU-MOBILE-APP",
    "API-Secret": API_SECRET,
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
    try:
        return cast(Json, json.loads(session_path().read_text()))
    except FileNotFoundError:
        return {}


def save(session: Json) -> None:
    path = session_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    # O_CREAT applies the mode only to a new file.
    os.fchmod(descriptor, 0o600)
    with os.fdopen(descriptor, "w") as file:
        json.dump(session, file)


def headers(session: Json) -> dict[str, str]:
    return HEADERS | {
        "APP-UUID": session["app_uuid"],
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


def app_uuid() -> str:
    """Fitatu accepts a login only from a device UUID it already knows for the
    account; a new one gets a 500 or 422."""
    value = os.environ.get("FITATU_APP_UUID")
    if not value:
        raise FitatuCliError(
            "FITATU_APP_UUID is not set.",
            "Copy the APP-UUID request header from the Fitatu web app (browser dev "
            "tools, Network tab) and run 'export FITATU_APP_UUID=<value>'.",
        )
    return value


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
            "Copy a session file from a Mac that ran 'fitatu login' and point "
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


def store(response: Json, device: str) -> Json:
    """Saves the session from a login or refresh response."""
    token = response.get("token")
    if not token:
        raise unreadable()
    session = {"token": token, "uid": str(claims(token)["id"]), "app_uuid": device}
    if response.get("refresh_token"):
        session["refresh_token"] = response["refresh_token"]
    save(session)
    return session


def login(http: Http) -> Json:
    address = email()
    device = app_uuid()
    secret = password(address)
    try:
        response = http(
            f"{API_BASE}/api/login",
            HEADERS | {"APP-UUID": device},
            {"_username": address, "_password": secret},
        )
    except HTTPError as error:
        if error.code in (400, 401, 422):
            raise FitatuCliError(
                f"Fitatu rejected the login for {address}.",
                "Check the Keychain password for service 'fitatu' and FITATU_APP_UUID.",
            ) from None
        raise
    return store(response, device)


def session(http: Http, now: Callable[[], float]) -> Json:
    """A session with a token valid for at least MARGIN seconds."""
    current = load()
    if current.get("token") and claims(current["token"])["exp"] - MARGIN > now():
        return current
    if current.get("refresh_token"):
        try:
            response = http(
                f"{API_BASE}/api/token/refresh",
                HEADERS | {"APP-UUID": current["app_uuid"]},
                {"refresh_token": current["refresh_token"]},
            )
        except HTTPError:
            pass
        else:
            return store(response, current["app_uuid"])
    return login(http)
