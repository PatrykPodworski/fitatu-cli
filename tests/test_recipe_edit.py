import json
from pathlib import Path
from typing import Any

import pytest
from conftest import FakeClient, http_error, run_json, run_text

from fitatu_cli.cli import main

Json = dict[str, Any]

CURRENT: Json = {
    "id": 77,
    "name": "Stew",
    "serving": "2",
    "deleted": False,
    "recipeDescription": "Simmer.",
    "preparationTime": 10,
    "cookingTime": 20,
    "categories": [{"id": 4}],
    "mealSchema": ["dinner"],
    "tags": [{"name": "warm", "category": "RECIPE_TAG_USERS_TYPE"}],
    "shared": False,
    "energy": 270.17,
    "items": [
        {
            "type": "PRODUCT",
            "itemId": 501,
            "measureId": 1,
            "measureQuantity": "400.00",
            "name": "Beans",
            "measureName": "g",
        },
        {
            "type": "PRODUCT",
            "itemId": 502,
            "measureId": 3,
            "measureQuantity": "0.50",
            "name": "Onion",
            "measureName": "piece",
        },
    ],
}
# Fitatu keeps the ID on an edit that leaves the ingredients as they are, and gives
# a new one when they change.
UPDATED = {"id": 77, "name": "Soup", "energy": 270.17, "protein": 15}
REPLACED = {"id": 78, "name": "Stew", "energy": 180.4, "protein": 9}
# The full body for CURRENT, with the fields the web app sends back unchanged.
BODY = {
    "name": "Stew",
    "serving": "2",
    "items": [
        {"type": "PRODUCT", "itemId": 501, "measureId": 1, "measureQuantity": "400.00"},
        {"type": "PRODUCT", "itemId": 502, "measureId": 3, "measureQuantity": "0.50"},
    ],
    "recipeDescription": "Simmer.",
    "preparationTime": 10,
    "cookingTime": 20,
    "categories": [{"id": 4}],
    "mealSchema": ["dinner"],
    "tags": [{"name": "warm", "category": "RECIPE_TAG_USERS_TYPE"}],
    "shared": False,
}
SHAPE = "Run 'fitatu recipe edit --help' for the spec's shape."


def write(tmp_path: Path, spec: object) -> str:
    path = tmp_path / "spec.json"
    path.write_text(json.dumps(spec))
    return str(path)


