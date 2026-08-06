"""Generate COVERAGE.md, what Vintage actually serves, today.

DATA_SOURCES.md is the landscape: everything free that exists, ranked, most of it
not built yet. This is the opposite document, only what is wired up right now,
generated from the registry so it cannot drift away from the code.

    uv run python tools/build_coverage.py
"""

from __future__ import annotations

import asyncio
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "src"))

from vintage import registry  # noqa: E402

NL = chr(10)
BLANK = ""
from vintage.engine import backtest as bt  # noqa: E402
from vintage.sources import (apewisdom, bea, bls, cboe, coinbase, ecb, finra,  # noqa: E402
                             french, thirteenf)

HEADER = """# Coverage

What Vintage serves **today**. Generated from the registry by
`tools/build_coverage.py`: if a field is listed here, it is wired up.

For the wider landscape of free data that exists but is not built yet, see
[DATA_SOURCES.md](DATA_SOURCES.md). For the honest limits, see the Known gaps
section of the [README](README.md).

"""

VERBS = """## The six verbs

Source is a parameter, never a separate tool.

| Verb | Takes | Returns |
|---|---|---|
| `resolve` | ticker, CIK, FRED series id, French dataset name | the entity key every other verb accepts |
| `discover` | plain English, optional entity | matching fields across every source's catalog |
| `fetch` | a field, optional entity, optional `as_of` | rows carrying `observed_at` and `known_at` |
| `events` | an entity, optional form filter | filing timeline with exact acceptance timestamps |
| `backtest` | a universe and a signal | returns, costs, and an honesty report |
| `benchmark` | a run id and a factor set | correlation and alpha vs published factors |
| `status` | none | cache size, keys configured, specs tried this session |

"""


def field_routing() -> str:
    rows = ["## Field prefixes\n", "How a field name routes to a source.\n",
            "| Prefix | Source | Needs an entity |", "|---|---|---|"]
    needs = {
        "price:": "yes", "fred:": "no", "french:": "no", "filing:": "yes",
        "us-gaap:": "yes", "dei:": "yes", "ifrs-full:": "yes", "srt:": "yes", "invest:": "yes",
    }
    for prefix, source in registry.PREFIXES.items():
        rows.append(f"| `{prefix}` | {source} | {needs.get(prefix, ', ')} |")
    rows.append("")
    rows.append("A bare field with no prefix is routed to `sec-edgar-xbrl`. "
                "An unrecognised prefix returns an error naming the prefixes that exist, "
                "rather than guessing.\n")
    return "\n".join(rows) + "\n"


def sources_table() -> str:
    rows = ["## Sources wired up\n",
            "| Source | Covers | Field form | Point-in-time | Key |", "|---|---|---|---|---|"]
    for s in registry.SOURCES:
        key = "free key" if s["key_required"] else "none"
        note = f" {s['note']}" if s.get("note") else ""
        rows.append(
            f"| **{s['source']}** | {s['covers']}{note} | `{s['field_form']}` "
            f"| {s['point_in_time']} | {key} |"
        )
    rows.append("")
    return "\n".join(rows) + "\n"


def french_table() -> str:
    cat = french.catalog()
    rows = [f"## Ken French datasets ({len(cat)} wired up)\n",
            "Dartmouth. The benchmark every factor claim is scored against.\n",
            "| Field | Dataset | Coverage |", "|---|---|---|"]
    spans = asyncio.run(_french_spans([c["field"].split(":", 1)[1] for c in cat]))
    for c in cat:
        name = c["field"].split(":", 1)[1]
        rows.append(f"| `{c['field']}` | {c['label']} | {spans.get(name, ', ')} |")
    rows.append("")
    return "\n".join(rows) + "\n"


async def _french_spans(names: list[str]) -> dict[str, str]:
    out: dict[str, str] = {}
    for n in names:
        try:
            data = await french.load(n)
            dates = sorted(r["observed_at"] for r in data if r.get("observed_at"))
            out[n] = f"{dates[0]} → {dates[-1]}" if dates else ", "
        except Exception as exc:  # a dead upstream should not kill the doc
            out[n] = f"unavailable ({type(exc).__name__})"
    return out


def fred_table() -> str:
    rows = [f"## FRED curated series ({len(registry.CURATED)} shortcuts)\n",
            "Federal Reserve Bank of St. Louis. These are hand-picked so `discover` answers well "
            "before a key is configured, but **any** of FRED's 800,000+ series works by id, and "
            "ALFRED supplies first-release vintages.\n",
            "| Field | Series |", "|---|---|"]
    for item in registry.CURATED:
        rows.append(f"| `{item['field']}` | {item['label']} |")
    rows.append("")
    return "\n".join(rows) + "\n"


