"""One Fitatu day: the logged foods with their nutrients, and the day totals."""

import argparse
from datetime import date
from typing import Any

from fitatu_cli.client import Client, Connect
from fitatu_cli.dates import add_date_argument
from fitatu_cli.errors import unreadable

Json = dict[str, Any]

NUTRIENTS = ("energy", "carbohydrate", "protein", "fat", "fiber", "sugars", "salt")


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


def day(args: argparse.Namespace, connect: Connect) -> Json:
    plan = read_plan(connect(), args.date)
    if args.raw:
        return plan
    return {"date": f"{args.date:%Y-%m-%d}"} | day_foods(plan)


def register(subparsers: "argparse._SubParsersAction[argparse.ArgumentParser]") -> None:
    day_parser = subparsers.add_parser("day", help="one day's foods and totals")
    add_date_argument(day_parser)
    day_parser.add_argument(
        "--raw", action="store_true", help="print the full service response"
    )
    day_parser.set_defaults(run=day)
