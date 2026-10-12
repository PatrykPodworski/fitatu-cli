from typing import Any

import pytest
from conftest import FakeClient, http_error, run_json, run_text

from fitatu_cli.cli import main

Json = dict[str, Any]

SEARCH = "/api/search/food/user/{{uid}}?phrase=&page={page}&limit=100"


class SearchClient:
    """Answers search page N with `pages[N - 1]`, and an empty page after the last,
    and records the paths."""

    def __init__(self, *pages: Any) -> None:
        self.pages = pages
        self.paths: list[str] = []

    def get(self, path: str) -> Any:
        self.paths.append(path)
        for number, page in enumerate(self.pages, start=1):
            if path == SEARCH.format(page=number):
                return page
        assert path == SEARCH.format(page=len(self.pages) + 1)
        return []


def row(food_id: int, name: str, uses: int | None, **fields: Any) -> Json:
    return {
        "foodId": food_id,
        "name": name,
        "type": "RECIPE",
        "userNumberOfUse": uses,
        **fields,
    }


OATS = {"foodId": 5, "name": "Oats", "type": "PRODUCT", "userNumberOfUse": 90}


def test_recipe_list_pages_until_empty_and_sorts_most_used_first(
    capsys: pytest.CaptureFixture[str],
) -> None:
    client = SearchClient(
        [row(11, "Soup", 3), OATS, row(12, "Stew", 12)],
        [row(13, "Salad", 7)],
    )

    out = run_json(["recipe", "list", "--json"], client, capsys)

    assert client.paths == [SEARCH.format(page=n) for n in (1, 2, 3)]
    assert out == [
        {"id": 12, "name": "Stew", "uses": 12},
        {"id": 13, "name": "Salad", "uses": 7},
        {"id": 11, "name": "Soup", "uses": 3},
    ]


def test_recipe_list_hides_deleted_recipes(capsys: pytest.CaptureFixture[str]) -> None:
    client = SearchClient(
        [row(11, "Soup", 3, deleted=True), row(12, "Stew", 1, deleted=False)]
    )

    out = run_json(["recipe", "list", "--json"], client, capsys)

    assert out == [{"id": 12, "name": "Stew", "uses": 1}]


def test_recipe_list_counts_missing_uses_as_0(
    capsys: pytest.CaptureFixture[str],
) -> None:
    client = SearchClient([{"foodId": 11, "type": "RECIPE"}, row(12, "Stew", 1)])

    out = run_json(["recipe", "list", "--json"], client, capsys)

    assert out == [
        {"id": 12, "name": "Stew", "uses": 1},
        {"id": 11, "name": None, "uses": 0},
    ]


def test_recipe_list_prints_a_table(capsys: pytest.CaptureFixture[str]) -> None:
    client = SearchClient([row(11, "Soup", 3), {"foodId": 1234, "type": "RECIPE"}])

    assert run_text(["recipe", "list"], client, capsys) == (
        "id    uses  name\n11    3     Soup\n1234  0     -\n"
    )


def test_recipe_list_prints_no_recipes(capsys: pytest.CaptureFixture[str]) -> None:
    client = SearchClient([OATS])

    assert run_text(["recipe", "list"], client, capsys) == "no recipes\n"
    assert run_json(["recipe", "list", "--json"], client, capsys) == []


def test_recipe_list_raw_prints_recipe_rows_unchanged(
    capsys: pytest.CaptureFixture[str],
) -> None:
    soup = row(11, "Soup", 3, deleted=True, energy=1.23456)
    stew = row(12, "Stew", 12)

    out = run_json(
        ["recipe", "list", "--raw"], SearchClient([soup, OATS, stew]), capsys
    )

    assert out == [soup, stew]


def test_recipe_list_rejects_a_page_that_is_not_a_list(
    capsys: pytest.CaptureFixture[str],
) -> None:
    client: Any = SearchClient({"items": []})

    assert main(["recipe", "list"], connect=lambda: client) == 1
    assert capsys.readouterr().err.startswith(
        "fitatu: Fitatu sent a response fitatu-cli could not read."
    )


