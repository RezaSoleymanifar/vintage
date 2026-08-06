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

from .. import envelope, pit
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


async def _chart(symbol: str) -> dict[str, Any]:
    payload = await get_json(CHART.format(symbol=symbol), tier="session",
                             headers={"User-Agent": BROWSER_UA})
    chart = payload.get("chart") or {}
    if chart.get("error"):
        raise SourceError(
            f"Yahoo has no history for {symbol!r}: {chart['error'].get('description')}")
    results = chart.get("result") or []
    if not results:
        raise SourceError(f"Yahoo returned nothing for {symbol!r}")
    return results[0]


async def corporate_actions(ticker: str) -> list[dict[str, Any]]:
    """Every split and dividend Yahoo knows about, dated."""
    return pit.actions(await _chart(ticker.strip().upper()))


async def pit_prices(ticker: str, *, as_of: str | None = None) -> list[dict[str, Any]]:
    """Adjusted closes as they stood on `as_of`.

    Reconstructed from the raw close plus dated corporate actions, so nothing
    in the level depends on information published after that date. This is the
    only price series here that is honestly point-in-time.
    """
    symbol = ticker.strip().upper()
    result = await _chart(symbol)
    stamps = result.get("timestamp") or []
    quote = (result.get("indicators", {}).get("quote") or [{}])[0]
    raw = quote.get("close") or []
    if not raw:
        raise SourceError(f"Yahoo returned no raw close for {symbol}")

    import datetime as _dt
    closes = {
        _dt.datetime.fromtimestamp(s, _dt.timezone.utc).date().isoformat(): float(v)
        for s, v in zip(stamps, raw) if v is not None
    }
    return pit.rows(symbol, closes, pit.actions(result), as_of=as_of,
                    currency=result.get("meta", {}).get("currency", "USD"))


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
