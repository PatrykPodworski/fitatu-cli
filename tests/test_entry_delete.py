from datetime import datetime
from typing import Any

import pytest
from conftest import DiaryClient, http_error, run_json, run_text

from fitatu_cli import entry_delete
from fitatu_cli.cli import main
from fitatu_cli.errors import ISSUES

Json = dict[str, Any]

DAY = "/api/diet-and-activity-plan/{uid}/day/2026-07-05"
DAYS = "/api/diet-plan/{uid}/days"
RICE = {
    "planDayDietItemId": "e-1",
    "foodType": "PRODUCT",
    "name": "Rice",
    "measureId": 7,
    "measureQuantity": 2.5,
    "measureName": "cup",
    "ingredientsServing": None,
    "productId": 501,
    "source": "API",
    "eaten": True,
    "energy": 300,
}
STEW = {
    "planDayDietItemId": "e-2",
    "foodType": "RECIPE",
    "name": "Stew",
    "measureId": 39,
    "measureQuantity": 1,
    "ingredientsServing": 4,
    "recipeId": 77,
    "source": "WEB",
}
TEA = {"planDayDietItemId": "e-3", "foodType": "PRODUCT", "productId": 9}
PLAN = {
    "dietPlan": {
        "breakfast": {"mealName": "Breakfast", "items": [STEW]},
        "lunch": {"mealName": "Lunch", "items": [TEA, RICE]},
    },
    "note": "Rest day",
    "tagsIds": [3],
    "toilet": [{"id": "t-1", "time": "07:30"}],
}
DELETED = {"deletedAt": "2026-10-11 08:05:09", "updatedAt": "2026-10-11 08:05:09"}


class Now(datetime):
    @classmethod
    def now(cls) -> "Now":  # type: ignore[override]
        return cls(2026, 10, 11, 8, 5, 9)


