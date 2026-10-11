from datetime import date

import pytest

from fitatu_cli.day import Json, day_foods, read_plan


class FakeClient:
    """Answers `get(path)` with `routes[path]` and records the path."""

    def __init__(self, routes: dict[str, Json]) -> None:
        self.routes = routes
        self.paths: list[str] = []

    def login(self) -> None:
        raise AssertionError("unexpected login")

    def get(self, path: str) -> Json:
        self.paths.append(path)
        return self.routes[path]


def plan(*items: Json) -> Json:
    return {"dietPlan": {"lunch": {"items": list(items)}}}


def test_read_plan_gets_the_day_of_the_session_user() -> None:
    client = FakeClient({"/api/diet-and-activity-plan/{uid}/day/2026-07-05": {"x": 1}})

    assert read_plan(client, date(2026, 7, 5)) == {"x": 1}
    assert client.paths == ["/api/diet-and-activity-plan/{uid}/day/2026-07-05"]


def test_day_foods_sums_every_meal() -> None:
    day = {
        "dietPlan": {
            "breakfast": {"items": [{"energy": 500}, {"energy": 300}]},
            "lunch": {"items": [{"energy": 700}]},
        }
    }

    assert day_foods(day)["totals"]["energy"] == 1500


def test_day_foods_reads_a_recipe_item_like_a_product() -> None:
    """Fitatu sends a recipe item's nutrients for the portions eaten, even when
    the entry splits the batch into other portions than the recipe."""
    item = {
        "foodType": "RECIPE",
        "recipeId": 77,
        "ingredientsServing": 1.5,
        "measureQuantity": 3,
        "energy": 900,
    }

    assert day_foods(plan(item))["totals"]["energy"] == 900


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
    assert day_foods(day) == {
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


def test_day_foods_lists_items_with_nutrients_and_totals() -> None:
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
                        "carbohydrate": 118.84,
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
                        "measureQuantity": 1,
                        "measureName": "portion",
                        "energy": 200,
                        "carbohydrate": 20,
                    },
                ]
            },
        }
    }

    assert day_foods(day) == {
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
    out = day_foods(plan(*[{"salt": 0.04}] * 3))

    assert [food["salt"] for food in out["foods"]] == [0.0, 0.0, 0.0]
    assert out["totals"]["salt"] == 0.1
