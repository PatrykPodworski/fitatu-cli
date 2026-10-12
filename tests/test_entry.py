import secrets
from datetime import datetime
from typing import Any
from uuid import UUID

import pytest
from conftest import http_error, run_json, run_text

from fitatu_cli import entry_create
from fitatu_cli.cli import main

Json = dict[str, Any]

DAY = "/api/diet-and-activity-plan/{uid}/day/2026-07-05"
DAYS = "/api/diet-plan/{uid}/days"
PLAN = {
    "dietPlan": {
        "breakfast": {"mealName": "Breakfast", "items": []},
        "second_breakfast": {"mealName": "Snack", "items": []},
        "lunch": {"items": [{"planDayDietItemId": "old", "productId": 9}]},
    }
}
STEW = {"name": "Stew", "serving": 4}
SAVED = [{"date": "2026-07-05", "revision": 3, "errorMessage": None}]
PRODUCT = ["--product", "501", "--quantity", "1", "--measure", "7"]


class DiaryClient:
    """Answers `get(path)` with `gets[path]`, or raises it when it is an
    exception, and `post` with `saved`; records the calls."""

    def __init__(self, gets: dict[str, Any], saved: Any = SAVED) -> None:
        self.gets = gets
        self.saved = saved
        self.calls: list[tuple[Any, ...]] = []

    def get(self, path: str) -> Any:
        self.calls.append(("get", path))
        response = self.gets[path]
        if isinstance(response, BaseException):
            raise response
        return response

    def post(self, path: str, body: Json) -> Any:
        self.calls.append(("post", path, body))
        return self.saved


class Now(datetime):
    @classmethod
    def now(cls) -> "Now":  # type: ignore[override]
        return cls(2026, 10, 11, 8, 5, 9)


