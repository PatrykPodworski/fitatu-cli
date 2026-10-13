import pytest
from conftest import FakeClient, http_error, run_json, run_text

from fitatu_cli.cli import main

PRODUCT = {"name": "Bean stew", "private": True, "deleted": False}
LIST = "Run 'fitatu product list' to see your products' IDs.\n"
YOURS = (
    "You can delete only your own products; run 'fitatu product list' to see them.\n"
)


def test_product_delete_deletes_the_product_and_names_it(
    capsys: pytest.CaptureFixture[str],
) -> None:
    client = FakeClient(get=PRODUCT, delete=None)

    out = run_text(["product", "delete", "501"], client, capsys)

    assert out == "deleted product 501: Bean stew\n"
    assert client.calls == [
        ("get", ("/api/products/501",), {}),
        ("delete", ("/api/products/501",), {}),
    ]


def test_product_delete_json(capsys: pytest.CaptureFixture[str]) -> None:
    out = run_json(
        ["product", "delete", "501", "--json"],
        FakeClient(get=PRODUCT, delete=None),
        capsys,
    )

    assert out == {"id": 501, "name": "Bean stew"}


def test_product_delete_of_a_product_without_a_name_prints_a_dash(
    capsys: pytest.CaptureFixture[str],
) -> None:
    out = run_text(
        ["product", "delete", "501"],
        FakeClient(get={"private": True}, delete=None),
        capsys,
    )

    assert out == "deleted product 501: -\n"


def test_product_delete_of_an_unknown_id_exits_1(
    capsys: pytest.CaptureFixture[str],
) -> None:
    client = FakeClient(get=http_error(404), delete=None)

    assert main(["product", "delete", "501"], connect=lambda: client) == 1
    assert (
        capsys.readouterr().err == "fitatu: Fitatu has no product with ID 501. " + LIST
    )
    assert [name for name, _, _ in client.calls] == ["get"]


def test_product_delete_of_a_deleted_product_exits_1(
    capsys: pytest.CaptureFixture[str],
) -> None:
    client = FakeClient(get=PRODUCT | {"deleted": True}, delete=None)

    assert main(["product", "delete", "501"], connect=lambda: client) == 1
    assert capsys.readouterr().err == "fitatu: Product 501 is already deleted. " + LIST
    assert [name for name, _, _ in client.calls] == ["get"]


@pytest.mark.parametrize("private", [{"private": False}, {"private": None}, {}])
def test_product_delete_of_a_catalog_product_exits_1_without_a_delete(
    private: dict[str, bool | None], capsys: pytest.CaptureFixture[str]
) -> None:
    client = FakeClient(get={"name": "Bean stew", **private}, delete=None)

    assert main(["product", "delete", "501"], connect=lambda: client) == 1
    assert (
        capsys.readouterr().err == "fitatu: Product 501 is not one of yours. " + YOURS
    )
    assert [name for name, _, _ in client.calls] == ["get"]


@pytest.mark.parametrize("code", [403, 404])
def test_product_delete_refused_by_fitatu_exits_1(
    code: int, capsys: pytest.CaptureFixture[str]
) -> None:
    client = FakeClient(get=PRODUCT, delete=http_error(code))

    assert main(["product", "delete", "501"], connect=lambda: client) == 1
    assert capsys.readouterr().err == (
        f"fitatu: Fitatu did not delete product 501 (HTTP {code}). " + YOURS
    )


def test_product_delete_reports_a_server_error_as_unexpected(
    capsys: pytest.CaptureFixture[str],
) -> None:
    client = FakeClient(get=PRODUCT, delete=http_error(500))

    assert main(["product", "delete", "501"], connect=lambda: client) == 1
    assert capsys.readouterr().err.startswith(
        "fitatu: Unexpected error (HTTPError: HTTP Error 500: error)."
    )


def test_product_delete_help_shows_its_arguments(
    capsys: pytest.CaptureFixture[str],
) -> None:
    with pytest.raises(SystemExit) as exit:
        main(["product", "delete", "--help"])

    assert exit.value.code == 0
    help_text = " ".join(capsys.readouterr().out.split())
    assert help_text.startswith(
        "usage: fitatu product delete [-h] [--json] ID "
        "Delete one of your products. There is no confirmation prompt. "
        "positional arguments: ID the product's ID options:"
    )


def test_product_delete_rejects_a_second_id(capsys: pytest.CaptureFixture[str]) -> None:
    with pytest.raises(SystemExit) as exit:
        main(["product", "delete", "501", "502"], connect=FakeClient)

    assert exit.value.code == 2
    assert capsys.readouterr().err == (
        "fitatu: Unexpected argument '502' for 'fitatu product delete'. "
        "Run 'fitatu product delete --help' for all options.\n"
    )
