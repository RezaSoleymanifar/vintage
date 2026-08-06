"""The library surface.

What matters here is not that pandas works, but that the two-date contract
survives the trip into a DataFrame. A frame that quietly drops `known_at` is
indistinguishable from any other price library.
"""

import asyncio

import pandas as pd
import pytest

import vintage as v
from vintage import envelope
from vintage.sdk import _run, frame


def rows(**over):
    base = dict(
        entity="AAPL", field="price:adjclose", observed_at="2020-01-02",
        known_at="2020-01-02", value=75.0,
        source="yahoo-finance", source_url="https://example.invalid",
    )
    base.update(over)
    return envelope.row(**base)


# ------------------------------------------------------------------ plumbing


def test_run_works_without_a_loop():
    async def answer():
        return 42
    assert _run(answer()) == 42


def test_run_works_inside_a_running_loop():
    """Every notebook has a live loop, where asyncio.run raises."""
    async def outer():
        async def answer():
            return 7
        return _run(answer())
    assert asyncio.run(outer()) == 7


# --------------------------------------------------------------------- frame


def test_frame_indexes_on_observed_at():
    df = frame([rows(observed_at="2020-01-03"), rows(observed_at="2020-01-02")])
    assert df.index.name == "observed_at"
    assert list(df.index) == sorted(df.index)


def test_frame_keeps_known_at_as_a_column():
    """Dropping it for tidiness would turn this into an ordinary price library."""
    df = frame([rows()])
    assert "known_at" in df.columns
    assert pd.api.types.is_datetime64_any_dtype(df["known_at"])


def test_frame_renames_value_when_asked():
    assert "adjclose" in frame([rows()], value="adjclose").columns


def test_frame_of_nothing_is_empty_not_an_error():
    assert frame([]).empty


def test_frame_survives_an_unparseable_date():
    df = frame([rows(known_at="not-a-date")])
    assert df["known_at"].isna().all()


# ------------------------------------------------------------------ contract


def test_public_api_is_exported():
    for name in ("prices", "panel", "claim", "factors", "backtest", "trials"):
        assert hasattr(v, name), name
    assert set(v.__all__) - {"__version__"} <= set(dir(v))


def test_returns_drops_the_leading_nan():
    px = pd.DataFrame({"A": [10.0, 11.0, 12.0]},
                      index=pd.date_range("2020-01-01", periods=3))
    out = v.returns(px)
    assert len(out) == 2
    assert out["A"].iloc[0] == pytest.approx(0.1)


def test_signals_and_sources_are_listable_offline():
    assert not v.signals().empty
    assert v.sources().shape[0] >= 9


def test_trials_starts_at_zero_in_a_fresh_session():
    assert isinstance(v.trials(), int)


# ------------------------------------------------------------------- network


@pytest.mark.network
def test_prices_carry_both_dates():
    df = v.prices("AAPL", start="2024-01-01")
    assert not df.empty
    assert {"adjclose", "known_at"} <= set(df.columns)
    assert df.index.name == "observed_at"


@pytest.mark.network
def test_as_of_hides_the_future():
    """The whole product, in one assertion."""
    df = v.fundamentals("AAPL", "us-gaap:Assets", form="10-K", as_of="2020-01-01")
    assert not df.empty
    assert df["known_at"].max() < pd.Timestamp("2020-01-01")


@pytest.mark.network
def test_panel_is_dates_by_tickers():
    px = v.panel(["AAPL", "MSFT"], start="2024-01-01")
    assert set(px.columns) == {"AAPL", "MSFT"}
    assert px.index.is_monotonic_increasing


@pytest.mark.network
def test_claim_returns_the_published_number():
    c = v.claim("Mom12m")
    assert c["value"] == pytest.approx(1.31, abs=0.01)
    assert "Jegadeesh" in c["authors"]


@pytest.mark.network
def test_factors_come_back_wide():
    ff3 = v.factors("ff3", start="2020-01-01")
    assert {"Mkt-RF", "SMB", "HML", "RF"} <= set(ff3.columns)
