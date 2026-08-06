"""Frames, Treasury and CFTC.

Each has one convention that produces a plausible wrong answer if missed: the
instant-versus-duration period key, the tenor naming, and the reporting lag
that makes positioning safe to trade on.
"""

import pytest

from vintage import envelope, registry
from vintage.sources import cftc, frames, treasury


@pytest.mark.parametrize("field,expected", [
    ("frame:us-gaap/Assets/CY2023Q1I", "frames"),
    ("ust:10y", "treasury"),
    ("cot:noncommercial_net", "cftc"),
])
def test_prefixes_route(field, expected):
    assert registry.route(field) == expected


# -------------------------------------------------------------------- frames


@pytest.mark.parametrize("year,quarter,instant,expected", [
    (2023, None, False, "CY2023"),
    (2023, 1, False, "CY2023Q1"),
    (2023, 1, True, "CY2023Q1I"),
])
def test_period_keys_build(year, quarter, instant, expected):
    assert frames.period_for(year, quarter, instant=instant) == expected


@pytest.mark.parametrize("tag,instant", [
    ("Assets", True), ("StockholdersEquity", True), ("CashAndCashEquivalents", True),
    ("Revenues", False), ("NetIncomeLoss", False),
])
def test_instant_is_guessed_from_the_concept(tag, instant):
    """A duration key on a balance-sheet tag returns an empty frame, not an
    error, which is a confusing way to learn the convention."""
    assert frames.guess_instant(tag) is instant


@pytest.mark.asyncio
async def test_a_malformed_period_says_what_one_looks_like():
    with pytest.raises(frames.SourceError) as exc:
        await frames.cross_section("Assets", "2023Q1")
    assert "CY2023Q1I" in str(exc.value)


def test_frames_admit_they_carry_no_filing_date():
    note = frames.warnings_for("CY2023Q1I", [{}] * 10)
    assert "no known_at" in note[0]
    assert "restated" in note[0]


# ------------------------------------------------------------------ treasury


def test_every_tenor_is_catalogued():
    fields = {c["field"] for c in treasury.catalog()}
    assert {"ust:1m", "ust:2y", "ust:10y", "ust:30y"} <= fields


@pytest.mark.parametrize("raw,expected", [
    ("08/05/2026", "2026-08-05"), ("2026-08-05", "2026-08-05"), ("", None),
])
def test_treasury_dates_parse(raw, expected):
    assert treasury._iso(raw) == expected


@pytest.mark.asyncio
async def test_unknown_tenor_lists_the_real_ones():
    with pytest.raises(treasury.SourceError) as exc:
        await treasury.yields("15y")
    assert "10y" in str(exc.value)


# ---------------------------------------------------------------------- cftc


def test_market_shortcuts_cover_the_usual_contracts():
    assert {"SP500", "GOLD", "CRUDE", "EUR"} <= set(cftc.MARKETS)


@pytest.mark.asyncio
async def test_unknown_measure_lists_the_real_ones():
    with pytest.raises(cftc.SourceError) as exc:
        await cftc.positioning("SP500", measure="retail_net")
    assert "noncommercial_net" in str(exc.value)


def test_the_reporting_lag_is_stated():
    """Acting on Tuesday's positioning on Tuesday is the mistake this invites."""
    note = cftc.warnings_for()
    assert "Tuesday" in note[0] and "Friday" in note[0]


@pytest.mark.network
@pytest.mark.asyncio
async def test_positioning_is_knowable_after_it_is_observed():
    rows = await cftc.positioning("GOLD", limit=8)
    assert rows
    assert all(r["known_at"] > r["observed_at"] for r in rows)
    assert all(r["vintage"] == envelope.AS_FILED for r in rows)


@pytest.mark.network
@pytest.mark.asyncio
async def test_a_market_with_an_ampersand_still_queries():
    """E-MINI S&P 500 truncated the Socrata query and returned a 400."""
    assert await cftc.positioning("SP500", limit=4)


@pytest.mark.network
@pytest.mark.asyncio
async def test_one_frame_call_returns_the_whole_cross_section():
    rows = await frames.cross_section("Assets", "CY2023Q1I")
    assert len(rows) > 5000
    assert all(r["vintage"] == envelope.UNKNOWN_VINTAGE for r in rows)
    assert all(r["known_at"] is None for r in rows)
