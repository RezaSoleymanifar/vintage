"""Vintage — six verbs over every free data source.

Adding a source adds zero tools. The model learns six verbs once and the
breadth arrives through `discover`.
"""

from __future__ import annotations

import json
from typing import Any

import pandas as pd
from mcp.server import MCPServer

from . import cache, envelope, pit, registry
from .engine import backtest as bt
from .engine import benchmark as bm
from .engine import honesty
from .http import SourceError
from .sources import (apewisdom, bea, bls, cboe, cftc, coinbase, delistings,
                      ecb, edgar, finra, frames, fred, french, openap,
                      thirteenf, treasury, yahoo)

mcp = MCPServer(
    "vintage",
    instructions=(
        "Vintage is a point-in-time research terminal over free financial data.\n\n"
        "Every value carries two dates: `observed_at` (what period it describes) "
        "and `known_at` (when it first became public). Backtests may only use "
        "rows whose known_at precedes the trade date, and that is enforced "
        "structurally rather than by a flag.\n\n"
        "Six verbs: resolve, discover, fetch, events, backtest, benchmark. "
        "Source is a parameter, never a separate tool.\n\n"
        "Responses carry `warnings` and `suggested_next`. Surface warnings to "
        "the user — a restated figure or a missing delisted name is usually the "
        "most important thing in the answer. Follow suggested_next when it "
        "would deepen the analysis.\n\n"
        "Backtesting conversationally is an overfitting risk. Every backtest "
        "returns a deflated Sharpe that accounts for how many specs were tried "
        "this session. Report it. Never present a raw Sharpe alone."
    ),
    version="0.9.0",
)

# Backtests keep their return series here so the model does not have to carry
# thousands of numbers through the conversation to benchmark them.
_runs: dict[str, pd.Series] = {}


# ---------------------------------------------------------------- resolve


@mcp.tool()
async def resolve(identifier: str) -> str:
    """Turn any identifier into the entity key every other verb accepts.

    Accepts a ticker ("AAPL"), a CIK ("CIK0000320193" or "320193"), a FRED
    series id, or a French dataset name. Start here when unsure what an
    entity is called.
    """
    key = identifier.strip()

    if key.lower().startswith("fred:"):
        return envelope.respond(
            "resolve",
            entity=key,
            kind="macro-series",
            source="fred",
            suggested_next=[{"verb": "fetch", "args": {"field": key}}],
        )

    if key.lower().startswith("french:"):
        name = key.split(":", 1)[1]
        if name not in french.DATASETS:
            return envelope.fail(
                "resolve",
                f"Unknown French dataset {name!r}",
                did_you_mean=list(french.DATASETS),
            )
        return envelope.respond(
            "resolve",
            entity=key,
            kind="factor-dataset",
            source=french.SOURCE,
            components=french.DATASETS[name]["fields"],
            suggested_next=[{"verb": "fetch", "args": {"field": key}}],
        )

    try:
        hit = await edgar.resolve(key)
    except SourceError as exc:
        return envelope.fail("resolve", str(exc))

    return envelope.respond(
        "resolve",
        entity=hit["entity"],
        ticker=hit["ticker"],
        cik=hit["cik"],
        name=hit["name"],
        exchange=hit["exchange"],
        kind="us-filer",
        suggested_next=[
            {"verb": "discover", "args": {"query": "revenue", "entity": hit["ticker"]},
             "why": "see which fundamentals this filer actually reports"},
            {"verb": "events", "args": {"entity": hit["ticker"]},
             "why": "recent filings timeline"},
        ],
    )


# --------------------------------------------------------------- discover


