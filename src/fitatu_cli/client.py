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


class NoRedirect(urllib.request.HTTPRedirectHandler):
    """Turns a redirect into an HTTPError, since a followed redirect would resend
    the token to wherever it points."""

    def redirect_request(self, *_: Any) -> None:
        return None


OPENER = urllib.request.build_opener(NoRedirect)


def http(url: str, headers: dict[str, str], body: Json | None, method: str) -> Json:
    """Sends a `method` request to `url`, with `body` as JSON when given."""
    data = None
    if body is not None:
        data = json.dumps(body).encode()
        headers = headers | {"Content-Type": "application/json"}
    # The URL is always API_BASE plus a path from this package.
    request = urllib.request.Request(  # noqa: S310
        url, data=data, headers=headers, method=method
    )
    try:
        with OPENER.open(request, timeout=20) as response:
            if method == "DELETE":
                # The body of Fitatu's answer to a delete is undocumented.
                return {}
            return cast(Json, json.load(response))
    except HTTPError as error:
        if 300 <= error.code < 400:
            raise FitatuCliError(
                f"Fitatu answered with a redirect (HTTP {error.code}), which "
                "fitatu-cli does not follow.",
                f"The API may have changed; report it at {ISSUES}.",
            ) from error
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

    def put(self, path: str, body: Json) -> Json: ...

    def delete(self, path: str) -> None: ...


class FitatuClient:
    def __init__(
        self, http: auth.Http = http, now: Callable[[], float] = time.time
    ) -> None:
        self.http = http
        self.now = now
        # The account of this client's first request; every later request,
        # retries included, must go out as the same account.
        self.uid: str | None = None

    def login(self) -> None:
        auth.login(self.http)

    def get(self, path: str) -> Json:
        return self.send("GET", path, None)

    def post(self, path: str, body: Json) -> Json:
        return self.send("POST", path, body)

    def put(self, path: str, body: Json) -> Json:
        return self.send("PUT", path, body)

    def delete(self, path: str) -> None:
        self.send("DELETE", path, None)

    def send(self, method: str, path: str, body: Json | None) -> Json:
        """Sends a `method` request to an API path, with `{uid}` replaced by the
        user's ID. A 401 gets one fresh login and retry, as the same account."""
        try:
            return self.request(method, path, auth.session(self.http, self.now), body)
        except HTTPError as error:
            if error.code != 401:
                raise
        try:
            return self.request(method, path, auth.login(self.http), body)
        except HTTPError as error:
            if error.code != 401:
                raise
        raise FitatuCliError(
            "Fitatu did not accept a fresh login.",
            "Run 'fitatu auth login'; if it keeps failing, the API may have changed — "
            f"report it at {ISSUES}.",
        )

    def request(self, method: str, path: str, session: Json, body: Json | None) -> Json:
        if self.uid is None:
            self.uid = session["uid"]
        elif session["uid"] != self.uid:
            raise FitatuCliError(
                "The Fitatu login changed to another account during this command, "
                "so it stopped before sending anything as that account.",
                "Run it again.",
            )
        url = auth.API_BASE + path.replace("{uid}", session["uid"])
        return self.http(url, auth.headers(session), body, method)


def connect() -> Client:
    """Returns the client. It logs in on its first request, so `--help` and
    argument errors work without a login."""
    return FitatuClient()


Connect = Callable[[], Client]
