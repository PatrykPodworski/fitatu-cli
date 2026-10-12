"""Removes one entry from a day, as the web app does: it writes the item again with
`deletedAt` set, and the day's read no longer lists it."""

import argparse
from datetime import datetime
from typing import Any

from fitatu_cli.client import Connect
from fitatu_cli.dates import parse_date, timestamp
from fitatu_cli.day import read_plan
from fitatu_cli.entry_create import save_item
from fitatu_cli.errors import ISSUES, FitatuCliError
from fitatu_cli.recipe import dash

Json = dict[str, Any]


def find_entry(args: argparse.Namespace, plan: Json) -> tuple[str, str, Json]:
    """The meal key, the meal's display name and the item of entry `args.entry`."""
    for key, meal in (plan.get("dietPlan") or {}).items():
        if not isinstance(meal, dict):
            continue
        for item in meal.get("items") or []:
            if item.get("planDayDietItemId") == args.entry:
                return key, meal.get("mealName") or key, item
    day = f"{args.date:%Y-%m-%d}"
    raise FitatuCliError(
        f"No entry '{args.entry}' on {day}.",
        f"Run 'fitatu day view {day}' to see the day's entry IDs.",
    )


def delete_entry(args: argparse.Namespace, connect: Connect) -> Json:
    client = connect()
    plan = read_plan(client, args.date)
    key, meal, item = find_entry(args, plan)
    food = "productId" if item.get("foodType") == "PRODUCT" else "recipeId"
    now = timestamp(datetime.now())
    save_item(
        client,
        args.date,
        plan,
        key,
        {
            "planDayDietItemId": args.entry,
            "foodType": item.get("foodType"),
            "measureId": item.get("measureId"),
            "measureQuantity": item.get("measureQuantity"),
            "ingredientsServing": item.get("ingredientsServing"),
            "mealNumber": None,
            "numberOfMeals": None,
            "eaten": False,
            food: item.get(food),
            "source": item.get("source"),
            "deletedAt": now,
            "updatedAt": now,
        },
        verb="delete",
        action=f"Rerun with --debug and report it at {ISSUES}.",
    )
    return {
        "id": args.entry,
        "date": f"{args.date:%Y-%m-%d}",
        "meal": meal,
        "name": item.get("name"),
    }


def entry_text(entry: Json) -> str:
    return f"deleted entry {entry['id']} from {entry['meal']}: {dash(entry['name'])}"


def register(verbs: "argparse._SubParsersAction[argparse.ArgumentParser]") -> None:
    delete = verbs.add_parser(
        "delete",
        help="remove an entry from a day",
        description="Remove one entry from a day. There is no confirmation prompt.",
    )
    delete.add_argument(
        "date", metavar="DATE", type=parse_date, help="today | yesterday | YYYY-MM-DD"
    )
    delete.add_argument(
        "entry",
        metavar="ENTRY_ID",
        help="the entry's ID, the id column of 'fitatu day view'",
    )
    delete.set_defaults(run=delete_entry, text=entry_text, parser=delete)