@mcp.tool()
async def discover(query: str, entity: str | None = None, limit: int = 25) -> str:
    """Search every source's catalog for fields matching a plain-English query.

    This is how breadth is reached — there is no per-source tool. With
    `entity` set, it also searches that company's reported XBRL concepts,
    which is the reliable way to find the exact field name for fundamentals.
    """
    found: list[dict[str, Any]] = registry.search_static(query, limit=limit)
    warnings: list[str] = []

    if entity:
        try:
            hit = await edgar.resolve(entity)
            facts = await edgar.company_facts(hit["cik"])
            terms = [t for t in query.lower().split() if t]
            for item in edgar.catalog(facts):
                haystack = f"{item['field']} {item.get('label') or ''}".lower()
                if not terms or any(t in haystack for t in terms):
                    found.append({**item, "entity": hit["entity"]})
                if len(found) >= limit * 2:
                    break
        except SourceError as exc:
            warnings.append(str(exc))

    try:
        found.extend(await openap.search(query, limit=8))
    except SourceError as exc:
        warnings.append(str(exc))

    if fred.has_key():
        try:
            found.extend(await fred.search(query, limit=10))
        except SourceError as exc:
            warnings.append(str(exc))
    else:
        warnings.append(
            "FRED_API_KEY is not set, so 800k macro series are not searchable. "
            "Only curated FRED fields are shown. Free key: "
            "https://fred.stlouisfed.org/docs/api/api_key.html"
        )

    if not found:
        return envelope.fail(
            "discover",
            f"Nothing matches {query!r}"
            + (f" for {entity}" if entity else "")
            + ".",
            did_you_mean=[s["field_form"] for s in registry.SOURCES],
            searched_sources=[s["source"] for s in registry.SOURCES],
        )

    return envelope.respond(
        "discover",
        query=query,
        matches=found[:limit],
        match_count=len(found[:limit]),
        warnings=warnings,
        suggested_next=[
            {"verb": "fetch", "args": {"field": found[0]["field"], "entity": entity},
             "why": "pull the top match"}
        ],
    )


# ------------------------------------------------------------------ fetch