RECIPE = {
    "id": 77,
    "name": "Stew",
    "serving": 4,
    "deleted": False,
    "items": [
        {"name": "Beans", "measureQuantity": 400, "measureName": "g"},
        {"name": "Stock", "measureQuantity": 0.5, "measureName": "l"},
    ],
    "energy": 540.34,
    "carbohydrate": 60,
    "protein": 30,
    "fat": 18,
    "fiber": 6,
    "sugars": 5,
    "salt": 1.8,
    "zinc": 2,
}

STEW = """\
id: 77
name: Stew
servings: 4
deleted: no

ingredient  quantity  measure
Beans       400       g
Stock       0.5       l

per portion
energy_kcal  carbohydrate_g  protein_g  fat_g  fiber_g  sugars_g  salt_g
540.3        60.0            30.0       18.0   6.0      5.0       1.8
"""


def test_recipe_view_prints_ingredients_and_nutrients_per_portion(
    capsys: pytest.CaptureFixture[str],
) -> None:
    client = FakeClient(get=RECIPE)

    assert run_text(["recipe", "view", "77"], client, capsys) == STEW
    assert client.calls == [("get", ("/api/recipes/77",), {})]


def test_recipe_view_json(capsys: pytest.CaptureFixture[str]) -> None:
    out = run_json(["recipe", "view", "77", "--json"], FakeClient(get=RECIPE), capsys)

    assert out == {
        "id": 77,
        "name": "Stew",
        "servings": 4,
        "deleted": False,
        "ingredients": [
            {"name": "Beans", "quantity": 400, "measure": "g"},
            {"name": "Stock", "quantity": 0.5, "measure": "l"},
        ],
        "per_portion": {
            "energy": 540.3,
            "carbohydrate": 60,
            "protein": 30,
            "fat": 18,
            "fiber": 6,
            "sugars": 5,
            "salt": 1.8,
        },
    }


def test_recipe_view_marks_a_deleted_recipe(
    capsys: pytest.CaptureFixture[str],
) -> None:
    client = FakeClient(get=RECIPE | {"deleted": True})

    assert "deleted: yes\n" in run_text(["recipe", "view", "77"], client, capsys)


def test_recipe_view_tolerates_missing_fields(
    capsys: pytest.CaptureFixture[str],
) -> None:
    client = FakeClient(get={"items": None, "energy": 12})

    assert run_text(["recipe", "view", "77"], client, capsys) == (
        """\
id: 77
name: -
servings: -
deleted: no

no ingredients

per portion
energy_kcal  carbohydrate_g  protein_g  fat_g  fiber_g  sugars_g  salt_g
12.0         0.0             0.0        0.0    0.0      0.0       0.0
"""
    )


def test_recipe_view_prints_a_dash_for_a_missing_ingredient_field(
    capsys: pytest.CaptureFixture[str],
) -> None:
    client = FakeClient(get={"items": [{"measureQuantity": 2}]})

    assert "\ningredient  quantity  measure\n-           2         -\n" in run_text(
        ["recipe", "view", "77"], client, capsys
    )


QUANTITY_STRINGS = {
    "items": [
        {"name": "Rice", "measureQuantity": "1.50", "measureName": "cup"},
        {"name": "Salt", "measureQuantity": "1.00", "measureName": "pinch"},
        {"name": "Water", "measureName": "l"},
    ]
}


def test_recipe_view_prints_a_quantity_string_as_a_number(
    capsys: pytest.CaptureFixture[str],
) -> None:
    out = run_json(
        ["recipe", "view", "77", "--json"], FakeClient(get=QUANTITY_STRINGS), capsys
    )
    text = run_text(["recipe", "view", "77"], FakeClient(get=QUANTITY_STRINGS), capsys)

    assert out["ingredients"] == [
        {"name": "Rice", "quantity": 1.5, "measure": "cup"},
        {"name": "Salt", "quantity": 1.0, "measure": "pinch"},
        {"name": "Water", "quantity": None, "measure": "l"},
    ]
    assert (
        "ingredient  quantity  measure\n"
        "Rice        1.5       cup\n"
        "Salt        1         pinch\n"
        "Water       -         l\n"
    ) in text


def test_recipe_view_rejects_a_quantity_that_is_not_a_number(
    capsys: pytest.CaptureFixture[str],
) -> None:
    client = FakeClient(get={"items": [{"measureQuantity": "a cup"}]})

    assert main(["recipe", "view", "77"], connect=lambda: client) == 1
    assert capsys.readouterr().err.startswith(
        "fitatu: Fitatu sent a response fitatu-cli could not read."
    )


