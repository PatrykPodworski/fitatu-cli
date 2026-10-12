import json
import time
import urllib.request
from collections.abc import Callable
from http.client import IncompleteRead
from typing import Any, Protocol, cast
from urllib.error import HTTPError

from fitatu_cli import auth
from fitatu_cli.errors import ISSUES, FitatuCliError, reason, unreadable

Json = dict[str, Any]


def http(
    url: str, headers: dict[str, str], body: Json | None, method: str | None = None
) -> Json:
    """GETs `url`, or POSTs `body` as JSON when given, or sends `method`."""
    data = None
    if body is not None:
        data = json.dumps(body).encode()
        headers = headers | {"Content-Type": "application/json"}
    # The URL is always API_BASE plus a path from this package.
    request = urllib.request.Request(  # noqa: S310
        url, data=data, headers=headers, method=method
    )
    try:
        with urllib.request.urlopen(request, timeout=20) as response:  # noqa: S310
            if method == "DELETE":
                # The body of Fitatu's answer to a delete is undocumented.
                return {}
            return cast(Json, json.load(response))
    except HTTPError as error:
        if error.code == 429:
            raise FitatuCliError(
                "Fitatu is rate-limiting requests from this machine.",
                "Wait a few minutes and try again.",
            ) from error
        raise
    # URLError, timeouts and dropped connections are all OSErrors; IncompleteRead
    # is a body cut off mid-read.
    except (OSError, IncompleteRead) as error:
        raise FitatuCliError(
            f"Could not reach Fitatu ({reason(error)}).",
            "Check your internet connection and try again.",
        ) from error
    # JSONDecodeError and UnicodeDecodeError.
    except ValueError as error:
        raise unreadable() from error


class Client(Protocol):
    """The service methods the subcommands call."""

    def login(self) -> None: ...

    def get(self, path: str) -> Json: ...

    def post(self, path: str, body: Json) -> Json: ...

    def delete(self, path: str) -> None: ...


class FitatuClient:
    def __init__(
        self, http: auth.Http = http, now: Callable[[], float] = time.time
    ) -> None:
        self.http = http
        self.now = now

    def login(self) -> None:
        auth.login(self.http)

    def get(self, path: str) -> Json:
        return self.send(path, None)

    def post(self, path: str, body: Json) -> Json:
        return self.send(path, body)

    def delete(self, path: str) -> None:
        self.send(path, None, "DELETE")

    def send(self, path: str, body: Json | None, method: str | None = None) -> Json:
        """GETs an API path, with `{uid}` replaced by the user's ID, or POSTs
        `body` to it, or sends `method`. A 401 gets one fresh login and retry."""
        try:
            return self.request(path, auth.session(self.http, self.now), body, method)
        except HTTPError as error:
            if error.code != 401:
                raise
        try:
            return self.request(path, auth.login(self.http), body, method)
        except HTTPError as error:
            if error.code != 401:
                raise
        raise FitatuCliError(
            "Fitatu did not accept a fresh login.",
            "Run 'fitatu auth login'; if it keeps failing, the API may have changed — "
            f"report it at {ISSUES}.",
        )

    def request(
        self, path: str, session: Json, body: Json | None, method: str | None
    ) -> Json:
        url = auth.API_BASE + path.replace("{uid}", session["uid"])
        return self.http(url, auth.headers(session), body, method)


def connect() -> Client:
    """Returns the client. It logs in on its first request, so `--help` and
    argument errors work without a login."""
    return FitatuClient()


Connect = Callable[[], Client]
