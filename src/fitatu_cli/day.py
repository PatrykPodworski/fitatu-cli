"""One Fitatu day: the logged foods with their nutrients, and the day totals."""

import argparse
from datetime import date, timedelta
from typing import Any

from fitatu_cli.client import Client, Connect
from fitatu_cli.dates import add_date_argument, add_range_arguments
from fitatu_cli.errors import unreadable

Json = dict[str, Any]

NUTRIENTS = {
    "energy": "kcal",
    "carbohydrate": "g",
    "protein": "g",
    "fat": "g",
    "fiber": "g",
    "sugars": "g",
    "salt": "g",
}
FOOD_COLUMNS = ("meal", "name", "quantity", "measure")

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


def table(rows: list[list[str]]) -> str:
    """The rows as lines, each column padded with spaces to its widest cell."""
    widths = [max(len(cell) for cell in column) for column in zip(*rows, strict=True)]
    return "\n".join(
        "  ".join(
            cell.ljust(width) for cell, width in zip(row, widths, strict=True)
        ).rstrip()
        for row in rows
    )


def day_text(day: Json) -> str:
    """The date line, then a table of the foods with a `total` row."""
    heading = f"date: {day['date']}"
    if not day["foods"]:
        return f"{heading}\nno foods logged"
    header = [*FOOD_COLUMNS, *(f"{key}_{unit}" for key, unit in NUTRIENTS.items())]
    foods = [
        [
            *("-" if food[key] is None else str(food[key]) for key in FOOD_COLUMNS),
            *(f"{food[key]:.1f}" for key in NUTRIENTS),
        ]
        for food in day["foods"]
    ]
    total = ["total", "", "", "", *(f"{day['totals'][key]:.1f}" for key in NUTRIENTS)]
    return f"{heading}\n{table([header, *foods, total])}"


def days_text(days: list[Json]) -> str:
    return "\n\n".join(day_text(day) for day in days)


def days(args: argparse.Namespace) -> list[date]:
    fail = args.parser.fail
    prog = args.parser.prog
    if not args.start:
        fail(f"Missing --from for '{prog}'. Run '{prog} --help'.")
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


def view_day(args: argparse.Namespace, connect: Connect) -> Json:
    return summary(connect(), args.date, args.raw)


def list_days(args: argparse.Namespace, connect: Connect) -> list[Json]:
    dates = days(args)
    client = connect()
    return [summary(client, when, args.raw) for when in dates]


def register(subparsers: "argparse._SubParsersAction[argparse.ArgumentParser]") -> None:
    verbs = subparsers.add_parser("day", help="foods and totals by day").add_subparsers(
        required=True
    )
    view = verbs.add_parser("view", help="one day's foods and totals")
    add_date_argument(view)
    view.set_defaults(run=view_day, text=day_text, parser=view)
    list_parser = verbs.add_parser(
        "list", help="each day's foods and totals in a range"
    )
    add_range_arguments(list_parser, default=None)
    list_parser.set_defaults(run=list_days, text=days_text, parser=list_parser)
    for parser in (view, list_parser):
        parser.add_argument(
            "--raw", action="store_true", help="print the full service response"
        )
