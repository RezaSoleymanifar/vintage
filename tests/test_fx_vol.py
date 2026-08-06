"""Foreign exchange and volatility indices.

Both are unusually clean on vintage — published once and never revised — so
what needs guarding is the conventions: which way a pair is quoted, and that a
cross rate is labelled as derived rather than passed off as a traded quote.
"""

import pytest

from vintage import envelope, registry
from vintage.sources import cboe, ecb


# ------------------------------------------------------------------- routing


@pytest.mark.parametrize("field,expected", [
    ("fx:EURUSD", "ecb"),
    ("vol:VIX", "cboe"),
    ("price:close", "prices"),
])
def test_prefixes_route(field, expected):
    assert registry.route(field) == expected


def test_both_sources_are_keyless():
    for name in ("ecb-reference-rates", "cboe-indices"):
        entry = next(s for s in registry.SOURCES if s["source"] == name)
        assert entry["key_required"] is False


def test_indices_are_discoverable_by_name():
    """Nobody guesses the caret tickers unprompted."""
    hits = registry.search_static("nikkei")
    assert any(h.get("entity") == "^N225" for h in hits)
    assert any(h.get("entity") == "^GSPC" for h in registry.search_static("s&p 500"))


# ------------------------------------------------------------------------ fx


@pytest.mark.parametrize("raw,expected", [
    ("EURUSD", ("EUR", "USD")),
    ("usdjpy", ("USD", "JPY")),
    ("USD/JPY", ("USD", "JPY")),
    ("gbp-chf", ("GBP", "CHF")),
    ("USD", ("EUR", "USD")),          # a bare code is quoted against the euro
])
def test_pairs_parse(raw, expected):
    assert ecb.parse_pair(raw) == expected


def test_a_nonsense_pair_says_what_a_pair_looks_like():
    with pytest.raises(ecb.SourceError) as exc:
        ecb.parse_pair("DOLLARS")
    assert "EURUSD" in str(exc.value)


def test_cross_rates_are_declared_as_derived():
    """Arithmetic on two reference rates is not a broker's fix, and saying so
    is the difference between a data source and a trap."""
    note = ecb.warnings_for("USDJPY")
    assert note and "cross rate" in note[0]
    assert "will not match a broker" in note[0]


def test_euro_pairs_need_no_such_warning():
    assert ecb.warnings_for("EURUSD") == []
    assert ecb.warnings_for("JPY") == []


def test_fx_catalog_covers_the_majors():
    fields = {c["field"] for c in ecb.catalog()}
    assert {"fx:EURUSD", "fx:EURJPY", "fx:EURGBP"} <= fields


# ------------------------------------------------------------------ vix family


@pytest.mark.parametrize("raw,expected", [
    ("01/02/1990", "1990-01-02"),
    ("12/31/2025", "2025-12-31"),
    ("2020-03-16", "2020-03-16"),
    ("", None),
    ("garbage", None),
])
def test_cboe_dates_parse(raw, expected):
    assert cboe._iso(raw) == expected


@pytest.mark.asyncio
async def test_unknown_index_lists_the_real_ones():
    with pytest.raises(cboe.SourceError) as exc:
        await cboe.levels("VIXX")
    assert "VIX3M" in str(exc.value)


def test_catalog_covers_the_term_structure_and_skew():
    fields = {c["field"] for c in cboe.catalog()}
    assert {"vol:VIX", "vol:VIX9D", "vol:VIX3M", "vol:VVIX", "vol:SKEW"} <= fields


def test_index_levels_are_not_sold_as_option_chains():
    """The single most likely misreading of this source."""
    note = cboe.warnings_for("VIX")
    assert "not an option chain" in note[0]
    assert "paid at every vendor" in note[0]


# ------------------------------------------------------------------- network


@pytest.mark.network
@pytest.mark.asyncio
async def test_ecb_rates_are_as_filed():
    rows = await ecb.rates("EURUSD", start="2024-01-01")
    assert rows
    assert all(r["vintage"] == envelope.AS_FILED for r in rows)
    assert all(r["known_at"] == r["observed_at"] for r in rows)


@pytest.mark.network
@pytest.mark.asyncio
async def test_a_cross_rate_is_the_ratio_of_its_legs():
    usdjpy = {r["observed_at"]: r["value"] for r in
              await ecb.rates("USDJPY", start="2024-06-01", end="2024-06-30")}
    eurusd = {r["observed_at"]: r["value"] for r in
              await ecb.rates("EURUSD", start="2024-06-01", end="2024-06-30")}
    eurjpy = {r["observed_at"]: r["value"] for r in
              await ecb.rates("EURJPY", start="2024-06-01", end="2024-06-30")}
    day = sorted(set(usdjpy) & set(eurusd) & set(eurjpy))[0]
    assert usdjpy[day] == pytest.approx(eurjpy[day] / eurusd[day], rel=1e-6)


@pytest.mark.network
@pytest.mark.asyncio
async def test_vix_reaches_back_to_1990():
    rows = await cboe.levels("VIX")
    assert rows[0]["observed_at"] == "1990-01-02"
    assert len(rows) > 9000


@pytest.mark.network
@pytest.mark.asyncio
async def test_single_column_files_are_handled():
    """VVIX and SKEW carry one column named after the index, not OHLC."""
    rows = await cboe.levels("SKEW", start="2020-01-01")
    assert rows and all(r["value"] > 0 for r in rows)
