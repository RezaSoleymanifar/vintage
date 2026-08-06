"""The sector label exists so a cross-sectional transform can group on it.

What matters is not the code itself but that it never pretends to be dated:
EDGAR states the current classification and nothing else, so a row that
claimed an honest `known_at` would be the exact failure this project is for.
"""

from __future__ import annotations

import pytest

from vintage import envelope, registry
from vintage.sources import sector


def test_prefix_routes_to_the_sector_adapter():
    assert registry.route("sector:sic") == "sector"
    assert registry.ADAPTER_SOURCE["sector"] == "sec-edgar-sic"
    assert "sector" in registry.FETCH_ADAPTERS


def test_the_source_is_declared_as_not_point_in_time():
    row = next(s for s in registry.SOURCES if s["source"] == "sec-edgar-sic")
    assert row["point_in_time"].startswith("no")
    assert row["key_required"] is False


@pytest.mark.parametrize("code,expected", [
    (3571, "manufacturing"),
    ("6021", "finance, insurance and real estate"),
    (1311, "mining"),
    (7372, "services"),
    (5812, "retail trade"),
])
def test_division_buckets_a_code(code, expected):
    assert sector.division(code) == expected


@pytest.mark.parametrize("bad", [None, "", "not a code", 99999])
def test_division_refuses_to_guess(bad):
    assert sector.division(bad) is None


def test_unknown_field_is_rejected_with_the_alternatives(anyio_backend=None):
    with pytest.raises(ValueError) as exc:
        import asyncio
        asyncio.run(sector.classification("AAPL", "sector:gics"))
    assert "sector:sic" in str(exc.value)


def test_every_field_is_declared():
    for field in sector.FIELDS:
        assert field.startswith("sector:")
    assert registry.PREFIX_SPECS["sector:"]["example_field"] in sector.FIELDS


def test_a_row_carries_no_invented_date():
    """The shape the adapter builds, without going near the network."""
    row = envelope.row(
        entity="CIK0000320193",
        field="sector:sic",
        observed_at=None,
        known_at=None,
        value="3571",
        unit="SIC code",
        source=sector.SOURCE,
        source_url="https://www.sec.gov/cgi-bin/browse-edgar",
        vintage=envelope.UNKNOWN_VINTAGE,
    )
    assert row["vintage"] == envelope.UNKNOWN_VINTAGE
    assert row["known_at"] is None
    assert row["observed_at"] is None
