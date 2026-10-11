import json
from pathlib import Path

import pytest
from conftest import APP_UUID, NOW, FakeHttp, jwt, run_json

from fitatu_cli.cli import main
from fitatu_cli.client import FitatuClient

TOKEN = jwt(NOW + 3600)
NEW_TOKEN = jwt(NOW + 7200)


def test_login_logs_in_and_prints_session_path(
    account: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    account.parent.mkdir(parents=True)
    account.write_text(json.dumps({"token": TOKEN, "uid": "101", "app_uuid": "x"}))
    http = FakeHttp({"/api/login": [{"token": NEW_TOKEN}]})
    client = FitatuClient(http=http, now=lambda: NOW)

    result = run_json(["login"], client, capsys)

    assert result == {"session": str(account)}
    assert http.paths == ["/api/login"]
    assert json.loads(account.read_text())["token"] == NEW_TOKEN


def test_login_never_prints_the_token_or_app_uuid(
    account: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    http = FakeHttp({"/api/login": [{"token": NEW_TOKEN}]})

    assert main(["login"], connect=lambda: FitatuClient(http=http)) == 0
    out = capsys.readouterr()
    assert NEW_TOKEN not in out.out + out.err
    assert NEW_TOKEN.split(".")[1] not in out.out + out.err
    assert APP_UUID not in out.out + out.err


def test_login_without_email_exits_1(
    account: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.delenv("FITATU_EMAIL")

    assert main(["login"], connect=lambda: FitatuClient(http=FakeHttp({}))) == 1
    out = capsys.readouterr()
    assert out.out == ""
    assert out.err.startswith("fitatu: FITATU_EMAIL is not set.")
