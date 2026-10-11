import json
from datetime import date
from typing import Any

import pytest
from conftest import FakeClient, run_json, run_text

from fitatu_cli import day
from fitatu_cli.cli import main
from fitatu_cli.day import Json, day_foods, read_plan


def plan(*items: Json) -> Json:
    return {"dietPlan": {"lunch": {"items": list(items)}}}


def test_read_plan_gets_the_day_of_the_session_user() -> None:
    client = FakeClient(get={"x": 1})

    assert read_plan(client, date(2026, 7, 5)) == {"x": 1}
    assert client.calls == [
        ("get", ("/api/diet-and-activity-plan/{uid}/day/2026-07-05",), {})
    ]


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
                        "name": "Bar",
                        "measureQuantity": 2,
                        "measureName": "piece",
                        "energy": 300,
                        "carbohydrate": 50.44,
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
                "name": "Bar",
                "quantity": 2,
                "measure": "piece",
                "energy": 300,
                "carbohydrate": 50.4,
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
            "energy": 500,
            "carbohydrate": 70.4,
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


ZERO_TOTALS = dict.fromkeys(
    ("energy", "carbohydrate", "protein", "fat", "fiber", "sugars", "salt"), 0
)


def test_day_prints_foods_in_response_meal_order(
    capsys: pytest.CaptureFixture[str],
) -> None:
    client = FakeClient(
        get={
            "dietPlan": {
                "dinner": {
                    "mealName": "Dinner",
                    "items": [
                        {
                            "name": "Stew",
                            "foodType": "RECIPE",
                            "recipeId": 77,
                            "ingredientsServing": 4,
                            "measureQuantity": 2,
                            "measureName": "portion",
                            "energy": 640.25,
                            "protein": None,
                        }
                    ],
                },
                "breakfast": {
                    "mealName": "Breakfast",
                    "items": [{"name": "Oats", "measureQuantity": 50, "energy": 190}],
                },
            }
        }
    )

    out = run_json(["day", "view", "2026-07-05", "--json"], client, capsys)

    assert client.calls == [
        ("get", ("/api/diet-and-activity-plan/{uid}/day/2026-07-05",), {})
    ]
    assert out == {
        "date": "2026-07-05",
        "foods": [
            {
                "meal": "Dinner",
                "name": "Stew",
                "quantity": 2,
                "measure": "portion",
                **ZERO_TOTALS,
                "energy": 640.2,
            },
            {
                "meal": "Breakfast",
                "name": "Oats",
                "quantity": 50,
                "measure": None,
                **ZERO_TOTALS,
                "energy": 190,
            },
        ],
        "totals": {**ZERO_TOTALS, "energy": 830.2},
    }


def test_day_defaults_to_today_and_prints_an_empty_day(
    capsys: pytest.CaptureFixture[str],
) -> None:
    client = FakeClient(get={"dietPlan": {"breakfast": {"items": []}}})

    out = run_json(["day", "view", "--json"], client, capsys)

    assert client.calls[0][1] == (
        f"/api/diet-and-activity-plan/{{uid}}/day/{date.today():%Y-%m-%d}",
    )
    assert out == {
        "date": f"{date.today():%Y-%m-%d}",
        "foods": [],
        "totals": ZERO_TOTALS,
    }


def test_day_raw_prints_the_response_unchanged(
    capsys: pytest.CaptureFixture[str],
) -> None:
    response = {"dietPlan": {"lunch": {"items": [{"energy": 1.23456}]}}, "water": 2}

    assert run_json(
        ["day", "view", "2026-07-05", "--raw"], FakeClient(get=response), capsys
    ) == (response)


def test_day_invalid_date_exits_2(capsys: pytest.CaptureFixture[str]) -> None:
    with pytest.raises(SystemExit) as exit:
        main(["day", "view", "5.07"], connect=FakeClient)

    assert exit.value.code == 2
    assert capsys.readouterr().err == (
        "fitatu: Invalid date '5.07'. Use today, yesterday or YYYY-MM-DD.\n"
    )


def test_help_lists_day_and_its_verbs(capsys: pytest.CaptureFixture[str]) -> None:
    with pytest.raises(SystemExit):
        main(["--help"])
    assert "day foods and totals by day" in " ".join(capsys.readouterr().out.split())

    with pytest.raises(SystemExit) as exit:
        main(["day", "--help"])

    assert exit.value.code == 0
    help_text = " ".join(capsys.readouterr().out.split())
    assert "usage: fitatu day [-h] {view,list}" in help_text
    assert "view one day's foods and totals" in help_text
    assert "list each day's foods and totals in a range" in help_text


