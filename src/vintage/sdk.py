"""The Python API. Same data as the MCP server, shaped for a notebook.

    import vintage as v

    px    = v.prices("AAPL")                       # one series
    panel = v.panel(["AAPL", "MSFT"], start="2010-01-01")
    facts = v.fundamentals("AAPL", "us-gaap:Assets", as_of="2020-01-01")
    ff3   = v.factors("ff3")
    claim = v.claim("Mom12m")

Three decisions worth knowing about.

**Synchronous.** The sources are async because the server needs them to be, but
nobody wants `await` in a research notebook. Every function here blocks, and it
works inside Jupyter, where a loop is already running and `asyncio.run` would
raise.

**DataFrames.** Rows come back as pandas frames indexed by `observed_at`, with
`known_at` kept as a column rather than dropped. Losing that column is how a
point-in-time dataset quietly turns into an ordinary one.

**`as_of` everywhere.** Pass it and rows published after that date are removed
before you see them. That is the same filter the server applies, not a
reimplementation of it.
"""

from __future__ import annotations

import asyncio
import concurrent.futures
from typing import Any, Awaitable, Iterable, TypeVar

import pandas as pd

from . import envelope, registry
from .engine import backtest as _bt
from .engine import honesty as _honesty
from .engine import validation as _validation
from .sources import (apewisdom, cboe, cftc, coinbase,
                      delistings as _delistings, ecb, edgar, finra,
                      frames as _frames, fred, french, openap,
                      sector as _sector,
                      treasury as _treasury, yahoo)

T = TypeVar("T")

__all__ = [
    "prices", "panel", "returns", "fundamentals", "filings", "factors", "macro",
    "claim", "claims", "crypto", "short_volume", "sentiment",
    "resolve", "search", "sources", "signals", "backtest", "trials", "frame",
    "delistings", "survivorship_warning", "fx", "volatility", "index",
    "sectors", "splits", "overfitting_probability",
    "cross_section", "treasury_yields", "positioning",
    "corporate_actions",
]


# --------------------------------------------------------------------- plumbing


def _run(coro: Awaitable[T]) -> T:
    """Block on a coroutine, including inside a live Jupyter loop.

    `asyncio.run` raises when a loop is already running, which is every notebook.
    Handing the coroutine to a worker thread with its own loop is the boring fix
    and avoids asking users to install nest_asyncio.
    """
    try:
        asyncio.get_running_loop()
    except RuntimeError:
        return asyncio.run(coro)

    with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
        return pool.submit(asyncio.run, coro).result()


def frame(rows: list[dict[str, Any]], *, value: str | None = None) -> pd.DataFrame:
    """Envelope rows to a DataFrame indexed by `observed_at`.

    `known_at` survives as a column. It is the only thing separating this from
    any other price library, so it is never dropped for tidiness.
    """
    if not rows:
        return pd.DataFrame()
    df = pd.DataFrame(rows)
    for col in ("observed_at", "known_at"):
        if col in df:
            df[col] = pd.to_datetime(df[col], errors="coerce", utc=True).dt.tz_localize(None)
    if "observed_at" in df:
        df = df.sort_values("observed_at").set_index("observed_at")
    if value:
        df = df.rename(columns={"value": value})
    return df


def _asof(rows: list[dict[str, Any]], as_of: str | None) -> list[dict[str, Any]]:
    return envelope.visible_at(rows, as_of) if as_of else rows


def _window(df: pd.DataFrame, start: str | None, end: str | None) -> pd.DataFrame:
    if df.empty:
        return df
    if start:
        df = df[df.index >= pd.Timestamp(start)]
    if end:
        df = df[df.index <= pd.Timestamp(end)]
    return df


# ------------------------------------------------------------------------ prices


