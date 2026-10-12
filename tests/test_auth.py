import json
import stat
import subprocess
from pathlib import Path
from typing import Any
from urllib.error import HTTPError

import pytest
from conftest import APP_UUID, EMAIL, NOW, FakeHttp, http_error, jwt

from fitatu_cli import auth
from fitatu_cli.client import FitatuClient
from fitatu_cli.errors import FitatuCliError

TOKEN = jwt(NOW + 3600)
NEW_TOKEN = jwt(NOW + 7200)
PLAN: dict[str, Any] = {"dietPlan": {}}
DAY = "/api/diet-and-activity-plan/{uid}/day/2026-07-05"
DAY_101 = "/api/diet-and-activity-plan/101/day/2026-07-05"
LOGIN = "/api/login"
REFRESH = "/api/token/refresh"


def client(http: FakeHttp) -> FitatuClient:
    return FitatuClient(http=http, now=lambda: NOW)


def save(path: Path, **session: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({"uid": "101", **session}))


def logged_in(refresh_token: str = "fake-refresh") -> dict[str, str]:
    return {"token": NEW_TOKEN, "refresh_token": refresh_token}


def test_first_get_logs_in_and_saves_session(
    account: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.delenv("FITATU_APP_UUID", raising=False)
    http = FakeHttp({LOGIN: [logged_in()], DAY_101: [PLAN]})

    assert client(http).get(DAY) == PLAN

    assert http.paths == [LOGIN, DAY_101]
    _, login_headers, login_body = http.calls[0]
    assert login_body == {"_username": EMAIL, "_password": "fake password "}
    assert "Authorization" not in login_headers
    session = json.loads(account.read_text())
    assert session == {
        "token": NEW_TOKEN,
        "refresh_token": "fake-refresh",
        "uid": "101",
    }
    assert login_headers["APP-UUID"] == APP_UUID
    assert "API-Cluster" not in login_headers
    assert "APP-Timezone" not in login_headers
    assert stat.S_IMODE(account.stat().st_mode) == 0o600


def test_data_request_carries_session_headers(account: Path) -> None:
    save(account, token=TOKEN)
    http = FakeHttp({DAY_101: [PLAN]})

    client(http).get(DAY)

    _, headers, body = http.calls[0]
    assert body is None
    assert headers["Authorization"] == f"Bearer {TOKEN}"
    assert headers["API-Cluster"] == "en-gb101"
    assert headers["APP-UUID"] == APP_UUID
    assert "APP-Timezone" not in headers
    assert headers["API-Key"] == "FITATU-MOBILE-APP"
    assert headers["API-Secret"] == auth.API_SECRET


@pytest.mark.parametrize("uid", [1, 12, 123])
def test_claims_of_any_payload_length(uid: int) -> None:
    assert auth.claims(jwt(NOW, uid)) == {"id": uid, "exp": NOW}


@pytest.mark.parametrize("ttl", [61, 3600])
def test_valid_token_is_reused_without_login(account: Path, ttl: int) -> None:
    save(account, token=jwt(NOW + ttl))
    http = FakeHttp({DAY_101: [PLAN]})

    assert client(http).get(DAY) == PLAN

    assert http.paths == [DAY_101]


@pytest.mark.parametrize("ttl", [60, 0, -3600])
def test_expiring_token_is_refreshed(account: Path, ttl: int) -> None:
    save(account, token=jwt(NOW + ttl), refresh_token="fake-refresh")
    http = FakeHttp({REFRESH: [logged_in("new-refresh")], DAY_101: [PLAN]})

    assert client(http).get(DAY) == PLAN

    assert http.paths == [REFRESH, DAY_101]
    _, headers, body = http.calls[0]
    assert body == {"refresh_token": "fake-refresh"}
    assert headers["APP-UUID"] == APP_UUID
    assert http.calls[1][1]["Authorization"] == f"Bearer {NEW_TOKEN}"
    assert json.loads(account.read_text()) == {
        "token": NEW_TOKEN,
        "refresh_token": "new-refresh",
        "uid": "101",
    }


def test_old_session_file_with_app_uuid_still_works(account: Path) -> None:
    account.parent.mkdir(parents=True)
    old = "00000000-0000-1000-8000-000000000002"
    account.write_text(
        json.dumps(
            {"token": jwt(NOW), "refresh_token": "fake", "uid": "101", "app_uuid": old}
        )
    )
    http = FakeHttp({REFRESH: [logged_in()], DAY_101: [PLAN]})

    assert client(http).get(DAY) == PLAN

    assert [headers["APP-UUID"] for _, headers, _ in http.calls] == [APP_UUID] * 2
    assert json.loads(account.read_text()) == {
        "token": NEW_TOKEN,
        "refresh_token": "fake-refresh",
        "uid": "101",
    }


def test_failed_refresh_logs_in(account: Path) -> None:
    save(account, token=jwt(NOW), refresh_token="fake-refresh")
    http = FakeHttp({REFRESH: [http_error(401)], LOGIN: [logged_in()], DAY_101: [PLAN]})

    assert client(http).get(DAY) == PLAN

    assert http.paths == [REFRESH, LOGIN, DAY_101]


def test_expired_token_without_refresh_token_logs_in(account: Path) -> None:
    save(account, token=jwt(NOW))
    http = FakeHttp({LOGIN: [logged_in()], DAY_101: [PLAN]})

    client(http).get(DAY)

    assert http.paths == [LOGIN, DAY_101]
    assert http.calls[0][1]["APP-UUID"] == APP_UUID
    assert http.calls[1][1]["APP-UUID"] == APP_UUID


def test_login_without_refresh_token_saves_none(account: Path) -> None:
    http = FakeHttp({LOGIN: [{"token": NEW_TOKEN}], DAY_101: [PLAN]})

    client(http).get(DAY)

    assert "refresh_token" not in json.loads(account.read_text())


def test_401_logs_in_once_and_retries(account: Path) -> None:
    save(account, token=TOKEN)
    http = FakeHttp({DAY_101: [http_error(401), PLAN], LOGIN: [logged_in()]})

    assert client(http).get(DAY) == PLAN

    assert http.paths == [DAY_101, LOGIN, DAY_101]
    assert http.calls[2][1]["Authorization"] == f"Bearer {NEW_TOKEN}"


def test_401_after_fresh_login_fails(account: Path) -> None:
    save(account, token=TOKEN)
    http = FakeHttp({DAY_101: [http_error(401), http_error(401)], LOGIN: [logged_in()]})

    with pytest.raises(FitatuCliError) as error:
        client(http).get(DAY)

    assert str(error.value) == (
        "Fitatu did not accept a fresh login. Run 'fitatu auth login'; if it keeps "
        "failing, the API may have changed — report it at "
        "https://github.com/PatrykPodworski/fitatu-cli/issues."
    )
    assert http.paths == [DAY_101, LOGIN, DAY_101]


@pytest.mark.parametrize("first", [True, False])
def test_other_http_error_is_not_retried(account: Path, first: bool) -> None:
    save(account, token=TOKEN)
    responses: list[Any] = [http_error(500)]
    if not first:
        responses.insert(0, http_error(401))
    http = FakeHttp({DAY_101: responses, LOGIN: [logged_in()]})

    with pytest.raises(HTTPError) as error:
        client(http).get(DAY)

    assert error.value.code == 500


def test_two_runs_share_one_login(account: Path) -> None:
    http = FakeHttp({LOGIN: [logged_in()], DAY_101: [PLAN, PLAN]})

    client(http).get(DAY)
    client(http).get(DAY)

    assert http.paths == [LOGIN, DAY_101, DAY_101]


@pytest.mark.parametrize("code", [400, 401, 422])
def test_rejected_login(account: Path, code: int) -> None:
    http = FakeHttp({LOGIN: [http_error(code)]})

    with pytest.raises(FitatuCliError) as error:
        client(http).get(DAY)

    assert str(error.value) == (
        f"Fitatu rejected the login for {EMAIL}. "
        "Check the Keychain password for service 'fitatu'."
    )


def test_login_server_error_is_not_rejection(account: Path) -> None:
    http = FakeHttp({LOGIN: [http_error(500)]})

    with pytest.raises(HTTPError):
        client(http).get(DAY)


def test_missing_email(account: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("FITATU_EMAIL")

    with pytest.raises(FitatuCliError) as error:
        client(FakeHttp({})).get(DAY)

    assert str(error.value) == (
        "FITATU_EMAIL is not set. Run 'export FITATU_EMAIL=you@example.com' "
        "with your Fitatu account email."
    )


def test_missing_keychain_entry(account: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        subprocess,
        "run",
        lambda argv, **_: subprocess.CompletedProcess(argv, 44, "", "not found"),
    )

    with pytest.raises(FitatuCliError) as error:
        client(FakeHttp({})).get(DAY)

    assert str(error.value) == (
        f"No Keychain password for account {EMAIL} (service 'fitatu'). "
        f"Add it with 'security add-generic-password -s fitatu -a {EMAIL} -w'."
    )


def no_security(*args: Any, **kwargs: Any) -> Any:
    raise FileNotFoundError("security")


def test_no_keychain_with_fitatu_session(
    account: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(subprocess, "run", no_security)

    with pytest.raises(FitatuCliError) as error:
        client(FakeHttp({})).get(DAY)

    assert str(error.value) == (
        "Logging in to Fitatu reads the password from the macOS Keychain, which "
        "is not available here. Copy a session file from a Mac that ran "
        "'fitatu auth login' and point FITATU_SESSION at it."
    )


def test_no_keychain_without_fitatu_session(
    account: Path, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.delenv("FITATU_SESSION")
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setattr(subprocess, "run", no_security)

    with pytest.raises(FitatuCliError) as error:
        client(FakeHttp({})).get(DAY)

    assert str(error.value) == (
        "Logging in to Fitatu reads the password from the macOS Keychain, which "
        "is not available here. Log in on a Mac and copy ~/.fitatu/session.json "
        "to this machine, or set FITATU_SESSION to a copied session file."
    )


def test_default_session_path(
    account: Path, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.delenv("FITATU_SESSION")
    monkeypatch.setenv("HOME", str(tmp_path))
    http = FakeHttp({LOGIN: [logged_in()], DAY_101: [PLAN]})

    client(http).get(DAY)

    saved = tmp_path / ".fitatu" / "session.json"
    assert auth.session_path() == saved
    assert json.loads(saved.read_text())["token"] == NEW_TOKEN


def test_existing_session_file_is_made_private(account: Path) -> None:
    save(account, token=jwt(NOW))
    account.chmod(0o644)
    http = FakeHttp({LOGIN: [logged_in()], DAY_101: [PLAN]})

    client(http).get(DAY)

    assert stat.S_IMODE(account.stat().st_mode) == 0o600


def test_post_sends_the_body_and_retries_once_after_401(account: Path) -> None:
    save(account, token=TOKEN)
    days = "/api/diet-plan/101/days"
    saved = [{"date": "2026-07-05", "revision": 3, "errorMessage": None}]
    http = FakeHttp({days: [http_error(401), saved], LOGIN: [logged_in()]})

    answer: object = client(http).post("/api/diet-plan/{uid}/days", {"day": 1})

    assert answer == saved

    assert http.paths == [days, LOGIN, days]
    assert [http.calls[0][2], http.calls[2][2]] == [{"day": 1}, {"day": 1}]
    assert http.calls[2][1]["Authorization"] == f"Bearer {NEW_TOKEN}"