def test_recipe_view_raw_prints_the_response_unchanged(
    capsys: pytest.CaptureFixture[str],
) -> None:
    out = run_json(["recipe", "view", "77", "--raw"], FakeClient(get=RECIPE), capsys)

    assert out == RECIPE


def test_recipe_view_of_an_unknown_id_exits_1(
    capsys: pytest.CaptureFixture[str],
) -> None:
    client = FakeClient(get=http_error(404))

    assert main(["recipe", "view", "78"], connect=lambda: client) == 1
    assert capsys.readouterr().err == (
        "fitatu: Fitatu has no recipe with ID 78. "
        "Run 'fitatu recipe list' to see your recipes' IDs.\n"
    )


def test_recipe_view_reports_another_http_error_as_unexpected(
    capsys: pytest.CaptureFixture[str],
) -> None:
    client = FakeClient(get=http_error(500))

    assert main(["recipe", "view", "78"], connect=lambda: client) == 1
    assert capsys.readouterr().err.startswith(
        "fitatu: Unexpected error (HTTPError: HTTP Error 500: error)."
    )


def test_recipe_view_rejects_an_id_that_is_not_a_number(
    capsys: pytest.CaptureFixture[str],
) -> None:
    with pytest.raises(SystemExit) as exit:
        main(["recipe", "view", "stew"], connect=FakeClient)

    assert exit.value.code == 2
    assert capsys.readouterr().err == (
        "fitatu: Invalid recipe ID 'stew'. Give the number from 'fitatu recipe list'.\n"
    )


def test_help_lists_recipe_and_its_verbs(capsys: pytest.CaptureFixture[str]) -> None:
    with pytest.raises(SystemExit):
        main(["--help"])
    assert " recipe your recipes " in " ".join(capsys.readouterr().out.split())

    with pytest.raises(SystemExit) as exit:
        main(["recipe", "--help"])

    assert exit.value.code == 0
    help_text = " ".join(capsys.readouterr().out.split())
    assert "usage: fitatu recipe [-h] {list,view,create,edit}" in help_text
    assert (
        " list list your recipes, most used first "
        "view view one recipe: ingredients and nutrients per portion "
        "create create a recipe from a JSON spec and print its ID "
        "edit edit a recipe from a JSON spec and print its ID"
    ) in help_text


@pytest.mark.parametrize(
    ("verb", "usage", "options"),
    [
        (
            ["list"],
            "usage: fitatu recipe list [-h] [--raw] [--json] options:",
            " --raw print the service's rows for your recipes --json ",
        ),
        (
            ["view"],
            "usage: fitatu recipe view [-h] [--raw] [--json] ID "
            "positional arguments: ID the recipe's ID options:",
            " --raw print the full service response --json ",
        ),
    ],
)
def test_recipe_verb_help_shows_its_arguments(
    verb: list[str], usage: str, options: str, capsys: pytest.CaptureFixture[str]
) -> None:
    with pytest.raises(SystemExit) as exit:
        main(["recipe", *verb, "--help"])

    assert exit.value.code == 0
    help_text = " ".join(capsys.readouterr().out.split())
    assert help_text.startswith(usage)
    assert options in help_text


@pytest.mark.parametrize(
    ("argv", "error"),
    [
        (
            ["recipe"],
            "No command given. Run 'fitatu recipe <command>', one of: list, view, "
            "create, edit.",
        ),
        (
            ["recipe", "list", "77"],
            "Unexpected argument '77' for 'fitatu recipe list'. "
            "Run 'fitatu recipe list --help' for all options.",
        ),
        (
            ["recipe", "view", "77", "78"],
            "Unexpected argument '78' for 'fitatu recipe view'. "
            "Run 'fitatu recipe view --help' for all options.",
        ),
    ],
)
def test_recipe_argument_error_exits_2(
    argv: list[str], error: str, capsys: pytest.CaptureFixture[str]
) -> None:
    with pytest.raises(SystemExit) as exit:
        main(argv, connect=FakeClient)

    assert exit.value.code == 2
    assert capsys.readouterr().err == f"fitatu: {error}\n"
