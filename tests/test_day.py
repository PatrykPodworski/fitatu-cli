from datetime import date
from typing import Any

import pytest
from conftest import http_error

from fitatu_cli.day import Json, day_foods, read_plan, recipe_servings


class FakeClient:
    """Answers `get(path)` with `routes[path]`, or raises it when it is an
    exception, and records the path."""

    def __init__(self, routes: dict[str, Any]) -> None:
        self.routes = routes
        self.paths: list[str] = []

    def login(self) -> None:
        raise AssertionError("unexpected login")

    def get(self, path: str) -> Json:
        self.paths.append(path)
        response = self.routes[path]
        if isinstance(response, BaseException):
            raise response
        return dict(response)


def no_recipes(recipe_id: int) -> float | None:
    raise AssertionError(f"unexpected recipe lookup: {recipe_id}")


def recipe(energy: float, servings: int | None, recipe_id: int = 77) -> Json:
    return {
        "energy": energy,
        "foodType": "RECIPE",
        "recipeId": recipe_id,
        "ingredientsServing": servings,
    }


def plan(*items: Json) -> Json:
    return {"dietPlan": {"lunch": {"items": list(items)}}}


def test_read_plan_gets_the_day_of_the_session_user() -> None:
    client = FakeClient({"/api/diet-and-activity-plan/{uid}/day/2026-07-05": {"x": 1}})

    assert read_plan(client, date(2026, 7, 5)) == {"x": 1}


def test_day_foods_sums_every_meal() -> None:
    day = {
        "dietPlan": {
            "breakfast": {"items": [{"energy": 500}, {"energy": 300}]},
            "lunch": {"items": [{"energy": 700}]},
        }
    }

    assert day_foods(day, no_recipes)["totals"]["energy"] == 1500


def test_day_foods_rescales_a_recipe_cut_into_other_portions() -> None:
    """Fitatu prices a recipe entry at the recipe's own serving count, even when
    the entry splits the batch into a different number of portions."""
    out = day_foods(plan(recipe(900, 18)), lambda _: 12)

    assert out["foods"][0]["energy"] == 600
    assert out["totals"]["energy"] == 600
    assert "rescaled" not in out["foods"][0]
    assert "warnings" not in out


@pytest.mark.parametrize(
    "item",
    [
        recipe(900, 12),
        recipe(900, None),
        {"energy": 900, "foodType": "PRODUCT", "ingredientsServing": 18},
    ],
)
def test_day_foods_leaves_unsplit_entries_alone(item: Json) -> None:
    assert day_foods(plan(item), lambda _: 12)["totals"]["energy"] == 900


@pytest.mark.parametrize(
    "day",
    [
        {},
        {"dietPlan": None},
        {"dietPlan": {"breakfast": None}},
        {"dietPlan": {"breakfast": {"items": None}}},
    ],
)
def test_day_foods_tolerates_holes(day: Json) -> None:
    """Fitatu omits or nulls sections for an empty day."""
    assert day_foods(day, no_recipes) == {
        "foods": [],
        "totals": {
            "energy": 0,
            "carbohydrate": 0,
            "protein": 0,
            "fat": 0,
            "fiber": 0,
            "sugars": 0,
            "salt": 0,
        },
    }


def test_day_foods_lists_items_with_rescaled_macros_and_totals() -> None:
    day = {
        "dietPlan": {
            "breakfast": {
                "mealName": "Snack",
                "items": [
                    {
                        "name": "Gel",
                        "measureQuantity": 3,
                        "measureName": "package",
                        "energy": 471,
                        "carbohydrate": 118.8,
                        "protein": 1,
                        "fat": 2,
                        "fiber": 3,
                        "sugars": 4,
                        "salt": None,
                    },
                ],
            },
            "dinner": {
                "items": [
                    {
                        "name": "Stew",
                        "foodType": "RECIPE",
                        "recipeId": 7,
                        "ingredientsServing": 4,
                        "measureQuantity": 1,
                        "measureName": "portion",
                        "energy": 400,
                        "carbohydrate": 40,
                    },
                ]
            },
        }
    }

    out = day_foods(day, lambda _: 2)

    assert out == {
        "foods": [
            {
                "meal": "Snack",
                "name": "Gel",
                "quantity": 3,
                "measure": "package",
                "energy": 471,
                "carbohydrate": 118.8,
                "protein": 1,
                "fat": 2,
                "fiber": 3,
                "sugars": 4,
                "salt": 0,
            },
            {
                "meal": "dinner",
                "name": "Stew",
                "quantity": 1,
                "measure": "portion",
                "energy": 200,
                "carbohydrate": 20,
                "protein": 0,
                "fat": 0,
                "fiber": 0,
                "sugars": 0,
                "salt": 0,
            },
        ],
        "totals": {
            "energy": 671,
            "carbohydrate": 138.8,
            "protein": 1,
            "fat": 2,
            "fiber": 3,
            "sugars": 4,
            "salt": 0,
        },
    }


def test_totals_sum_unrounded_values() -> None:
    """Three foods of 0.04 g round to 0.0 each, but sum to 0.1."""
    out = day_foods(plan(*[{"salt": 0.04}] * 3), no_recipes)

    assert [food["salt"] for food in out["foods"]] == [0.0, 0.0, 0.0]
    assert out["totals"]["salt"] == 0.1


def test_recipe_servings_reads_serving_as_a_number() -> None:
    client = FakeClient({"/api/recipes/77": {"serving": "12"}})

    assert recipe_servings(client)(77) == 12.0


def test_recipe_servings_gets_a_recipe_once() -> None:
    client = FakeClient({"/api/recipes/77": {"serving": 12}})

    out = day_foods(plan(recipe(900, 18), recipe(450, 18)), recipe_servings(client))

    assert out["totals"]["energy"] == 900
    assert client.paths == ["/api/recipes/77"]


@pytest.mark.parametrize("code", [404, 410])
def test_a_missing_recipe_keeps_unscaled_values_and_warns(code: int) -> None:
    client = FakeClient(
        {"/api/recipes/77": http_error(code), "/api/recipes/78": {"serving": 12}}
    )

    out = day_foods(
        plan(recipe(900, 18), recipe(900, 18), recipe(900, 18, recipe_id=78)),
        recipe_servings(client),
    )

    assert [food["energy"] for food in out["foods"]] == [900, 900, 600]
    assert [food.get("rescaled") for food in out["foods"]] == [False, False, None]
    assert out["warnings"] == [77]
    assert client.paths == ["/api/recipes/77", "/api/recipes/78"]


def test_a_recipe_without_serving_keeps_unscaled_values_and_warns() -> None:
    client = FakeClient({"/api/recipes/77": {}})

    out = day_foods(plan(recipe(900, 18)), recipe_servings(client))

    assert out["foods"][0]["energy"] == 900
    assert out["foods"][0]["rescaled"] is False
    assert out["warnings"] == [77]


def test_other_recipe_errors_propagate() -> None:
    client = FakeClient({"/api/recipes/77": http_error(500)})

    with pytest.raises(Exception, match="HTTP Error 500"):
        day_foods(plan(recipe(900, 18)), recipe_servings(client))
