import io
import json
import subprocess
import urllib.request
from collections.abc import Callable
from http.client import IncompleteRead, RemoteDisconnected
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urlsplit

import pytest
from conftest import NOW, http_error, jwt

from fitatu_cli import client
from fitatu_cli.cli import main
from fitatu_cli.errors import FitatuCliError

LOGIN = "/api/login"
REFRESH = "/api/token/refresh"
DAY = "/api/diet-and-activity-plan/101/day/2026-07-05"
LOGGED_IN = {"token": jwt(NOW + 3600), "refresh_token": "fake-refresh"}
ISSUES = "https://github.com/PatrykPodworski/fitatu-cli/issues"
UNREADABLE = (
    "Fitatu sent a response fitatu-cli could not read. Fitatu may have changed its "
    f"API; rerun with --debug and report it at {ISSUES}."
)
RATE_LIMITED = (
    "Fitatu is rate-limiting requests from this machine. "
    "Wait a few minutes and try again."
)
OFFLINE = "Check your internet connection and try again."


class FakeUrlopen:
    """Answers a request for a path with the next item of `routes[path]`: bytes as
    the body, an exception to raise, anything else as JSON."""

    def __init__(self, routes: dict[str, list[Any]]) -> None:
        # A copy, since parametrized routes outlive one run.
        self.routes = {path: list(items) for path, items in routes.items()}
        self.requests: list[tuple[urllib.request.Request, float]] = []

    def __call__(self, request: urllib.request.Request, timeout: float) -> Any:
        self.requests.append((request, timeout))
        response = self.routes[urlsplit(request.full_url).path].pop(0)
        if isinstance(response, BaseException):
            raise response
        if not isinstance(response, bytes):
            response = json.dumps(response).encode()
        return io.BytesIO(response)


def serve(monkeypatch: pytest.MonkeyPatch, routes: dict[str, list[Any]]) -> FakeUrlopen:
    fake = FakeUrlopen(routes)
    monkeypatch.setattr(urllib.request, "urlopen", fake)
    return fake


def test_http_get(monkeypatch: pytest.MonkeyPatch) -> None:
    urlopen = serve(monkeypatch, {"/a": [{"ok": 1}]})

    assert client.http("https://example.com/a", {"API-Key": "k"}, None) == {"ok": 1}

    [(request, timeout)] = urlopen.requests
    assert request.get_method() == "GET"
    assert request.full_url == "https://example.com/a"
    assert request.data is None
    assert request.header_items() == [("Api-key", "k")]
    assert timeout == 20


def test_http_post_sends_json(monkeypatch: pytest.MonkeyPatch) -> None:
    urlopen = serve(monkeypatch, {"/a": [{"ok": 1}]})

    client.http("https://example.com/a", {"API-Key": "k"}, {"x": 1})

    [(request, _)] = urlopen.requests
    assert request.get_method() == "POST"
    assert json.loads(request.data) == {"x": 1}  # type: ignore[arg-type]
    assert dict(request.header_items()) == {
        "Api-key": "k",
        "Content-type": "application/json",
    }


def test_connect_returns_fitatu_client() -> None:
    connected = client.connect()

    assert isinstance(connected, client.FitatuClient)
    assert connected.http is client.http


def no_keychain(monkeypatch: pytest.MonkeyPatch, _: Path) -> None:
    monkeypatch.setattr(
        subprocess,
        "run",
        lambda argv, **_: subprocess.CompletedProcess(argv, 44, "", "not found"),
    )


def no_security(monkeypatch: pytest.MonkeyPatch, _: Path) -> None:
    def run(*args: Any, **kwargs: Any) -> Any:
        raise FileNotFoundError("security")

    monkeypatch.setattr(subprocess, "run", run)


def expired_session(_: pytest.MonkeyPatch, session: Path) -> None:
    session.parent.mkdir(parents=True)
    session.write_text(
        json.dumps(
            {
                "token": jwt(NOW),
                "refresh_token": "fake-refresh",
                "uid": "101",
                "app_uuid": "00000000-0000-1000-8000-000000000002",
            }
        )
    )


def nothing(_: pytest.MonkeyPatch, __: Path) -> None:
    pass


Setup = Callable[[pytest.MonkeyPatch, Path], None]


