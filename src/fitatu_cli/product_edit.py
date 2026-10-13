"""Editing one of your products from a JSON spec of the label values to change.
Fitatu has no partial update: the command reads the product and sends it back whole,
with the spec applied. Fitatu reads the nutrients of a product with a portion as per
portion, and drops a portion the request leaves out, so the body follows the product's
portion. An edit of the nutrients or of the portion can save the product under a new
ID and mark the old one deleted; name and brand edits keep the ID."""

import argparse
from typing import Any
from urllib.error import HTTPError

from fitatu_cli.client import Client, Connect
from fitatu_cli.errors import FitatuCliError, unreadable
from fitatu_cli.product import product_id, read_product
from fitatu_cli.product_create import (
    FIELDS,
    NOUN,
    NUTRIENTS,
    PER_100_G,
    check_product,
    saved,
)
from fitatu_cli.spec import finite, load_spec, spec_error

Json = dict[str, Any]

PORTION_MEASURE = 39
YOURS = "run 'fitatu product list' to see them."


def edit_spec(path: str) -> Json:
    """The spec in the file at `path`, checked before any request."""
    spec = load_spec(path, NOUN, "edit")
    keys = [key for key in FIELDS if key in spec]
    check_product(path, "edit", spec, keys)
    if not keys:
        names = ", ".join(f'"{key}"' for key in FIELDS[:-1])
        raise spec_error(
            path, NOUN, "edit", f'needs at least one of {names} or "{FIELDS[-1]}".'
        )
    return spec


def current_portion(product: Json) -> float | None:
    """The grams in the product's portion measure, or None without one."""
    for measure in product.get("measures") or []:
        if measure.get("id") == PORTION_MEASURE:
            grams = measure.get("weightPerUnit")
            if not finite(grams) or grams <= 0:
                raise unreadable()
            return grams
    return None


def edit_body(product: Json, spec: Json) -> Json:
    """The product's values with the spec applied: per 100 g without a portion, and
    per portion, with the portion measure, with one."""
    per = spec.get("per")
    new_portion = per["grams"] if isinstance(per, dict) else None
    values: Json = {key: product.get(key) for key in ("name", "brand", *NUTRIENTS)}
    for key in ("name", "brand"):
        if key in spec:
            values[key] = spec[key]
    for key in NUTRIENTS:
        if key in spec:
            values[key] = spec[key] * PER_100_G / (new_portion or PER_100_G)
    portion = new_portion or current_portion(product)
    if portion is None:
        return values
    for key in NUTRIENTS:
        if values[key] is not None:
            values[key] = round(values[key] * portion / PER_100_G, 2)
    measure = {"measureKey": "PORTION", "measureUnit": "g", "weight": portion}
    return values | {"measures": [measure]}


def put(client: Client, id: int, body: Json) -> Json:
    try:
        return client.put(f"/api/products/{id}", body)
    except HTTPError as error:
        if error.code not in (403, 404):
            raise
        raise FitatuCliError(
            f"Fitatu did not edit product {id} (HTTP {error.code}).",
            f"You can edit only your own products; {YOURS}",
        ) from error


def edit_product(args: argparse.Namespace, connect: Connect) -> Json:
    client = connect()
    product = read_product(client, args.id)
    if product.get("deleted"):
        raise FitatuCliError(
            f"Product {args.id} is deleted.",
            "An edit of its nutrients gives a product a new ID; "
            "run 'fitatu product list' for its current ID.",
        )
    if product.get("private") is not True:
        raise FitatuCliError(
            f"Product {args.id} is not one of yours.",
            f"You can edit only your own products; {YOURS}",
        )
    body = edit_body(product, args.spec)
    return saved(args, lambda: put(client, args.id, body))


def register(verbs: "argparse._SubParsersAction[argparse.ArgumentParser]") -> None:
    edit = verbs.add_parser(
        "edit",
        help="edit one of your products from a JSON spec and print its ID",
        description=(
            "Edit product ID, one of yours, with SPEC, a JSON file with any of the "
            "keys of a 'fitatu product create' spec. Each key given replaces that "
            'value. Nutrients are per 100 g, or per portion with "per": '
            '{"measure": "portion", "grams": 450}, which also sets the product\'s '
            "portion to that weight; otherwise the product keeps its portion. "
            "Prints the product's ID. An edit of the nutrients or of the portion "
            "can give the product a new ID; the old one stays, marked deleted, and "
            "diary entries keep using it."
        ),
    )
    edit.add_argument("id", metavar="ID", type=product_id, help="the product's ID")
    edit.add_argument(
        "spec", metavar="SPEC", type=edit_spec, help="the changes' JSON file"
    )
    edit.set_defaults(
        run=edit_product, text=lambda product: str(product["id"]), parser=edit
    )
    edit.add_argument(
        "--raw", action="store_true", help="print the full service response"
    )