@pytest.mark.parametrize(
    ("verb", "usage"),
    [
        ("view", "usage: fitatu day view [-h] [--raw] [--json] [date]"),
        (
            "list",
            "usage: fitatu day list [-h] [--from DATE] [--to DATE] [--raw] [--json]",
        ),
    ],
)
def test_day_verb_help_shows_its_options(
    verb: str, usage: str, capsys: pytest.CaptureFixture[str]
) -> None:
    with pytest.raises(SystemExit) as exit:
        main(["day", verb, "--help"])

    assert exit.value.code == 0
    help_text = " ".join(capsys.readouterr().out.split())
    assert usage in help_text
    assert "--raw print the full service response" in help_text
    assert "--json print JSON instead of text" in help_text


PATH = "/api/diet-and-activity-plan/{uid}/day/"


class Today(date):
    @classmethod
    def today(cls) -> "Today":
        return cls(2026, 7, 5)


def test_day_range_logs_in_once_and_reads_each_day_in_order(
    capsys: pytest.CaptureFixture[str],
) -> None:
    client = FakeClient(get={"dietPlan": {"lunch": {"items": [{"energy": 100}]}}})
    logins: list[Any] = []

    def connect() -> FakeClient:
        logins.append(client)
        return client

    assert (
        main(
            ["day", "list", "--from", "2026-06-30", "--to", "2026-07-02", "--json"],
            connect,
        )
        == 0
    )
    out = json.loads(capsys.readouterr().out)

    assert len(logins) == 1
    assert [call[1][0] for call in client.calls] == [
        f"{PATH}2026-06-30",
        f"{PATH}2026-07-01",
        f"{PATH}2026-07-02",
    ]
    assert [item["date"] for item in out] == ["2026-06-30", "2026-07-01", "2026-07-02"]
    assert out[0]["totals"]["energy"] == 100


