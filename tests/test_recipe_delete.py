import pytest
from conftest import FakeClient, http_error, run_json, run_text

from fitatu_cli.cli import main

RECIPE = {"name": "Stew", "serving": 2, "deleted": False}
FORBIDDEN = (
    "Fitatu did not delete recipe 77 (HTTP {code}). "
    "You can delete only your own recipes; run 'fitatu recipe list' to see them.\n"
)


def test_recipe_delete_deletes_the_recipe_and_names_it(
    capsys: pytest.CaptureFixture[str],
) -> None:
    client = FakeClient(get=RECIPE, delete=None)

    out = run_text(["recipe", "delete", "77"], client, capsys)

    assert out == "deleted recipe 77: Stew\n"
    assert client.calls == [
        ("get", ("/api/recipes/77",), {}),
        ("delete", ("/api/recipes/77",), {}),
    ]


def test_recipe_delete_json(capsys: pytest.CaptureFixture[str]) -> None:
    out = run_json(
        ["recipe", "delete", "77", "--json"],
        FakeClient(get=RECIPE, delete=None),
        capsys,
    )

    assert out == {"id": 77, "name": "Stew"}


def test_recipe_delete_of_a_recipe_without_a_name_prints_a_dash(
    capsys: pytest.CaptureFixture[str],
) -> None:
    out = run_text(
        ["recipe", "delete", "77"], FakeClient(get={"serving": 2}, delete=None), capsys
    )

    assert out == "deleted recipe 77: -\n"


def test_recipe_delete_of_an_unknown_id_exits_1(
    capsys: pytest.CaptureFixture[str],
) -> None:
    client = FakeClient(get=http_error(404), delete=None)

    assert main(["recipe", "delete", "77"], connect=lambda: client) == 1
    assert capsys.readouterr().err == (
        "fitatu: Fitatu has no recipe with ID 77. "
        "Run 'fitatu recipe list' to see your recipes' IDs.\n"
    )
    assert [name for name, _, _ in client.calls] == ["get"]


def test_recipe_delete_of_a_deleted_recipe_exits_1(
    capsys: pytest.CaptureFixture[str],
) -> None:
    client = FakeClient(get=RECIPE | {"deleted": True}, delete=None)

    assert main(["recipe", "delete", "77"], connect=lambda: client) == 1
    assert capsys.readouterr().err == (
        "fitatu: Recipe 77 is already deleted. "
        "Run 'fitatu recipe list' to see your recipes' IDs.\n"
    )
    assert [name for name, _, _ in client.calls] == ["get"]


@pytest.mark.parametrize("code", [403, 404])
def test_recipe_delete_refused_by_fitatu_exits_1(
    code: int, capsys: pytest.CaptureFixture[str]
) -> None:
    client = FakeClient(get=RECIPE, delete=http_error(code))

    assert main(["recipe", "delete", "77"], connect=lambda: client) == 1
    assert capsys.readouterr().err == "fitatu: " + FORBIDDEN.format(code=code)


def test_recipe_delete_of_a_recipe_fitatu_hides_exits_1(
    capsys: pytest.CaptureFixture[str],
) -> None:
    client = FakeClient(get=http_error(403), delete=None)

    assert main(["recipe", "delete", "77"], connect=lambda: client) == 1
    assert capsys.readouterr().err == "fitatu: " + FORBIDDEN.format(code=403)
    assert [name for name, _, _ in client.calls] == ["get"]


def test_recipe_delete_reports_a_server_error_as_unexpected(
    capsys: pytest.CaptureFixture[str],
) -> None:
    client = FakeClient(get=RECIPE, delete=http_error(500))

    assert main(["recipe", "delete", "77"], connect=lambda: client) == 1
    assert capsys.readouterr().err.startswith(
        "fitatu: Unexpected error (HTTPError: HTTP Error 500: error)."
    )


def test_recipe_delete_rejects_an_id_that_is_not_a_number(
    capsys: pytest.CaptureFixture[str],
) -> None:
    with pytest.raises(SystemExit) as exit:
        main(["recipe", "delete", "stew"], connect=FakeClient)

    assert exit.value.code == 2
    assert capsys.readouterr().err == (
        "fitatu: Invalid recipe ID 'stew'. Give the number from 'fitatu recipe list'.\n"
    )


def test_recipe_delete_help_shows_its_arguments(
    capsys: pytest.CaptureFixture[str],
) -> None:
    with pytest.raises(SystemExit) as exit:
        main(["recipe", "delete", "--help"])

    assert exit.value.code == 0
    help_text = " ".join(capsys.readouterr().out.split())
    assert help_text.startswith(
        "usage: fitatu recipe delete [-h] [--json] ID "
        "Delete one of your recipes. There is no confirmation prompt. "
        "positional arguments: ID the recipe's ID options:"
    )


def test_recipe_delete_rejects_a_second_id(capsys: pytest.CaptureFixture[str]) -> None:
    with pytest.raises(SystemExit) as exit:
        main(["recipe", "delete", "77", "78"], connect=FakeClient)

    assert exit.value.code == 2
    assert capsys.readouterr().err == (
        "fitatu: Unexpected argument '78' for 'fitatu recipe delete'. "
        "Run 'fitatu recipe delete --help' for all options.\n"
    )