@mcp.tool()
async def fetch(
    field: str,
    entity: str | None = None,
    start: str | None = None,
    end: str | None = None,
    as_of: str | None = None,
    form: str | None = None,
    quarter: str | None = None,
    limit: int = 400,
) -> str:
    """Fetch any field from any source, as point-in-time rows.

    Field forms: "us-gaap:Assets" (needs entity), "price:close" (needs
    entity), "fred:CPIAUCSL", "french:ff3", "openap:Mom12m" (or "openap:*"
    for all 331 published claims), "crypto:close" (needs an entity like
    BTC-USD), "short:short_ratio" (needs an entity), "ape:all-stocks",
    "13f:value" (needs a manager like BERKSHIRE), "bls:CUUR0000SA0",
    "bea:T10101". Run discover first if unsure.

    `as_of` is the point-in-time switch: it drops every row that was not
    public on that date, so you see what a researcher on that day saw,
    restatements and all. `quarter` picks a reporting period for 13F
    holdings ("2024-12-31" or "2024"); without it you get the latest.
    """
    source = registry.route(field)
    rows: list[dict[str, Any]] = []
    warnings: list[str] = []

    try:
        if source == "french":
            rows = await french.load(field.split(":", 1)[1])
        elif source == "frames":
            # frame:us-gaap/Assets/CY2023Q1I  — taxonomy/tag/period, unit optional
            parts = field.split(":", 1)[1].split("/")
            if len(parts) < 3:
                return envelope.fail(
                    "fetch", "frame fields look like frame:us-gaap/Assets/CY2023Q1I",
                    did_you_mean=["frame:us-gaap/Assets/CY2023Q1I",
                                  "frame:us-gaap/Revenues/CY2023"])
            taxonomy, tag, period = parts[0], parts[1], parts[-1]
            unit = parts[2] if len(parts) > 3 else "USD"
            rows = await frames.cross_section(tag, period, taxonomy=taxonomy,
                                              unit=unit, limit=limit)
            warnings += frames.warnings_for(period, rows)
        elif source == "treasury":
            rows = await treasury.yields(field.split(":", 1)[1], start=start, end=end)
        elif source == "cftc":
            if not entity:
                return envelope.fail("fetch", "cot fields need an `entity`, e.g. SP500",
                                     did_you_mean=list(cftc.MARKETS))
            rows = await cftc.positioning(entity, measure=field.split(":", 1)[1])
            warnings += cftc.warnings_for()
        elif source == "thirteenf":
            if not entity:
                return envelope.fail(
                    "fetch", "13f fields need an `entity` — a manager, not a stock. "
                             "Try BERKSHIRE, or any name EDGAR knows.",
                    did_you_mean=sorted(thirteenf.MANAGERS))
            # A 13F describes one quarter, not a span, so `quarter` selects and
            # start/end are left alone.
            rows = await thirteenf.holdings(
                entity, field=field.split(":", 1)[1],
                quarter=quarter, as_of=as_of, limit=limit)
            warnings += thirteenf.warnings_for(rows, as_of)
        elif source == "bls":
            rows = await bls.series(field.split(":", 1)[1], start=start, end=end)
            warnings += bls.warnings_for(field, rows)
        elif source == "bea":
            spec = field.split(":", 1)[1]
            rows = await bea.table(spec)
            warnings += bea.warnings_for(spec, rows)
        elif source == "delistings":
            # Bulk history: one scan of EDGAR's quarterly indexes, then cached.
            # `as_of` keeps its usual meaning here — delistings already public
            # on that date. Inverting it to mean "still listed then" would have
            # made one verb mean two opposite things depending on the field.
            rows = delistings.load()
            warnings += delistings.warnings_for(rows, as_of)
        elif source == "ecb":
            pair = field.split(":", 1)[1]
            rows = await ecb.rates(pair, start=start, end=end)
            warnings += ecb.warnings_for(pair)
        elif source == "cboe":
            sym = field.split(":", 1)[1]
            rows = await cboe.levels(sym, start=start, end=end)
            warnings += cboe.warnings_for(sym)
        elif source == "crypto":
            if not entity:
                return envelope.fail("fetch", "crypto fields need an `entity`, e.g. BTC-USD")
            rows = await coinbase.candles(entity, field=field.split(":", 1)[1], limit=limit)
            warnings += coinbase.warnings_for(entity)
        elif source == "finra":
            if not entity:
                return envelope.fail("fetch", "short-volume fields need an `entity`, e.g. AAPL")
            rows = await finra.short_volume(entity, field=field.split(":", 1)[1])
            warnings += finra.warnings_for(rows)
        elif source == "apewisdom":
            rows = await apewisdom.mentions(field.split(":", 1)[1], limit=limit)
            warnings += apewisdom.warnings_for(rows)
        elif source == "openap":
            name = field.split(":", 1)[1]
            # "openap:*" is the whole scoreboard; a bare acronym is one claim.
            rows = await openap.load() if name in ("*", "") else [await openap.get(name)]
        elif source == "fred":
            rows = await fred.observations(
                field.split(":", 1)[1], start=start, end=end
            )
        elif source == "prices":
            if not entity:
                return envelope.fail("fetch", "price fields need an `entity`, e.g. AAPL")
            sub = field.split(":", 1)[1]
            if sub in ("pit_adjclose", "pit"):
                rows = await yahoo.pit_prices(entity, as_of=as_of)
                warnings += pit.warnings_for(
                    await yahoo.corporate_actions(entity), as_of)
            else:
                rows = await yahoo.prices(entity, field=sub)
        elif source == "sec-edgar-xbrl":
            if not entity:
                return envelope.fail(
                    "fetch", f"{field} is a company field and needs an `entity`"
                )
            hit = await edgar.resolve(entity)
            facts = await edgar.company_facts(hit["cik"])
            rows = edgar.to_rows(facts, field, hit["entity"], form=form)
            if not rows:
                nearby = [c["field"] for c in edgar.catalog(facts)[:15]]
                return envelope.fail(
                    "fetch",
                    f"{hit['ticker']} reports no facts for {field!r}",
                    did_you_mean=nearby,
                )
        else:
            return envelope.fail(
                "fetch",
                f"No source answers for field {field!r}",
                did_you_mean=[s["field_form"] for s in registry.SOURCES],
            )
    except SourceError as exc:
        return envelope.fail("fetch", str(exc))

    if start:
        rows = [r for r in rows if (r["observed_at"] or "") >= start]
    if end:
        rows = [r for r in rows if (r["observed_at"] or "") <= end]

    before = len(rows)
    rows = envelope.visible_at(rows, as_of)
    if as_of and before != len(rows):
        warnings.append(
            f"{before - len(rows)} row(s) hidden — they were not public on {as_of}."
        )

    warnings.extend(envelope.warn_unknown_vintage(rows))

    restated = envelope.restatements(rows)
    if restated:
        warnings.append(
            f"{len(restated)} period(s) were restated after first filing. "
            "Backtesting on the final figures would be look-ahead."
        )

    truncated = len(rows) > limit
    if truncated:
        warnings.append(f"Showing the most recent {limit} of {len(rows)} rows.")
        rows = rows[-limit:]

    return envelope.respond(
        "fetch",
        field=field,
        entity=entity,
        as_of=as_of,
        rows=rows,
        restatements=restated[:20],
        warnings=warnings,
        suggested_next=_fetch_next(field, entity),
    )


