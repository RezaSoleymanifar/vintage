"""Generate QUALITY.md, the data quality audit.

COVERAGE.md answers "what is wired up". This answers "is it any good", which is a
different question and the one that decides whether a signal is tradable.

Six measures, in the order they matter:

  publication lag   known_at - observed_at. The number that decides tradability:
                    a factor whose data lands 45 days late is a different
                    strategy from one that lands overnight. Only Vintage can
                    compute this across every source, because only Vintage keeps
                    both dates on every row.
  unknown vintage   the share of rows with no honest known_at at all.
  staleness         days since the newest observation, which catches a feed that
                    died quietly.
  gap runs          the longest run of consecutive missing business days, which
                    separates "thin" from "broken".
  panel density     on a given date, how many of a universe actually have a
                    value. A cross-sectional sort on a sparse date is noise.
  revisions         how often one (entity, field, observed_at) is reported twice
                    with different numbers.

Everything is measured live. A probe that fails is reported as failed rather
than dropped, because a quality audit that hides its own gaps is worth nothing.

    uv run python tools/build_quality.py
"""

from __future__ import annotations

import asyncio
import os
import statistics
import sys
from datetime import date, datetime, timedelta
from typing import Any, Callable

sys.path.insert(0, os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "src"))

os.environ.setdefault("VINTAGE_USER_AGENT", "Vintage quality audit reza@soleymanifar.com")

import vintage as v  # noqa: E402
from vintage import registry  # noqa: E402
from vintage.sources import delistings as _delistings, edgar  # noqa: E402
from vintage.sdk import _run  # noqa: E402

TODAY = date.today()

# (label, prefix it exercises, how to fetch it). Keyless and reasonably quick;
# anything needing a key is listed as skipped rather than silently omitted.
PROBES: list[tuple[str, str, Callable[[], Any]]] = [
    ("Yahoo daily prices",   "price:",     lambda: v.prices("AAPL", start="2015-01-01")),
    ("Market index",         "index:",     lambda: v.index("^GSPC", start="2015-01-01")),
    ("Coinbase crypto",      "crypto:",    lambda: v.crypto("BTC-USD")),
    ("ECB reference rates",  "fx:",        lambda: v.fx("EURUSD")),
    ("CBOE volatility",      "vol:",       lambda: v.volatility("VIX")),
    ("US Treasury curve",    "ust:",       lambda: v.treasury_yields("10y")),
    ("FINRA short volume",   "short:",     lambda: v.short_volume("AAPL", days=250)),
    ("CFTC positioning",     "cot:",       lambda: v.positioning("SP500")),
    ("Ken French FF3",       "french:",    lambda: v.factors("ff3")),
    ("SEC EDGAR XBRL",       "us-gaap:",   lambda: v.fundamentals("AAPL", "us-gaap:Assets")),
    ("SEC filing stream",    "filing:",    lambda: v.filings("AAPL", limit=200)),
    ("SEC Form 25",          "delisting:", lambda: v.delistings()),
    ("ApeWisdom mentions",   "ape:",       lambda: v.sentiment("all-stocks")),
]

SKIPPED = [
    ("FRED / ALFRED", "fred:", "needs a free API key; not set in this environment"),
    ("BEA national accounts", "bea:", "needs a free API key; not set in this environment"),
    ("BLS", "bls:", "keyless tier returns ~3 years, so lag stats would describe the tier"),
    ("SEC Form 13F", "13f:", "returns one quarter per call, so a lag distribution needs a crawl"),
    ("SEC XBRL frames", "frame:", "a cross-section at one period; lag is not defined for it"),
]

# Gaps only mean something for a series that is supposed to have a value every
# period. Counting them on monthly or event-driven data reports "1,199 gaps" for
# a factor file that is monthly by design.
FREQUENCY = {
    "price:": "daily", "index:": "daily", "fx:": "daily", "vol:": "daily",
    "ust:": "daily", "short:": "daily", "crypto:": "daily",
    "french:": "monthly", "cot:": "weekly", "us-gaap:": "quarterly",
    "filing:": "event", "delisting:": "event", "ape:": "snapshot",
}


