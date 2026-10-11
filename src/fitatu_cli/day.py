"""One Fitatu day: the logged foods with their nutrients, and the day totals."""

from datetime import date
from typing import Any

from fitatu_cli.client import Client

Json = dict[str, Any]

NUTRIENTS = ("energy", "carbohydrate", "protein", "fat", "fiber", "sugars", "salt")


def read_plan(client: Client, day: date) -> Json:
    return client.get(f"/api/diet-and-activity-plan/{{uid}}/day/{day:%Y-%m-%d}")


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
