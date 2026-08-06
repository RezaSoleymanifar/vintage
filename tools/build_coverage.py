"""Generate COVERAGE.md — what Vintage actually serves, today.

DATA_SOURCES.md is the landscape: everything free that exists, ranked, most of it
not built yet. This is the opposite document — only what is wired up right now,
generated from the registry so it cannot drift away from the code.

    uv run python tools/build_coverage.py
"""

from __future__ import annotations

import asyncio
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "src"))

from vintage import registry  # noqa: E402
from vintage.engine import backtest as bt  # noqa: E402
from vintage.sources import apewisdom, coinbase, finra, french  # noqa: E402

HEADER = """# Coverage

What Vintage serves **today**. Generated from the registry by
`tools/build_coverage.py` — if a field is listed here, it is wired up.

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
| `status` | — | cache size, keys configured, specs tried this session |

"""


def field_routing() -> str:
    rows = ["## Field prefixes\n", "How a field name routes to a source.\n",
            "| Prefix | Source | Needs an entity |", "|---|---|---|"]
    needs = {
        "price:": "yes", "fred:": "no", "french:": "no", "filing:": "yes",
        "us-gaap:": "yes", "dei:": "yes", "ifrs-full:": "yes", "srt:": "yes", "invest:": "yes",
    }
    for prefix, source in registry.PREFIXES.items():
        rows.append(f"| `{prefix}` | {source} | {needs.get(prefix, '—')} |")
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
        rows.append(f"| `{c['field']}` | {c['label']} | {spans.get(name, '—')} |")
    rows.append("")
    return "\n".join(rows) + "\n"


async def _french_spans(names: list[str]) -> dict[str, str]:
    out: dict[str, str] = {}
    for n in names:
        try:
            data = await french.load(n)
            dates = sorted(r["observed_at"] for r in data if r.get("observed_at"))
            out[n] = f"{dates[0]} → {dates[-1]}" if dates else "—"
        except Exception as exc:  # a dead upstream should not kill the doc
            out[n] = f"unavailable ({type(exc).__name__})"
    return out


def fred_table() -> str:
    rows = [f"## FRED curated series ({len(registry.CURATED)} shortcuts)\n",
            "Federal Reserve Bank of St. Louis. These are hand-picked so `discover` answers well "
            "before a key is configured — but **any** of FRED's 800,000+ series works by id, and "
            "ALFRED supplies first-release vintages.\n",
            "| Field | Series |", "|---|---|"]
    for item in registry.CURATED:
        rows.append(f"| `{item['field']}` | {item['label']} |")
    rows.append("")
    return "\n".join(rows) + "\n"


def sentiment_table() -> str:
    rows = [
        f"## Forum sentiment ({len(apewisdom.FILTERS)} scopes)\n",
        "ApeWisdom. No key. **No history endpoint upstream** — every row is stamped "
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
        "not short interest** — shares sold short during the session, including "
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


def signals_table() -> str:
    rows = [f"## Backtest signals ({len(bt.SIGNALS)} built in)\n",
            "| Signal | Definition |", "|---|---|"]
    for name, desc in bt.SIGNALS.items():
        rows.append(f"| `{name}` | {desc} |")
    rows.append("")
    rows.append(f"Costs are charged on turnover on every run — there is no zero-cost mode. "
                f"Returns are computed over {bt.TRADING_DAYS} trading days per year.\n")
    return "\n".join(rows)


def xbrl_note() -> str:
    return """## SEC XBRL fields

Every concept every US filer has tagged is reachable — there is no fixed list, because the
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
