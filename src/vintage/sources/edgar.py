"""SEC EDGAR, the only free point-in-time fundamentals that exist.

Every XBRL fact carries `filed`, the day the number became public. That maps
straight onto `known_at`, which is what makes look-ahead prevention real
rather than aspirational.
"""

from __future__ import annotations

from typing import Any

from .. import envelope
from ..http import SourceError, get_json

SOURCE = "sec-edgar-xbrl"

TICKER_MAP_URL = "https://www.sec.gov/files/company_tickers.json"
EXCHANGE_MAP_URL = "https://www.sec.gov/files/company_tickers_exchange.json"
FACTS_URL = "https://data.sec.gov/api/xbrl/companyfacts/CIK{cik}.json"
FRAMES_URL = "https://data.sec.gov/api/xbrl/frames/{taxonomy}/{concept}/{unit}/{frame}.json"
SUBMISSIONS_URL = "https://data.sec.gov/submissions/CIK{cik}.json"


async def ticker_map() -> dict[str, dict[str, Any]]:
    raw = await get_json(TICKER_MAP_URL, tier="monthly")
    return {
        str(e["ticker"]).upper(): {"cik": str(e["cik_str"]).zfill(10), "name": e["title"]}
        for e in raw.values()
    }


async def exchange_map() -> dict[str, str]:
    """Ticker -> listing venue, when SEC knows it."""
    try:
        raw = await get_json(EXCHANGE_MAP_URL, tier="monthly")
    except SourceError:
        return {}
    fields = raw.get("fields", [])
    try:
        t_idx, e_idx = fields.index("ticker"), fields.index("exchange")
    except ValueError:
        return {}
    out = {}
    for entry in raw.get("data", []):
        ticker, exchange = entry[t_idx], entry[e_idx]
        if ticker and exchange:
            out[str(ticker).upper()] = exchange
    return out


async def resolve(identifier: str) -> dict[str, Any]:
    mapping = await ticker_map()
    key = identifier.strip().upper()

    if key in mapping:
        hit = {"ticker": key, **mapping[key]}
    elif key.replace("CIK", "").isdigit():
        cik = key.replace("CIK", "").zfill(10)
        match = next(
            ((t, v) for t, v in mapping.items() if v["cik"] == cik), None
        )
        if not match:
            raise SourceError(f"No EDGAR filer with CIK {cik}")
        hit = {"ticker": match[0], **match[1]}
    else:
        near = [t for t in mapping if t.startswith(key[:2])][:8]
        raise SourceError(
            f"No SEC filer maps to {key!r}. It may be a fund, a foreign listing, "
            f"or delisted before EDGAR's ticker file was built. "
            f"Similar tickers on file: {', '.join(sorted(near)) or 'none'}"
        )

    hit["exchange"] = (await exchange_map()).get(hit["ticker"])
    hit["entity"] = f"CIK{hit['cik']}"
    return hit


async def company_facts(cik: str) -> dict[str, Any]:
    return await get_json(FACTS_URL.format(cik=cik), tier="daily")


def catalog(facts: dict[str, Any]) -> list[dict[str, Any]]:
    """Every concept this filer actually reports, most-populated first."""
    out = []
    for taxonomy, entries in facts.get("facts", {}).items():
        for concept, body in entries.items():
            out.append(
                {
                    "field": f"{taxonomy}:{concept}",
                    "label": body.get("label"),
                    "units": list(body.get("units", {}).keys()),
                    "observations": sum(len(v) for v in body.get("units", {}).values()),
                    "source": SOURCE,
                }
            )
    return sorted(out, key=lambda c: -c["observations"])


def to_rows(
    facts: dict[str, Any],
    field: str,
    entity: str,
    *,
    form: str | None = None,
) -> list[dict[str, Any]]:
    """Pull one field out of a company-facts payload, as envelope rows.

    `field` is "taxonomy:concept" ("us-gaap:Assets"). A bare concept name is
    accepted and searched across taxonomies.
    """
    taxonomy, _, concept = field.rpartition(":")
    url = FACTS_URL.format(cik=entity.replace("CIK", ""))
    rows = []

    for tax_name, entries in facts.get("facts", {}).items():
        if taxonomy and tax_name != taxonomy:
            continue
        body = entries.get(concept)
        if body is None:
            continue
        for unit, observations in body.get("units", {}).items():
            for obs in observations:
                if form and obs.get("form") != form:
                    continue
                rows.append(
                    envelope.row(
                        entity=entity,
                        field=f"{tax_name}:{concept}",
                        observed_at=obs.get("end"),
                        known_at=obs.get("filed"),
                        value=obs.get("val"),
                        unit=unit,
                        source=SOURCE,
                        source_url=url,
                        period_start=obs.get("start"),
                        fiscal_year=obs.get("fy"),
                        fiscal_period=obs.get("fp"),
                        form=obs.get("form"),
                        accession=obs.get("accn"),
                    )
                )

    return sorted(rows, key=lambda r: (r["observed_at"] or "", r["known_at"] or ""))


async def recent_filings(cik: str, limit: int = 40) -> list[dict[str, Any]]:
    """Filing stream for an entity, the event timeline's backbone."""
    data = await get_json(SUBMISSIONS_URL.format(cik=cik), tier="session")
    recent = data.get("filings", {}).get("recent", {})
    forms = recent.get("form", [])
    entity = f"CIK{cik}"

    out = []
    for i in range(min(limit, len(forms))):
        accession = recent["accessionNumber"][i].replace("-", "")
        out.append(
            envelope.row(
                entity=entity,
                field=f"filing:{forms[i]}",
                observed_at=recent["reportDate"][i] or recent["filingDate"][i],
                known_at=recent["filingDate"][i],
                value=recent["primaryDocDescription"][i] or forms[i],
                unit=None,
                source="sec-edgar-filings",
                source_url=(
                    f"https://www.sec.gov/Archives/edgar/data/{int(cik)}/{accession}/"
                    f"{recent['primaryDocument'][i]}"
                ),
                form=forms[i],
                accepted=recent["acceptanceDateTime"][i],
            )
        )
    return out