def _fetch_next(field: str, entity: str | None) -> list[dict[str, Any]]:
    if field.startswith("openap:"):
        return [{"verb": "backtest",
                 "why": "replicate the claim and compare your Sharpe to the published one"}]
    if field.startswith("french:"):
        return [{"verb": "backtest", "why": "build a factor and score it against this"}]
    if field.startswith("price:") and entity:
        return [{"verb": "backtest", "args": {"universe": [entity]},
                 "why": "test a signal on this price history"}]
    if entity:
        return [{"verb": "events", "args": {"entity": entity},
                 "why": "see what was filed around these figures"}]
    return []


# ----------------------------------------------------------------- events


@mcp.tool()
async def events(entity: str, limit: int = 40, as_of: str | None = None) -> str:
    """Timeline of what happened to an entity, with exact public timestamps.

    Currently the SEC filing stream — 8-K material events, 10-K/10-Q, Form 4
    insider transactions, 13D/G stakes. Every row carries the minute it became
    public, which is what makes event studies possible.
    """
    try:
        hit = await edgar.resolve(entity)
        rows = await edgar.recent_filings(hit["cik"], limit=limit)
    except SourceError as exc:
        return envelope.fail("events", str(exc))

    rows = envelope.visible_at(rows, as_of)
    counts: dict[str, int] = {}
    for r in rows:
        counts[r["form"]] = counts.get(r["form"], 0) + 1

    return envelope.respond(
        "events",
        entity=hit["entity"],
        ticker=hit["ticker"],
        rows=rows,
        form_counts=dict(sorted(counts.items(), key=lambda kv: -kv[1])),
        suggested_next=[
            {"verb": "fetch", "args": {"field": "price:close", "entity": hit["ticker"]},
             "why": "line these events up against price"}
        ],
    )


# --------------------------------------------------------------- backtest


