"""Your recipes: the list, most used first, and one recipe with its ingredients
and nutrients per portion."""

import argparse
from typing import Any
from urllib.error import HTTPError

from fitatu_cli.client import Client, Connect
from fitatu_cli.day import NUTRIENTS, table
from fitatu_cli.errors import FitatuCliError, unreadable

Json = dict[str, Any]

INGREDIENT_COLUMNS = ("name", "quantity", "measure")


def recipe_rows(client: Client) -> list[Json]:
    """The search rows of your recipes, deleted ones included, in service order.
    The search pages through every food you created or used."""
    rows: list[Json] = []
    page_number = 1
    while True:
        # The search answers with a list, not the object `get` is typed for.
        page: object = client.get(
            f"/api/search/food/user/{{uid}}?phrase=&page={page_number}&limit=100"
        )
        if not isinstance(page, list):
            raise unreadable()
        if not page:
            return rows
        rows += [row for row in page if row.get("type") == "RECIPE"]
        page_number += 1


def list_recipes(args: argparse.Namespace, connect: Connect) -> list[Json]:
    rows = recipe_rows(connect())
    if args.raw:
        return rows
    recipes = [
        {
            "id": row.get("foodId"),
            "name": row.get("name"),
            "uses": row.get("userNumberOfUse") or 0,
        }
        for row in rows
        if not row.get("deleted")
    ]
    return sorted(recipes, key=lambda recipe: -recipe["uses"])


def recipes_text(recipes: list[Json]) -> str:
    if not recipes:
        return "no recipes"
    rows = [
        [str(recipe["id"]), str(recipe["uses"]), recipe["name"] or "-"]
        for recipe in recipes
    ]
    return table([["id", "uses", "name"], *rows])


def recipe_id(value: str) -> int:
    try:
        return int(value)
    except ValueError:
        raise argparse.ArgumentTypeError(
            f"Invalid recipe ID '{value}'. Give the number from 'fitatu recipe list'."
        ) from None


def read_recipe(client: Client, id: int) -> Json:
    try:
        return client.get(f"/api/recipes/{id}")
    except HTTPError as error:
        if error.code != 404:
            raise
        raise FitatuCliError(
            f"Fitatu has no recipe with ID {id}.",
            "Run 'fitatu recipe list' to see your recipes' IDs.",
        ) from error


def view_recipe(args: argparse.Namespace, connect: Connect) -> Json:
    recipe = read_recipe(connect(), args.id)
    if args.raw:
        return recipe
    return {
        "id": args.id,
        "name": recipe.get("name"),
        "servings": recipe.get("serving"),
        "deleted": bool(recipe.get("deleted")),
        "ingredients": [
            {
                "name": item.get("name"),
                "quantity": item.get("measureQuantity"),
                "measure": item.get("measureName"),
            }
            for item in recipe.get("items") or []
        ],
        "per_portion": {
            nutrient: round(recipe.get(nutrient) or 0, 1) for nutrient in NUTRIENTS
        },
    }


def dash(value: Any) -> str:
    return "-" if value is None else str(value)


def recipe_text(recipe: Json) -> str:
    """The recipe's fields, a table of its ingredients, and a one-row table of
    its nutrients per portion."""
    fields = "\n".join(
        [
            f"id: {recipe['id']}",
            f"name: {dash(recipe['name'])}",
            f"servings: {dash(recipe['servings'])}",
            f"deleted: {'yes' if recipe['deleted'] else 'no'}",
        ]
    )
    ingredients = (
        table(
            [
                ["ingredient", "quantity", "measure"],
                *(
                    [dash(item[key]) for key in INGREDIENT_COLUMNS]
                    for item in recipe["ingredients"]
                ),
            ]
        )
        if recipe["ingredients"]
        else "no ingredients"
    )
    nutrients = table(
        [
            [f"{key}_{unit}" for key, unit in NUTRIENTS.items()],
            [f"{recipe['per_portion'][key]:.1f}" for key in NUTRIENTS],
        ]
    )
    return f"{fields}\n\n{ingredients}\n\nper portion\n{nutrients}"


def register(subparsers: "argparse._SubParsersAction[argparse.ArgumentParser]") -> None:
    verbs = subparsers.add_parser("recipe", help="your recipes").add_subparsers(
        required=True
    )
    list_parser = verbs.add_parser("list", help="list your recipes, most used first")
    list_parser.set_defaults(run=list_recipes, text=recipes_text, parser=list_parser)
    list_parser.add_argument(
        "--raw", action="store_true", help="print the service's rows for your recipes"
    )
    view = verbs.add_parser(
        "view", help="view one recipe: ingredients and nutrients per portion"
    )
    view.add_argument("id", metavar="ID", type=recipe_id, help="the recipe's ID")
    view.set_defaults(run=view_recipe, text=recipe_text, parser=view)
    view.add_argument(
        "--raw", action="store_true", help="print the full service response"
    )