def sentiment_table() -> str:
    rows = [
        f"## Forum sentiment ({len(apewisdom.FILTERS)} scopes)\n",
        "ApeWisdom. No key. **No history endpoint upstream**. Every row is stamped "
        "`known_at` = the moment Vintage fetched it, so backtestable history begins "
        'the day you start recording. Vendors selling years of "historical sentiment" '
        "built it by re-scoring archived posts with a model that already knew what "
        "happened next.\n",
        "| Field | Scope |",
        "|---|---|",
    ]
    for key, label in apewisdom.FILTERS.items():
        rows.append(f"| `ape:{key}` | {label} |")
    rows.append("")
    return "\n".join(rows) + "\n"


def crypto_table() -> str:
    intervals = ", ".join(f"`{g}`" for g in coinbase.GRANULARITY)
    rows = [
        "## Crypto\n",
        "Coinbase Exchange, no key. A trade print is never restated, so these rows are "
        "*more* honestly point-in-time than equity adjusted closes. Survivorship runs the "
        "other way: dead tokens are absent entirely, which is a worse bias than equities, "
        "not a milder one.\n",
        f"Intervals: {intervals}. All crypto fields need an entity such as `BTC-USD`.\n",
        "| Field | Returns |",
        "|---|---|",
    ]
    for f in sorted(coinbase.FIELDS):
        rows.append(f"| `crypto:{f}` | {f} of each bar |")
    rows.append("")
    return "\n".join(rows) + "\n"


def short_table() -> str:
    rows = [
        "## Short sale volume\n",
        "FINRA, published after each close and never revised. This is **short volume, "
        "not short interest**, shares sold short during the session, including "
        "market-maker hedging that is flat again by the close. A flow measure, not "
        "outstanding bearish positioning.\n",
        "| Field | Returns |",
        "|---|---|",
        "| `short:short_ratio` | short volume as a share of total reported volume |",
        "| `short:short_volume` | shares sold short |",
        "| `short:exempt_volume` | short-exempt shares |",
        "| `short:total_volume` | total reported volume |",
        "",
        f"One HTTP request per trading day, so `days` defaults to {finra.DEFAULT_DAYS} "
        f"and caps at {finra.MAX_DAYS}.\n",
    ]
    return "\n".join(rows) + "\n"


def fx_table() -> str:
    rows = [
        "## Foreign exchange" + BLANK,
        "European Central Bank reference rates, no key. Published each working day "
        "around 16:00 CET and never revised, so these are honestly point-in-time. "
        "Everything is quoted against the euro; a cross rate such as `fx:USDJPY` is "
        "derived from the two euro legs and labelled as derived." + BLANK,
        "| Field | Pair |", "|---|---|",
    ]
    for code in ecb.MAJORS:
        rows.append("| `fx:EUR" + code + "` | Euro to " + code + " |")
    rows.append("")
    rows.append("Any ISO code the ECB publishes works, and any two of them cross. "
                "History begins in 1999." + BLANK)
    return NL.join(rows) + NL


def vol_table() -> str:
    rows = [
        "## Volatility indices (" + str(len(cboe.INDICES)) + ")" + BLANK,
        "CBOE, no key. Index levels are computed from that session's option prices and "
        "are not revised. **Levels only**, historical option chains are paid at "
        "every vendor and remain a gap." + BLANK,
        "| Field | Covers |", "|---|---|",
    ]
    for symbol, label in cboe.INDICES.items():
        rows.append("| `vol:" + symbol + "` | " + label + " |")
    rows.append("")
    return NL.join(rows) + NL


def index_table() -> str:
    rows = [
        "## Market indices" + BLANK,
        "Routed through the price adapter. Listed here because nobody guesses the caret "
        "tickers unprompted." + BLANK,
        "| Entity | Index |", "|---|---|",
    ]
    for item in registry.INDICES:
        rows.append("| `" + item["entity"] + "` | " + item["label"] + " |")
    rows.append("")
    return NL.join(rows) + NL


def delistings_table() -> str:
    rows = [
        "## Delistings, and survivorship" + BLANK,
        "SEC Form 25 filings: 36,830 covering 11,614 companies, 2003 to 2026, each with "
        "a company name, a CIK and an exact date. This is the correction for a universe "
        "built from currently-listed names, which is a universe of survivors." + BLANK,
        "| Field | Returns |", "|---|---|",
        "| `delisting:form25` | every delisting on record, dated |", "",
        "Electronic Form 25 filing became mandatory in April 2006, and the counts show "
        "the step: about 450 a year through 2005, 1,421 in 2006, then 1,300 to 2,300 a "
        "year. Complete from 2006, partial before, and the response says which." + BLANK,
    ]
    return NL.join(rows) + NL



