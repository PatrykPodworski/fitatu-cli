"""Creating a private product from the values on a food label."""

import argparse
from collections.abc import Callable, Iterable
from typing import Any
from urllib.error import HTTPError

from fitatu_cli.client import Connect
from fitatu_cli.errors import FitatuCliError, unreadable
from fitatu_cli.spec import check_keys, finite, load_spec, spec_error

Json = dict[str, Any]

NOUN = "Product"
REQUIRED = ("name", "energy", "protein", "fat", "carbohydrate")
NUTRIENTS = ("energy", "protein", "fat", "carbohydrate", "fiber", "sugars", "salt")
FIELDS = ("name", "brand", *NUTRIENTS, "per")
PER_100_G = 100
PORTION = "portion"


def valid_per(per: object) -> bool:
    """Whether `per` is 100, or `{"measure": "portion", "grams": N}` with N above
    0."""
    if not isinstance(per, dict):
        return per == PER_100_G
    grams = per.get("grams")
    return (
        per.keys() == {"measure", "grams"}
        and per["measure"] == PORTION
        and finite(grams)
        and grams > 0
    )


def check_product(path: str, verb: str, spec: Json, keys: Iterable[str]) -> None:
    """Checks the spec's `keys`; a missing key fails as an invalid one."""
    check_keys(path, NOUN, verb, spec, FIELDS)
    for key in keys:
        value = spec.get(key)
        if key in ("name", "brand"):
            if not isinstance(value, str) or not value:
                raise spec_error(
                    path, NOUN, verb, f'needs "{key}": a non-empty string.'
                )
        elif key == "per":
            if not valid_per(value):
                raise spec_error(
                    path,
                    NOUN,
                    verb,
                    f'needs "per": {PER_100_G}, or {{"measure": "{PORTION}", '
                    '"grams": N} with N above 0.',
                )
        elif not finite(value) or value < 0:
            raise spec_error(path, NOUN, verb, f'needs "{key}": a number of 0 or more.')


def product_spec(path: str) -> Json:
    """The spec in the file at `path`, checked before any request."""
    spec = load_spec(path, NOUN, "create")
    keys = [key for key in FIELDS if key in REQUIRED or key in spec]
    check_product(path, "create", spec, keys)
    return spec


def product_body(spec: Json) -> Json:
    """The request body for the spec. With a portion, Fitatu reads the nutrients as
    per portion, stores them per 100 g and adds a portion measure of that weight."""
    body = {key: spec[key] for key in ("name", "brand", *NUTRIENTS) if key in spec}
    per = spec.get("per")
    if isinstance(per, dict):
        body["measures"] = [
            {"measureKey": "PORTION", "measureUnit": "g", "weight": per["grams"]}
        ]
    return body


def saved(args: argparse.Namespace, save: Callable[[], Json]) -> Json:
    """Runs `save`, a request that writes a product, and returns what the command
    prints: the product's ID, or the response with `--raw`."""
    try:
        response = save()
    except HTTPError as error:
        if not 400 <= error.code < 500:
            raise
        raise FitatuCliError(
            f"Fitatu rejected the product (HTTP {error.code}).",
            "Check the spec with 'fitatu product create --help'.",
        ) from error
    if response.get("id") is None:
        raise unreadable()
    if args.raw:
        return response
    return {"id": response["id"]}


def create_product(args: argparse.Namespace, connect: Connect) -> Json:
    body = product_body(args.spec)
    return saved(args, lambda: connect().post("/api/products", body))


def register(verbs: "argparse._SubParsersAction[argparse.ArgumentParser]") -> None:
    create = verbs.add_parser(
        "create",
        help="create a product from a food label's values and print its ID",
        description=(
            "Create a private product from SPEC, a JSON file with the values on a "
            'food label: {"name": "Bean stew", "brand": "Bistro", "energy": 129, '
            '"protein": 7.8, "fat": 3.4, "carbohydrate": 10.9, "fiber": 1.2, '
            '"sugars": 2.3, "salt": 0.9, "per": 100}. "brand", "fiber", "sugars", '
            '"salt" and "per" are optional. energy is in kcal, the other nutrients '
            'in grams. With "per": 100, the default, the values are per 100 g. '
            'With "per": {"measure": "portion", "grams": 450}, they are per '
            "portion, as printed on the label, and the product gets a portion "
            "measure of that weight. Prints the product's ID. Log the product with "
            "'fitatu entry create DATE MEAL --product ID --measure 1 --quantity "
            "GRAMS', or with --measure 39 --quantity PORTIONS when it has a portion."
        ),
    )
    create.add_argument(
        "spec", metavar="SPEC", type=product_spec, help="the product's JSON file"
    )
    create.set_defaults(
        run=create_product, text=lambda product: str(product["id"]), parser=create
    )
    create.add_argument(
        "--raw", action="store_true", help="print the full service response"
    )