def _dates(frame, col: str) -> list[date]:
    out = []
    if frame is None or len(frame) == 0:
        return out
    series = frame[col] if col in getattr(frame, "columns", []) else frame.index.to_series()
    for raw in series.dropna():
        text = str(raw)[:10]
        try:
            out.append(datetime.strptime(text, "%Y-%m-%d").date())
        except ValueError:
            continue
    return out


def lag_stats(frame) -> dict[str, Any]:
    """known_at - observed_at, in days, over rows that carry both."""
    if frame is None or len(frame) == 0:
        return {}
    cols = getattr(frame, "columns", [])
    if "known_at" not in cols:
        return {"unknown_vintage_pct": 100.0}

    observed = frame.index.to_series() if "observed_at" not in cols else frame["observed_at"]
    lags, unknown = [], 0
    for obs, known in zip(observed, frame["known_at"]):
        if known is None or str(known) == "nan" or not str(known).strip():
            unknown += 1
            continue
        try:
            o = datetime.strptime(str(obs)[:10], "%Y-%m-%d").date()
            k = datetime.strptime(str(known)[:10], "%Y-%m-%d").date()
        except ValueError:
            unknown += 1
            continue
        lags.append((k - o).days)

    out: dict[str, Any] = {"unknown_vintage_pct": round(unknown / len(frame) * 100, 1)}
    if lags:
        lags.sort()
        out.update({
            "lag_median": statistics.median(lags),
            "lag_p90": lags[min(int(len(lags) * 0.9), len(lags) - 1)],
            "lag_max": max(lags),
            "lag_n": len(lags),
        })
    return out


def gap_stats(dates: list[date], business_days: bool) -> dict[str, Any]:
    """Longest run of consecutive missing days, and how many runs there are."""
    if len(dates) < 2:
        return {}
    dates = sorted(set(dates))
    longest, gaps = 0, 0
    for prev, nxt in zip(dates, dates[1:]):
        missing = 0
        cursor = prev + timedelta(days=1)
        while cursor < nxt:
            if not business_days or cursor.weekday() < 5:
                missing += 1
            cursor += timedelta(days=1)
        if missing:
            gaps += 1
            longest = max(longest, missing)
    return {"gap_runs": gaps, "longest_gap": longest}


async def probe(label: str, prefix: str, fetch: Callable[[], Any]) -> dict[str, Any]:
    row: dict[str, Any] = {"source": label, "prefix": prefix}
    try:
        frame = await asyncio.get_running_loop().run_in_executor(None, fetch)
    except Exception as exc:                      # noqa: BLE001 - reported, not hidden
        row["failed"] = f"{type(exc).__name__}: {str(exc)[:90]}"
        return row

    for src in registry.SOURCES:
        if src.get("field_form", "").startswith(prefix) or prefix.rstrip(":") in src.get("source", ""):
            row["claims_pit"] = str(src.get("point_in_time", "")).lower().startswith("yes")
            break
    row["rows"] = len(frame)
    row.update(lag_stats(frame))

    cols = getattr(frame, "columns", [])
    observed = _dates(frame, "observed_at" if "observed_at" in cols else "")
    if observed:
        row["first"] = min(observed).isoformat()
        row["last"] = max(observed).isoformat()
        row["stale_days"] = max((TODAY - max(observed)).days, 0)
        row["freq"] = FREQUENCY.get(prefix, "unknown")
        if row["freq"] == "daily":
            row.update(gap_stats(observed, prefix != "crypto:"))
    return row


# A universe of names that are all still listed measures 100% density and calls
# it a clean bill of health. That is survivorship reappearing inside the audit
# meant to detect it, so WBA is in the list on purpose: it left the index and its
# price history is exactly what a survivors-only universe silently drops.
DENSITY_UNIVERSE = ["AAPL", "MSFT", "JNJ", "XOM", "JPM", "KO", "PG", "WMT",
                    "CVX", "MRK", "HD", "INTC", "CSCO", "VZ", "BA", "MMM",
                    "CAT", "IBM", "NKE", "WBA"]


