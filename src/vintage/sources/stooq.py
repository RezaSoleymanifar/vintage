"""Stooq — free daily OHLCV, plain CSV, no key, global coverage.

BLOCKED as of 2026-08: Stooq now gates programmatic access behind a
JavaScript browser check, so this adapter returns an explanatory error rather
than data. Kept because the terms are the friendliest of any free price
source, and the gate may lift. `yahoo.py` is the working spine.
"""

from __future__ import annotations

import csv
import io
from typing import Any

from .. import envelope
from ..http import SourceError, get_bytes

SOURCE = "stooq"
URL = "https://stooq.com/q/d/l/?s={symbol}&i=d"

# Stooq suffixes the market onto the symbol.
SUFFIXES = {"us": ".us", "uk": ".uk", "de": ".de", "jp": ".jp"}


def _symbol(ticker: str, market: str = "us") -> str:
    ticker = ticker.strip().lower()
    if "." in ticker or "^" in ticker:
        return ticker
    return ticker + SUFFIXES.get(market, ".us")


async def prices(
    ticker: str,
    *,
    market: str = "us",
    field: str = "close",
) -> list[dict[str, Any]]:
    """Daily bars as envelope rows. `field` is one of open/high/low/close/volume."""
    symbol = _symbol(ticker, market)
    url = URL.format(symbol=symbol)
    raw = await get_bytes(url, tier="session")
    text = raw.decode("utf-8", errors="replace")

    if "Date" not in text.split("\n", 1)[0]:
        raise SourceError(
            "Stooq is serving a JavaScript browser check instead of CSV, so it "
            "cannot be read programmatically. Vintage uses Yahoo for prices; "
            "this adapter stays in case the gate lifts."
        )

    column = field.strip().lower().capitalize()
    reader = csv.DictReader(io.StringIO(text))
    if column not in (reader.fieldnames or []):
        raise SourceError(
            f"Stooq returns {reader.fieldnames}; {field!r} is not one of them."
        )

    rows = []
    for record in reader:
        try:
            value = float(record[column])
        except (TypeError, ValueError):
            continue
        rows.append(
            envelope.row(
                entity=ticker.strip().upper(),
                field=f"price:{field.lower()}",
                observed_at=record["Date"],
                # A daily bar is knowable at that day's close. Adjustments are
                # applied retroactively, so the level is not strictly as-known.
                known_at=record["Date"],
                value=value,
                unit="USD" if market == "us" else market.upper(),
                source=SOURCE,
                source_url=url,
                vintage="adjusted-retroactively",
            )
        )

    if not rows:
        raise SourceError(f"Stooq returned no rows for {symbol}")
    return rows
