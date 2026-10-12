"""Puts a product or a recipe into a meal on a day, as the web app does: one POST
that holds only the new item."""

import argparse
import secrets
import uuid
from collections.abc import Callable
from datetime import date, datetime
from http.client import IncompleteRead
from typing import Any, NoReturn
from urllib.error import HTTPError

from fitatu_cli.client import Client, Connect
from fitatu_cli.dates import parse_date, timestamp
from fitatu_cli.day import read_plan
from fitatu_cli.errors import FitatuCliError, reason, unreadable
from fitatu_cli.recipe import read_recipe, recipe_id

Json = dict[str, Any]

PORTION = 39
FROM_SEARCH = "Give the number from 'fitatu food search'."
CHECK_ENTRY = "Check the food ID, the measure ID and the quantity."


def product_id(value: str) -> int:
    try:
        return int(value)
    except ValueError:
        raise argparse.ArgumentTypeError(
            f"Invalid product ID '{value}'. {FROM_SEARCH}"
        ) from None


def measure_id(value: str) -> int:
    try:
        return int(value)
    except ValueError:
        raise argparse.ArgumentTypeError(
            f"Invalid measure ID '{value}'. {FROM_SEARCH}"
        ) from None


def quantity(value: str) -> float:
    try:
        number = float(value)
    except ValueError:
        number = 0
    # NaN fails every comparison, so this also rejects it.
    if not 0 < number < float("inf"):
        raise argparse.ArgumentTypeError(
            f"Invalid quantity '{value}'. Give a number greater than 0."
        )
    return number


def new_entry_id() -> str:
    """A UUID v1, as the web app makes. Python's `uuid1` puts this machine's MAC
    address in the ID; a random node with the multicast bit set, as RFC 9562
    allows, keeps it out."""
    return str(uuid.uuid1(node=secrets.randbits(48) | 1 << 40))


def meal_key(args: argparse.Namespace, plan: Json) -> tuple[str, str]:
    """The key and display name of the meal `args.meal` names: by display name
    first, since meals are renamed per account, then by key."""
    meals = {
        key: meal.get("mealName") or key
        for key, meal in (plan.get("dietPlan") or {}).items()
        if isinstance(meal, dict)
    }
    if not meals:
        raise unreadable()
    wanted = args.meal.lower()
    for key, name in meals.items():
        if name.lower() == wanted:
            return key, name
    for key, name in meals.items():
        if key.lower() == wanted:
            return key, name
    fail: Callable[[str], NoReturn] = args.parser.fail
    fail(
        f"No meal '{args.meal}' on {args.date:%Y-%m-%d}. "
        f"Use one of: {', '.join(meals.values())}."
    )


def food(args: argparse.Namespace, client: Client) -> Json:
    if args.product is not None:
        return {"ingredientsServing": None, "productId": args.product}
    recipe = read_recipe(client, args.recipe)
    return {"ingredientsServing": recipe.get("serving"), "recipeId": args.recipe}


def save_item(client: Client, day: date, plan: Json, key: str, item: Json) -> None:
    """Writes one item into meal `key` of `day`, whose read is `plan`. Fitatu
    upserts items by `planDayDietItemId` and leaves the day's other items as they
    are, but sets the note and tags to what the write holds, so the write resends
    them, and the toilet items, from the read."""
    tags = plan.get("tagsIds")
    toilet = plan.get("toilet")
    try:
        receipts: object = client.post(
            "/api/diet-plan/{uid}/days",
            {
                f"{day:%Y-%m-%d}": {
                    "dietPlan": {key: {"items": [item]}},
                    "toiletItems": toilet if isinstance(toilet, list) else [],
                    "note": plan.get("note"),
                    "tagsIds": tags if isinstance(tags, list) else [],
                }
            },
        )
    except HTTPError as error:
        if not 400 <= error.code < 500:
            raise
        raise FitatuCliError(
            f"Fitatu did not save the entry (HTTP {error.code}).", CHECK_ENTRY
        ) from error
    if (
        not isinstance(receipts, list)
        or not receipts
        or not all(isinstance(receipt, dict) for receipt in receipts)
    ):
        raise unreadable()
    for receipt in receipts:
        if receipt.get("errorMessage"):
            raise FitatuCliError(
                f"Fitatu did not save the entry ({receipt['errorMessage']}).",
                CHECK_ENTRY,
            )


def create_entry(args: argparse.Namespace, connect: Connect) -> Json:
    measure = args.measure
    if measure is None:
        if args.product is not None:
            args.parser.fail(
                "--product needs --measure. "
                "Give the measure ID from 'fitatu food search'."
            )
        measure = PORTION
    client = connect()
    plan = read_plan(client, args.date)
    key, meal = meal_key(args, plan)
    entry_id = new_entry_id()
    item = {
        "planDayDietItemId": entry_id,
        "foodType": "PRODUCT" if args.product is not None else "RECIPE",
        "measureId": measure,
        "measureQuantity": args.quantity,
        **food(args, client),
        "source": "API",
        "updatedAt": timestamp(datetime.now()),
    }
    try:
        save_item(client, args.date, plan, key, item)
    except FitatuCliError as error:
        # A connection lost after the request went out may still have saved the
        # entry, and each run makes a new entry. An HTTPError, such as a 429, is
        # an OSError too, but an answer.
        cause = error.__cause__
        if not isinstance(cause, OSError | IncompleteRead) or isinstance(
            cause, HTTPError
        ):
            raise
        raise FitatuCliError(
            f"Fitatu's answer did not arrive ({reason(cause)}), so the "
            "entry may be saved.",
            f"Wait a minute and check 'fitatu day view {args.date:%Y-%m-%d}' "
            "before you run this again.",
        ) from error
    return {"id": entry_id, "date": f"{args.date:%Y-%m-%d}", "meal": meal}


def entry_text(entry: Json) -> str:
    return str(entry["id"])


def register(verbs: "argparse._SubParsersAction[argparse.ArgumentParser]") -> None:
    create = verbs.add_parser(
        "create", help="put a product or a recipe into a meal on a day"
    )
    create.add_argument(
        "date", metavar="DATE", type=parse_date, help="today | yesterday | YYYY-MM-DD"
    )
    create.add_argument(
        "meal",
        metavar="MEAL",
        help="the meal's name as the app shows it, or its key, such as breakfast",
    )
    food_group = create.add_mutually_exclusive_group(required=True)
    food_group.add_argument(
        "--product",
        metavar="ID",
        type=product_id,
        help="a product ID from 'fitatu food search'",
    )
    food_group.add_argument(
        "--recipe",
        metavar="ID",
        type=recipe_id,
        help="a recipe ID from 'fitatu recipe list'",
    )
    create.add_argument(
        "--quantity",
        metavar="N",
        type=quantity,
        required=True,
        help="how many of the measure",
    )
    create.add_argument(
        "--measure",
        metavar="ID",
        type=measure_id,
        help="the measure's ID from 'fitatu food search' "
        f"(default for a recipe: {PORTION}, a portion)",
    )
    create.set_defaults(run=create_entry, text=entry_text, parser=create)
