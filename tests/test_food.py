from typing import Any

import pytest
from conftest import FakeClient, http_error, run_json, run_text

from fitatu_cli.cli import main
from fitatu_cli.day import Json

USER = "/api/users/{uid}"
CATALOG = (
    "/api/search/new/food?hasFilters=false&accessType[]=FREE&accessType[]=PREMIUM"
    "&page=1&limit=40&phrase=rye+bread&locale=xx_XX"
)
LAST_USED = "/api/search/food/{uid}/last-used?page=1&limit=100"


LOCALES = "pl_PL, en_GB, en_US, de_DE, cs_CZ, es_ES, it_IT, fr_FR"


class RoutedClient:
    """Answers `get(path)` with `routes[path]`, or raises it when it is an
    exception, and records the paths."""

    def __init__(self, routes: dict[str, Any]) -> None:
        self.routes = routes
        self.paths: list[str] = []

    def get(self, path: str) -> Any:
        self.paths.append(path)
        response = self.routes[path]
        if isinstance(response, BaseException):
            raise response
        return response


BREAD: Json = {
    "foodId": 501,
    "type": "PRODUCT",
    "name": "Rye bread",
    "brand": "Bakery",
    "energy": 240.33333,
    "measure": {
        "measureId": 7,
        "measureName": "slice",
        "measureQuantity": 1,
        "measureWeight": 32.5,
    },
    "items": [],
}
STEW: Json = {
    "foodId": 9001,
    "type": "RECIPE",
    "name": "Stew",
    "brand": None,
    "energy": 410,
    "measure": {
        "measureId": 39,
        "measureName": "portion",
        "measureQuantity": 1,
        "measureWeight": 350,
    },
}
BREAD_ROW = {
    "id": 501,
    "type": "product",
    "name": "Rye bread",
    "brand": "Bakery",
    "energy": 240.3,
    "measure": {"id": 7, "name": "slice", "grams": 32.5},
}
STEW_ROW = {
    "id": 9001,
    "type": "recipe",
    "name": "Stew",
    "brand": None,
    "energy": 410,
    "measure": {"id": 39, "name": "portion", "grams": 350},
}


def catalog(*items: Json) -> RoutedClient:
    return RoutedClient({USER: {"searchLocale": "xx_XX"}, CATALOG: list(items)})


def test_phrase_searches_the_catalog_in_the_account_locale(
    capsys: pytest.CaptureFixture[str],
) -> None:
    client = catalog(BREAD, STEW)

    out = run_json(["food", "search", "rye bread", "--json"], client, capsys)

    assert out == [BREAD_ROW, STEW_ROW]
    assert client.paths == [USER, CATALOG]


def test_locale_overrides_the_account_locale_in_the_request(
    capsys: pytest.CaptureFixture[str],
) -> None:
    client = RoutedClient({CATALOG.replace("xx_XX", "en_GB"): [BREAD]})

    out = run_json(
        ["food", "search", "rye bread", "--locale", "en_GB", "--json"], client, capsys
    )

    assert out == [BREAD_ROW]
    assert client.paths == [CATALOG.replace("xx_XX", "en_GB")]


def test_an_unknown_locale_goes_to_fitatu_and_its_400_exits_1(
    capsys: pytest.CaptureFixture[str],
) -> None:
    client: Any = RoutedClient({CATALOG: http_error(400)})
    argv = ["food", "search", "rye bread", "--locale", "xx_XX"]

    assert main(argv, connect=lambda: client) == 1
    assert client.paths == [CATALOG]
    assert capsys.readouterr().err == (
        f"fitatu: Fitatu does not search in locale 'xx_XX'. Use one of: {LOCALES}.\n"
    )


@pytest.mark.parametrize(("argv", "code"), [(["--locale", "xx_XX"], 500), ([], 400)])
def test_another_search_http_error_is_unexpected(
    argv: list[str], code: int, capsys: pytest.CaptureFixture[str]
) -> None:
    client: Any = RoutedClient(
        {USER: {"searchLocale": "xx_XX"}, CATALOG: http_error(code)}
    )

    assert main(["food", "search", "rye bread", *argv], connect=lambda: client) == 1
    assert capsys.readouterr().err.startswith(
        f"fitatu: Unexpected error (HTTPError: HTTP Error {code}: error)."
    )


def test_no_phrase_lists_the_last_used_foods(
    capsys: pytest.CaptureFixture[str],
) -> None:
    client = RoutedClient({LAST_USED: [STEW, BREAD]})

    out = run_json(["food", "search", "--json"], client, capsys)

    assert out == [STEW_ROW, BREAD_ROW]
    assert client.paths == [LAST_USED]


def test_empty_phrase_lists_the_last_used_foods(
    capsys: pytest.CaptureFixture[str],
) -> None:
    client = RoutedClient({LAST_USED: [STEW]})

    assert run_json(["food", "search", "", "--json"], client, capsys) == [STEW_ROW]
    assert client.paths == [LAST_USED]


def test_phrase_is_url_encoded(capsys: pytest.CaptureFixture[str]) -> None:
    path = (
        "/api/search/new/food?hasFilters=false&accessType[]=FREE&accessType[]=PREMIUM"
        "&page=1&limit=40&phrase=%C5%BCur+%26+%7Buid%7D&locale=xx_XX"
    )
    client = RoutedClient({USER: {"searchLocale": "xx_XX"}, path: [BREAD]})

    assert run_json(["food", "search", "żur & {uid}", "--json"], client, capsys) == [
        BREAD_ROW
    ]


