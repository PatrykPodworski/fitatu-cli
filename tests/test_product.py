from typing import Any

import pytest
from conftest import SEARCH, FakeClient, SearchClient, http_error, run_json, run_text

from fitatu_cli.cli import main

Json = dict[str, Any]


def row(food_id: int, name: str, uses: int | None, brand: str, **fields: Any) -> Json:
    return {
        "foodId": food_id,
        "name": name,
        "type": "PRODUCT",
        "userNumberOfUse": uses,
        "brand": brand,
        **fields,
    }


STEW = {"foodId": 9001, "name": "Stew", "type": "RECIPE", "userNumberOfUse": 50}
FLAKES = row(502, "Oat flakes", 12, "")
BREAD = row(501, "Rye bread", 3, "Bakery", energy=240.3)
JAM = row(503, "Old jam", 40, "Jams", deleted=True)
YOGURT = row(504, "Plain yogurt", 3, "Dairy", deleted=False)
PAGES = ([BREAD, STEW, FLAKES, JAM], [YOGURT])


def test_product_list_pages_until_empty_and_sorts_most_used_first(
    capsys: pytest.CaptureFixture[str],
) -> None:
    client = SearchClient(*PAGES)

    out = run_json(["product", "list", "--json"], client, capsys)

    assert client.paths == [SEARCH.format(page=n) for n in (1, 2, 3)]
    assert out == [
        {"id": 502, "uses": 12, "brand": None, "name": "Oat flakes"},
        {"id": 501, "uses": 3, "brand": "Bakery", "name": "Rye bread"},
        {"id": 504, "uses": 3, "brand": "Dairy", "name": "Plain yogurt"},
    ]


def test_product_list_prints_a_table(capsys: pytest.CaptureFixture[str]) -> None:
    assert run_text(["product", "list"], SearchClient(*PAGES), capsys) == (
        "id   uses  brand   name\n"
        "502  12    -       Oat flakes\n"
        "501  3     Bakery  Rye bread\n"
        "504  3     Dairy   Plain yogurt\n"
    )


def test_product_list_prints_no_products(capsys: pytest.CaptureFixture[str]) -> None:
    client = SearchClient([STEW, JAM])

    assert run_text(["product", "list"], client, capsys) == "no products\n"
    assert run_json(["product", "list", "--json"], client, capsys) == []


def test_product_list_tolerates_missing_fields(
    capsys: pytest.CaptureFixture[str],
) -> None:
    client = SearchClient(
        [{"foodId": 505, "type": "PRODUCT", "name": "Salt"}, {"type": "PRODUCT"}]
    )

    out = run_json(["product", "list", "--json"], client, capsys)
    text = run_text(["product", "list"], client, capsys)

    assert out == [
        {"id": 505, "uses": 0, "brand": None, "name": "Salt"},
        {"id": None, "uses": 0, "brand": None, "name": None},
    ]
    assert (
        text == "id   uses  brand  name\n505  0     -      Salt\n-    0     -      -\n"
    )


def test_product_list_raw_prints_product_rows_unchanged(
    capsys: pytest.CaptureFixture[str],
) -> None:
    out = run_json(["product", "list", "--raw"], SearchClient(*PAGES), capsys)

    assert out == [BREAD, FLAKES, JAM, YOGURT]


PRODUCT = {
    "id": 501,
    "name": "Rye bread",
    "brand": "Bakery",
    "private": True,
    "deleted": False,
    "measures": [
        {"id": 39, "name": "portion", "weightPerUnit": 450, "energyPerUnit": 580.0},
        {"id": 7, "name": "slice", "weightPerUnit": 32.5, "energyPerUnit": 41.9},
    ],
    "energy": 128.88889,
    "carbohydrate": 20.04,
    "protein": 6.5,
    "fat": 1.26,
    "fiber": 5.96,
    "sugars": 2,
    "salt": 1.1,
    "sodium": 440,
}

BREAD_TEXT = """\
id: 501
name: Rye bread
brand: Bakery
mine: yes
deleted: no

measure_id  measure  grams
39          portion  450
7           slice    32.5

per 100 g
energy_kcal  carbohydrate_g  protein_g  fat_g  fiber_g  sugars_g  salt_g
128.9        20.0            6.5        1.3    6.0      2.0       1.1
"""


def test_product_view_prints_measures_and_nutrients_per_100_g(
    capsys: pytest.CaptureFixture[str],
) -> None:
    client = FakeClient(get=PRODUCT)

    assert run_text(["product", "view", "501"], client, capsys) == BREAD_TEXT
    assert client.calls == [("get", ("/api/products/501",), {})]


def test_product_view_json(capsys: pytest.CaptureFixture[str]) -> None:
    out = run_json(
        ["product", "view", "501", "--json"], FakeClient(get=PRODUCT), capsys
    )

    assert out == {
        "id": 501,
        "name": "Rye bread",
        "brand": "Bakery",
        "mine": True,
        "deleted": False,
        "measures": [
            {"id": 39, "name": "portion", "grams": 450},
            {"id": 7, "name": "slice", "grams": 32.5},
        ],
        "per_100g": {
            "energy": 128.9,
            "carbohydrate": 20.0,
            "protein": 6.5,
            "fat": 1.3,
            "fiber": 6.0,
            "sugars": 2,
            "salt": 1.1,
        },
    }