def prices(ticker: str, *, field: str = "adjclose", start: str | None = None,
           end: str | None = None, as_of: str | None = None,
           point_in_time: bool = False) -> pd.DataFrame:
    """Daily prices for one ticker.

    With `point_in_time=True` the adjusted series is rebuilt from the raw close
    using only the splits and dividends that had happened by `as_of`, so the
    level is what a screen showed that day. Without it, `adjclose` is today's
    adjusted series and `as_of` only trims the tail.
    """
    if point_in_time:
        rows = _run(yahoo.pit_prices(ticker, as_of=as_of))
        return _window(frame(rows, value="pit_adjclose"), start, end)
    rows = _asof(_run(yahoo.prices(ticker, field=field)), as_of)
    return _window(frame(rows, value=field), start, end)


def corporate_actions(ticker: str) -> pd.DataFrame:
    """Every split and dividend, dated. The raw material for point-in-time."""
    return pd.DataFrame(_run(yahoo.corporate_actions(ticker)))


def panel(tickers: Iterable[str], *, field: str = "adjclose", start: str | None = None,
          end: str | None = None, as_of: str | None = None,
          point_in_time: bool = False, progress: bool = False) -> pd.DataFrame:
    """A dates-by-tickers frame, the shape a cross-sectional backtest wants."""
    series, missing = {}, []
    tickers = list(tickers)
    for i, t in enumerate(tickers, 1):
        try:
            df = prices(t, field=field, as_of=as_of, point_in_time=point_in_time)
        except Exception:
            missing.append(t)
            continue
        if not df.empty:
            series[t] = df["pit_adjclose" if point_in_time else field]
        else:
            missing.append(t)
        if progress and i % 20 == 0:
            print(f"  {i}/{len(tickers)}")
    if progress and missing:
        print(f"  unavailable: {', '.join(missing[:10])}"
              + (" ..." if len(missing) > 10 else ""))
    return _window(pd.DataFrame(series).sort_index(), start, end)


def returns(prices_frame: pd.DataFrame, *, periods: int = 1) -> pd.DataFrame:
    """Simple returns. Here so a notebook does not reinvent it in cell three."""
    return prices_frame.pct_change(periods).dropna(how="all")


def cross_section(tag: str, period: str, *, taxonomy: str = "us-gaap",
                  unit: str = "USD", limit: int = 10_000) -> pd.DataFrame:
    """One accounting concept for every filer in a period.

    The shape a cross-sectional sort needs, in one request rather than 6,000.
    Balance-sheet concepts need the instant period form, CY2023Q1I.
    """
    return frame(_run(_frames.cross_section(tag, period, taxonomy=taxonomy,
                                            unit=unit, limit=limit)))



def sectors(entities: Iterable[str]) -> pd.DataFrame:
    """The industry label per name, for neutralizing a cross-section.

    One row per entity with its SIC code, the SEC's description of it, and the
    coarser division most neutralizations actually group on. Names that cannot
    be resolved come back with a null rather than being dropped, so a missing
    label is visible instead of quietly shrinking the universe.

    EDGAR publishes the current classification with no history, so every row is
    UNKNOWN_VINTAGE. Group today's cross-section with it; do not backdate it.
    """
    rows = _run(_sector.classifications(list(entities)))
    return pd.DataFrame(rows)[
        ["entity", "ticker", "name", "sic", "sic_description", "division", "vintage"]
    ] if rows else pd.DataFrame()



def splits(n_obs: int, *, folds: int = 5, horizon: int = 1,
           embargo_pct: float = 0.01, combinatorial: bool = False,
           groups: int = 6, test_groups: int = 2) -> list[tuple[list[int], list[int]]]:
    """Purged, embargoed train/test splits as integer positions.

    For fitting anything on a financial series outside the backtester. Ordinary
    k-fold leaks: a label computed over the next `horizon` days spans the
    boundary, and serial correlation makes the days just after a test block
    near-copies of it. This purges the first and embargoes the second.

    `combinatorial=True` returns every combination of held-out blocks instead
    of one pass, which is what turns a single out-of-sample number into a
    distribution (Lopez de Prado, AFML ch. 7 and 12).
    """
    if combinatorial:
        return _validation.combinatorial_purged(
            n_obs, n_groups=groups, n_test_groups=test_groups,
            horizon=horizon, embargo_pct=embargo_pct)
    return _validation.purged_kfold(
        n_obs, n_splits=folds, horizon=horizon, embargo_pct=embargo_pct)