def panel_density() -> dict[str, Any]:
    """On a given date, how many of a universe actually carry a price."""
    try:
        panel = v.panel(DENSITY_UNIVERSE, start="2010-01-01")
    except Exception as exc:                      # noqa: BLE001
        return {"failed": f"{type(exc).__name__}: {str(exc)[:90]}"}
    filled = panel.notna().sum(axis=1)
    total = len(DENSITY_UNIVERSE)
    return {
        "universe": total,
        "dates": len(panel),
        "median_filled": int(filled.median()),
        "median_density_pct": round(float(filled.median()) / total * 100, 1),
        "worst_filled": int(filled.min()),
        "full_rows_pct": round(float((filled == total).mean()) * 100, 1),
    }


def revision_rate(tickers: list[str], field: str = "us-gaap:Assets") -> dict[str, Any]:
    """How often one (entity, field, observed_at) is filed twice, differently."""
    checked, revised, periods = 0, 0, 0
    for ticker in tickers:
        try:
            hit = _run(edgar.resolve(ticker))
            facts = _run(edgar.company_facts(hit["cik"]))
            rows = edgar.to_rows(facts, field, hit["entity"])
        except Exception:                         # noqa: BLE001
            continue
        checked += 1
        seen: dict[tuple[str, str], set] = {}
        for r in rows:
            key = (r["entity"], str(r.get("observed_at")))
            seen.setdefault(key, set()).add(r.get("value"))
        periods += len(seen)
        revised += sum(1 for values in seen.values() if len(values) > 1)
    return {"filers_checked": checked, "periods": periods, "revised_periods": revised,
            "revision_pct": round(revised / periods * 100, 1) if periods else 0.0}


# The service level this data promises, as numbers rather than adjectives. These
# are the thresholds a user is entitled to assume without checking, which is what
# makes them an SLA rather than a description: breaching one is a defect, and the
# build fails on it.
#
# Freshness is keyed to how often a source is supposed to publish, because "two
# days old" is broken for a price feed and early for a quarterly filing.
FRESHNESS_SLO = {          # max acceptable days since the newest observation
    "daily": 4,            # a long weekend plus a holiday
    "weekly": 12,
    "monthly": 45,
    "quarterly": 130,      # filers have 40-90 days, plus slack
    "event": 30,
    "snapshot": 2,
}
CONTINUITY_SLO = 5         # longest run of missing business days, daily series
# A long lag is only suspicious where the source publishes a value once. A 10-K
# restates the prior year's balance sheet as a comparative, so AAPL's FY2018
# assets legitimately carry a known_at two years later: the first run of this
# gate flagged that 760-day lag as a fault when it is the filing system working
# as designed. Applied only where a value is published once and not repeated.
LAG_SANITY_SLO = 400
LAG_SANITY_APPLIES = {"daily", "weekly", "snapshot"}


def grade(row: dict[str, Any]) -> tuple[str, list[str]]:
    """PASS, WARN or FAIL against the SLA, plus the reason for anything short."""
    if row.get("failed"):
        return "FAIL", [f"probe failed: {row['failed']}"]

    freq = row.get("freq", "unknown")
    breaches, warnings = [], []

    limit = FRESHNESS_SLO.get(freq)
    stale = row.get("stale_days")
    if limit is not None and stale is not None and stale > limit:
        (breaches if stale > limit * 2 else warnings).append(
            f"stale {stale} d against a {limit} d target for {freq} data")

    longest = row.get("longest_gap")
    if longest is not None and longest > CONTINUITY_SLO:
        (breaches if longest > CONTINUITY_SLO * 2 else warnings).append(
            f"a {longest} business-day hole, target {CONTINUITY_SLO}")

    # An unknown vintage is only a defect where the registry claims the source is
    # point-in-time. Where it does not, the flag is the source being honest.
    unknown = row.get("unknown_vintage_pct", 0.0)
    if unknown and row.get("claims_pit"):
        breaches.append(f"{unknown}% of rows carry no known_at, but this source "
                        "is registered as point-in-time")

    if freq in LAG_SANITY_APPLIES and (row.get("lag_max") or 0) > LAG_SANITY_SLO:
        warnings.append(f"a {row['lag_max']} d maximum lag, which is more likely "
                        "a parsing fault than a filing")

    if breaches:
        return "FAIL", breaches
    if warnings:
        return "WARN", warnings
    return "PASS", []


