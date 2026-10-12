import json
from pathlib import Path
from typing import Any

import pytest
from conftest import FakeClient, http_error, run_json, run_text

from fitatu_cli.cli import main

Json = dict[str, Any]

SPEC: Json = {
    "name": "Stew",
    "serving": 2,
    "description": "Simmer.",
    "items": [
        {"itemId": 501, "measureId": 1, "measureQuantity": 400},
        {"itemId": 502, "measureId": 3, "measureQuantity": 0.5},
    ],
}
CREATED = {"id": 77, "name": "Stew", "energy": 270.17, "protein": 15}
BODY = {
    "name": "Stew",
    "serving": "2",
    "items": [
        {"type": "PRODUCT", "itemId": 501, "measureId": 1, "measureQuantity": 400},
        {"type": "PRODUCT", "itemId": 502, "measureId": 3, "measureQuantity": 0.5},
    ],
    "recipeDescription": "Simmer.",
    "preparationTime": "",
    "cookingTime": None,
    "categories": [],
    "mealSchema": [],
    "tags": [],
    "shared": False,
}
SHAPE = "Run 'fitatu recipe create --help' for the spec's shape."


def write(tmp_path: Path, spec: object) -> str:
    path = tmp_path / "spec.json"
    path.write_text(json.dumps(spec))
    return str(path)


