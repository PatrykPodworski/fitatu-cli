import json
from pathlib import Path
from typing import Any

import pytest
from conftest import FakeClient, http_error, run_json, run_text

from fitatu_cli.cli import main

Json = dict[str, Any]

# A product with only a gram measure, and one with a 450 g portion. Fitatu returns
# the nutrients per 100 g in both.
GRAMS: Json = {
    "id": 501,
    "name": "Oat bar",
    "brand": "Mill",
    "private": True,
    "deleted": False,
    "measures": [{"id": 1, "name": "g", "weightPerUnit": 1}],
    "energy": 400,
    "protein": 10,
    "fat": 15,
    "carbohydrate": 55,
    "fiber": 6,
    "sugars": 20,
    "salt": 0.3,
}
PORTION: Json = {
    "id": 502,
    "name": "Bean stew",
    "brand": None,
    "private": True,
    "deleted": False,
    "measures": [
        {"id": 39, "name": "portion", "weightPerUnit": 450, "energyPerUnit": 580},
        {"id": 1, "name": "g", "weightPerUnit": 1, "energyPerUnit": 1.29},
    ],
    "energy": 128.89,
    "protein": 7.8,
    "fat": 3.4,
    "carbohydrate": 10.9,
    "fiber": 1.2,
    "sugars": None,
    "salt": 0.9,
}
KEPT = {"id": 501, "name": "Oat crunch", "newProductCreated": False}
# Fitatu saves an edit of the nutrients under a new ID.
REPLACED = {"id": 503, "name": "Bean stew", "newProductCreated": True}
PORTION_MEASURE = {"measureKey": "PORTION", "measureUnit": "g", "weight": 450}
SHAPE = "Run 'fitatu product edit --help' for the spec's shape."


def write(tmp_path: Path, spec: object) -> str:
    path = tmp_path / "spec.json"
    path.write_text(json.dumps(spec))
    return str(path)


def put_body(client: FakeClient) -> Json:
    [_, (name, (_, body), _)] = client.calls
    assert name == "put"
    return body  # type: ignore[no-any-return]


