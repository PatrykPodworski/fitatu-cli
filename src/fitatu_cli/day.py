"""One Fitatu day: the logged foods with their nutrients, and the day totals."""

import argparse
from datetime import date, timedelta
from typing import Any

from fitatu_cli.client import Client, Connect
from fitatu_cli.dates import add_date_argument, add_range_arguments
from fitatu_cli.errors import unreadable

Json = dict[str, Any]

NUTRIENTS = ("energy", "carbohydrate", "protein", "fat", "fiber", "sugars", "salt")

# ponytail: guards Fitatu's unknown rate limit; raise it once the limit is known.
MAX_DAYS = 31


def read_plan(client: Client, day: date) -> Json:
    plan = client.get(f"/api/diet-and-activity-plan/{{uid}}/day/{day:%Y-%m-%d}")
    if not isinstance(plan.get("dietPlan"), dict | None):
        raise unreadable()
    return plan


def _items(plan: Json) -> list[tuple[str, Json]]:
    return [
        (meal.get("mealName") or key, item)
        for key, meal in (plan.get("dietPlan") or {}).items()
        if isinstance(meal, dict)
        for item in meal.get("items") or []
    ]


def day_foods(plan: Json) -> Json:
    """Every logged food with its meal and nutrients, plus the day totals. A
    recipe item's nutrients already cover the portions eaten, like a product's."""
    foods = []
    totals = dict.fromkeys(NUTRIENTS, 0.0)
    for meal, item in _items(plan):
        food = {
            "meal": meal,
            "name": item.get("name"),
            "quantity": item.get("measureQuantity"),
            "measure": item.get("measureName"),
        }
        for nutrient in NUTRIENTS:
            value = item.get(nutrient) or 0
            totals[nutrient] += value
            food[nutrient] = round(value, 1)
        foods.append(food)
    return {
        "foods": foods,
        "totals": {nutrient: round(value, 1) for nutrient, value in totals.items()},
    }


def summary(client: Client, when: date, raw: bool) -> Json:
    plan = read_plan(client, when)
    if raw:
        return plan
    return {"date": f"{when:%Y-%m-%d}"} | day_foods(plan)


def days(args: argparse.Namespace) -> list[date]:
    fail = args.parser.fail
    help = f"Run '{args.parser.prog} --help'."
    if args.date:
        fail(f"Give either a date or --from/--to, not both. {help}")
    if not args.start:
        fail(f"Missing --from for '{args.parser.prog}'. {help}")
    start = args.start
    end = args.end or date.today()
    if end < start:
        fail(f"--to {end} is before --from {start}. Give a --to on or after --from.")
    count = (end - start).days + 1
    if count > MAX_DAYS:
        fail(
            f"The range covers {count} days; the limit is {MAX_DAYS}. "
            "Split it into shorter ranges."
        )
    return [start + timedelta(days=n) for n in range(count)]


def day(args: argparse.Namespace, connect: Connect) -> Json | list[Json]:
    if not (args.start or args.end):
        return summary(connect(), args.date or date.today(), args.raw)
    dates = days(args)
    client = connect()
    return [summary(client, when, args.raw) for when in dates]


def register(subparsers: "argparse._SubParsersAction[argparse.ArgumentParser]") -> None:
    day_parser = subparsers.add_parser("day", help="one day's foods and totals")
    add_date_argument(day_parser)
    add_range_arguments(day_parser, default=None)
    day_parser.add_argument(
        "--raw", action="store_true", help="print the full service response"
    )
    # A date of None tells an omitted date apart from one given with --from/--to.
    day_parser.set_defaults(run=day, parser=day_parser, date=None)
