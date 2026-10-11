import json
from pathlib import Path

import pytest
from conftest import NOW, FakeClient, FakeHttp, jwt, run_json, run_text

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

    result = run_text(["auth", "login"], client, capsys)

    assert result == f"Saved the session to {account}.\n"
    assert http.paths == ["/api/login"]
    assert json.loads(account.read_text())["token"] == NEW_TOKEN


def test_login_json_prints_the_session_path(
    account: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    http = FakeHttp({"/api/login": [{"token": NEW_TOKEN}]})

    result = run_json(["auth", "login", "--json"], FitatuClient(http=http), capsys)

    assert result == {"session": str(account)}


def test_login_never_prints_the_token(
    account: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    http = FakeHttp({"/api/login": [{"token": NEW_TOKEN}]})

    assert main(["auth", "login"], connect=lambda: FitatuClient(http=http)) == 0
    out = capsys.readouterr()
    assert NEW_TOKEN not in out.out + out.err
    assert NEW_TOKEN.split(".")[1] not in out.out + out.err


def test_login_without_email_exits_1(
    account: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.delenv("FITATU_EMAIL")

    assert main(["auth", "login"], connect=lambda: FitatuClient(http=FakeHttp({}))) == 1
    out = capsys.readouterr()
    assert out.out == ""
    assert out.err.startswith("fitatu: FITATU_EMAIL is not set.")


def test_auth_help_lists_login(capsys: pytest.CaptureFixture[str]) -> None:
    with pytest.raises(SystemExit) as exit:
        main(["auth", "--help"])

    assert exit.value.code == 0
    help_text = " ".join(capsys.readouterr().out.split())
    assert (
        "login log in as FITATU_EMAIL with the Keychain password, save the session"
        in help_text
    )


def test_login_extra_argument_exits_2(capsys: pytest.CaptureFixture[str]) -> None:
    with pytest.raises(SystemExit) as exit:
        main(["auth", "login", "extra"], connect=FakeClient)

    assert exit.value.code == 2
    assert capsys.readouterr().err == (
        "fitatu: Unexpected argument 'extra' for 'fitatu auth login'. "
        "Run 'fitatu auth login --help' for all options.\n"
    )