def test_product_edit_of_the_name_puts_the_current_values_per_100_g(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    client = FakeClient(get=GRAMS, put=KEPT)

    out = run_text(
        ["product", "edit", "501", write(tmp_path, {"name": "Oat crunch"})],
        client,
        capsys,
    )

    assert out == "501\n"
    assert client.calls == [
        ("get", ("/api/products/501",), {}),
        (
            "put",
            (
                "/api/products/501",
                {
                    "name": "Oat crunch",
                    "brand": "Mill",
                    "energy": 400,
                    "protein": 10,
                    "fat": 15,
                    "carbohydrate": 55,
                    "fiber": 6,
                    "sugars": 20,
                    "salt": 0.3,
                },
            ),
            {},
        ),
    ]


def test_product_edit_of_a_portion_product_puts_values_per_portion_and_keeps_it(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    client = FakeClient(get=PORTION, put=REPLACED)
    spec = {"brand": "Bistro", "energy": 600}
    spec |= {"per": {"measure": "portion", "grams": 450}}

    out = run_text(["product", "edit", "502", write(tmp_path, spec)], client, capsys)

    assert out == "503\n"
    assert client.calls[1][1][0] == "/api/products/502"
    assert put_body(client) == {
        "name": "Bean stew",
        "brand": "Bistro",
        "energy": 600,
        "protein": 35.1,
        "fat": 15.3,
        "carbohydrate": 49.05,
        "fiber": 5.4,
        "sugars": None,
        "salt": 4.05,
        "measures": [PORTION_MEASURE],
    }


def test_product_edit_converts_nutrients_per_100_g_on_a_portion_product(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    client = FakeClient(get=PORTION, put=REPLACED)

    run_text(
        ["product", "edit", "502", write(tmp_path, {"protein": 8.2, "per": 100})],
        client,
        capsys,
    )

    body = put_body(client)
    assert (body["energy"], body["protein"]) == (580, 36.9)
    assert body["measures"] == [PORTION_MEASURE]


def test_product_edit_with_a_portion_adds_one_to_a_gram_product(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    client = FakeClient(get=GRAMS, put=REPLACED)
    spec = {"salt": 1, "per": {"measure": "portion", "grams": 250}}

    run_text(["product", "edit", "501", write(tmp_path, spec)], client, capsys)

    assert put_body(client) == {
        "name": "Oat bar",
        "brand": "Mill",
        "energy": 1000,
        "protein": 25,
        "fat": 37.5,
        "carbohydrate": 137.5,
        "fiber": 15,
        "sugars": 50,
        "salt": 1,
        "measures": [{"measureKey": "PORTION", "measureUnit": "g", "weight": 250}],
    }


def test_product_edit_with_a_new_portion_converts_through_the_new_weight(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    client = FakeClient(get=PORTION, put=REPLACED)
    spec = {"fat": 2.5, "per": {"measure": "portion", "grams": 200}}

    run_text(["product", "edit", "502", write(tmp_path, spec)], client, capsys)

    body = put_body(client)
    assert (body["energy"], body["fat"], body["salt"]) == (257.78, 2.5, 1.8)
    assert body["measures"] == [
        {"measureKey": "PORTION", "measureUnit": "g", "weight": 200}
    ]


def test_product_edit_json(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    out = run_json(
        ["product", "edit", "502", write(tmp_path, {"energy": 140}), "--json"],
        FakeClient(get=PORTION, put=REPLACED),
        capsys,
    )

    assert out == {"id": 503}


def test_product_edit_raw_prints_the_response_unchanged(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    out = run_json(
        ["product", "edit", "502", write(tmp_path, {"energy": 140}), "--raw"],
        FakeClient(get=PORTION, put=REPLACED),
        capsys,
    )

    assert out == REPLACED


def test_product_edit_sends_missing_values_as_null_and_no_measures(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    client = FakeClient(get={"private": True, "energy": 90}, put=KEPT)

    run_text(
        ["product", "edit", "501", write(tmp_path, {"name": "Oat crunch"})],
        client,
        capsys,
    )

    assert put_body(client) == {
        "name": "Oat crunch",
        "brand": None,
        "energy": 90,
        "protein": None,
        "fat": None,
        "carbohydrate": None,
        "fiber": None,
        "sugars": None,
        "salt": None,
    }


def test_product_edit_keeps_a_portion_under_a_gram(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    measures = [{"id": 39, "name": "portion", "weightPerUnit": 0.5}]
    client = FakeClient(get=PORTION | {"measures": measures}, put=REPLACED)

    run_text(
        ["product", "edit", "502", write(tmp_path, {"name": "Soup"})], client, capsys
    )

    body = put_body(client)
    assert (body["energy"], body["protein"]) == (0.64, 0.04)
    assert body["measures"] == [
        {"measureKey": "PORTION", "measureUnit": "g", "weight": 0.5}
    ]


def run_failing(
    client: FakeClient,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
    spec: Json | None = None,
) -> str:
    argv = ["product", "edit", "502", write(tmp_path, spec or {"name": "Soup"})]
    assert main(argv, connect=lambda: client) == 1
    return capsys.readouterr().err


@pytest.mark.parametrize(
    "measure", [{"id": 39, "name": "portion"}, {"id": 39, "weightPerUnit": 0}]
)
def test_product_edit_rejects_a_portion_without_a_weight(
    measure: Json, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    client = FakeClient(get=PORTION | {"measures": [measure]}, put=REPLACED)

    assert run_failing(client, tmp_path, capsys).startswith(
        "fitatu: Fitatu sent a response fitatu-cli could not read."
    )
    assert [name for name, _, _ in client.calls] == ["get"]


def test_product_edit_reports_an_unknown_id(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    client = FakeClient(get=http_error(404), put=REPLACED)

    assert run_failing(client, tmp_path, capsys) == (
        "fitatu: Fitatu has no product with ID 502. "
        "Run 'fitatu product list' to see your products' IDs.\n"
    )
    assert [name for name, _, _ in client.calls] == ["get"]


def test_product_edit_refuses_a_deleted_product(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    client = FakeClient(get=PORTION | {"deleted": True}, put=REPLACED)

    assert run_failing(client, tmp_path, capsys) == (
        "fitatu: Product 502 is deleted. An edit of its nutrients gives a product a "
        "new ID; run 'fitatu product list' for its current ID.\n"
    )
    assert [name for name, _, _ in client.calls] == ["get"]


@pytest.mark.parametrize("private", [False, None, "true"])
def test_product_edit_refuses_a_product_that_is_not_yours(
    private: object, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    client = FakeClient(get=PORTION | {"private": private}, put=REPLACED)

    assert run_failing(client, tmp_path, capsys) == (
        "fitatu: Product 502 is not one of yours. You can edit only your own "
        "products; run 'fitatu product list' to see them.\n"
    )
    assert [name for name, _, _ in client.calls] == ["get"]


@pytest.mark.parametrize("code", [403, 404])
def test_product_edit_reports_a_product_fitatu_did_not_edit(
    code: int, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    client = FakeClient(get=PORTION, put=http_error(code))

    assert run_failing(client, tmp_path, capsys) == (
        f"fitatu: Fitatu did not edit product 502 (HTTP {code}). You can edit only "
        "your own products; run 'fitatu product list' to see them.\n"
    )


@pytest.mark.parametrize("code", [400, 422])
def test_product_edit_reports_a_rejected_product(
    code: int, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    client = FakeClient(get=PORTION, put=http_error(code))

    assert run_failing(client, tmp_path, capsys) == (
        f"fitatu: Fitatu rejected the product (HTTP {code}). "
        "Check the spec with 'fitatu product create --help'.\n"
    )


def test_product_edit_reports_a_server_error_as_unexpected(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    client = FakeClient(get=PORTION, put=http_error(500))

    assert run_failing(client, tmp_path, capsys).startswith(
        "fitatu: Unexpected error (HTTPError: HTTP Error 500: error)."
    )


KEYS = (
    '"name", "brand", "energy", "protein", "fat", "carbohydrate", "fiber", '
    '"sugars", "salt", "per"'
)
ANY = (
    '"name", "brand", "energy", "protein", "fat", "carbohydrate", "fiber", '
    '"sugars", "salt" or "per"'
)
PER = 'needs "per": 100, or {"measure": "portion", "grams": N} with N above 0.'


@pytest.mark.parametrize(
    ("spec", "problem"),
    [
        ([{"name": "Soup"}], "is not a JSON object."),
        ({}, f"needs at least one of {ANY}."),
        ({"kcal": 129}, f'has an unknown key "kcal". The keys are {KEYS}.'),
        ({"name": ""}, 'needs "name": a non-empty string.'),
        ({"brand": None}, 'needs "brand": a non-empty string.'),
        ({"energy": -1}, 'needs "energy": a number of 0 or more.'),
        ({"salt": "0.9"}, 'needs "salt": a number of 0 or more.'),
        ({"energy": 100, "per": 50}, PER),
        ({"per": {"measure": "portion", "grams": 0}}, PER),
    ],
)
def test_product_edit_rejects_an_invalid_spec(
    spec: object, problem: str, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    path = write(tmp_path, spec)
    client = FakeClient()

    with pytest.raises(SystemExit) as exit:
        main(["product", "edit", "502", path], connect=lambda: client)

    assert exit.value.code == 2
    assert (
        capsys.readouterr().err == f"fitatu: Product spec '{path}' {problem} {SHAPE}\n"
    )
    assert client.calls == []


def test_product_edit_rejects_an_id_that_is_not_a_number(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    with pytest.raises(SystemExit) as exit:
        main(["product", "edit", "stew", write(tmp_path, {"name": "Soup"})])

    assert exit.value.code == 2
    assert capsys.readouterr().err == (
        "fitatu: Invalid product ID 'stew'. Give the number from 'fitatu product "
        "list'.\n"
    )


def test_product_edit_help_says_which_edits_give_a_new_id(
    capsys: pytest.CaptureFixture[str],
) -> None:
    with pytest.raises(SystemExit) as exit:
        main(["product", "edit", "--help"])

    assert exit.value.code == 0
    help_text = " ".join(capsys.readouterr().out.split())
    assert help_text.startswith(
        "usage: fitatu product edit [-h] [--raw] [--json] ID SPEC "
        "Edit product ID, one of yours, with SPEC, a JSON file with any of the "
        "keys of a 'fitatu product create' spec. Each key given replaces that "
        'value. Nutrients are per 100 g, or per portion with "per": {"measure": '
        '"portion", "grams": 450}, which also sets the product\'s portion to that '
        "weight; otherwise the product keeps its portion. Prints the product's "
        "ID. An edit of the nutrients or of the portion can give the product a "
        "new ID; the old one stays, marked deleted, and diary entries keep using "
        "it. "
    )
    assert (
        " positional arguments: ID the product's ID SPEC the changes' JSON file "
        "options: -h, --help show this help message and exit "
        "--raw print the full service response --json "
    ) in help_text


def test_product_edit_rejects_a_third_argument(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    with pytest.raises(SystemExit) as exit:
        main(["product", "edit", "502", write(tmp_path, {"name": "Soup"}), "x"])

    assert exit.value.code == 2
    assert capsys.readouterr().err == (
        "fitatu: Unexpected argument 'x' for 'fitatu product edit'. "
        "Run 'fitatu product edit --help' for all options.\n"
    )
