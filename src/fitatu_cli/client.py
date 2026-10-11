from collections.abc import Callable
from typing import Any, Protocol


class Client(Protocol):
    """The service methods the subcommands call."""

    def get_status(self) -> dict[str, Any]: ...


class StubClient:
    # ponytail: fixed data so the template runs offline; replace with the
    # service's API client.
    def get_status(self) -> dict[str, Any]:
        return {"state": "ok", "updatedAt": "2026-01-01T00:00:00", "load": 0.123456}


def connect() -> Client:
    """Logs in to the service. Commands call it only when they need data, so
    `--help` and argument errors work without a login."""
    return StubClient()


Connect = Callable[[], Client]