@pytest.fixture(autouse=True)
def fixed_clock_and_node(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(entry_create, "datetime", Now)
    monkeypatch.setattr(secrets, "randbits", lambda bits: 0x0102 if bits == 48 else 0)


def posted(client: DiaryClient) -> tuple[str, Json]:
    """The entry ID and the body of the one write, with the ID left out of it."""
    [(_, path, body)] = [call for call in client.calls if call[0] == "post"]
    assert path == DAYS
    [meal] = body["2026-07-05"]["dietPlan"].values()
    entry_id = meal["items"][0].pop("planDayDietItemId")
    return entry_id, body


def assert_new_entry_id(entry_id: str) -> None:
    """A UUID v1, as the web app makes, with 48 random bits as the node instead
    of this machine's MAC address: RFC 9562 marks such a node with the multicast
    bit."""
    uuid = UUID(entry_id)
    assert (uuid.version, uuid.node) == (1, 0x0100_0000_0102)


def test_entry_create_posts_only_the_new_product_item(
    capsys: pytest.CaptureFixture[str],
) -> None:
    client: Any = DiaryClient({DAY: PLAN})

    out = run_text(
        [
            "entry",
            "create",
            "2026-07-05",
            "lunch",
            "--product",
            "501",
            "--quantity",
            "2.5",
            "--measure",
            "7",
        ],
        client,
        capsys,
    )

    entry_id, body = posted(client)
    assert client.calls[0] == ("get", DAY)
    assert body == {
        "2026-07-05": {
            "dietPlan": {
                "lunch": {
                    "items": [
                        {
                            "foodType": "PRODUCT",
                            "measureId": 7,
                            "measureQuantity": 2.5,
                            "ingredientsServing": None,
                            "productId": 501,
                            "source": "API",
                            "updatedAt": "2026-10-11 08:05:09",
                        }
                    ]
                }
            },
            "toiletItems": [],
            "note": None,
            "tagsIds": [],
        }
    }
    assert out == f"{entry_id}\n"
    assert_new_entry_id(entry_id)


def test_entry_create_puts_a_recipe_in_portions_with_its_servings(
    capsys: pytest.CaptureFixture[str],
) -> None:
    client: Any = DiaryClient({DAY: PLAN, "/api/recipes/77": STEW})

    run_text(
        [
            "entry",
            "create",
            "2026-07-05",
            "Breakfast",
            "--recipe",
            "77",
            "--quantity",
            "1",
        ],
        client,
        capsys,
    )

    _, body = posted(client)
    assert body["2026-07-05"]["dietPlan"] == {
        "breakfast": {
            "items": [
                {
                    "foodType": "RECIPE",
                    "measureId": 39,
                    "measureQuantity": 1,
                    "ingredientsServing": 4,
                    "recipeId": 77,
                    "source": "API",
                    "updatedAt": "2026-10-11 08:05:09",
                }
            ]
        }
    }


def test_entry_create_takes_another_measure_for_a_recipe(
    capsys: pytest.CaptureFixture[str],
) -> None:
    client: Any = DiaryClient({DAY: PLAN, "/api/recipes/77": STEW})

    run_text(
        [
            "entry",
            "create",
            "2026-07-05",
            "lunch",
            "--recipe",
            "77",
            "--quantity",
            "300",
            "--measure",
            "1",
        ],
        client,
        capsys,
    )

    _, body = posted(client)
    item = body["2026-07-05"]["dietPlan"]["lunch"]["items"][0]
    assert (item["measureId"], item["measureQuantity"]) == (1, 300)


def test_entry_create_sends_no_servings_for_a_recipe_without_them(
    capsys: pytest.CaptureFixture[str],
) -> None:
    client: Any = DiaryClient({DAY: PLAN, "/api/recipes/77": {"name": "Stew"}})

    run_text(
        ["entry", "create", "2026-07-05", "lunch", "--recipe", "77", "--quantity", "1"],
        client,
        capsys,
    )

    _, body = posted(client)
    assert body["2026-07-05"]["dietPlan"]["lunch"]["items"][0][
        "ingredientsServing"
    ] is (None)


@pytest.mark.parametrize(
    ("meal", "key"),
    [
        ("Snack", "second_breakfast"),
        ("SNACK", "second_breakfast"),
        ("second_breakfast", "second_breakfast"),
        ("Lunch", "lunch"),
    ],
)
def test_entry_create_matches_the_meal_by_name_then_key(
    meal: str, key: str, capsys: pytest.CaptureFixture[str]
) -> None:
    client: Any = DiaryClient({DAY: PLAN})

    run_text(
        ["entry", "create", "2026-07-05", meal, *PRODUCT],
        client,
        capsys,
    )

    _, body = posted(client)
    assert list(body["2026-07-05"]["dietPlan"]) == [key]


def test_entry_create_prefers_a_meal_name_over_another_meal_key(
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Meals are renamed per account, so one meal's name can be another's key."""
    plan = {
        "dietPlan": {
            "dinner": {"mealName": "Late", "items": []},
            "supper": {"mealName": "Dinner", "items": []},
        }
    }
    client: Any = DiaryClient({DAY: plan})

    run_text(
        ["entry", "create", "2026-07-05", "dinner", *PRODUCT],
        client,
        capsys,
    )

    _, body = posted(client)
    assert list(body["2026-07-05"]["dietPlan"]) == ["supper"]


def test_entry_create_json_prints_the_entry(capsys: pytest.CaptureFixture[str]) -> None:
    client: Any = DiaryClient({DAY: PLAN})

    out = run_json(
        ["entry", "create", "2026-07-05", "snack", *PRODUCT, "--json"],
        client,
        capsys,
    )

    entry_id, _ = posted(client)
    assert out == {"id": entry_id, "date": "2026-07-05", "meal": "Snack"}


def test_entry_create_in_an_unknown_meal_exits_2_with_the_days_meals(
    capsys: pytest.CaptureFixture[str],
) -> None:
    client: Any = DiaryClient({DAY: PLAN})

    with pytest.raises(SystemExit) as exit:
        main(
            ["entry", "create", "2026-07-05", "brunch", *PRODUCT],
            connect=lambda: client,
        )

    assert exit.value.code == 2
    assert capsys.readouterr().err == (
        "fitatu: No meal 'brunch' on 2026-07-05. Use one of: Breakfast, Snack, lunch.\n"
    )
    assert client.calls == [("get", DAY)]


@pytest.mark.parametrize("plan", [{}, {"dietPlan": None}, {"dietPlan": {}}])
def test_entry_create_on_a_day_without_meals_exits_1(
    plan: Json, capsys: pytest.CaptureFixture[str]
) -> None:
    client: Any = DiaryClient({DAY: plan})

    code = main(
        ["entry", "create", "2026-07-05", "lunch", *PRODUCT],
        connect=lambda: client,
    )

    assert code == 1
    assert capsys.readouterr().err.startswith(
        "fitatu: Fitatu sent a response fitatu-cli could not read."
    )
    assert client.calls == [("get", DAY)]


def test_entry_create_of_an_unknown_recipe_exits_1(
    capsys: pytest.CaptureFixture[str],
) -> None:
    client: Any = DiaryClient({DAY: PLAN, "/api/recipes/78": http_error(404)})

    code = main(
        ["entry", "create", "2026-07-05", "lunch", "--recipe", "78", "--quantity", "1"],
        connect=lambda: client,
    )

    assert code == 1
    assert capsys.readouterr().err == (
        "fitatu: Fitatu has no recipe with ID 78. "
        "Run 'fitatu recipe list' to see your recipes' IDs.\n"
    )
    assert [call[0] for call in client.calls] == ["get", "get"]


def test_entry_create_reports_an_error_message_from_fitatu(
    capsys: pytest.CaptureFixture[str],
) -> None:
    saved = [{"date": "2026-07-05", "revision": 3, "errorMessage": "Invalid measure"}]
    client: Any = DiaryClient({DAY: PLAN}, saved)

    code = main(
        ["entry", "create", "2026-07-05", "lunch", *PRODUCT],
        connect=lambda: client,
    )

    assert code == 1
    assert capsys.readouterr().err == (
        "fitatu: Fitatu did not save the entry (Invalid measure). "
        "Check the food ID, the measure ID and the quantity.\n"
    )


@pytest.mark.parametrize("saved", [{"ok": True}, [], ["2026-07-05"]])
def test_entry_create_rejects_an_unreadable_answer(
    saved: Any, capsys: pytest.CaptureFixture[str]
) -> None:
    client: Any = DiaryClient({DAY: PLAN}, saved)

    code = main(
        ["entry", "create", "2026-07-05", "lunch", *PRODUCT],
        connect=lambda: client,
    )

    assert code == 1
    assert capsys.readouterr().err.startswith(
        "fitatu: Fitatu sent a response fitatu-cli could not read."
    )


CREATE = ["create", "2026-07-05", "lunch"]


@pytest.mark.parametrize(
    ("argv", "error"),
    [
        (
            [*CREATE, "--product", "501", "--quantity", "1"],
            "--product needs --measure. Give the measure ID from 'fitatu food search'.",
        ),
        (
            [*CREATE, "--quantity", "1"],
            "One of the arguments --product --recipe is required. "
            "Run 'fitatu entry create --help'.",
        ),
        (
            [*CREATE, "--product", "5", "--recipe", "7", "--quantity", "1"],
            "Argument --recipe: not allowed with argument --product. "
            "Run 'fitatu entry create --help'.",
        ),
        (
            [*CREATE, "--product", "rye", "--quantity", "1"],
            "Invalid product ID 'rye'. Give the number from 'fitatu food search'.",
        ),
        (
            [*CREATE, "--recipe", "stew", "--quantity", "1"],
            "Invalid recipe ID 'stew'. Give the number from 'fitatu recipe list'.",
        ),
        (
            [*CREATE, "--product", "5", "--measure", "g", "--quantity", "1"],
            "Invalid measure ID 'g'. Give the number from 'fitatu food search'.",
        ),
        *(
            (
                [*CREATE, "--recipe", "7", "--quantity", quantity],
                f"Invalid quantity '{quantity}'. Give a number greater than 0.",
            )
            for quantity in ("0", "-1", "two", "nan", "inf")
        ),
        (
            [*CREATE, "--recipe", "7"],
            "Missing --quantity for 'fitatu entry create'. "
            "Run 'fitatu entry create --help'.",
        ),
        (
            ["create", "2026-07-05", "--recipe", "7", "--quantity", "1"],
            "Missing MEAL for 'fitatu entry create'. Run 'fitatu entry create --help'.",
        ),
        (
            ["create", "5.07", "lunch", "--recipe", "7", "--quantity", "1"],
            "Invalid date '5.07'. Use today, yesterday or YYYY-MM-DD.",
        ),
        ([], "No command given. Run 'fitatu entry <command>', one of: create."),
    ],
)
def test_entry_argument_error_exits_2_without_a_request(
    argv: list[str], error: str, capsys: pytest.CaptureFixture[str]
) -> None:
    client: Any = DiaryClient({})

    with pytest.raises(SystemExit) as exit:
        main(["entry", *argv], connect=lambda: client)

    assert exit.value.code == 2
    assert capsys.readouterr().err == f"fitatu: {error}\n"
    assert client.calls == []


def test_help_lists_entry_and_its_create_options(
    capsys: pytest.CaptureFixture[str],
) -> None:
    with pytest.raises(SystemExit):
        main(["--help"])
    assert " entry foods in your diary " in " ".join(capsys.readouterr().out.split())

    with pytest.raises(SystemExit) as exit:
        main(["entry", "create", "--help"])

    assert exit.value.code == 0
    help_text = " ".join(capsys.readouterr().out.split())
    assert help_text.startswith(
        "usage: fitatu entry create [-h] (--product ID | --recipe ID) "
        "--quantity N [--measure ID] [--json] DATE MEAL "
    )
    assert (
        " --measure ID the measure's ID from 'fitatu food search' "
        "(default for a recipe: 39, a portion) "
    ) in help_text
