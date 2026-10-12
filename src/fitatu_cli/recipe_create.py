"""Creating a recipe from a JSON spec. The recipe stays private: the CLI never adds
it to Fitatu's recipe catalog."""

import argparse
import json
from typing import Any
from urllib.error import HTTPError

from fitatu_cli.client import Connect
from fitatu_cli.errors import FitatuCliError, unreadable

Json = dict[str, Any]

SHAPE = "Run 'fitatu recipe create --help' for the spec's shape."
SEARCH = "Take itemId and measureId from 'fitatu food search'."
ITEM_KEYS = ("itemId", "measureId", "measureQuantity")
# The web app refuses a recipe with fewer ingredients; the service accepts one.
MIN_ITEMS = 2


def spec_error(path: str, problem: str) -> argparse.ArgumentTypeError:
    return argparse.ArgumentTypeError(f"Recipe spec '{path}' {problem} {SHAPE}")


def check_items(path: str, items: object) -> None:
    if not isinstance(items, list) or len(items) < MIN_ITEMS:
        raise spec_error(
            path, f'needs "items": a list of at least {MIN_ITEMS} ingredients.'
        )
    for number, item in enumerate(items, start=1):
        where = f"Item {number} in recipe spec '{path}'"
        if not isinstance(item, dict):
            raise argparse.ArgumentTypeError(f"{where} is not a JSON object. {SEARCH}")
        for key in ITEM_KEYS:
            if item.get(key) is None:
                raise argparse.ArgumentTypeError(f'{where} needs "{key}". {SEARCH}')


def recipe_spec(path: str) -> Json:
    """The spec in the file at `path`, checked before any request."""
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
            path, f"is not valid JSON ({error.msg}, line {error.lineno})."
        ) from None
    if not isinstance(spec, dict):
        raise spec_error(path, "is not a JSON object.")
    name = spec.get("name")
    if not isinstance(name, str) or not name:
        raise spec_error(path, 'needs "name": a non-empty string.')
    serving = spec.get("serving")
    if (
        isinstance(serving, bool)
        or not isinstance(serving, int | float)
        or serving <= 0
    ):
        raise spec_error(path, 'needs "serving": a positive number.')
    check_items(path, spec.get("items"))
    return spec


def request_body(spec: Json) -> Json:
    """The body the web app sends for a new private recipe."""
    return {
        "name": spec["name"],
        "serving": str(spec["serving"]),
        "items": [
            {"type": "PRODUCT", **{key: item[key] for key in ITEM_KEYS}}
            for item in spec["items"]
        ],
        "recipeDescription": spec.get("description"),
        "preparationTime": "",
        "cookingTime": None,
        "categories": [],
        "mealSchema": [],
        "tags": [],
        "shared": False,
    }


def create_recipe(args: argparse.Namespace, connect: Connect) -> Json:
    try:
        response = connect().post("/api/recipes", request_body(args.spec))
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
