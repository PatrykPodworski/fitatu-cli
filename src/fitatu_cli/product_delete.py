"""Deleting one of your products. Fitatu keeps it marked deleted, so diary entries
that use it keep their name and values."""

import argparse
from typing import Any
from urllib.error import HTTPError

from fitatu_cli.client import Connect
from fitatu_cli.errors import FitatuCliError
from fitatu_cli.food import dash
from fitatu_cli.product import product_id, read_product

Json = dict[str, Any]

YOURS = "You can delete only your own products; run 'fitatu product list' to see them."


def delete_product(args: argparse.Namespace, connect: Connect) -> Json:
    client = connect()
    product = read_product(client, args.id)
    # Fitatu answers a second DELETE with 200 too, so the state is checked first.
    if product.get("deleted"):
        raise FitatuCliError(
            f"Product {args.id} is already deleted.",
            "Run 'fitatu product list' to see your products' IDs.",
        )
    if product.get("private") is not True:
        raise FitatuCliError(f"Product {args.id} is not one of yours.", YOURS)
    try:
        client.delete(f"/api/products/{args.id}")
    except HTTPError as error:
        if error.code not in (403, 404):
            raise
        raise FitatuCliError(
            f"Fitatu did not delete product {args.id} (HTTP {error.code}).", YOURS
        ) from error
    return {"id": args.id, "name": product.get("name")}


def register(verbs: "argparse._SubParsersAction[argparse.ArgumentParser]") -> None:
    delete = verbs.add_parser(
        "delete",
        help="delete one of your products",
        description="Delete one of your products. There is no confirmation prompt.",
    )
    delete.add_argument("id", metavar="ID", type=product_id, help="the product's ID")
    delete.set_defaults(
        run=delete_product,
        text=lambda product: (
            f"deleted product {product['id']}: {dash(product['name'])}"
        ),
        parser=delete,
    )
