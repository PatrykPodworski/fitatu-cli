"""Editing a recipe from a JSON spec of the fields to change. Fitatu has no partial
update: the command reads the recipe and sends it back whole, with the spec's
fields applied. When the ingredients or their quantities change, Fitatu saves the
result under a new ID and marks the old one deleted; other edits keep the ID."""

import argparse
from typing import Any

from fitatu_cli.client import Connect
from fitatu_cli.errors import FitatuCliError, unreadable
from fitatu_cli.recipe import read_recipe, recipe_id
from fitatu_cli.recipe_create import (
    ITEM_KEYS,
    NEW_RECIPE,
    check_fields,
    load_spec,
    saved,
    spec_error,
    spec_fields,
)

Json = dict[str, Any]

FIELDS = ("name", "serving", "description", "items")
ITEM_FIELDS = ("type", *ITEM_KEYS)
# The body fields besides "items" that an edit sends back as they are, unless the
# spec sets them.
KEPT = ("name", "serving", *NEW_RECIPE)


def edit_spec(path: str) -> Json:
    """The spec in the file at `path`, checked before any request."""
    spec = load_spec(path, "edit")
    keys = [key for key in FIELDS if key in spec]
    if not keys:
        raise spec_error(
            path,
            "edit",
            'needs at least one of "name", "serving", "description" or "items".',
        )
    check_fields(path, "edit", spec, keys)
    return spec


def current_items(recipe: Json) -> list[Json]:
    """The recipe's ingredients as the request body lists them. Like the web app,
    it sends the values back as Fitatu returned them, such as `"1.00"`
    quantities."""
    items = []
    for item in recipe.get("items") or []:
        if any(item.get(key) is None for key in ITEM_FIELDS):
            raise unreadable()
        items.append({key: item[key] for key in ITEM_FIELDS})
    return items


def edit_recipe(args: argparse.Namespace, connect: Connect) -> Json:
    client = connect()
    recipe = read_recipe(client, args.id)
    if recipe.get("deleted"):
        raise FitatuCliError(
            f"Recipe {args.id} is deleted.",
            "An edit of its ingredients gives a recipe a new ID; "
            "run 'fitatu recipe list' for its current ID.",
        )
    fields = spec_fields(args.spec)
    if "items" not in fields:
        fields["items"] = current_items(recipe)
    body = {key: recipe.get(key) for key in KEPT} | fields
    return saved(args, lambda: client.put(f"/api/recipes/{args.id}", body))


def register(verbs: "argparse._SubParsersAction[argparse.ArgumentParser]") -> None:
    edit = verbs.add_parser(
        "edit",
        help="edit a recipe from a JSON spec and print its ID",
        description=(
            "Edit recipe ID with SPEC, a JSON file with any of the keys of a "
            '\'fitatu recipe create\' spec: "name", "serving", "description" '
            'and "items". Each key given replaces that field; "items" replaces '
            "every ingredient. Prints the recipe's ID: an edit of the ingredients "
            "or their quantities gives the recipe a new ID and marks the old one "
            "deleted; other edits keep the ID."
        ),
    )
    edit.add_argument("id", metavar="ID", type=recipe_id, help="the recipe's ID")
    edit.add_argument(
        "spec", metavar="SPEC", type=edit_spec, help="the changes' JSON file"
    )
    edit.set_defaults(
        run=edit_recipe, text=lambda recipe: str(recipe["id"]), parser=edit
    )
    edit.add_argument(
        "--raw", action="store_true", help="print the full service response"
    )
