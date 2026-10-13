"""Your products: the list, most used first, and one product with its measures
and nutrients per 100 g."""

import argparse
from typing import Any
from urllib.error import HTTPError

from fitatu_cli.client import Client, Connect
from fitatu_cli.day import NUTRIENTS, table
from fitatu_cli.errors import FitatuCliError
from fitatu_cli.food import dash, number, user_foods

Json = dict[str, Any]


def list_products(args: argparse.Namespace, connect: Connect) -> list[Json]:
    rows = user_foods(connect(), "PRODUCT")
    if args.raw:
        return rows
    products = [
        {
            "id": row.get("foodId"),
            "uses": row.get("userNumberOfUse") or 0,
            # The search sends "" for a product without a brand.
            "brand": row.get("brand") or None,
            "name": row.get("name"),
        }
        for row in rows
        if not row.get("deleted")
    ]
    return sorted(products, key=lambda product: -product["uses"])


def products_text(products: list[Json]) -> str:
    if not products:
        return "no products"
    rows = [
        [dash(product[key]) for key in ("id", "uses", "brand", "name")]
        for product in products
    ]
    return table([["id", "uses", "brand", "name"], *rows])


def product_id(value: str) -> int:
    try:
        return int(value)
    except ValueError:
        raise argparse.ArgumentTypeError(
            f"Invalid product ID '{value}'. Give the number from 'fitatu product list'."
        ) from None


def read_product(client: Client, id: int) -> Json:
    try:
        return client.get(f"/api/products/{id}")
    except HTTPError as error:
        if error.code != 404:
            raise
        raise FitatuCliError(
            f"Fitatu has no product with ID {id}.",
            "Run 'fitatu product list' to see your products' IDs.",
        ) from error


def view_product(args: argparse.Namespace, connect: Connect) -> Json:
    product = read_product(connect(), args.id)
    if args.raw:
        return product
    return {
        "id": args.id,
        "name": product.get("name"),
        "brand": product.get("brand") or None,
        "mine": product.get("private") is True,
        "deleted": bool(product.get("deleted")),
        "measures": [
            {
                "id": measure.get("id"),
                "name": measure.get("name"),
                "grams": measure.get("weightPerUnit"),
            }
            for measure in product.get("measures") or []
        ],
        "per_100g": {
            nutrient: round(product.get(nutrient) or 0, 1) for nutrient in NUTRIENTS
        },
    }


def yes_no(value: bool) -> str:
    return "yes" if value else "no"


def product_text(product: Json) -> str:
    """The product's fields, a table of its measures, and a one-row table of its
    nutrients per 100 g."""
    fields = "\n".join(
        [
            f"id: {product['id']}",
            f"name: {dash(product['name'])}",
            f"brand: {dash(product['brand'])}",
            f"mine: {yes_no(product['mine'])}",
            f"deleted: {yes_no(product['deleted'])}",
        ]
    )
    measures = (
        table(
            [
                ["measure_id", "measure", "grams"],
                *(
                    [
                        dash(measure["id"]),
                        dash(measure["name"]),
                        number(measure["grams"], "g"),
                    ]
                    for measure in product["measures"]
                ),
            ]
        )
        if product["measures"]
        else "no measures"
    )
    nutrients = table(
        [
            [f"{key}_{unit}" for key, unit in NUTRIENTS.items()],
            [f"{product['per_100g'][key]:.1f}" for key in NUTRIENTS],
        ]
    )
    return f"{fields}\n\n{measures}\n\nper 100 g\n{nutrients}"


def register(
    subparsers: "argparse._SubParsersAction[argparse.ArgumentParser]",
) -> "argparse._SubParsersAction[argparse.ArgumentParser]":
    """Registers the read verbs and returns the group, for the write verbs."""
    verbs = subparsers.add_parser("product", help="your products").add_subparsers(
        required=True
    )
    list_parser = verbs.add_parser("list", help="list your products, most used first")
    list_parser.set_defaults(run=list_products, text=products_text, parser=list_parser)
    list_parser.add_argument(
        "--raw", action="store_true", help="print the service's rows for your products"
    )
    view = verbs.add_parser(
        "view", help="view one product: measures and nutrients per 100 g"
    )
    view.add_argument("id", metavar="ID", type=product_id, help="the product's ID")
    view.set_defaults(run=view_product, text=product_text, parser=view)
    view.add_argument(
        "--raw", action="store_true", help="print the full service response"
    )
    return verbs
