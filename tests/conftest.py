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

Json = dict[str, Any]


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


SAVED = [{"date": "2026-07-05", "revision": 3, "errorMessage": None}]


class DiaryClient:
    """Answers `get(path)` with `gets[path]` and `post` with `saved`, or raises
    either when it is an exception; records the calls."""

    def __init__(self, gets: dict[str, Any], saved: Any = SAVED) -> None:
        self.gets = gets
        self.saved = saved
        self.calls: list[tuple[Any, ...]] = []

    def get(self, path: str) -> Any:
        self.calls.append(("get", path))
        response = self.gets[path]
        if isinstance(response, BaseException):
            raise response
        return response

    def post(self, path: str, body: Json) -> Any:
        self.calls.append(("post", path, body))
        if isinstance(self.saved, BaseException):
            raise self.saved
        return self.saved


SEARCH = "/api/search/food/user/{{uid}}?phrase=&page={page}&limit=100"


class SearchClient:
    """Answers search page N with `pages[N - 1]`, and an empty page after the last,
    and records the paths."""

    def __init__(self, *pages: Any) -> None:
        self.pages = pages
        self.paths: list[str] = []

    def get(self, path: str) -> Any:
        self.paths.append(path)
        for number, page in enumerate(self.pages, start=1):
            if path == SEARCH.format(page=number):
                return page
        assert path == SEARCH.format(page=len(self.pages) + 1)
        return []


def run_json(argv: list[str], client: Any, capsys: pytest.CaptureFixture[str]) -> Any:
    assert main(argv, connect=lambda: client) == 0
    return json.loads(capsys.readouterr().out)


def run_text(argv: list[str], client: Any, capsys: pytest.CaptureFixture[str]) -> str:
    assert main(argv, connect=lambda: client) == 0
    return capsys.readouterr().out


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
        self.calls: list[tuple[str, dict[str, str], Json | None, str]] = []

    def __call__(
        self, url: str, headers: dict[str, str], body: Json | None, method: str
    ) -> Json:
        path = url.removeprefix("https://en-gb.fitatu.com")
        self.calls.append((path, headers, body, method))
        response = self.routes[path].pop(0)
        if isinstance(response, BaseException):
            raise response
        return cast(Json, response)

    @property
    def paths(self) -> list[str]:
        return [path for path, *_ in self.calls]


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