def table(rows: list[dict[str, Any]]) -> str:
    head = ("| Source | Prefix | Freq | Rows | Median lag | p90 | Max | No `known_at` | "
            "Stale | Gap runs | Longest | Grade |\n"
            "|---|---|---|---|---|---|---|---|---|---|---|---|")
    out = [head]
    for r in rows:
        if r.get("failed"):
            out.append(f"| **{r['source']}** | `{r['prefix']}` | — | "
                       f"probe failed: {r['failed']} ||||||||")
            continue
        d = lambda k, suffix="": (f"{r[k]}{suffix}" if r.get(k) is not None else "—")  # noqa: E731
        out.append(
            f"| **{r['source']}** | `{r['prefix']}` | {r.get('freq', '—')} | "
            f"{r.get('rows', 0):,} | "
            f"{d('lag_median', ' d')} | {d('lag_p90', ' d')} | {d('lag_max', ' d')} | "
            f"{d('unknown_vintage_pct', '%')} | {d('stale_days', ' d')} | "
            f"{d('gap_runs')} | {d('longest_gap', ' d')} | {r.get('grade', '—')} |")
    return "\n".join(out)


async def main() -> None:
    print("probing sources, this makes live requests ...", flush=True)
    rows = []
    for label, prefix, fetch in PROBES:
        r = await probe(label, prefix, fetch)
        r["grade"], r["reasons"] = grade(r)
        rows.append(r)
        print(f"  {r['grade']:<4} {label}: "
              f"{r.get('failed') or str(r.get('rows', 0)) + ' rows'}", flush=True)

    print("measuring panel density ...", flush=True)
    density = panel_density()
    print("measuring revision rate ...", flush=True)
    revisions = revision_rate(DENSITY_UNIVERSE[:8])
    try:
        delisted = len({r["cik"] for r in _delistings.load()})
    except Exception:                             # noqa: BLE001
        delisted = 0

    worst = "FAIL" if any(r["grade"] == "FAIL" for r in rows) else (
            "WARN" if any(r["grade"] == "WARN" for r in rows) else "PASS")
    counts = {g: sum(1 for r in rows if r["grade"] == g) for g in ("PASS", "WARN", "FAIL")}
    detail = [f"- **{r['source']}** — {r['grade']}: {'; '.join(r['reasons'])}"
              for r in rows if r["reasons"]]
    nl = chr(10)
    gate_summary = (
        f"**Gate: {worst}.** {counts['PASS']} pass, {counts['WARN']} warn, "
        f"{counts['FAIL']} fail, of {len(rows)} probed." + nl + nl
        + (nl.join(detail) if detail else "Nothing to report; every probe met its target.")
    )

    body = f"""# Quality

What [COVERAGE.md](COVERAGE.md) does not tell you: whether the data is any good.
Generated by `tools/build_quality.py`, measured live on {TODAY.isoformat()}.

Every number here is measured. A probe that failed says so rather than being
dropped, because an audit that hides its own gaps is worth nothing.

## Publication lag, and what carries an honest date

`known_at - observed_at`, in days. This is the number that decides whether a
signal is tradable: a factor whose data arrives 45 days after the period it
describes is a different strategy from one that arrives overnight. Vintage can
measure it across every source because it keeps both dates on every row.

{table(rows)}

Gap runs are only counted for daily series; a monthly factor file is not full of
holes, it is monthly. On a daily series a one-day run is almost always an
exchange holiday rather than a fault, so read the longest run, not the count.

A lag of `0 d` means the value and its publication share a date, which is normal
for market prints and never true of filings. `No known_at` at 100% means the
source ships no release date at all, and those rows are flagged
`UNKNOWN_VINTAGE` rather than given a plausible one.

## Panel density

On a given date, how many names in a universe actually carry a value. A
cross-sectional sort run on a sparse date is mostly noise, and the median is the
honest summary of that.

| Measure | Value |
|---|---|
| Universe | {density.get('universe', '—')} large-cap US names |
| Dates | {density.get('dates', 0):,} |
| Median names with a price | {density.get('median_filled', '—')} of {density.get('universe', '—')} ({density.get('median_density_pct', '—')}%) |
| Worst date | {density.get('worst_filled', '—')} names |
| Dates with every name | {density.get('full_rows_pct', '—')}% |

{"**Probe failed:** " + density["failed"] if density.get("failed") else ""}

**Read this one carefully.** The universe is nineteen names that are still listed
plus WBA, which is not. A universe drawn only from names that exist today
measures near 100% density and reads as a clean bill of health, which is
survivorship reappearing inside the audit built to detect it. The gap between
100% and the number above is one delisted name out of twenty. Form 25 has
{delisted:,} companies on record, so a universe reconstructed honestly for an
older `as_of` is far sparser than this table suggests.

## Revisions

How often one `(entity, field, observed_at)` is filed more than once with a
different number. This is the thing a point-in-time store exists for, and it is
measurable here because restatements arrive as rows rather than overwrites.

| Measure | Value |
|---|---|
| Filers checked | {revisions['filers_checked']} |
| Periods observed | {revisions['periods']:,} |
| Periods later restated | {revisions['revised_periods']:,} |
| Revision rate | **{revisions['revision_pct']}%** |

Field: `us-gaap:Assets`. A revision rate above zero is the whole argument for
`as_of`: a backtest reading today's value for a period that was restated is
reading a number nobody had at the time.

## The gate

The table above is a description. This is a promise: the level a user is entitled
to assume without checking. A breach is a defect, not a note, and
`tools/build_quality.py` exits non-zero on one so it can gate a release.

| Check | Target | Applies to | Why this number |
|---|---|---|---|
| Freshness | {FRESHNESS_SLO["daily"]} d | daily | a long weekend plus a holiday |
| | {FRESHNESS_SLO["weekly"]} d | weekly | one missed release, not two |
| | {FRESHNESS_SLO["monthly"]} d | monthly | factor files land mid-month |
| | {FRESHNESS_SLO["quarterly"]} d | quarterly | filers get 40-90 days, plus slack |
| | {FRESHNESS_SLO["snapshot"]} d | snapshot | a live board is worthless when stale |
| Continuity | {CONTINUITY_SLO} business days | daily | longer is an outage, not a holiday |
| Honest vintage | 0% missing `known_at` | sources the registry registers as point-in-time | the whole promise |
| Lag sanity | {LAG_SANITY_SLO} d maximum | daily, weekly, snapshot | beyond this it is a parsing fault. Excluded for filings, where a 10-K restates the prior year as a comparative and a two-year lag is correct |
| Reachability | probe succeeds | any | unreachable is unusable |

**WARN** is a breach inside 2x the target. **FAIL** is beyond it, or any missing
`known_at` on a source that claims point-in-time, or an unreachable source.

{gate_summary}

## Not measured, and why

{chr(10).join(f"- **{n}** (`{p}`) — {why}" for n, p, why in SKIPPED)}

Counts and distributions measured at generation time. Vintage redistributes none
of this data; each upstream source keeps its own terms.
"""
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    path = os.path.join(root, "QUALITY.md")
    with open(path, "w", encoding="utf-8", newline="\n") as fh:
        fh.write(body)
    print(f"wrote {path} ({len(body):,} bytes)")
    print(f"gate: {worst} ({counts['PASS']} pass, {counts['WARN']} warn, {counts['FAIL']} fail)")
    if worst == "FAIL":
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
