"""Coinbase Exchange — crypto OHLCV, free and without a key.

Crypto is the one asset class where retail gets institutional-grade history
for nothing, so it belongs here. Binance returns 451 from US addresses, and
Kraken works but pages awkwardly; Coinbase is the clean default.

On vintage: a trade print is not restated, so `known_at` equals the close of
the bar and these rows are `AS_FILED` rather than adjusted-in-hindsight. That
makes crypto prices *more* honestly point-in-time than equity adjusted closes.

What crypto does have, far worse than equities, is survivorship: thousands of
tokens have died and are simply absent from any exchange's product list. Any
cross-sectional crypto backtest built from a current product list is a
survivors-only test, and `products()` says so.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any

from .. import envelope
from ..http import SourceError, get_json

SOURCE = "coinbase-exchange"
BASE = "https://api.exchange.coinbase.com"
HOME = "https://exchange.coinbase.com/"

GRANULARITY = {"1d": 86400, "6h": 21600, "1h": 3600, "15m": 900, "5m": 300, "1m": 60}
MAX_CANDLES = 300          # Coinbase's hard per-request cap
MAX_REQUESTS = 12          # ~10 years of daily bars, and a bound on politeness

FIELDS = {"open": 3, "high": 2, "low": 1, "close": 4, "volume": 5}


def normalize(symbol: str) -> str:
    """BTC, btc-usd and BTC/USD all mean the same product."""
    s = symbol.strip().upper().replace("/", "-")
    return s if "-" in s else f"{s}-USD"


async def products() -> list[dict[str, Any]]:
    """Every tradable product. Currently listed only — see the module docstring."""
    payload = await get_json(f"{BASE}/products", tier="daily")
    return [
        {
            "field": f"crypto:{p['id']}",
            "label": f"{p.get('base_currency')} / {p.get('quote_currency')}",
            "source": SOURCE,
            "status": p.get("status"),
        }
        for p in payload
        if isinstance(p, dict) and p.get("id") and p.get("status") == "online"
    ]


async def candles(
    symbol: str,
    field: str = "close",
    interval: str = "1d",
    limit: int = 500,
) -> list[dict[str, Any]]:
    """OHLCV bars, oldest first, paged backwards from now."""
    if field not in FIELDS:
        raise SourceError(f"Unknown crypto field {field!r}. Try: {', '.join(FIELDS)}.")
    if interval not in GRANULARITY:
        raise SourceError(
            f"Unknown interval {interval!r}. Try: {', '.join(GRANULARITY)}."
        )

    product = normalize(symbol)
    seconds = GRANULARITY[interval]
    idx = FIELDS[field]

    seen: dict[int, list[Any]] = {}
    end = datetime.now(timezone.utc)

    for _ in range(MAX_REQUESTS):
        if len(seen) >= limit:
            break
        start = end - timedelta(seconds=seconds * MAX_CANDLES)
        url = (
            f"{BASE}/products/{product}/candles"
            f"?granularity={seconds}"
            f"&start={start.isoformat().replace('+00:00', 'Z')}"
            f"&end={end.isoformat().replace('+00:00', 'Z')}"
        )
        batch = await get_json(url, tier="session")
        if isinstance(batch, dict):                       # Coinbase errors as an object
            raise SourceError(
                f"Coinbase rejected {product}: {batch.get('message', batch)}. "
                "Check the product id — try BTC-USD."
            )
        if not batch:
            break
        for row in batch:
            seen[int(row[0])] = row
        end = start

    if not seen:
        raise SourceError(
            f"No candles for {product}. Use discover to list tradable products."
        )

    rows = []
    for ts in sorted(seen)[-limit:]:
        row = seen[ts]
        closed = datetime.fromtimestamp(ts + seconds, tz=timezone.utc)
        rows.append(
            envelope.row(
                entity=product,
                field=f"crypto:{field}",
                observed_at=datetime.fromtimestamp(ts, tz=timezone.utc).date().isoformat(),
                # A trade print is never restated, and the bar is knowable the
                # moment it closes. No hindsight adjustment, unlike equity
                # adjusted closes.
                known_at=closed.isoformat(timespec="seconds"),
                value=float(row[idx]),
                unit="USD" if field != "volume" else "base units",
                source=SOURCE,
                source_url=f"{HOME}trade/{product}",
                vintage=envelope.AS_FILED,
                interval=interval,
            )
        )
    return rows


def warnings_for(symbol: str) -> list[str]:
    return [
        "Crypto universes here are currently-listed products only. Thousands of "
        "tokens have delisted or died and are absent entirely, so any "
        "cross-sectional crypto backtest built from this list is survivors-only "
        "— a worse bias than equities, not a milder one.",
        "Coinbase pricing is one venue. Cross-exchange spreads in crypto are real "
        "and can be wide for thin pairs.",
    ]