def test_recipe_create_posts_the_spec_and_prints_the_id(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    client = FakeClient(post=CREATED)

    out = run_text(["recipe", "create", write(tmp_path, SPEC)], client, capsys)

    assert out == "77\n"
    assert client.calls == [("post", ("/api/recipes", BODY), {})]


def test_recipe_create_without_a_description_sends_null(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    client = FakeClient(post=CREATED)
    spec = {key: value for key, value in SPEC.items() if key != "description"}

    run_text(
        ["recipe", "create", write(tmp_path, spec | {"serving": 1})], client, capsys
    )

    [(_, (_, body), _)] = client.calls
    assert body == BODY | {"serving": "1", "recipeDescription": None}


def test_recipe_create_json(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    out = run_json(
        ["recipe", "create", write(tmp_path, SPEC), "--json"],
        FakeClient(post=CREATED),
        capsys,
    )

    assert out == {"id": 77}


def test_recipe_create_raw_prints_the_response_unchanged(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    out = run_json(
        ["recipe", "create", write(tmp_path, SPEC), "--raw"],
        FakeClient(post=CREATED),
        capsys,
    )

    assert out == CREATED


def test_recipe_create_rejects_a_response_without_an_id(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    client = FakeClient(post={"name": "Stew"})

    assert (
        main(["recipe", "create", write(tmp_path, SPEC)], connect=lambda: client) == 1
    )
    assert capsys.readouterr().err.startswith(
        "fitatu: Fitatu sent a response fitatu-cli could not read."
    )


@pytest.mark.parametrize("code", [400, 404])
def test_recipe_create_reports_a_rejected_recipe(
    code: int, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    client = FakeClient(post=http_error(code))

    assert (
        main(["recipe", "create", write(tmp_path, SPEC)], connect=lambda: client) == 1
    )
    assert capsys.readouterr().err == (
        f"fitatu: Fitatu rejected the recipe (HTTP {code}). "
        "Check each item's itemId and measureId with 'fitatu food search'.\n"
    )


def test_recipe_create_reports_a_server_error_as_unexpected(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    client = FakeClient(post=http_error(500))

    assert (
        main(["recipe", "create", write(tmp_path, SPEC)], connect=lambda: client) == 1
    )
    assert capsys.readouterr().err.startswith(
        "fitatu: Unexpected error (HTTPError: HTTP Error 500: error)."
    )


def item(**fields: Any) -> Json:
    return {"itemId": 501, "measureId": 1, "measureQuantity": 400} | fields


INGREDIENTS = 'needs "items": a list of at least 2 ingredients.'


@pytest.mark.parametrize(
    ("spec", "problem", "action"),
    [
        ([SPEC], "is not a JSON object.", SHAPE),
        (SPEC | {"name": None}, 'needs "name": a non-empty string.', SHAPE),
        (SPEC | {"name": ""}, 'needs "name": a non-empty string.', SHAPE),
        (SPEC | {"name": 7}, 'needs "name": a non-empty string.', SHAPE),
        (SPEC | {"serving": None}, 'needs "serving": a positive number.', SHAPE),
        (SPEC | {"serving": 0}, 'needs "serving": a positive number.', SHAPE),
        (SPEC | {"serving": -1.5}, 'needs "serving": a positive number.', SHAPE),
        (SPEC | {"serving": "2"}, 'needs "serving": a positive number.', SHAPE),
        (SPEC | {"serving": True}, 'needs "serving": a positive number.', SHAPE),
        (SPEC | {"items": None}, INGREDIENTS, SHAPE),
        (SPEC | {"items": {}}, INGREDIENTS, SHAPE),
        (SPEC | {"items": []}, INGREDIENTS, SHAPE),
        (SPEC | {"items": [item()]}, INGREDIENTS, SHAPE),
    ],
)
def test_recipe_create_rejects_an_invalid_spec(
    spec: object,
    problem: str,
    action: str,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    path = write(tmp_path, spec)

    with pytest.raises(SystemExit) as exit:
        main(["recipe", "create", path], connect=FakeClient)

    assert exit.value.code == 2
    assert capsys.readouterr().err == (
        f"fitatu: Recipe spec '{path}' {problem} {action}\n"
    )


SEARCH = "Take itemId and measureId from 'fitatu food search'."


@pytest.mark.parametrize(
    ("items", "problem"),
    [
        ([item(), "501"], "Item 2 in recipe spec '{path}' is not a JSON object."),
        (
            [item(itemId=None), item()],
            "Item 1 in recipe spec '{path}' needs \"itemId\".",
        ),
        (
            [item(), {"itemId": 502, "measureQuantity": 1}],
            "Item 2 in recipe spec '{path}' needs \"measureId\".",
        ),
        (
            [item(), item(), {"itemId": 502, "measureId": 1}],
            "Item 3 in recipe spec '{path}' needs \"measureQuantity\".",
        ),
    ],
)
def test_recipe_create_rejects_an_invalid_item(
    items: list[object],
    problem: str,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    path = write(tmp_path, SPEC | {"items": items})

    with pytest.raises(SystemExit) as exit:
        main(["recipe", "create", path], connect=FakeClient)

    assert exit.value.code == 2
    assert capsys.readouterr().err == (
        f"fitatu: {problem.format(path=path)} {SEARCH}\n"
    )


def test_recipe_create_rejects_a_file_that_is_not_json(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    path = tmp_path / "spec.json"
    path.write_text('{\n"name" "Stew"}')

    with pytest.raises(SystemExit) as exit:
        main(["recipe", "create", str(path)], connect=FakeClient)

    assert exit.value.code == 2
    assert capsys.readouterr().err == (
        f"fitatu: Recipe spec '{path}' is not valid JSON (Expecting ':' delimiter, "
        f"line 2). {SHAPE}\n"
    )


def test_recipe_create_rejects_a_missing_file(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    path = tmp_path / "missing.json"

    with pytest.raises(SystemExit) as exit:
        main(["recipe", "create", str(path)], connect=FakeClient)

    assert exit.value.code == 2
    assert capsys.readouterr().err == (
        f"fitatu: Cannot read recipe spec '{path}' (No such file or directory). "
        "Give the path of a JSON file.\n"
    )


def test_recipe_create_help_shows_the_spec_shape(
    capsys: pytest.CaptureFixture[str],
) -> None:
    with pytest.raises(SystemExit) as exit:
        main(["recipe", "create", "--help"])

    assert exit.value.code == 0
    help_text = " ".join(capsys.readouterr().out.split())
    assert help_text.startswith(
        "usage: fitatu recipe create [-h] [--raw] [--json] SPEC "
        'Create a recipe from SPEC, a JSON file: {"name": "Stew", "serving": 2, '
        '"description": "Simmer." (optional), "items": [{"itemId": 501, '
        '"measureId": 1, "measureQuantity": 400}, ...]}, with at least 2 items. '
        "Take itemId and measureId from 'fitatu food search'; measureQuantity "
        "counts that measure. "
    )
    assert (
        " positional arguments: SPEC the recipe's JSON file options: "
        "-h, --help show this help message and exit "
        "--raw print the full service response --json "
    ) in help_text


def test_recipe_create_rejects_a_second_argument(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    with pytest.raises(SystemExit) as exit:
        main(["recipe", "create", write(tmp_path, SPEC), "x"], connect=FakeClient)

    assert exit.value.code == 2
    assert capsys.readouterr().err == (
        "fitatu: Unexpected argument 'x' for 'fitatu recipe create'. "
        "Run 'fitatu recipe create --help' for all options.\n"
    )
