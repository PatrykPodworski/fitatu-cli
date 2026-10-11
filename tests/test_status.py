import json
from typing import Any

import pytest
from conftest import FakeClient, run_json

from fitatu_cli.cli import main

STATUS = {"state": "ok", "updatedAt": "2026-07-05T08:00:00", "load": 0.5, "x": 1}


def test_status_prints_summary(capsys: pytest.CaptureFixture[str]) -> None:
    client = FakeClient(get_status=STATUS)

    result = run_json(["status"], client, capsys)

    assert client.calls == [("get_status", (), {})]
    assert result == {"state": "ok", "updated_at": "2026-07-05T08:00:00", "load": 0.5}


def test_status_missing_optional_fields_are_null(
    capsys: pytest.CaptureFixture[str],
) -> None:
    result = run_json(["status"], FakeClient(get_status={"state": "ok"}), capsys)

    assert result == {"state": "ok", "updated_at": None, "load": None}


@pytest.mark.parametrize("response", [{}, {"state": None}])
def test_status_missing_state_exits_1(
    response: dict[str, Any], capsys: pytest.CaptureFixture[str]
) -> None:
    code = main(["status"], connect=lambda: FakeClient(get_status=response))

    assert code == 1
    out = capsys.readouterr()
    assert out.out == ""
    assert out.err == "fitatu: No status yet. Try again in a few minutes.\n"


def test_status_raw_prints_full_response(capsys: pytest.CaptureFixture[str]) -> None:
    result = run_json(["status", "--raw"], FakeClient(get_status=STATUS), capsys)

    assert result == STATUS


def test_status_default_connect_uses_stub(capsys: pytest.CaptureFixture[str]) -> None:
    assert main(["status", "--raw"]) == 0
    assert json.loads(capsys.readouterr().out) == {
        "state": "ok",
        "updatedAt": "2026-01-01T00:00:00",
        "load": 0.123456,
    }
