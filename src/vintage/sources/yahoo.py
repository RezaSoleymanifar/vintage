"""Yahoo Finance chart API — the price spine.

Stooq was the first choice because it publishes terms, but as of 2026 it
gates programmatic access behind a JavaScript browser check. Yahoo's chart
endpoint is unofficial and its terms are grey; it is used here because it is
the only free source of long adjusted daily history that still answers.

Adjusted close is used for returns: it folds in splits and dividends, which
is what a total-return backtest needs. It is also revised retroactively on
every corporate action, so these rows carry no honest `known_at` and say so.
"""

from __future__ import annotations

from typing import Any

from .. import envelope
from ..http import SourceError, get_json

SOURCE = "yahoo-finance"
CHART = (
    "https://query1.finance.yahoo.com/v8/finance/chart/{symbol}"
    "?period1=0&period2=9999999999&interval=1d&events=div%2Csplit"
)

BROWSER_UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/120.0 Safari/537.36"
)


async def prices(ticker: str, *, field: str = "close") -> list[dict[str, Any]]:
    """Daily bars as envelope rows.

    `field` is one of open/high/low/close/volume/adjclose. Backtests use
    adjclose; `close` is what a human means when they ask for the price.
    """
    symbol = ticker.strip().upper()
    url = CHART.format(symbol=symbol)

    payload = await get_json(url, tier="session", headers={"User-Agent": BROWSER_UA})
    chart = payload.get("chart") or {}

    if chart.get("error"):
        raise SourceError(
            f"Yahoo has no history for {symbol!r}: {chart['error'].get('description')}"
        )
    results = chart.get("result") or []
    if not results:
        raise SourceError(f"Yahoo returned nothing for {symbol!r}")

    result = results[0]
    stamps = result.get("timestamp") or []
    quote = (result.get("indicators", {}).get("quote") or [{}])[0]
    adjusted = (result.get("indicators", {}).get("adjclose") or [{}])[0]
    currency = result.get("meta", {}).get("currency", "USD")

    key = field.strip().lower()
    if key in ("adjclose", "adj_close", "adjusted"):
        series = adjusted.get("adjclose") or []
        key = "adjclose"
    else:
        series = quote.get(key) or []

    if not series:
        available = sorted(set(quote) | {"adjclose"})
        raise SourceError(
            f"Yahoo returned no {field!r} series for {symbol}. Available: {available}"
        )

    import datetime as _dt

    rows = []
    for stamp, value in zip(stamps, series):
        if value is None:
            continue
        date = _dt.datetime.fromtimestamp(stamp, _dt.timezone.utc).date().isoformat()
        rows.append(
            envelope.row(
                entity=symbol,
                field=f"price:{key}",
                observed_at=date,
                # Knowable at that day's close. Adjustments are applied
                # backwards, so the level is not strictly as-known.
                known_at=date,
                value=round(float(value), 6),
                unit=currency,
                source=SOURCE,
                source_url=f"https://finance.yahoo.com/quote/{symbol}/history",
                vintage="adjusted-retroactively"
                if key == "adjclose"
                else envelope.AS_FILED,
            )
        )

    if not rows:
        raise SourceError(f"Yahoo returned an empty series for {symbol}")
    return rows