def overfitting_probability(columns: dict[str, dict[str, float]] | None = None,
                            *, blocks: int = 8) -> dict[str, Any]:
    """How often the best-looking configuration failed out of sample.

    Pass a mapping of name -> {date: return}. With nothing passed it uses the
    backtests run this session, which is usually what you want: the question is
    whether picking the winner from what *you* tried would have held up.
    """
    series = list(columns.values()) if columns else _honesty.trial_series()
    if len(series) < 2:
        return {"pbo": None, "note": "needs at least two return series to compare"}
    dates, matrix = _validation.align(series)
    out = _validation.probability_of_overfitting(matrix, n_blocks=blocks)
    out["overlapping_days"] = len(dates)
    return out


def treasury_yields(tenor: str = "10y", *, start: str | None = None,
                    end: str | None = None) -> pd.DataFrame:
    """US Treasury par yields. Keyless, 14 tenors, never revised."""
    return frame(_run(_treasury.yields(tenor, start=start, end=end)), value=tenor)


def positioning(market: str = "SP500", *, measure: str = "noncommercial_net",
                limit: int = 520) -> pd.DataFrame:
    """CFTC Commitments of Traders. Tuesday positions, Friday release, lag kept."""
    return frame(_run(cftc.positioning(market, measure=measure, limit=limit)),
                 value=measure)


def fx(pair: str = "EURUSD", *, start: str | None = None,
       end: str | None = None) -> pd.DataFrame:
    """ECB daily reference rates. Published each afternoon, never revised, so
    these are honestly point-in-time. Cross rates are derived from the two euro
    legs."""
    return frame(_run(ecb.rates(pair, start=start, end=end)), value=pair.upper())


def volatility(symbol: str = "VIX", *, field: str = "close",
               start: str | None = None, end: str | None = None) -> pd.DataFrame:
    """CBOE volatility indices. Levels, not option chains."""
    return frame(_run(cboe.levels(symbol, field=field, start=start, end=end)),
                 value=symbol.upper())


def index(symbol: str = "^GSPC", **kwargs) -> pd.DataFrame:
    """A market index. Same path as any other price series."""
    return prices(symbol, **kwargs)


def crypto(symbol: str = "BTC-USD", *, field: str = "close", interval: str = "1d",
           limit: int = 800) -> pd.DataFrame:
    """Crypto OHLCV. Trade prints are never restated, so these are honestly
    point-in-time in a way adjusted equity closes are not."""
    return frame(_run(coinbase.candles(symbol, field=field, interval=interval,
                                       limit=limit)), value=field)


# ------------------------------------------------------------------ fundamentals


def fundamentals(entity: str, field: str, *, form: str | None = None,
                 as_of: str | None = None) -> pd.DataFrame:
    """One XBRL concept for one filer, every version of it that was filed.

    A restated period appears more than once, with different `known_at` values.
    That is the point: `.restatements()` on the result finds them.
    """
    hit = _run(edgar.resolve(entity))
    facts = _run(edgar.company_facts(hit["cik"]))
    rows = _asof(edgar.to_rows(facts, field, hit["entity"], form=form), as_of)
    return frame(rows)


def restatements(entity: str, field: str) -> pd.DataFrame:
    """Periods this filer reported more than once with a different number."""
    hit = _run(edgar.resolve(entity))
    facts = _run(edgar.company_facts(hit["cik"]))
    return pd.DataFrame(envelope.restatements(edgar.to_rows(facts, field, hit["entity"])))


def filings(entity: str, *, limit: int = 40, as_of: str | None = None) -> pd.DataFrame:
    """Filing timeline with the timestamp EDGAR accepted each one."""
    hit = _run(edgar.resolve(entity))
    return frame(_asof(_run(edgar.recent_filings(hit["cik"], limit=limit)), as_of))


def resolve(identifier: str) -> dict[str, Any]:
    """Ticker, CIK or name to the entity key everything else accepts."""
    return _run(edgar.resolve(identifier))