def test_day_from_alone_runs_to_today(
    capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(day, "date", Today)
    client = FakeClient(get={})

    out = run_json(["day", "list", "--from", "2026-07-04", "--json"], client, capsys)

    assert [call[1][0] for call in client.calls] == [
        f"{PATH}2026-07-04",
        f"{PATH}2026-07-05",
    ]
    assert [item["date"] for item in out] == ["2026-07-04", "2026-07-05"]


def test_day_from_today_alone_reads_today(
    capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(day, "date", Today)

    out = run_json(["day", "list", "--from", "2026-07-05"], FakeClient(get={}), capsys)

    assert [item["date"] for item in out] == ["2026-07-05"]


def test_day_range_of_31_days_passes(capsys: pytest.CaptureFixture[str]) -> None:
    client = FakeClient(get={})

    out = run_json(
        ["day", "list", "--from", "2026-07-01", "--to", "2026-07-31", "--json"],
        client,
        capsys,
    )

    assert len(out) == 31
    assert client.calls[-1][1][0] == f"{PATH}2026-07-31"


def test_day_range_of_one_day_prints_an_array(
    capsys: pytest.CaptureFixture[str],
) -> None:
    out = run_json(
        ["day", "list", "--from", "2026-07-05", "--to", "2026-07-05", "--json"],
        FakeClient(get={}),
        capsys,
    )

    assert [item["date"] for item in out] == ["2026-07-05"]


def test_day_range_raw_prints_the_responses_unchanged(
    capsys: pytest.CaptureFixture[str],
) -> None:
    response = {"dietPlan": {"lunch": {"items": [{"energy": 1.23456}]}}}

    out = run_json(
        ["day", "list", "--from", "2026-07-04", "--to", "2026-07-05", "--raw"],
        FakeClient(get=response),
        capsys,
    )

    assert out == [response, response]


LIST_HELP = "Run 'fitatu day list --help'"


@pytest.mark.parametrize(
    ("argv", "error"),
    [
        (
            ["list", "--to", "2026-07-05"],
            f"Missing --from for 'fitatu day list'. {LIST_HELP}.",
        ),
        (
            ["list", "2026-07-05", "--from", "2026-07-01"],
            "Unexpected argument '2026-07-05' for 'fitatu day list'. "
            f"{LIST_HELP} for all options.",
        ),
        (
            ["view", "2026-07-05", "--to", "2026-07-06"],
            "Unknown option '--to' for 'fitatu day view'. Did you mean '--json'? "
            "Run 'fitatu day view --help' for all options.",
        ),
        (
            ["--json", "view", "2026-07-05"],
            "Option '--json' goes after the command. "
            "Run 'fitatu day view --json 2026-07-05'.",
        ),
        (
            ["--raw", "view", "2026-07-05"],
            "Option '--raw' goes after the command. "
            "Run 'fitatu day view --raw 2026-07-05'.",
        ),
        (
            ["list", "--from", "2026-07-05", "--to", "2026-07-04"],
            "--to 2026-07-04 is before --from 2026-07-05. "
            "Give a --to on or after --from.",
        ),
        (
            ["list", "--from", "2026-07-06"],
            "--from 2026-07-06 is in the future. Give a --from on or before today.",
        ),
        (
            ["list", "--from", "2026-07-01", "--to", "2026-08-01"],
            "The range covers 32 days; the limit is 31. Split it into shorter ranges.",
        ),
    ],
)
def test_day_bad_range_exits_2(
    argv: list[str],
    error: str,
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(day, "date", Today)
    client = FakeClient(get={})

    with pytest.raises(SystemExit) as exit:
        main(["day", *argv], connect=lambda: client)

    assert exit.value.code == 2
    assert capsys.readouterr().err == f"fitatu: {error}\n"
    assert client.calls == []


OATS = {
    "name": "Oats",
    "measureQuantity": 80,
    "measureName": "g",
    "energy": 300,
    "carbohydrate": 50.44,
    "protein": 10,
    "fat": 5.6,
    "fiber": 8,
    "sugars": 1,
    "salt": 0,
}
STEW = {
    "name": "Stew",
    "measureQuantity": 1.5,
    "measureName": "portion",
    "energy": 540.3,
    "carbohydrate": 60,
    "protein": 30,
    "fat": 18,
    "fiber": 6,
    "sugars": 5,
    "salt": 1.8,
}
OATS_AND_STEW = """\
date: 2026-07-05
meal       name  quantity  measure  energy_kcal  carbohydrate_g  protein_g  fat_g  fiber_g  sugars_g  salt_g
Breakfast  Oats  80        g        300.0        50.4            10.0       5.6    8.0      1.0       0.0
Lunch      Stew  1.5       portion  540.3        60.0            30.0       18.0   6.0      5.0       1.8
total                               840.3        110.4           40.0       23.6   14.0     6.0       1.8
"""  # noqa: E501


def test_day_prints_a_table_of_foods_with_a_total_row(
    capsys: pytest.CaptureFixture[str],
) -> None:
    client = FakeClient(
        get={
            "dietPlan": {
                "breakfast": {"mealName": "Breakfast", "items": [OATS]},
                "lunch": {"mealName": "Lunch", "items": [STEW]},
            }
        }
    )

    assert run_text(["day", "view", "2026-07-05"], client, capsys) == OATS_AND_STEW


def test_day_prints_a_dash_for_a_missing_value_and_0_for_a_missing_nutrient(
    capsys: pytest.CaptureFixture[str],
) -> None:
    client = FakeClient(get=plan({"name": "Tea", "measureQuantity": 1, "energy": 2}))

    assert run_text(["day", "view", "2026-07-05"], client, capsys) == (
        """\
date: 2026-07-05
meal   name  quantity  measure  energy_kcal  carbohydrate_g  protein_g  fat_g  fiber_g  sugars_g  salt_g
lunch  Tea   1         -        2.0          0.0             0.0        0.0    0.0      0.0       0.0
total                           2.0          0.0             0.0        0.0    0.0      0.0       0.0
"""  # noqa: E501
    )


def test_day_prints_no_foods_logged_for_an_empty_day(
    capsys: pytest.CaptureFixture[str],
) -> None:
    client = FakeClient(get={"dietPlan": {"breakfast": {"items": []}}})

    assert run_text(["day", "view", "2026-07-05"], client, capsys) == (
        "date: 2026-07-05\nno foods logged\n"
    )


def test_day_list_prints_one_block_per_day_with_a_blank_line_between(
    capsys: pytest.CaptureFixture[str],
) -> None:
    client = FakeClient(get=plan({"name": "Tea", "measureQuantity": 1, "energy": 2}))

    assert run_text(
        ["day", "list", "--from", "2026-07-04", "--to", "2026-07-05"], client, capsys
    ) == (
        """\
date: 2026-07-04
meal   name  quantity  measure  energy_kcal  carbohydrate_g  protein_g  fat_g  fiber_g  sugars_g  salt_g
lunch  Tea   1         -        2.0          0.0             0.0        0.0    0.0      0.0       0.0
total                           2.0          0.0             0.0        0.0    0.0      0.0       0.0

date: 2026-07-05
meal   name  quantity  measure  energy_kcal  carbohydrate_g  protein_g  fat_g  fiber_g  sugars_g  salt_g
lunch  Tea   1         -        2.0          0.0             0.0        0.0    0.0      0.0       0.0
total                           2.0          0.0             0.0        0.0    0.0      0.0       0.0
"""  # noqa: E501
    )


def test_day_raw_ignores_json_flag(capsys: pytest.CaptureFixture[str]) -> None:
    response = {"dietPlan": {"lunch": {"items": [{"energy": 1.23456}]}}}

    assert run_json(
        ["day", "view", "2026-07-05", "--raw", "--json"],
        FakeClient(get=response),
        capsys,
    ) == (response)