@mcp.tool()
async def backtest(
    universe: list[str],
    signal: str = "momentum_12_1",
    start: str | None = None,
    end: str | None = None,
    long_pct: float = 0.2,
    short_pct: float = 0.0,
    cost_bps: float = 10.0,
    rebalance: str = "ME",
) -> str:
    """Run a cross-sectional backtest. Point-in-time and costed by construction.

    At each rebalance the engine sees only data knowable strictly before that
    date. Costs are always charged on turnover; there is no zero-cost mode.

    The result includes a deflated Sharpe that accounts for how many specs
    have been tried this session. Always report it alongside the raw Sharpe —
    a conversational backtester is an overfitting machine without it.

    Signals: momentum_12_1, momentum_6_1, reversal_1m, low_volatility, trend_200d.
    """
    if len(universe) < 4:
        return envelope.fail(
            "backtest",
            f"A cross-sectional backtest needs at least 4 names; got {len(universe)}.",
        )
    if signal not in bt.SIGNALS:
        return envelope.fail(
            "backtest", f"Unknown signal {signal!r}", did_you_mean=bt.SIGNALS
        )

    rows: list[dict[str, Any]] = []
    missing: list[str] = []
    for ticker in universe:
        try:
            # Adjusted close: splits and dividends folded in, which is what a
            # total-return backtest needs.
            rows.extend(await yahoo.prices(ticker, field="adjclose"))
        except SourceError:
            missing.append(ticker.upper())

    if not rows:
        return envelope.fail(
            "backtest", f"No price history for any of: {', '.join(universe)}"
        )

    prices = bt.panel(rows)

    try:
        result = bt.run(
            prices,
            signal=signal,
            rebalance=rebalance,
            long_pct=long_pct,
            short_pct=short_pct,
            cost_bps=cost_bps,
            start=start,
            end=end,
        )
    except ValueError as exc:
        return envelope.fail("backtest", str(exc))

    series = pd.Series(
        {pd.Timestamp(k): v for k, v in result["returns"].items()}
    ).sort_index()
    run_id = f"run{len(_runs) + 1}"
    _runs[run_id] = series

    warnings = [
        "Universe is a fixed list of names that exist today. Any company that "
        "delisted during the period is absent, which flatters the result. This "
        "is survivorship bias and it is not corrected here yet.",
        f"Costs charged at {cost_bps}bps of turnover. Real spreads on small or "
        "illiquid names are wider.",
    ]
    if missing:
        warnings.append(f"No price history for: {', '.join(missing)} — excluded.")

    annual = {
        str(year): round(float((1 + group).prod() - 1), 4)
        for year, group in series.groupby(series.index.year)
    }

    return envelope.respond(
        "backtest",
        run_id=run_id,
        spec=result["spec"],
        stats=result["stats"],
        honesty=result["honesty"],
        annual_returns=annual,
        excluded=missing,
        warnings=warnings,
        suggested_next=[
            {"verb": "benchmark", "args": {"run_id": run_id, "dataset": "ff3"},
             "why": "find out whether this is just a known factor in disguise"}
        ],
    )


# -------------------------------------------------------------- benchmark


@mcp.tool()
async def benchmark(run_id: str, dataset: str = "ff3") -> str:
    """Score a backtest against the published Fama-French factors.

    Answers the question that decides whether a result is interesting: did you
    discover something, or rebuild a factor that has been public since 1993?

    Datasets: ff3, ff5, momentum, ff3_daily, industry49.
    """
    series = _runs.get(run_id)
    if series is None:
        return envelope.fail(
            "benchmark",
            f"No backtest called {run_id!r} in this session",
            did_you_mean=list(_runs) or ["run a backtest first"],
        )

    try:
        rows = await french.load(dataset)
    except SourceError as exc:
        return envelope.fail("benchmark", str(exc))

    frame = pd.DataFrame(rows).pivot_table(
        index="observed_at", columns="field", values="value", aggfunc="last"
    )
    result = bm.compare(series, frame)
    if "error" in result:
        return envelope.fail("benchmark", result["error"])

    return envelope.respond(
        "benchmark",
        run_id=run_id,
        dataset=dataset,
        result=result,
        warnings=[
            "French factors carry no filing date, so this comparison is not "
            "point-in-time. That is fine for scoring, not for trading."
        ],
        suggested_next=[
            {"verb": "backtest", "why": "vary one spec choice and see if the alpha survives"}
        ],
    )


# ------------------------------------------------------------- diagnostics


@mcp.tool()
async def status() -> str:
    """Cache size, configured keys, sources available, and specs tried so far."""
    return envelope.respond(
        "status",
        cache=cache.stats(),
        sources=registry.SOURCES,
        fred_key_configured=fred.has_key(),
        specs_tried_this_session=honesty.trial_count(),
        backtests_in_memory=list(_runs),
    )


def main() -> None:
    mcp.run()


if __name__ == "__main__":
    main()