# ------------------------------------------------------- factors, macro, claims


def factors(dataset: str = "ff3", *, start: str | None = None,
            end: str | None = None, wide: bool = True) -> pd.DataFrame:
    """Ken French factors. Wide by default, one column per factor."""
    df = frame(_run(french.load(dataset)))
    if wide and not df.empty and "field" in df:
        df = df.pivot_table(index=df.index, columns="field", values="value")
    return _window(df, start, end)


def macro(series: str, *, start: str | None = None, end: str | None = None,
          as_of: str | None = None) -> pd.DataFrame:
    """A FRED series. With `as_of`, ALFRED's first-release vintage."""
    rows = _asof(_run(fred.observations(series, start=start, end=end)), as_of)
    return _window(frame(rows, value=series), start, end)


def claim(acronym: str) -> dict[str, Any]:
    """What a published paper claimed for one predictor, from Open Source
    Asset Pricing. The number a replication has to beat."""
    return _run(openap.get(acronym))


def claims(*, price_only: bool = False) -> pd.DataFrame:
    """All 331 documented predictors. `price_only` narrows to the subset
    computable from price history alone."""
    rows = _run(openap.load())
    if price_only:
        rows = openap.supported_only(rows)
    return pd.DataFrame(rows)


def short_volume(entity: str, *, days: int = 20,
                 field: str = "short_ratio") -> pd.DataFrame:
    """FINRA daily short volume. Short *volume*, not short interest."""
    return frame(_run(finra.short_volume(entity, days=days, field=field)), value=field)


def sentiment(scope: str = "all-stocks", *, limit: int = 100) -> pd.DataFrame:
    """Forum mention ranks, stamped with the moment they were fetched."""
    return pd.DataFrame(_run(apewisdom.mentions(scope, limit=limit)))


def delistings(*, start_year: int = 2003, as_of: str | None = None) -> pd.DataFrame:
    """Every SEC Form 25 delisting, dated. The survivorship correction.

    First call scans EDGAR's quarterly indexes and takes a couple of minutes;
    closed quarters are immutable so it is cached after that. With `as_of`, only
    companies that delisted *after* that date, which is exactly the set a
    universe built today is missing.
    """
    rows = _delistings.load(start_year)
    if as_of:
        rows = [r for r in rows if r["known_at"] > as_of]
    return frame(rows)


def survivorship_warning(as_of: str | None = None) -> list[str]:
    """How badly a universe built today misrepresents `as_of`."""
    return _delistings.warnings_for(_delistings.load(), as_of)


# ------------------------------------------------------------------- discovery


def search(query: str, *, limit: int = 25) -> pd.DataFrame:
    """Plain-English search across the catalogs that need no key."""
    hits = registry.search_static(query, limit=limit)
    try:
        hits += _run(openap.search(query, limit=8))
    except Exception:
        pass
    return pd.DataFrame(hits)


def sources() -> pd.DataFrame:
    """What is wired up, and whether each preserves vintage."""
    return pd.DataFrame(registry.SOURCES)


def signals() -> pd.DataFrame:
    """Signals the built-in backtester knows."""
    return pd.DataFrame(
        [{"signal": k, "definition": v} for k, v in _bt.SIGNALS.items()]
    ).set_index("signal")


# ------------------------------------------------------------------- backtest


def backtest(universe: Iterable[str], signal: str = "momentum_12_1", *,
             start: str | None = None, end: str | None = None,
             cost_bps: float = 10.0, long_pct: float = 0.2,
             short_pct: float = 0.0, rebalance: str = "ME") -> dict[str, Any]:
    """Run a built-in signal and get the honesty report with it.

    The deflated Sharpe counts every specification tried in this session, so
    calling this in a loop makes the bar rise. That is deliberate, and
    `trials()` shows the running count.
    """
    px = panel(universe, start=start, end=end)
    return _bt.run(px, signal=signal, cost_bps=cost_bps, long_pct=long_pct,
                   short_pct=short_pct, rebalance=rebalance)


def trials() -> int:
    """How many specifications have been scored this session."""
    return _honesty.trial_count()
