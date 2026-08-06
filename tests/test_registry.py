"""Routing and discovery — the part that keeps six verbs from becoming twenty."""

import pytest

from vintage import registry


@pytest.mark.parametrize(
    "field,expected",
    [
        ("us-gaap:Assets", "sec-edgar-xbrl"),
        ("dei:EntityCommonStockSharesOutstanding", "sec-edgar-xbrl"),
        ("price:adjclose", "prices"),
        ("fred:CPIAUCSL", "fred"),
        ("french:ff3", "french"),
        ("filing:8-K", "sec-edgar-filings"),
    ],
)
def test_prefixes_route_to_their_source(field, expected):
    assert registry.route(field) == expected


def test_bare_field_defaults_to_xbrl():
    assert registry.route("Assets") == "sec-edgar-xbrl"


def test_unknown_prefix_routes_nowhere_rather_than_guessing():
    assert registry.route("bloomberg:PX_LAST") is None


def test_every_declared_source_is_self_describing():
    for source in registry.SOURCES:
        assert {"source", "covers", "field_form", "point_in_time"} <= set(source)
        assert isinstance(source["key_required"], bool)


def test_search_ranks_by_how_many_terms_matched():
    hits = registry.search_static("10 year treasury yield")
    assert hits
    assert hits[0]["field"] == "fred:DGS10"


def test_search_respects_its_limit():
    assert len(registry.search_static("rate", limit=2)) <= 2


def test_search_returns_nothing_for_a_miss_rather_than_everything():
    assert registry.search_static("zzzznotarealseries") == []


def test_static_catalog_marks_fred_entries_as_key_gated():
    fred_items = [i for i in registry.static_catalog() if i.get("source") == "fred"]
    assert fred_items
    assert all("key_required" in i for i in fred_items)
