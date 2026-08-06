"""Open Source Asset Pricing, Chen & Zimmermann's replication of the anomaly zoo.

SignalDoc.csv is the scoreboard for the whole "does published alpha survive"
question: 331 documented predictors, each with the return and t-statistic the
original paper claimed, the sample it claimed them over, and a hand-written
definition precise enough to implement from.

This source answers "what did the literature claim", never "what is true now".
Its rows are claims about a fixed historical sample, so they carry the paper's
publication year as `known_at` and are `IMMUTABLE`. A 1993 claim does not
change, even when a replication disagrees with it.
"""

from __future__ import annotations

import csv
import difflib
import io
from typing import Any

from .. import envelope
from ..http import SourceError, get_bytes

SOURCE = "open-source-asset-pricing"
URL = "https://raw.githubusercontent.com/OpenSourceAP/CrossSection/master/SignalDoc.csv"
HOME = "https://www.openassetpricing.com/"

# What each signal needs in order to be computed. Vintage can serve Price
# today; the rest are honest about why they are out of reach.
DATA_CATEGORY_SUPPORT = {
    "Price": "supported, computable from price history Vintage already serves",
    "Accounting": "partial, SEC XBRL only reaches back to ~2009",
    "Analyst": "unsupported, no free estimates source exists",
    "Trading": "partial, volume yes, microstructure no",
    "13F": "planned, SEC 13F filings are free and not yet wired",
    "Event": "partial. The SEC filing stream covers some of these",
    "Options": "unsupported, historical chains are paid everywhere",
    "Other": "varies",
}


def _num(raw: str) -> float | None:
    try:
        return float(raw)
    except (TypeError, ValueError):
        return None


async def load() -> list[dict[str, Any]]:
    """Every documented predictor, as envelope rows.

    `value` is the monthly long-short return the paper claimed, in percent.
    Everything else the paper asserted rides along as extra columns so a
    replication can be scored without a second fetch.
    """
    raw = await get_bytes(URL, tier="monthly")
    try:
        text = raw.decode("utf-8-sig")
    except UnicodeDecodeError:
        text = raw.decode("latin-1")

    records = list(csv.DictReader(io.StringIO(text)))
    if not records:
        raise SourceError(f"{SOURCE} returned an empty SignalDoc")

    rows = []
    for r in records:
        acronym = (r.get("Acronym") or "").strip()
        if not acronym:
            continue
        year = (r.get("Year") or "").strip()
        category = (r.get("Cat.Data") or "").strip()
        rows.append(
            envelope.row(
                entity=acronym,
                field=f"openap:{acronym}",
                observed_at=f"{r.get('SampleEndYear', '').strip()}-12-31" or None,
                # A published claim becomes public in its publication year. That
                # is the honest known_at: nobody could trade it earlier.
                known_at=f"{year}-12-31" if year else None,
                value=_num(r.get("Return")),
                unit="percent per month, long-short",
                source=SOURCE,
                source_url=HOME,
                vintage=envelope.IMMUTABLE,
                label=(r.get("LongDescription") or acronym).strip(),
                authors=(r.get("Authors") or "").strip(),
                year=_num(year),
                journal=(r.get("Journal") or "").strip(),
                t_stat=_num(r.get("T-Stat")),
                sample_start=(r.get("SampleStartYear") or "").strip(),
                sample_end=(r.get("SampleEndYear") or "").strip(),
                data_category=category,
                vintage_support=DATA_CATEGORY_SUPPORT.get(category, "varies"),
                predictability=(r.get("Predictability in OP") or "").strip(),
                replication_quality=(r.get("Signal Rep Quality") or "").strip(),
                sign=_num(r.get("Sign")),
                stock_weight=(r.get("Stock Weight") or "").strip(),
                quantile=_num(r.get("LS Quantile")),
                holding_months=_num(r.get("Portfolio Period")),
                citations=_num(r.get("GScholarCites202509")),
                definition=(r.get("Detailed Definition") or "").strip(),
            )
        )
    return rows


async def catalog() -> list[dict[str, Any]]:
    """One catalog entry per predictor, for `discover` to search."""
    return [
        {
            "field": r["field"],
            "label": f"{r['label']}, {r['authors']} ({r['sample_start']}-{r['sample_end']})",
            "source": SOURCE,
            "claimed_monthly_return": r["value"],
            "claimed_t_stat": r["t_stat"],
            "data_category": r["data_category"],
            "vintage_support": r["vintage_support"],
            "citations": r["citations"],
            "vintage": envelope.IMMUTABLE,
        }
        for r in await load()
    ]


async def get(acronym: str) -> dict[str, Any]:
    """One predictor by acronym, with the error teaching what is available."""
    wanted = acronym.strip().lower()
    rows = await load()
    for r in rows:
        if r["entity"].lower() == wanted:
            return r

    names = [r["entity"] for r in rows]
    close = difflib.get_close_matches(acronym.strip(), names, n=6, cutoff=0.5)
    if not close:
        stem = wanted[:3]
        close = sorted(n for n in names if stem and n.lower().startswith(stem))[:6]
    raise SourceError(
        f"No OpenAP predictor called '{acronym}'. "
        + (f"Close matches: {', '.join(close)}. " if close else "")
        + f"{len(rows)} predictors are documented, use discover to search them."
    )


async def search(query: str, limit: int = 10) -> list[dict[str, Any]]:
    """Rank predictors against a plain-English query.

    Matches acronym, description and authors, then breaks ties by citation
    count: so "momentum" surfaces Jegadeesh-Titman rather than an obscure
    variant that happens to share the word.
    """
    terms = [t for t in query.lower().split() if t]
    if not terms:
        return []

    scored = []
    for item in await catalog():
        haystack = f"{item['field']} {item['label']}".lower()
        score = sum(1 for t in terms if t in haystack)
        if score:
            scored.append((score, item.get("citations") or 0.0, item))

    scored.sort(key=lambda triple: (-triple[0], -triple[1]))
    return [item for _, _, item in scored[:limit]]


def supported_only(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """The subset Vintage can actually replicate today: price-only signals."""
    return [r for r in rows if r.get("data_category") == "Price"]