def holdings_table() -> str:
    rows = [
        "## Institutional holdings" + BLANK,
        "SEC Form 13F. Every manager running over $100m in US equities files a holdings "
        "table within 45 days of each quarter end, and that 45-day gap is the point: the "
        "positions are dated to the quarter, the document is dated to the day it was "
        "accepted, and `as_of` returns the filing that actually existed on a given day."
        + BLANK,
        "| Field | Returns |", "|---|---|",
        "| `13f:value` | position market value in USD |",
        "| `13f:shares` | position size in shares |", "",
        "Three things this handles that a naive parse does not. Filings from January 2023 "
        "report market value in dollars and everything before reports thousands, with "
        "nothing in the document saying which, so a series across the boundary jumps by "
        "1,000x. A manager with sub-advisers files one line per manager per security, so "
        "the lines have to be summed rather than counted. And an amendment comes in two "
        "kinds: RESTATED replaces the table, NEW HOLDINGS lists only additions, so "
        "treating the second as the quarter turns an eleven-name book into one position."
        + BLANK,
        f"{len(thirteenf.MANAGERS)} managers have shortcuts; any other filer is found by "
        "name through EDGAR." + BLANK,
        "| Shortcut | Filer |", "|---|---|",
    ]
    for key, (cik, name) in thirteenf.MANAGERS.items():
        rows.append("| `" + key + "` | " + name + " (CIK " + cik + ") |")
    rows.append("")
    rows.append("13F covers long US equity, ADRs, convertibles and listed options only. "
                "Shorts, cash, bonds, commodities and foreign listings are never in it, "
                "so this is one side of a book and never the book." + BLANK)
    return NL.join(rows) + NL


def macro_table() -> str:
    rows = [
        "## Macro beyond FRED" + BLANK,
        "Two statistical agencies served directly. Both are breadth rather than vintage: "
        "neither ships a release date with the value, so their rows carry no `known_at` "
        "and say so. When the backtest needs the number that was actually published at "
        "the time, `fred:` with ALFRED vintages is the free answer and these are not."
        + BLANK,
        "### Bureau of Labor Statistics (" + str(len(bls.CURATED)) + " shortcuts, no key)"
        + BLANK,
        "CPI down to item strata, payrolls, JOLTS, wages, productivity. Any BLS series id "
        "works, not just these. Keyless requests are capped at 25 a day and "
        + str(bls.SPAN_KEYLESS) + " years per call; a free key raises that to 500 and "
        + str(bls.SPAN_KEYED) + "." + BLANK,
        "| Field | Series |", "|---|---|",
    ]
    for item in bls.CURATED:
        rows.append("| `" + item["field"] + "` | " + item["label"] + " |")
    rows += [
        "",
        "### Bureau of Economic Analysis (" + str(len(bea.TABLES))
        + " tables, free key)" + BLANK,
        "One call returns every line of a NIPA table rather than one series, which is the "
        "shape a GDP decomposition needs. GDP is published as an advance estimate, revised "
        "twice within three months, then again at every annual and benchmark revision, "
        "this endpoint serves only the current estimate." + BLANK,
        "| Field | Table |", "|---|---|",
    ]
    for table, (_, label) in bea.TABLES.items():
        rows.append("| `bea:" + table + "` | " + label + " |")
    rows.append("")
    return NL.join(rows) + NL


def signals_table() -> str:
    rows = [f"## Backtest signals ({len(bt.SIGNALS)} built in)\n",
            "| Signal | Definition |", "|---|---|"]
    for name, desc in bt.SIGNALS.items():
        rows.append(f"| `{name}` | {desc} |")
    rows.append("")
    rows.append(f"Costs are charged on turnover on every run. There is no zero-cost mode. "
                f"Returns are computed over {bt.TRADING_DAYS} trading days per year.\n")
    return "\n".join(rows)


def xbrl_note() -> str:
    return """## SEC XBRL fields

Every concept every US filer has tagged is reachable. There is no fixed list, because the
list is per-filer. A large filer exposes roughly 500 concepts across the `us-gaap` and `dei`
taxonomies. Use `discover` against an entity to see what that filer actually reports.

Common starting points: `us-gaap:Assets`, `us-gaap:Revenues`,
`us-gaap:NetIncomeLoss`, `us-gaap:StockholdersEquity`,
`us-gaap:CashAndCashEquivalentsAtCarryingValue`,
`dei:EntityCommonStockSharesOutstanding`.

**Coverage starts around 2009**, when XBRL tagging became mandatory. Anything before that is
in EDGAR as text, not as structured data. This is the single biggest limit on replicating
accounting-based anomalies, whose original samples usually start in the 1960s or 1970s.

"""


def main() -> None:
    doc = (
        HEADER
        + VERBS
        + sources_table()
        + field_routing()
        + french_table()
        + fred_table()
        + fx_table()
        + vol_table()
        + index_table()
        + delistings_table()
        + holdings_table()
        + macro_table()
        + crypto_table()
        + short_table()
        + sentiment_table()
        + xbrl_note()
        + signals_table()
        + "---\n\nCounts and coverage spans measured at generation time. "
        "Vintage redistributes none of this data; each upstream source keeps its own terms.\n"
    )
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    out = os.path.join(root, "COVERAGE.md")
    with open(out, "w", encoding="utf-8", newline="\n") as fh:
        fh.write(doc)
    print(f"wrote {out} ({len(doc):,} bytes)")


if __name__ == "__main__":
    main()