def test_product_view_marks_a_deleted_product_that_is_not_mine(
    capsys: pytest.CaptureFixture[str],
) -> None:
    client = FakeClient(get=PRODUCT | {"private": False, "deleted": True})

    out = run_json(["product", "view", "501", "--json"], client, capsys)
    text = run_text(["product", "view", "501"], client, capsys)

    assert (out["mine"], out["deleted"]) == (False, True)
    assert "\nmine: no\ndeleted: yes\n" in text


def test_product_view_tolerates_missing_fields(
    capsys: pytest.CaptureFixture[str],
) -> None:
    client = FakeClient(
        get={"brand": "", "measures": None, "energy": None, "protein": 3}
    )

    out = run_json(["product", "view", "501", "--json"], client, capsys)
    text = run_text(["product", "view", "501"], client, capsys)

    assert out == {
        "id": 501,
        "name": None,
        "brand": None,
        "mine": False,
        "deleted": False,
        "measures": [],
        "per_100g": {
            "energy": 0,
            "carbohydrate": 0,
            "protein": 3,
            "fat": 0,
            "fiber": 0,
            "sugars": 0,
            "salt": 0,
        },
    }
    assert text == (
        """\
id: 501
name: -
brand: -
mine: no
deleted: no

no measures

per 100 g
energy_kcal  carbohydrate_g  protein_g  fat_g  fiber_g  sugars_g  salt_g
0.0          0.0             3.0        0.0    0.0      0.0       0.0
"""
    )


def test_product_view_prints_a_dash_for_a_missing_measure_field(
    capsys: pytest.CaptureFixture[str],
) -> None:
    client = FakeClient(get={"measures": [{"name": "slice"}]})

    out = run_json(["product", "view", "501", "--json"], client, capsys)
    text = run_text(["product", "view", "501"], client, capsys)

    assert out["measures"] == [{"id": None, "name": "slice", "grams": None}]
    assert "\nmeasure_id  measure  grams\n-           slice    -\n" in text


def test_product_view_raw_prints_the_response_unchanged(
    capsys: pytest.CaptureFixture[str],
) -> None:
    out = run_json(["product", "view", "501", "--raw"], FakeClient(get=PRODUCT), capsys)

    assert out == PRODUCT


def test_product_view_of_an_unknown_id_exits_1(
    capsys: pytest.CaptureFixture[str],
) -> None:
    client = FakeClient(get=http_error(404))

    assert main(["product", "view", "502"], connect=lambda: client) == 1
    assert capsys.readouterr().err == (
        "fitatu: Fitatu has no product with ID 502. "
        "Run 'fitatu product list' to see your products' IDs.\n"
    )


def test_product_view_reports_another_http_error_as_unexpected(
    capsys: pytest.CaptureFixture[str],
) -> None:
    client = FakeClient(get=http_error(500))

    assert main(["product", "view", "502"], connect=lambda: client) == 1
    assert capsys.readouterr().err.startswith(
        "fitatu: Unexpected error (HTTPError: HTTP Error 500: error)."
    )


def test_product_view_rejects_an_id_that_is_not_a_number(
    capsys: pytest.CaptureFixture[str],
) -> None:
    with pytest.raises(SystemExit) as exit:
        main(["product", "view", "bread"], connect=FakeClient)

    assert exit.value.code == 2
    assert capsys.readouterr().err == (
        "fitatu: Invalid product ID 'bread'. "
        "Give the number from 'fitatu product list'.\n"
    )


def test_help_lists_product_and_its_verbs(capsys: pytest.CaptureFixture[str]) -> None:
    with pytest.raises(SystemExit):
        main(["--help"])
    assert " product your products " in " ".join(capsys.readouterr().out.split())

    with pytest.raises(SystemExit) as exit:
        main(["product", "--help"])

    assert exit.value.code == 0
    help_text = " ".join(capsys.readouterr().out.split())
    assert "usage: fitatu product [-h] {list,view}" in help_text
    assert (
        " list list your products, most used first "
        "view view one product: measures and nutrients per 100 g "
    ) in help_text


@pytest.mark.parametrize(
    ("verb", "usage", "options"),
    [
        (
            ["list"],
            "usage: fitatu product list [-h] [--raw] [--json] options:",
            " --raw print the service's rows for your products --json ",
        ),
        (
            ["view"],
            "usage: fitatu product view [-h] [--raw] [--json] ID "
            "positional arguments: ID the product's ID options:",
            " --raw print the full service response --json ",
        ),
    ],
)
def test_product_verb_help_shows_its_arguments(
    verb: list[str], usage: str, options: str, capsys: pytest.CaptureFixture[str]
) -> None:
    with pytest.raises(SystemExit) as exit:
        main(["product", *verb, "--help"])

    assert exit.value.code == 0
    help_text = " ".join(capsys.readouterr().out.split())
    assert help_text.startswith(usage)
    assert options in help_text
