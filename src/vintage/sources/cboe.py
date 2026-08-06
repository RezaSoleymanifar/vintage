"""CBOE volatility indices, VIX and its family, free and complete.

VIX back to 1990, published by the exchange that computes it. Index levels are
calculated from that session's option prices and are not revised, so `known_at`
is the session date and these rows are `AS_FILED`.

Worth being precise about what this is. It is the *index*, not the options
underneath it. Historical option chains are paid everywhere and remain one of
the gaps this project does not pretend to fill. What the VIX family does give
you, for nothing, is the term structure and the skew, enough for regime work,
volatility-managed portfolios and most of what a paper means by "conditioning
on volatility".

Two file shapes come back from the same endpoint. The tradable-index files
carry OHLC; VVIX and SKEW carry a single column. Both are handled.
"""

from __future__ import annotations

import csv
import io
from typing import Any

from .. import envelope
from ..http import SourceError, get_bytes

SOURCE = "cboe-indices"
CSV_URL = "https://cdn.cboe.com/api/global/us_indices/daily_prices/{symbol}_History.csv"
HOME = "https://www.cboe.com/tradable_products/vix/"

INDICES = {
    "VIX": "S&P 500 30-day implied volatility, from 1990",
    "VIX9D": "S&P 500 9-day implied volatility, from 2011",
    "VIX3M": "S&P 500 3-month implied volatility, from 2009",
    "VIX6M": "S&P 500 6-month implied volatility",
    "VVIX": "Volatility of VIX itself, from 2006",
    "SKEW": "Tail-risk skew of S&P 500 options, from 1990",
    "VXN": "Nasdaq-100 implied volatility",
    "RVX": "Russell 2000 implied volatility",
    "OVX": "Crude oil ETF implied volatility",
    "GVZ": "Gold ETF implied volatility",
}


def catalog() -> list[dict[str, Any]]:
    return [
        {"field": f"vol:{symbol}", "label": label, "source": SOURCE,
         "vintage": envelope.AS_FILED}
        for symbol, label in INDICES.items()
    ]


def _iso(day: str) -> str | None:
    """CBOE writes MM/DD/YYYY; some files use ISO already."""
    day = day.strip()
    if not day:
        return None
    if "/" in day:
        try:
            month, dom, year = day.split("/")
            return f"{int(year):04d}-{int(month):02d}-{int(dom):02d}"
        except ValueError:
            return None
    return day if day[:4].isdigit() else None


async def levels(symbol: str = "VIX", *, field: str = "close",
                 start: str | None = None, end: str | None = None) -> list[dict[str, Any]]:
    """Daily index levels."""
    key = symbol.strip().upper()
    if key not in INDICES:
        raise SourceError(
            f"No CBOE index called {symbol!r}. Available: {', '.join(INDICES)}."
        )

    raw = await get_bytes(CSV_URL.format(symbol=key), tier="daily")
    reader = csv.DictReader(io.StringIO(raw.decode("utf-8-sig")))
    columns = [c.strip() for c in (reader.fieldnames or [])]
    if not columns:
        raise SourceError(f"CBOE returned an empty file for {key}")

    wanted = field.strip().lower()
    lookup = {c.lower(): c for c in columns}
    # Single-column files (VVIX, SKEW) name the column after the index itself.
    column = lookup.get(wanted) or lookup.get(key.lower())
    if column is None:
        raise SourceError(
            f"{key} has no {field!r} column. Available: "
            f"{', '.join(c for c in columns if c.lower() != 'date')}."
        )

    date_col = lookup.get("date") or columns[0]
    rows = []
    for record in reader:
        day = _iso(record.get(date_col) or "")
        if not day or (start and day < start) or (end and day > end):
            continue
        cell = (record.get(column) or "").strip()
        if not cell:
            continue
        try:
            value = float(cell)
        except ValueError:
            continue
        rows.append(
            envelope.row(
                entity=key,
                field=f"vol:{key}",
                observed_at=day,
                # Computed from that session's option prices, never revised.
                known_at=day,
                value=round(value, 6),
                unit="index level",
                source=SOURCE,
                source_url=HOME,
                vintage=envelope.AS_FILED,
                column=column,
            )
        )

    if not rows:
        raise SourceError(f"CBOE returned no {key} levels in that window")
    return rows


def warnings_for(symbol: str) -> list[str]:
    return [
        f"{symbol.upper()} is an index level, not an option chain. Historical "
        "chains are paid at every vendor, so anything needing individual strikes "
        "cannot be built from free data."
    ]
