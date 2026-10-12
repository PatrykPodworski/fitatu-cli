"""Deleting one of your recipes. Fitatu keeps it marked deleted, so diary entries
that use it still read it."""

import argparse
from typing import Any
from urllib.error import HTTPError

from fitatu_cli.client import Connect
from fitatu_cli.errors import FitatuCliError
from fitatu_cli.recipe import dash, read_recipe, recipe_id

Json = dict[str, Any]

LIST = "Run 'fitatu recipe list' to see your recipes' IDs."


def delete_recipe(args: argparse.Namespace, connect: Connect) -> Json:
    client = connect()
    try:
        recipe = read_recipe(client, args.id)
        if recipe.get("deleted"):
            raise FitatuCliError(f"Recipe {args.id} is already deleted.", LIST)
        client.delete(f"/api/recipes/{args.id}")
    except HTTPError as error:
        if error.code not in (403, 404):
            raise
        raise FitatuCliError(
            f"Fitatu did not delete recipe {args.id} (HTTP {error.code}).",
            "You can delete only your own recipes; run 'fitatu recipe list' to see "
            "them.",
        ) from error
    return {"id": args.id, "name": recipe.get("name")}


def register(verbs: "argparse._SubParsersAction[argparse.ArgumentParser]") -> None:
    delete = verbs.add_parser(
        "delete",
        help="delete one of your recipes",
        description="Delete one of your recipes. There is no confirmation prompt.",
    )
    delete.add_argument("id", metavar="ID", type=recipe_id, help="the recipe's ID")
    delete.set_defaults(
        run=delete_recipe,
        text=lambda recipe: f"deleted recipe {recipe['id']}: {dash(recipe['name'])}",
        parser=delete,
    )
