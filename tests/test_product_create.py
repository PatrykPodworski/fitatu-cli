import json
from pathlib import Path
from typing import Any

import pytest
from conftest import FakeClient, http_error, run_json, run_text

from fitatu_cli.cli import main

Json = dict[str, Any]

SPEC: Json = {
    "name": "Bean stew",
    "energy": 129,
    "protein": 7.8,
    "fat": 3.4,
    "carbohydrate": 10.9,
}
CREATED = {"id": 100000031, "name": "Bean stew"}
PORTION = {"measure": "portion", "grams": 450}
SHAPE = "Run 'fitatu product create --help' for the spec's shape."
KEYS = (
    '"name", "brand", "energy", "protein", "fat", "carbohydrate", "fiber", '
    '"sugars", "salt", "per"'
)


def write(tmp_path: Path, spec: object) -> str:
    path = tmp_path / "spec.json"
    path.write_text(json.dumps(spec))
    return str(path)


def test_product_create_per_100_g_posts_no_measures_and_prints_the_id(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    client = FakeClient(post=CREATED)

    out = run_text(["product", "create", write(tmp_path, SPEC)], client, capsys)

    assert out == "100000031\n"
    assert client.calls == [
        (
            "post",
            (
                "/api/products",
                {
                    "name": "Bean stew",
                    "energy": 129,
                    "protein": 7.8,
                    "fat": 3.4,
                    "carbohydrate": 10.9,
                },
            ),
            {},
        )
    ]


def test_product_create_with_per_100_posts_no_measures(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    client = FakeClient(post=CREATED)

    run_text(
        ["product", "create", write(tmp_path, SPEC | {"per": 100})], client, capsys
    )

    [(_, (_, body), _)] = client.calls
    assert body == SPEC


def test_product_create_per_portion_posts_a_portion_measure(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    client = FakeClient(post=CREATED)
    spec = {"name": "Bean stew", "energy": 580, "protein": 35.1, "fat": 15.3}
    spec |= {"carbohydrate": 49, "per": {"grams": 450, "measure": "portion"}}

    run_text(["product", "create", write(tmp_path, spec)], client, capsys)

    [(_, (_, body), _)] = client.calls
    assert body == {
        "name": "Bean stew",
        "energy": 580,
        "protein": 35.1,
        "fat": 15.3,
        "carbohydrate": 49,
        "measures": [{"measureKey": "PORTION", "measureUnit": "g", "weight": 450}],
    }


def test_product_create_accepts_a_portion_under_a_gram(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    client = FakeClient(post=CREATED)
    spec = SPEC | {"per": {"measure": "portion", "grams": 0.5}}

    run_text(["product", "create", write(tmp_path, spec)], client, capsys)

    [(_, (_, body), _)] = client.calls
    assert body["measures"] == [
        {"measureKey": "PORTION", "measureUnit": "g", "weight": 0.5}
    ]


def test_product_create_passes_the_brand_and_optional_nutrients(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    client = FakeClient(post=CREATED)
    extra = {"brand": "Bistro", "fiber": 1.2, "sugars": 0, "salt": 0.9}

    run_text(["product", "create", write(tmp_path, SPEC | extra)], client, capsys)

    [(_, (_, body), _)] = client.calls
    assert body == {
        "name": "Bean stew",
        "brand": "Bistro",
        "energy": 129,
        "protein": 7.8,
        "fat": 3.4,
        "carbohydrate": 10.9,
        "fiber": 1.2,
        "sugars": 0,
        "salt": 0.9,
    }


def test_product_create_json(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    out = run_json(
        ["product", "create", write(tmp_path, SPEC), "--json"],
        FakeClient(post=CREATED),
        capsys,
    )

    assert out == {"id": 100000031}


def test_product_create_raw_prints_the_response_unchanged(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    out = run_json(
        ["product", "create", write(tmp_path, SPEC), "--raw"],
        FakeClient(post=CREATED),
        capsys,
    )

    assert out == CREATED


def test_product_create_rejects_a_response_without_an_id(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    client = FakeClient(post={"name": "Bean stew"})

    assert (
        main(["product", "create", write(tmp_path, SPEC)], connect=lambda: client) == 1
    )
    assert capsys.readouterr().err.startswith(
        "fitatu: Fitatu sent a response fitatu-cli could not read."
    )


@pytest.mark.parametrize("code", [400, 499])
def test_product_create_reports_a_rejected_product(
    code: int, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    client = FakeClient(post=http_error(code))

    assert (
        main(["product", "create", write(tmp_path, SPEC)], connect=lambda: client) == 1
    )
    assert capsys.readouterr().err == (
        f"fitatu: Fitatu rejected the product (HTTP {code}). "
        "Check the spec with 'fitatu product create --help'.\n"
    )


def test_product_create_reports_a_server_error_as_unexpected(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    client = FakeClient(post=http_error(500))

    assert (
        main(["product", "create", write(tmp_path, SPEC)], connect=lambda: client) == 1
    )
    assert capsys.readouterr().err.startswith(
        "fitatu: Unexpected error (HTTPError: HTTP Error 500: error)."
    )


def without(key: str) -> Json:
    return {name: value for name, value in SPEC.items() if name != key}


NAME = 'needs "name": a non-empty string.'
BRAND = 'needs "brand": a non-empty string.'
PER = 'needs "per": 100, or {"measure": "portion", "grams": N} with N above 0.'


def nutrient(key: str) -> str:
    return f'needs "{key}": a number of 0 or more.'


@pytest.mark.parametrize(
    ("spec", "problem"),
    [
        ([SPEC], "is not a JSON object."),
        (SPEC | {"kcal": 129}, f'has an unknown key "kcal". The keys are {KEYS}.'),
        (without("name"), NAME),
        (SPEC | {"name": ""}, NAME),
        (SPEC | {"name": 7}, NAME),
        (SPEC | {"brand": ""}, BRAND),
        (SPEC | {"brand": None}, BRAND),
        (without("energy"), nutrient("energy")),
        (without("protein"), nutrient("protein")),
        (without("fat"), nutrient("fat")),
        (without("carbohydrate"), nutrient("carbohydrate")),
        (SPEC | {"fat": -0.1}, nutrient("fat")),
        (SPEC | {"energy": "129"}, nutrient("energy")),
        (SPEC | {"protein": True}, nutrient("protein")),
        (SPEC | {"fiber": None}, nutrient("fiber")),
        (SPEC | {"sugars": -1}, nutrient("sugars")),
        (SPEC | {"salt": "0.9"}, nutrient("salt")),
        (SPEC | {"per": 50}, PER),
        (SPEC | {"per": "100"}, PER),
        (SPEC | {"per": True}, PER),
        (SPEC | {"per": None}, PER),
        (SPEC | {"per": {"measure": "slice", "grams": 100}}, PER),
        (SPEC | {"per": {"measure": "portion", "grams": 0}}, PER),
        (SPEC | {"per": {"measure": "portion", "grams": -450}}, PER),
        (SPEC | {"per": {"measure": "portion", "grams": "450"}}, PER),
        (SPEC | {"per": {"measure": "portion"}}, PER),
        (SPEC | {"per": PORTION | {"weight": 450}}, PER),
        (SPEC | {"per": [PORTION]}, PER),
    ],
)
def test_product_create_rejects_an_invalid_spec(
    spec: object, problem: str, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    path = write(tmp_path, spec)
    client = FakeClient()

    with pytest.raises(SystemExit) as exit:
        main(["product", "create", path], connect=lambda: client)

    assert exit.value.code == 2
    assert (
        capsys.readouterr().err == f"fitatu: Product spec '{path}' {problem} {SHAPE}\n"
    )
    assert client.calls == []


@pytest.mark.parametrize(
    ("value", "key"),
    [("NaN", "energy"), ("Infinity", "fat"), ("-Infinity", "salt")],
)
def test_product_create_rejects_a_number_json_allows_but_fitatu_cannot_store(
    value: str, key: str, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    path = tmp_path / "spec.json"
    path.write_text(json.dumps(SPEC)[:-1] + f', "{key}": {value}}}')

    with pytest.raises(SystemExit) as exit:
        main(["product", "create", str(path)], connect=FakeClient)

    assert exit.value.code == 2
    assert capsys.readouterr().err == (
        f"fitatu: Product spec '{path}' {nutrient(key)} {SHAPE}\n"
    )


def test_product_create_rejects_an_infinite_portion_weight(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    path = tmp_path / "spec.json"
    path.write_text(
        json.dumps(SPEC)[:-1] + ', "per": {"measure": "portion", "grams": Infinity}}'
    )

    with pytest.raises(SystemExit) as exit:
        main(["product", "create", str(path)], connect=FakeClient)

    assert exit.value.code == 2
    assert capsys.readouterr().err == f"fitatu: Product spec '{path}' {PER} {SHAPE}\n"


def test_product_create_accepts_zero_nutrients(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    client = FakeClient(post=CREATED)
    zeros = {"name": "Water", "energy": 0, "protein": 0, "fat": 0.0}
    zeros |= {"carbohydrate": 0, "fiber": 0, "sugars": 0, "salt": 0}

    out = run_text(["product", "create", write(tmp_path, zeros)], client, capsys)

    assert out == "100000031\n"
    [(_, (_, body), _)] = client.calls
    assert body == zeros


def test_product_create_rejects_a_file_that_is_not_json(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    path = tmp_path / "spec.json"
    path.write_text('{\n"name" "Bean stew"}')

    with pytest.raises(SystemExit) as exit:
        main(["product", "create", str(path)], connect=FakeClient)

    assert exit.value.code == 2
    assert capsys.readouterr().err == (
        f"fitatu: Product spec '{path}' is not valid JSON (Expecting ':' delimiter, "
        f"line 2). {SHAPE}\n"
    )


def test_product_create_rejects_a_missing_file(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    path = tmp_path / "missing.json"

    with pytest.raises(SystemExit) as exit:
        main(["product", "create", str(path)], connect=FakeClient)

    assert exit.value.code == 2
    assert capsys.readouterr().err == (
        f"fitatu: Cannot read product spec '{path}' (No such file or directory). "
        "Give the path of a JSON file.\n"
    )


def test_product_create_help_shows_the_spec_shape_and_how_to_log_it(
    capsys: pytest.CaptureFixture[str],
) -> None:
    with pytest.raises(SystemExit) as exit:
        main(["product", "create", "--help"])

    assert exit.value.code == 0
    help_text = " ".join(capsys.readouterr().out.split())
    assert help_text.startswith(
        "usage: fitatu product create [-h] [--raw] [--json] SPEC "
        "Create a private product from SPEC, a JSON file with the values on a food "
        'label: {"name": "Bean stew", "brand": "Bistro", "energy": 129, "protein": '
        '7.8, "fat": 3.4, "carbohydrate": 10.9, "fiber": 1.2, "sugars": 2.3, '
        '"salt": 0.9, "per": 100}. "brand", "fiber", "sugars", "salt" and "per" '
        "are optional. energy is in kcal, the other nutrients in grams. With "
        '"per": 100, the default, the values are per 100 g. With "per": '
        '{"measure": "portion", "grams": 450}, they are per portion, as printed on '
        "the label, and the product gets a portion measure of that weight. Prints "
        "the product's ID. Log the product with 'fitatu entry create DATE MEAL "
        "--product ID --measure 1 --quantity GRAMS', or with --measure 39 "
        "--quantity PORTIONS when it has a portion. "
    )
    assert (
        " positional arguments: SPEC the product's JSON file options: "
        "-h, --help show this help message and exit "
        "--raw print the full service response --json "
    ) in help_text


def test_product_create_rejects_a_second_argument(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    with pytest.raises(SystemExit) as exit:
        main(["product", "create", write(tmp_path, SPEC), "x"], connect=FakeClient)

    assert exit.value.code == 2
    assert capsys.readouterr().err == (
        "fitatu: Unexpected argument 'x' for 'fitatu product create'. "
        "Run 'fitatu product create --help' for all options.\n"
    )
