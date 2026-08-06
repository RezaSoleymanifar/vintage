"""CFTC Commitments of Traders, who is positioned where, weekly and free.

The classic free positioning dataset. Every Tuesday's open interest is broken
out by trader class and published the following Friday afternoon, which makes
the reporting lag explicit rather than something you have to remember: the
observation is Tuesday, the number becomes public on Friday, and both dates are
kept.

Served from the CFTC's Socrata endpoint, so filtering happens upstream and a
request returns kilobytes rather than a full history.
"""

from __future__ import annotations

import datetime as dt
from typing import Any
from urllib.parse import quote

from .. import envelope
from ..http import SourceError, get_json

SOURCE = "cftc-cot"
LEGACY = "https://publicreporting.cftc.gov/resource/6dca-aqww.json"
HOME = "https://www.cftc.gov/MarketReports/CommitmentsofTraders/index.htm"

# The contracts people actually ask about, so `discover` answers without the
# caller knowing CFTC's exact naming.
MARKETS = {
    "SP500": "E-MINI S&P 500",
    "NASDAQ": "NASDAQ-100",
    "GOLD": "GOLD",
    "SILVER": "SILVER",
    "CRUDE": "CRUDE OIL, LIGHT SWEET",
    "NATGAS": "NATURAL GAS",
    "CORN": "CORN",
    "WHEAT": "WHEAT-SRW",
    "SOYBEANS": "SOYBEANS",
    "USD": "USD INDEX",
    "EUR": "EURO FX",
    "JPY": "JAPANESE YEN",
    "10Y": "10 YEAR U.S. TREASURY NOTES",
    "VIX": "VIX FUTURES",
}

# The positioning columns worth surfacing.
MEASURES = {
    "commercial_net": ("comm_positions_long_all", "comm_positions_short_all"),
    "noncommercial_net": ("noncomm_positions_long_all", "noncomm_positions_short_all"),
    "open_interest": ("open_interest_all", None),
}

PUBLICATION_LAG_DAYS = 3          # Tuesday observation, Friday release


def catalog() -> list[dict[str, Any]]:
    return [
        {"field": f"cot:{key}", "label": f"CFTC positioning, {name}",
         "source": SOURCE, "vintage": envelope.AS_FILED}
        for key, name in MARKETS.items()
    ]


async def positioning(market: str = "SP500", *, measure: str = "noncommercial_net",
                      limit: int = 520) -> list[dict[str, Any]]:
    """Weekly positioning for one market."""
    key = market.strip().upper()
    name = MARKETS.get(key, market.strip().upper())
    if measure not in MEASURES:
        raise SourceError(
            f"No COT measure {measure!r}. Available: {', '.join(MEASURES)}."
        )

    # Market names contain ampersands ("E-MINI S&P 500"), which silently
    # truncate the query string and come back as a 400 rather than an empty
    # result. Encode the whole clause.
    where = quote(f"starts_with(market_and_exchange_names,'{name}')", safe="")
    order = quote("report_date_as_yyyy_mm_dd DESC", safe="")
    url = f"{LEGACY}?$where={where}&$order={order}&$limit={int(limit)}"
    payload = await get_json(url, tier="daily")
    if not isinstance(payload, list) or not payload:
        raise SourceError(
            f"CFTC returned nothing for {market!r}. Known shortcuts: "
            f"{', '.join(MARKETS)}."
        )

    long_col, short_col = MEASURES[measure]
    rows = []
    for record in payload:
        stamp = (record.get("report_date_as_yyyy_mm_dd") or "")[:10]
        if not stamp:
            continue
        try:
            value = float(record.get(long_col) or 0)
            if short_col:
                value -= float(record.get(short_col) or 0)
        except (TypeError, ValueError):
            continue

        observed = dt.date.fromisoformat(stamp)
        rows.append(
            envelope.row(
                entity=key,
                field=f"cot:{measure}",
                observed_at=stamp,
                # Tuesday's positions are released the following Friday. The
                # lag is the whole reason this dataset is safe to trade on.
                known_at=(observed + dt.timedelta(days=PUBLICATION_LAG_DAYS)).isoformat(),
                value=value,
                unit="contracts",
                source=SOURCE,
                source_url=HOME,
                vintage=envelope.AS_FILED,
                market=record.get("market_and_exchange_names"),
                open_interest=record.get("open_interest_all"),
            )
        )
    if not rows:
        raise SourceError(f"CFTC had no {measure} rows for {market!r}")
    return sorted(rows, key=lambda r: r["observed_at"])


def warnings_for() -> list[str]:
    return [
        "Positions are as of Tuesday and released the following Friday afternoon. "
        "known_at reflects that three-day lag, so a backtest cannot act on a reading "
        "before it existed, which is the mistake this dataset invites."
    ]
