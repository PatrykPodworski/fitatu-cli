"""One Fitatu day: the logged foods with their nutrients, and the day totals."""

import functools
from collections.abc import Callable
from datetime import date
from typing import Any
from urllib.error import HTTPError

from fitatu_cli.client import Client

Json = dict[str, Any]
RecipeServing = Callable[[int], float | None]

NUTRIENTS = ("energy", "carbohydrate", "protein", "fat", "fiber", "sugars", "salt")


def read_plan(client: Client, day: date) -> Json:
    return client.get(f"/api/diet-and-activity-plan/{{uid}}/day/{day:%Y-%m-%d}")


def recipe_servings(client: Client) -> RecipeServing:
    """The serving count of a recipe, or None when the recipe is gone or has none.
    Each recipe is fetched once per returned lookup."""

    @functools.cache
    def serving(recipe_id: int) -> float | None:
        try:
            recipe = client.get(f"/api/recipes/{recipe_id}")
        except HTTPError as error:
            if error.code in (404, 410):
                return None
            raise
        # Fitatu sends the serving count as a number or a numeric string.
        return float(recipe["serving"]) if recipe.get("serving") else None

    return serving


def _items(plan: Json) -> list[tuple[str, Json]]:
    return [
        (meal.get("mealName") or key, item)
        for key, meal in (plan.get("dietPlan") or {}).items()
        if isinstance(meal, dict)
        for item in meal.get("items") or []
    ]


def _scale(item: Json, recipe_serving: RecipeServing) -> float | None:
    """A recipe entry's nutrients are priced at the recipe's own serving count,
    even when the entry splits the batch into a different number of portions
    (`ingredientsServing`). Returns None when the recipe's serving is unknown."""
    servings = item.get("ingredientsServing")
    if servings and item.get("foodType") == "RECIPE":
        base = recipe_serving(item["recipeId"])
        return base / servings if base else None
    return 1.0


def day_foods(plan: Json, recipe_serving: RecipeServing) -> Json:
    """Every logged food with its meal and nutrients, recipes rescaled, plus the
    day totals. A recipe that could not be rescaled keeps its values, gets
    `"rescaled": false`, and its ID goes into `warnings`."""
    foods = []
    totals = dict.fromkeys(NUTRIENTS, 0.0)
    warnings: list[int] = []
    for meal, item in _items(plan):
        scale = _scale(item, recipe_serving)
        food = {
            "meal": meal,
            "name": item.get("name"),
            "quantity": item.get("measureQuantity"),
            "measure": item.get("measureName"),
        }
        for nutrient in NUTRIENTS:
            value = (item.get(nutrient) or 0) * (scale or 1.0)
            totals[nutrient] += value
            food[nutrient] = round(value, 1)
        if scale is None:
            food["rescaled"] = False
            if item["recipeId"] not in warnings:
                warnings.append(item["recipeId"])
        foods.append(food)
    result: Json = {
        "foods": foods,
        "totals": {nutrient: round(value, 1) for nutrient, value in totals.items()},
    }
    if warnings:
        result["warnings"] = warnings
    return result