def test_recipe_edit_puts_the_full_recipe_with_the_new_name(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    client = FakeClient(get=CURRENT, put=UPDATED)

    out = run_text(
        ["recipe", "edit", "77", write(tmp_path, {"name": "Soup"})], client, capsys
    )

    assert out == "77\n"
    assert client.calls == [
        ("get", ("/api/recipes/77",), {}),
        ("put", ("/api/recipes/77", BODY | {"name": "Soup"}), {}),
    ]


def test_recipe_edit_replaces_servings_description_and_every_ingredient(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    client = FakeClient(get=CURRENT, put=REPLACED)
    spec = {
        "serving": 3,
        "description": None,
        "items": [
            {"itemId": 503, "measureId": 2, "measureQuantity": 1},
            {"itemId": 501, "measureId": 1, "measureQuantity": 250},
        ],
    }

    out = run_text(["recipe", "edit", "77", write(tmp_path, spec)], client, capsys)

    assert out == "78\n"
    [_, (_, (_, body), _)] = client.calls
    assert body == BODY | {
        "serving": "3",
        "recipeDescription": None,
        "items": [
            {"type": "PRODUCT", "itemId": 503, "measureId": 2, "measureQuantity": 1},
            {"type": "PRODUCT", "itemId": 501, "measureId": 1, "measureQuantity": 250},
        ],
    }


def test_recipe_edit_json(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    out = run_json(
        ["recipe", "edit", "77", write(tmp_path, {"name": "Soup"}), "--json"],
        FakeClient(get=CURRENT, put=UPDATED),
        capsys,
    )

    assert out == {"id": 77}


def test_recipe_edit_raw_prints_the_response_unchanged(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    out = run_json(
        ["recipe", "edit", "77", write(tmp_path, {"name": "Soup"}), "--raw"],
        FakeClient(get=CURRENT, put=UPDATED),
        capsys,
    )

    assert out == UPDATED


def run_failing(
    client: FakeClient, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> str:
    argv = ["recipe", "edit", "77", write(tmp_path, {"name": "Soup"})]
    assert main(argv, connect=lambda: client) == 1
    return capsys.readouterr().err


def test_recipe_edit_reports_an_unknown_id(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    client = FakeClient(get=http_error(404), put=UPDATED)

    assert run_failing(client, tmp_path, capsys) == (
        "fitatu: Fitatu has no recipe with ID 77. "
        "Run 'fitatu recipe list' to see your recipes' IDs.\n"
    )
    assert [name for name, _, _ in client.calls] == ["get"]


def test_recipe_edit_refuses_a_deleted_recipe(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    client = FakeClient(get=CURRENT | {"deleted": True}, put=UPDATED)

    assert run_failing(client, tmp_path, capsys) == (
        "fitatu: Recipe 77 is deleted. An edit of its ingredients gives a recipe a "
        "new ID; "
        "run 'fitatu recipe list' for its current ID.\n"
    )
    assert [name for name, _, _ in client.calls] == ["get"]


@pytest.mark.parametrize("key", ["type", "itemId", "measureId", "measureQuantity"])
def test_recipe_edit_rejects_a_current_ingredient_without_a_field(
    key: str, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    items = [CURRENT["items"][0], {**CURRENT["items"][1], key: None}]
    client = FakeClient(get=CURRENT | {"items": items}, put=UPDATED)

    assert run_failing(client, tmp_path, capsys).startswith(
        "fitatu: Fitatu sent a response fitatu-cli could not read."
    )
    assert [name for name, _, _ in client.calls] == ["get"]


def test_recipe_edit_with_new_items_ignores_the_current_ones(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    client = FakeClient(get=CURRENT | {"items": [{"name": "Beans"}]}, put=UPDATED)
    items = [{"itemId": 503, "measureId": 2, "measureQuantity": 1}] * 2

    run_text(
        ["recipe", "edit", "77", write(tmp_path, {"items": items})], client, capsys
    )

    [_, (_, (_, body), _)] = client.calls
    assert [item["itemId"] for item in body["items"]] == [503, 503]


def test_recipe_edit_rejects_a_response_without_an_id(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    client = FakeClient(get=CURRENT, put={"name": "Soup"})

    assert run_failing(client, tmp_path, capsys).startswith(
        "fitatu: Fitatu sent a response fitatu-cli could not read."
    )


@pytest.mark.parametrize("code", [400, 404])
def test_recipe_edit_reports_a_rejected_recipe(
    code: int, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    client = FakeClient(get=CURRENT, put=http_error(code))

    assert run_failing(client, tmp_path, capsys) == (
        f"fitatu: Fitatu rejected the recipe (HTTP {code}). "
        "Check each item's itemId and measureId with 'fitatu food search'.\n"
    )


def test_recipe_edit_reports_a_server_error_as_unexpected(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    client = FakeClient(get=CURRENT, put=http_error(500))

    assert run_failing(client, tmp_path, capsys).startswith(
        "fitatu: Unexpected error (HTTPError: HTTP Error 500: error)."
    )


ITEM = {"itemId": 501, "measureId": 1, "measureQuantity": 400}


@pytest.mark.parametrize(
    ("spec", "problem", "action"),
    [
        ([{"name": "Soup"}], "is not a JSON object.", SHAPE),
        (
            {},
            'needs at least one of "name", "serving", "description" or "items".',
            SHAPE,
        ),
        (
            {"title": "Soup"},
            'needs at least one of "name", "serving", "description" or "items".',
            SHAPE,
        ),
        ({"name": ""}, 'needs "name": a non-empty string.', SHAPE),
        ({"name": None}, 'needs "name": a non-empty string.', SHAPE),
        ({"serving": 0}, 'needs "serving": a positive number.', SHAPE),
        ({"serving": "2"}, 'needs "serving": a positive number.', SHAPE),
        (
            {"items": [ITEM]},
            'needs "items": a list of at least 2 ingredients.',
            SHAPE,
        ),
    ],
)
def test_recipe_edit_rejects_an_invalid_spec(
    spec: object,
    problem: str,
    action: str,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    path = write(tmp_path, spec)

    with pytest.raises(SystemExit) as exit:
        main(["recipe", "edit", "77", path], connect=FakeClient)

    assert exit.value.code == 2
    assert capsys.readouterr().err == (
        f"fitatu: Recipe spec '{path}' {problem} {action}\n"
    )


def test_recipe_edit_rejects_an_invalid_item(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    path = write(tmp_path, {"items": [ITEM, {"itemId": 502, "measureQuantity": 1}]})

    with pytest.raises(SystemExit) as exit:
        main(["recipe", "edit", "77", path], connect=FakeClient)

    assert exit.value.code == 2
    assert capsys.readouterr().err == (
        f"fitatu: Item 2 in recipe spec '{path}' needs \"measureId\". "
        "Take itemId and measureId from 'fitatu food search'.\n"
    )


def test_recipe_edit_rejects_a_missing_file(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    path = tmp_path / "missing.json"

    with pytest.raises(SystemExit) as exit:
        main(["recipe", "edit", "77", str(path)], connect=FakeClient)

    assert exit.value.code == 2
    assert capsys.readouterr().err == (
        f"fitatu: Cannot read recipe spec '{path}' (No such file or directory). "
        "Give the path of a JSON file.\n"
    )


def test_recipe_edit_rejects_an_id_that_is_not_a_number(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    with pytest.raises(SystemExit) as exit:
        main(
            ["recipe", "edit", "stew", write(tmp_path, {"name": "Soup"})],
            connect=FakeClient,
        )

    assert exit.value.code == 2
    assert capsys.readouterr().err == (
        "fitatu: Invalid recipe ID 'stew'. Give the number from 'fitatu recipe list'.\n"
    )


def test_recipe_edit_help_shows_the_spec_shape(
    capsys: pytest.CaptureFixture[str],
) -> None:
    with pytest.raises(SystemExit) as exit:
        main(["recipe", "edit", "--help"])

    assert exit.value.code == 0
    help_text = " ".join(capsys.readouterr().out.split())
    assert help_text.startswith(
        "usage: fitatu recipe edit [-h] [--raw] [--json] ID SPEC "
        "Edit recipe ID with SPEC, a JSON file with any of the keys of a 'fitatu "
        'recipe create\' spec: "name", "serving", "description" and "items". Each '
        'key given replaces that field; "items" replaces every ingredient. '
        "Prints the recipe's ID: an edit of the ingredients or their quantities "
        "gives the recipe a new ID and marks the old one deleted; other edits keep "
        "the ID. "
    )
    assert (
        " positional arguments: ID the recipe's ID SPEC the changes' JSON file "
        "options: -h, --help show this help message and exit "
        "--raw print the full service response --json "
    ) in help_text


def test_recipe_edit_rejects_a_third_argument(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    with pytest.raises(SystemExit) as exit:
        main(
            ["recipe", "edit", "77", write(tmp_path, {"name": "Soup"}), "x"],
            connect=FakeClient,
        )

    assert exit.value.code == 2
    assert capsys.readouterr().err == (
        "fitatu: Unexpected argument 'x' for 'fitatu recipe edit'. "
        "Run 'fitatu recipe edit --help' for all options.\n"
    )
