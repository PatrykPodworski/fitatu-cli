"""Foods from Fitatu's search, as the web app's search box finds them: the
catalog for a phrase, the foods you used last without one."""

import argparse
from urllib.parse import urlencode

from fitatu_cli.client import Client, Connect
from fitatu_cli.day import Json, table
from fitatu_cli.errors import unreadable

CATALOG = (
    "/api/search/new/food?hasFilters=false&accessType[]=FREE&accessType[]=PREMIUM"
    "&page=1&limit=40&"
)
LAST_USED = "/api/search/food/{uid}/last-used?page=1&limit=100"
COLUMNS = ("id", "type", "name", "brand", "energy_kcal", "measure")


def search_locale(client: Client) -> str:
    locale = client.get("/api/users/{uid}").get("searchLocale")
    if not isinstance(locale, str):
        raise unreadable()
    return locale


def search_response(client: Client, phrase: str | None) -> list[Json]:
    response: object
    if phrase:
        query = urlencode({"phrase": phrase, "locale": search_locale(client)})
        response = client.get(CATALOG + query)
    else:
        response = client.get(LAST_USED)
    if not isinstance(response, list) or not all(
        isinstance(item, dict) for item in response
    ):
        raise unreadable()
    return response


def food_row(item: Json) -> Json:
    food_type = item.get("type")
    energy = item.get("energy")
    measure = item.get("measure")
    return {
        "id": item.get("foodId"),
        "type": food_type.lower() if isinstance(food_type, str) else None,
        "name": item.get("name"),
        "brand": item.get("brand"),
        "energy": energy if energy is None else round(energy, 1),
        "measure": None
        if measure is None
        else {
            "id": measure.get("measureId"),
            "name": measure.get("measureName"),
            "grams": measure.get("measureWeight"),
        },
    }


def search(args: argparse.Namespace, connect: Connect) -> list[Json]:
    response = search_response(connect(), args.phrase)
    if args.raw:
        return response
    return [food_row(item) for item in response]


def dash(value: object) -> str:
    return "-" if value is None else str(value)


def number(value: float | None, spec: str) -> str:
    return "-" if value is None else format(value, spec)


def measure_text(measure: Json | None) -> str:
    if measure is None:
        return "-"
    grams = number(measure["grams"], "g")
    return f"{dash(measure['id'])} {dash(measure['name'])} ({grams} g)"


def foods_text(foods: list[Json]) -> str:
    """A table of the foods, one row each, with the measure in the last column."""
    if not foods:
        return "no foods found"
    rows = [
        [
            *(dash(food[key]) for key in ("id", "type", "name", "brand")),
            number(food["energy"], ".1f"),
            measure_text(food["measure"]),
        ]
        for food in foods
    ]
    return table([list(COLUMNS), *rows])


def register(subparsers: "argparse._SubParsersAction[argparse.ArgumentParser]") -> None:
    verbs = subparsers.add_parser(
        "food", help="find foods and their measures"
    ).add_subparsers(required=True)
    search_parser = verbs.add_parser(
        "search",
        help="foods matching a phrase, or the foods you used last without one",
    )
    search_parser.add_argument(
        "phrase", nargs="?", help="what to search for (default: your last-used foods)"
    )
    search_parser.add_argument(
        "--raw", action="store_true", help="print the full service response"
    )
    search_parser.set_defaults(run=search, text=foods_text, parser=search_parser)
