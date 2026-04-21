from __future__ import annotations

import pytest
from figma_pat import urls


@pytest.mark.parametrize(
    "url,expected",
    [
        (
            "https://www.figma.com/design/AbCdEf123/Checkout-Mocks?node-id=12-56",
            {"kind": "node", "file_key": "AbCdEf123", "node_id": "12:56", "slug": "Checkout-Mocks"},
        ),
        (
            "https://figma.com/design/AbCdEf123/Checkout",
            {"kind": "file", "file_key": "AbCdEf123", "slug": "Checkout"},
        ),
        (
            "https://www.figma.com/file/XYZ789/Legacy",
            {"kind": "file", "file_key": "XYZ789", "slug": "Legacy"},
        ),
        (
            "https://www.figma.com/proto/abc/Proto?node-id=1-2",
            {"kind": "node", "file_key": "abc", "node_id": "1:2", "slug": "Proto"},
        ),
        (
            "https://www.figma.com/board/jam1/FigJam",
            {"kind": "file", "file_key": "jam1", "slug": "FigJam"},
        ),
        (
            "https://www.figma.com/files/team/1234567890/ACME",
            {"kind": "team", "team_id": "1234567890", "slug": "ACME"},
        ),
        (
            "https://www.figma.com/files/project/9876543/Web",
            {"kind": "project", "project_id": "9876543", "slug": "Web"},
        ),
        (
            "https://example.com/",
            {"kind": "unknown"},
        ),
    ],
)
def test_parse(url: str, expected: dict) -> None:
    parsed = urls.parse(url)
    for key, value in expected.items():
        assert getattr(parsed, key) == value, f"{key}: {getattr(parsed, key)!r} != {value!r}"


def test_node_id_conversion() -> None:
    assert urls.node_id_to_api_form("12-34") == "12:34"
    assert urls.node_id_to_api_form("12:34") == "12:34"
    assert urls.node_id_to_url_form("12:34") == "12-34"
    assert urls.node_id_filesystem_safe("12:34") == "12-34"


def test_deeplink() -> None:
    assert (
        urls.deeplink("AbCdEf123", "12:56", slug="Checkout")
        == "https://www.figma.com/design/AbCdEf123/Checkout?node-id=12-56"
    )
    assert urls.deeplink("AbCdEf123") == "https://www.figma.com/design/AbCdEf123"


def test_empty_and_bare_input() -> None:
    assert urls.parse("").kind == "unknown"
    # Accept bare 'figma.com/...' without scheme.
    parsed = urls.parse("figma.com/design/AbCdEf123/Checkout?node-id=12-56")
    assert parsed.kind == "node"
    assert parsed.file_key == "AbCdEf123"
    assert parsed.node_id == "12:56"