@pytest.mark.parametrize(
    ("setup", "routes", "message"),
    [
        pytest.param(
            lambda monkeypatch, _: monkeypatch.delenv("FITATU_EMAIL"),
            {},
            "FITATU_EMAIL is not set. Run 'export FITATU_EMAIL=you@example.com' "
            "with your Fitatu account email.",
            id="email-unset",
        ),
        pytest.param(
            no_keychain,
            {},
            "No Keychain password for account user@example.com (service 'fitatu'). "
            "Add it with 'security add-generic-password -s fitatu "
            "-a user@example.com -w'.",
            id="no-keychain-entry",
        ),
        pytest.param(
            no_security,
            {},
            "Logging in to Fitatu reads the password from the macOS Keychain, which "
            "is not available here. Copy a session file from a Mac that ran "
            "'fitatu login' and point FITATU_SESSION at it.",
            id="not-macos",
        ),
        pytest.param(
            nothing,
            {LOGIN: [http_error(422)]},
            "Fitatu rejected the login for user@example.com. Check the Keychain "
            "password for service 'fitatu'.",
            id="login-rejected",
        ),
        pytest.param(
            nothing,
            {LOGIN: [LOGGED_IN, LOGGED_IN], DAY: [http_error(401), http_error(401)]},
            "Fitatu did not accept a fresh login. Run 'fitatu login'; if it keeps "
            f"failing, the API may have changed — report it at {ISSUES}.",
            id="401-after-relogin",
        ),
        pytest.param(
            nothing, {LOGIN: [http_error(429)]}, RATE_LIMITED, id="429-on-login"
        ),
        pytest.param(
            nothing,
            {LOGIN: [LOGGED_IN], DAY: [http_error(429)]},
            RATE_LIMITED,
            id="429-on-data",
        ),
        pytest.param(
            nothing,
            {LOGIN: [URLError("[Errno 8] nodename nor servname provided")]},
            "Could not reach Fitatu (URLError: <urlopen error [Errno 8] nodename "
            f"nor servname provided>). {OFFLINE}",
            id="url-error",
        ),
        pytest.param(
            nothing,
            {LOGIN: [LOGGED_IN], DAY: [TimeoutError("The read operation timed out")]},
            "Could not reach Fitatu (TimeoutError: The read operation timed out). "
            f"{OFFLINE}",
            id="timeout",
        ),
        pytest.param(
            nothing,
            {LOGIN: [LOGGED_IN], DAY: [RemoteDisconnected("Remote end closed")]},
            "Could not reach Fitatu (RemoteDisconnected: Remote end closed). "
            f"{OFFLINE}",
            id="connection-dropped",
        ),
        pytest.param(
            nothing,
            {LOGIN: [LOGGED_IN], DAY: [IncompleteRead(b"{", 10)]},
            "Could not reach Fitatu (IncompleteRead: IncompleteRead(1 bytes read, 10 "
            f"more expected)). {OFFLINE}",
            id="body-cut-off",
        ),
        pytest.param(
            nothing,
            {LOGIN: [LOGGED_IN], DAY: [b"<html>Bad gateway</html>"]},
            UNREADABLE,
            id="not-json",
        ),
        pytest.param(nothing, {LOGIN: [b"\xff\xfe\xfa"]}, UNREADABLE, id="not-utf8"),
        pytest.param(
            nothing,
            {LOGIN: [{"refresh_token": "fake-refresh"}]},
            UNREADABLE,
            id="login-without-token",
        ),
        pytest.param(
            expired_session, {REFRESH: [{}]}, UNREADABLE, id="refresh-without-token"
        ),
        pytest.param(
            nothing,
            {LOGIN: [LOGGED_IN], DAY: [{"dietPlan": ["breakfast"]}]},
            UNREADABLE,
            id="diet-plan-not-dict",
        ),
        pytest.param(
            nothing,
            {LOGIN: [LOGGED_IN], DAY: [http_error(500)]},
            "Unexpected error (HTTPError: HTTP Error 500: error). Rerun with --debug "
            f"and report it at {ISSUES}.",
            id="server-error",
        ),
    ],
)
def test_error_prints_one_line(
    account: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    setup: Setup,
    routes: dict[str, list[Any]],
    message: str,
) -> None:
    setup(monkeypatch, account)
    serve(monkeypatch, routes)

    code = main(
        ["day", "2026-07-05"], connect=lambda: client.FitatuClient(now=lambda: NOW)
    )

    out = capsys.readouterr()
    assert (code, out.err, out.out) == (1, f"fitatu: {message}\n", "")


@pytest.mark.usefixtures("account")
def test_debug_raises_mapped_error_from_its_cause(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    serve(monkeypatch, {LOGIN: [http_error(429)]})

    with pytest.raises(FitatuCliError) as error:
        main(
            ["--debug", "day", "2026-07-05"],
            connect=lambda: client.FitatuClient(now=lambda: NOW),
        )

    assert str(error.value) == RATE_LIMITED
    assert isinstance(error.value.__cause__, HTTPError)
    assert error.value.__cause__.code == 429