def test_missing_fields_and_a_missing_measure_are_null(
    capsys: pytest.CaptureFixture[str],
) -> None:
    client = catalog({"foodId": 7, "measure": None}, {"measure": {}})

    assert run_json(["food", "search", "rye bread", "--json"], client, capsys) == [
        {
            "id": 7,
            "type": None,
            "name": None,
            "brand": None,
            "energy": None,
            "measure": None,
        },
        {
            "id": None,
            "type": None,
            "name": None,
            "brand": None,
            "energy": None,
            "measure": {"id": None, "name": None, "grams": None},
        },
    ]


def test_prints_a_table_of_foods(capsys: pytest.CaptureFixture[str]) -> None:
    out = run_text(["food", "search", "rye bread"], catalog(BREAD, STEW), capsys)

    assert out == (
        "id    type     name       brand   energy_kcal  measure\n"
        "501   product  Rye bread  Bakery  240.3        7 slice (32.5 g)\n"
        "9001  recipe   Stew       -       410.0        39 portion (350 g)\n"
    )


def test_prints_a_dash_for_missing_values_and_a_missing_measure(
    capsys: pytest.CaptureFixture[str],
) -> None:
    client = catalog({"foodId": 7}, {"foodId": 8, "measure": {}})

    assert run_text(["food", "search", "rye bread"], client, capsys) == (
        "id  type  name  brand  energy_kcal  measure\n"
        "7   -     -     -      -            -\n"
        "8   -     -     -      -            - - (- g)\n"
    )


@pytest.mark.parametrize("argv", [["rye bread"], []])
def test_no_results_prints_no_foods_found(
    argv: list[str], capsys: pytest.CaptureFixture[str]
) -> None:
    client = RoutedClient({LAST_USED: []} | catalog().routes)

    assert run_text(["food", "search", *argv], client, capsys) == "no foods found\n"
    assert run_json(["food", "search", *argv, "--json"], client, capsys) == []


def test_raw_prints_the_search_response_unchanged(
    capsys: pytest.CaptureFixture[str],
) -> None:
    assert run_json(
        ["food", "search", "rye bread", "--raw"], catalog(BREAD), capsys
    ) == [BREAD]


@pytest.mark.parametrize(
    "routes",
    [
        {USER: {}, CATALOG: [BREAD]},
        {USER: {"searchLocale": None}, CATALOG: [BREAD]},
        {USER: {"searchLocale": "xx_XX"}, CATALOG: {"items": [BREAD]}},
        {USER: {"searchLocale": "xx_XX"}, CATALOG: [BREAD, None]},
    ],
)
def test_unreadable_response_exits_1(
    routes: dict[str, Any], capsys: pytest.CaptureFixture[str]
) -> None:
    client: Any = RoutedClient(routes)

    assert main(["food", "search", "rye bread"], connect=lambda: client) == 1
    assert capsys.readouterr().err.startswith(
        "fitatu: Fitatu sent a response fitatu-cli could not read."
    )


def test_help_lists_food_and_search(capsys: pytest.CaptureFixture[str]) -> None:
    with pytest.raises(SystemExit):
        main(["--help"])
    help_text = " ".join(capsys.readouterr().out.split())
    assert "food find foods and their measures" in help_text

    with pytest.raises(SystemExit) as exit:
        main(["food", "--help"])

    assert exit.value.code == 0
    help_text = " ".join(capsys.readouterr().out.split())
    assert "usage: fitatu food [-h] {search}" in help_text
    assert (
        "search foods matching a phrase, or the foods you used last without one"
        in help_text
    )


def test_search_help_shows_the_phrase(capsys: pytest.CaptureFixture[str]) -> None:
    with pytest.raises(SystemExit) as exit:
        main(["food", "search", "--help"])

    assert exit.value.code == 0
    help_text = " ".join(capsys.readouterr().out.split())
    assert (
        "usage: fitatu food search [-h] [--locale LOCALE] [--raw] [--json] [phrase]"
        in help_text
    )
    assert "phrase what to search for (default: your last-used foods)" in help_text
    assert (
        "--locale LOCALE search the catalog in this locale instead of your account's: "
        f"{LOCALES}" in help_text
    )
    assert "--raw print the full service response" in help_text


@pytest.mark.parametrize(
    ("argv", "message"),
    [
        (
            ["food"],
            "No command given. Run 'fitatu food <command>', one of: search.",
        ),
        *(
            (
                ["food", "search", "rye", "--locale", locale],
                f"Invalid locale '{locale}'. Use one of: {LOCALES}.",
            )
            for locale in ("en-GB", "en", "EN_gb", "en_GBR", "xen_GB", "")
        ),
        (
            ["food", "search", "rye", "bread"],
            "Unexpected argument 'bread' for 'fitatu food search'. "
            "Run 'fitatu food search --help' for all options.",
        ),
    ],
)
def test_argument_error_exits_2(
    argv: list[str], message: str, capsys: pytest.CaptureFixture[str]
) -> None:
    with pytest.raises(SystemExit) as exit:
        main(argv, connect=FakeClient)

    assert exit.value.code == 2
    assert capsys.readouterr().err == f"fitatu: {message}\n"