@pytest.fixture(autouse=True)
def fixed_clock(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(entry_delete, "datetime", Now)


def posted(client: DiaryClient) -> Json:
    [(_, path, body)] = [call for call in client.calls if call[0] == "post"]
    assert path == DAYS
    day: Json = body
    return day


def test_entry_delete_posts_the_item_marked_deleted(
    capsys: pytest.CaptureFixture[str],
) -> None:
    """The web app deletes an item by writing it again with `deletedAt` set; the
    write keeps the day's note, tags and toilet items."""
    client: Any = DiaryClient({DAY: PLAN})

    out = run_text(["entry", "delete", "2026-07-05", "e-1"], client, capsys)

    assert posted(client) == {
        "2026-07-05": {
            "dietPlan": {
                "lunch": {
                    "items": [
                        {
                            "planDayDietItemId": "e-1",
                            "foodType": "PRODUCT",
                            "measureId": 7,
                            "measureQuantity": 2.5,
                            "ingredientsServing": None,
                            "mealNumber": None,
                            "numberOfMeals": None,
                            "eaten": False,
                            "productId": 501,
                            "source": "API",
                            **DELETED,
                        }
                    ]
                }
            },
            "toiletItems": [{"id": "t-1", "time": "07:30"}],
            "note": "Rest day",
            "tagsIds": [3],
        }
    }
    assert client.calls[0] == ("get", DAY)
    assert out == "deleted entry e-1 from Lunch: Rice\n"


def test_entry_delete_removes_the_last_entry_of_a_meal_by_its_recipe(
    capsys: pytest.CaptureFixture[str],
) -> None:
    client: Any = DiaryClient({DAY: PLAN})

    out = run_text(["entry", "delete", "2026-07-05", "e-2"], client, capsys)

    assert posted(client)["2026-07-05"]["dietPlan"] == {
        "breakfast": {
            "items": [
                {
                    "planDayDietItemId": "e-2",
                    "foodType": "RECIPE",
                    "measureId": 39,
                    "measureQuantity": 1,
                    "ingredientsServing": 4,
                    "mealNumber": None,
                    "numberOfMeals": None,
                    "eaten": False,
                    "recipeId": 77,
                    "source": "WEB",
                    **DELETED,
                }
            ]
        }
    }
    assert out == "deleted entry e-2 from Breakfast: Stew\n"


def test_entry_delete_names_the_meal_by_its_key_and_a_missing_name_with_a_dash(
    capsys: pytest.CaptureFixture[str],
) -> None:
    plan = {"dietPlan": {"breakfast": None, "supper": {"items": [TEA]}}}
    client: Any = DiaryClient({DAY: plan})

    out = run_text(["entry", "delete", "2026-07-05", "e-3"], client, capsys)

    day = posted(client)["2026-07-05"]
    assert (day["note"], day["tagsIds"], day["toiletItems"]) == (None, [], [])
    assert list(day["dietPlan"]) == ["supper"]
    assert out == "deleted entry e-3 from supper: -\n"


def test_entry_delete_json_prints_the_entry(capsys: pytest.CaptureFixture[str]) -> None:
    client: Any = DiaryClient({DAY: PLAN})

    out = run_json(["entry", "delete", "2026-07-05", "e-1", "--json"], client, capsys)

    assert out == {"id": "e-1", "date": "2026-07-05", "meal": "Lunch", "name": "Rice"}


@pytest.mark.parametrize(
    "plan",
    [
        PLAN,
        {"dietPlan": None},
        {"dietPlan": {"lunch": None, "supper": {"items": None}}},
    ],
)
def test_entry_delete_of_an_unknown_entry_exits_1_without_a_write(
    plan: Json, capsys: pytest.CaptureFixture[str]
) -> None:
    client: Any = DiaryClient({DAY: plan})

    code = main(["entry", "delete", "2026-07-05", "e-9"], connect=lambda: client)

    assert code == 1
    assert capsys.readouterr().err == (
        "fitatu: No entry 'e-9' on 2026-07-05. "
        "Run 'fitatu day view 2026-07-05' to see the day's entry IDs.\n"
    )
    assert client.calls == [("get", DAY)]


def test_entry_delete_reports_an_error_message_from_fitatu(
    capsys: pytest.CaptureFixture[str],
) -> None:
    saved = [{"date": "2026-07-05", "revision": 3, "errorMessage": "Invalid item"}]
    client: Any = DiaryClient({DAY: PLAN}, saved)

    code = main(["entry", "delete", "2026-07-05", "e-1"], connect=lambda: client)

    assert code == 1
    assert capsys.readouterr().err == (
        "fitatu: Fitatu did not delete the entry (Invalid item). "
        f"Rerun with --debug and report it at {ISSUES}.\n"
    )


def test_entry_delete_reports_a_refused_write(
    capsys: pytest.CaptureFixture[str],
) -> None:
    client: Any = DiaryClient({DAY: PLAN}, http_error(400))

    code = main(["entry", "delete", "2026-07-05", "e-1"], connect=lambda: client)

    assert code == 1
    assert capsys.readouterr().err == (
        "fitatu: Fitatu did not delete the entry (HTTP 400). "
        f"Rerun with --debug and report it at {ISSUES}.\n"
    )


@pytest.mark.parametrize(
    ("argv", "error"),
    [
        (
            ["2026-07-05"],
            "Missing ENTRY_ID for 'fitatu entry delete'. "
            "Run 'fitatu entry delete --help'.",
        ),
        (
            ["5.07", "e-1"],
            "Invalid date '5.07'. Use today, yesterday or YYYY-MM-DD.",
        ),
        (
            ["2026-07-05", "e-1", "e-2"],
            "Unexpected argument 'e-2' for 'fitatu entry delete'. "
            "Run 'fitatu entry delete --help' for all options.",
        ),
    ],
)
def test_entry_delete_argument_error_exits_2_without_a_request(
    argv: list[str], error: str, capsys: pytest.CaptureFixture[str]
) -> None:
    client: Any = DiaryClient({})

    with pytest.raises(SystemExit) as exit:
        main(["entry", "delete", *argv], connect=lambda: client)

    assert exit.value.code == 2
    assert capsys.readouterr().err == f"fitatu: {error}\n"
    assert client.calls == []


def test_help_lists_entry_delete(capsys: pytest.CaptureFixture[str]) -> None:
    with pytest.raises(SystemExit):
        main(["entry", "--help"])
    assert " delete remove an entry from a day " in " ".join(
        capsys.readouterr().out.split()
    )

    with pytest.raises(SystemExit) as exit:
        main(["entry", "delete", "--help"])

    assert exit.value.code == 0
    help_text = " ".join(capsys.readouterr().out.split())
    assert help_text.startswith(
        "usage: fitatu entry delete [-h] [--json] DATE ENTRY_ID "
        "Remove one entry from a day. There is no confirmation prompt. "
    )
    assert (
        " DATE today | yesterday | YYYY-MM-DD "
        "ENTRY_ID the entry's ID, the id column of 'fitatu day view' "
    ) in help_text
