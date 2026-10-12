"""Creating a recipe from a JSON spec. The recipe stays private: the CLI never adds
it to Fitatu's recipe catalog."""

import argparse
import json
from collections.abc import Callable, Iterable
from typing import Any, cast
from urllib.error import HTTPError

from fitatu_cli.client import Connect
from fitatu_cli.errors import FitatuCliError, unreadable

Json = dict[str, Any]

SEARCH = "Take itemId and measureId from 'fitatu food search'."
ITEM_KEYS = ("itemId", "measureId", "measureQuantity")
# The web app refuses a recipe with fewer ingredients; the service accepts one.
MIN_ITEMS = 2
NEW_RECIPE: Json = {
    "recipeDescription": None,
    "preparationTime": "",
    "cookingTime": None,
    "categories": [],
    "mealSchema": [],
    "tags": [],
    "shared": False,
}


def spec_error(path: str, verb: str, problem: str) -> argparse.ArgumentTypeError:
    return argparse.ArgumentTypeError(
        f"Recipe spec '{path}' {problem} "
        f"Run 'fitatu recipe {verb} --help' for the spec's shape."
    )


def check_items(path: str, verb: str, items: object) -> None:
    if not isinstance(items, list) or len(items) < MIN_ITEMS:
        raise spec_error(
            path, verb, f'needs "items": a list of at least {MIN_ITEMS} ingredients.'
        )
    for number, item in enumerate(items, start=1):
        where = f"Item {number} in recipe spec '{path}'"
        if not isinstance(item, dict):
            raise argparse.ArgumentTypeError(f"{where} is not a JSON object. {SEARCH}")
        for key in ITEM_KEYS:
            if item.get(key) is None:
                raise argparse.ArgumentTypeError(f'{where} needs "{key}". {SEARCH}')


def load_spec(path: str, verb: str) -> Json:
    """The JSON object in the file at `path`."""
    try:
        with open(path) as file:
            spec = json.load(file)
    except OSError as error:
        raise argparse.ArgumentTypeError(
            f"Cannot read recipe spec '{path}' ({error.strerror}). "
            "Give the path of a JSON file."
        ) from None
    except json.JSONDecodeError as error:
        raise spec_error(
            path, verb, f"is not valid JSON ({error.msg}, line {error.lineno})."
        ) from None
    if not isinstance(spec, dict):
        raise spec_error(path, verb, "is not a JSON object.")
    return cast(Json, spec)


def check_fields(path: str, verb: str, spec: Json, keys: Iterable[str]) -> None:
    """Checks the spec's `keys`; a missing key fails as an invalid one."""
    if "name" in keys:
        name = spec.get("name")
        if not isinstance(name, str) or not name:
            raise spec_error(path, verb, 'needs "name": a non-empty string.')
    if "serving" in keys:
        serving = spec.get("serving")
        if (
            isinstance(serving, bool)
            or not isinstance(serving, int | float)
            or serving <= 0
        ):
            raise spec_error(path, verb, 'needs "serving": a positive number.')
    if "items" in keys:
        check_items(path, verb, spec.get("items"))


def recipe_spec(path: str) -> Json:
    """The spec in the file at `path`, checked before any request."""
    spec = load_spec(path, "create")
    check_fields(path, "create", spec, ("name", "serving", "items"))
    return spec


def spec_fields(spec: Json) -> Json:
    """The request body fields the spec sets, as the web app sends them."""
    fields: Json = {}
    if "name" in spec:
        fields["name"] = spec["name"]
    if "serving" in spec:
        fields["serving"] = str(spec["serving"])
    if "description" in spec:
        fields["recipeDescription"] = spec["description"]
    if "items" in spec:
        fields["items"] = [
            {"type": "PRODUCT", **{key: item[key] for key in ITEM_KEYS}}
            for item in spec["items"]
        ]
    return fields


def saved(args: argparse.Namespace, save: Callable[[], Json]) -> Json:
    """Runs `save`, a request that writes a recipe, and returns what the command
    prints: the new recipe's ID, or the response with `--raw`."""
    try:
        response = save()
    except HTTPError as error:
        if not 400 <= error.code < 500:
            raise
        raise FitatuCliError(
            f"Fitatu rejected the recipe (HTTP {error.code}).",
            "Check each item's itemId and measureId with 'fitatu food search'.",
        ) from error
    if response.get("id") is None:
        raise unreadable()
    if args.raw:
        return response
    return {"id": response["id"]}


def create_recipe(args: argparse.Namespace, connect: Connect) -> Json:
    body = NEW_RECIPE | spec_fields(args.spec)
    return saved(args, lambda: connect().post("/api/recipes", body))


def register(verbs: "argparse._SubParsersAction[argparse.ArgumentParser]") -> None:
    create = verbs.add_parser(
        "create",
        help="create a recipe from a JSON spec and print its ID",
        description=(
            'Create a recipe from SPEC, a JSON file: {"name": "Stew", "serving": 2, '
            '"description": "Simmer." (optional), "items": [{"itemId": 501, '
            '"measureId": 1, "measureQuantity": 400}, ...]}, with at least '
            f"{MIN_ITEMS} items. Take itemId and measureId from 'fitatu food "
            "search'; measureQuantity counts that measure."
        ),
    )
    create.add_argument(
        "spec", metavar="SPEC", type=recipe_spec, help="the recipe's JSON file"
    )
    create.set_defaults(
        run=create_recipe, text=lambda recipe: str(recipe["id"]), parser=create
    )
    create.add_argument(
        "--raw", action="store_true", help="print the full service response"
    )
