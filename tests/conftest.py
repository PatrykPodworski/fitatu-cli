import base64
import json
import subprocess
from collections.abc import Callable
from email.message import Message
from pathlib import Path
from typing import Any, cast
from urllib.error import HTTPError

import pytest

from fitatu_cli.cli import main


class FakeClient:
    """Returns `responses[name]` for any `client.name(...)`, or raises it when it is
    an exception, and records the call."""

    def __init__(self, **responses: Any) -> None:
        self.responses = responses
        self.calls: list[tuple[str, tuple[Any, ...], dict[str, Any]]] = []

    def __getattr__(self, name: str) -> Callable[..., Any]:
        if name not in self.responses:
            raise AttributeError(name)

        def method(*args: Any, **kwargs: Any) -> Any:
            self.calls.append((name, args, kwargs))
            response = self.responses[name]
            if isinstance(response, BaseException):
                raise response
            return response

        return method


def run_json(argv: list[str], client: Any, capsys: pytest.CaptureFixture[str]) -> Any:
    assert main(argv, connect=lambda: client) == 0
    return json.loads(capsys.readouterr().out)


def run_text(argv: list[str], client: Any, capsys: pytest.CaptureFixture[str]) -> str:
    assert main(argv, connect=lambda: client) == 0
    return capsys.readouterr().out


Json = dict[str, Any]
NOW = 1_800_000_000
EMAIL = "user@example.com"
APP_UUID = "64c2d1b0-c8ad-11e8-8956-0242ac120008"
KEYCHAIN = ["security", "find-generic-password", "-s", "fitatu", "-a", EMAIL, "-w"]


def jwt(exp: int, uid: int = 101) -> str:
    """A fake token: Fitatu reads only the `id` and `exp` claims of its payload."""
    claims = json.dumps({"id": uid, "exp": exp}).encode()
    return f"header.{base64.urlsafe_b64encode(claims).decode().rstrip('=')}.sig"


def http_error(code: int) -> HTTPError:
    return HTTPError("https://example.com", code, "error", Message(), None)


class FakeHttp:
    """Answers a request for `path` with the next item of `routes[path]`, or raises
    it when it is an exception, and records the call."""

    def __init__(self, routes: dict[str, list[Any]]) -> None:
        self.routes = routes
        self.calls: list[tuple[str, dict[str, str], Json | None]] = []
        self.methods: list[str | None] = []

    def __call__(
        self,
        url: str,
        headers: dict[str, str],
        body: Json | None,
        method: str | None = None,
    ) -> Json:
        path = url.removeprefix("https://en-gb.fitatu.com")
        self.calls.append((path, headers, body))
        self.methods.append(method)
        response = self.routes[path].pop(0)
        if isinstance(response, BaseException):
            raise response
        return cast(Json, response)

    @property
    def paths(self) -> list[str]:
        return [path for path, _, _ in self.calls]


@pytest.fixture
def account(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> Path:
    """A Fitatu account with a Keychain password and no saved session; returns
    the session path."""
    session = tmp_path / "config" / "fitatu" / "session.json"
    monkeypatch.setenv("FITATU_EMAIL", EMAIL)
    monkeypatch.setenv("FITATU_SESSION", str(session))

    def security(argv: list[str], **kwargs: Any) -> subprocess.CompletedProcess[str]:
        assert argv == KEYCHAIN
        assert kwargs == {"capture_output": True, "text": True}
        return subprocess.CompletedProcess(argv, 0, "fake password \n", "")

    monkeypatch.setattr(subprocess, "run", security)
    return session
