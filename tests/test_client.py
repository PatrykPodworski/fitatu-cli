import io
import json
import urllib.request
from typing import Any

import pytest

from fitatu_cli import client


class FakeUrlopen:
    def __init__(self) -> None:
        self.requests: list[tuple[urllib.request.Request, float]] = []

    def __call__(self, request: urllib.request.Request, timeout: float) -> Any:
        self.requests.append((request, timeout))
        return io.BytesIO(b'{"ok": 1}')


@pytest.fixture
def urlopen(monkeypatch: pytest.MonkeyPatch) -> FakeUrlopen:
    fake = FakeUrlopen()
    monkeypatch.setattr(urllib.request, "urlopen", fake)
    return fake


def test_http_get(urlopen: FakeUrlopen) -> None:
    assert client.http("https://example.com/a", {"API-Key": "k"}, None) == {"ok": 1}

    [(request, timeout)] = urlopen.requests
    assert request.get_method() == "GET"
    assert request.full_url == "https://example.com/a"
    assert request.data is None
    assert request.header_items() == [("Api-key", "k")]
    assert timeout == 20


def test_http_post_sends_json(urlopen: FakeUrlopen) -> None:
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
