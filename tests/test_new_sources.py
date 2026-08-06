"""Crypto, short volume and forum sentiment.

The offline tests here guard the vintage contract for each source, because
that is what differs between them and is easy to get quietly wrong.
"""

import pytest

from vintage import envelope, registry
from vintage.sources import apewisdom, coinbase, finra


@pytest.mark.parametrize(
    "field,expected",
    [
        ("crypto:close", "crypto"),
        ("short:short_ratio", "finra"),
        ("ape:all-stocks", "apewisdom"),
    ],
)
def test_new_prefixes_route(field, expected):
    assert registry.route(field) == expected


def test_all_new_sources_are_keyless():
    for name in ("coinbase-exchange", "finra-short-volume", "apewisdom"):
        entry = next(s for s in registry.SOURCES if s["source"] == name)
        assert entry["key_required"] is False


# ------------------------------------------------------------------ coinbase


@pytest.mark.parametrize(
    "raw,expected",
    [("BTC", "BTC-USD"), ("btc-usd", "BTC-USD"), ("ETH/USD", "ETH-USD"), ("SOL-EUR", "SOL-EUR")],
)
def test_symbols_normalize_to_a_product_id(raw, expected):
    assert coinbase.normalize(raw) == expected


@pytest.mark.asyncio
async def test_unknown_crypto_field_names_the_valid_ones():
    with pytest.raises(coinbase.SourceError) as exc:
        await coinbase.candles("BTC-USD", field="vwap")
    assert "close" in str(exc.value)


@pytest.mark.asyncio
async def test_unknown_interval_is_rejected_before_any_request():
    with pytest.raises(coinbase.SourceError):
        await coinbase.candles("BTC-USD", interval="3y")


def test_crypto_survivorship_is_warned_about_not_hidden():
    joined = " ".join(coinbase.warnings_for("BTC-USD")).lower()
    assert "survivors-only" in joined
    assert "worse bias than equities" in joined or "worse" in joined


# --------------------------------------------------------------------- finra


def test_extract_pulls_the_right_symbol_from_a_daily_file():
    text = (
        "Date|Symbol|ShortVolume|ShortExemptVolume|TotalVolume|Market\n"
        "20260731|A|100.0|1.0|400.0|B,Q,N\n"
        "20260731|AAPL|250.0|2.0|1000.0|B,Q,N\n"
    )
    assert finra._extract(text, "AAPL") == (250.0, 2.0, 1000.0)


def test_extract_returns_none_for_a_symbol_that_did_not_trade():
    text = "Date|Symbol|ShortVolume|ShortExemptVolume|TotalVolume|Market\n20260731|A|1|0|2|B\n"
    assert finra._extract(text, "ZZZZ") is None


@pytest.mark.asyncio
async def test_unknown_short_field_is_rejected():
    with pytest.raises(finra.SourceError) as exc:
        await finra.short_volume("AAPL", field="short_interest")
    assert "short_ratio" in str(exc.value)


def test_short_volume_is_not_confused_with_short_interest():
    """The single most common misreading of this dataset."""
    joined = " ".join(finra.warnings_for([])).lower()
    assert "not short interest" in joined
    assert "flow" in joined


# ----------------------------------------------------------------- apewisdom


def test_every_filter_is_discoverable():
    fields = {c["field"] for c in apewisdom.catalog()}
    assert "ape:all-stocks" in fields
    assert "ape:all-crypto" in fields
    assert len(fields) == len(apewisdom.FILTERS)


@pytest.mark.asyncio
async def test_unknown_filter_lists_the_real_ones():
    with pytest.raises(apewisdom.SourceError) as exc:
        await apewisdom.mentions("r/superstonk")
    assert "all-stocks" in str(exc.value)


@pytest.mark.parametrize(
    "now,before,expected",
    [(150, 100, 0.5), (50, 100, -0.5), (100, 0, None), (None, 100, None), (100, None, None)],
)
def test_mention_change_handles_the_degenerate_cases(now, before, expected):
    assert apewisdom._delta(now, before) == expected


def test_sentiment_warns_that_history_starts_when_you_record_it():
    """The honest limitation, and the reason this source is worth having."""
    joined = " ".join(apewisdom.warnings_for([])).lower()
    assert "no history endpoint" in joined
    assert "re-scoring old posts" in joined


def test_sentiment_is_not_dressed_up_as_a_filing():
    assert "not a filing" in " ".join(apewisdom.warnings_for([])).lower()


@pytest.mark.network
@pytest.mark.asyncio
async def test_sentiment_rows_are_stamped_with_the_fetch_time():
    """known_at must be when we looked, since upstream asserts no date."""
    rows = await apewisdom.mentions("all-stocks", limit=5)
    assert rows
    for r in rows:
        assert r["vintage"] == "observed-at-fetch"
        assert r["known_at"] and "T" in r["known_at"]


@pytest.mark.network
@pytest.mark.asyncio
async def test_crypto_bars_are_knowable_when_the_bar_closes():
    rows = await coinbase.candles("BTC-USD", limit=5)
    assert rows
    for r in rows:
        assert r["vintage"] == envelope.AS_FILED
        assert r["known_at"] > r["observed_at"]
