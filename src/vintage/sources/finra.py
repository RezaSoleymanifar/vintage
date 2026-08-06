"""FINRA daily short sale volume — free, daily, and almost nobody glues it.

FINRA publishes one pipe-delimited file per trading day covering every
consolidated-tape symbol: short volume, short-exempt volume, total volume.
It is genuinely predictive, genuinely free, and genuinely annoying to use,
which is exactly the shape of thing this project exists to absorb.

Vintage-wise this is clean. Each file is published after that session closes
and is never revised, so `known_at` is the publication date and rows are
`AS_FILED`. Unlike the equity adjusted closes next door, nothing here gets
rewritten later.

The cost is one HTTP request per trading day, so `days` is deliberately small
by default and the response says how far back it actually reached.
"""

from __future__ import annotations

from datetime import date, timedelta
from typing import Any

from .. import envelope
from ..http import SourceError, get_bytes

SOURCE = "finra-short-volume"
BASE = "https://cdn.finra.org/equity/regsho/daily"
HOME = "https://www.finra.org/finra-data/browse-catalog/short-sale-volume-data"

DEFAULT_DAYS = 20
MAX_DAYS = 90


def _url(day: date) -> str:
    return f"{BASE}/CNMSshvol{day.strftime('%Y%m%d')}.txt"


async def short_volume(
    entity: str,
    days: int = DEFAULT_DAYS,
    field: str = "short_ratio",
) -> list[dict[str, Any]]:
    """Daily short volume for one symbol, newest `days` trading days.

    `field` is one of short_ratio, short_volume, total_volume, exempt_volume.
    The ratio is the one people actually want: short volume as a share of
    total reported volume that session.
    """
    fields = {"short_ratio", "short_volume", "total_volume", "exempt_volume"}
    if field not in fields:
        raise SourceError(f"Unknown FINRA field {field!r}. Try: {', '.join(sorted(fields))}.")

    symbol = entity.strip().upper()
    days = max(1, min(int(days), MAX_DAYS))

    rows: list[dict[str, Any]] = []
    misses = 0
    day = date.today()

    # Walk backwards. Weekends and holidays 404, which is how we find sessions
    # without shipping a market calendar.
    while len(rows) < days and misses < 12:
        day -= timedelta(days=1)
        if day.weekday() >= 5:
            continue
        try:
            raw = await get_bytes(_url(day), tier="immutable")
        except SourceError:
            misses += 1
            continue

        hit = _extract(raw.decode("utf-8", "replace"), symbol)
        if hit is None:
            misses += 1
            continue

        misses = 0
        short, exempt, total = hit
        value = {
            "short_ratio": round(short / total, 6) if total else None,
            "short_volume": short,
            "exempt_volume": exempt,
            "total_volume": total,
        }[field]

        rows.append(
            envelope.row(
                entity=symbol,
                field=f"short:{field}",
                observed_at=day.isoformat(),
                # Published after that session closes, and never revised.
                known_at=(day + timedelta(days=1)).isoformat(),
                value=value,
                unit="ratio" if field == "short_ratio" else "shares",
                source=SOURCE,
                source_url=_url(day),
                vintage=envelope.AS_FILED,
                short_volume=short,
                exempt_volume=exempt,
                total_volume=total,
            )
        )

    if not rows:
        raise SourceError(
            f"FINRA reported no short volume for {symbol} in the last {days} sessions. "
            "The file covers consolidated-tape equities — check the symbol, and note "
            "that today's file appears only after the session closes."
        )
    return sorted(rows, key=lambda r: r["observed_at"])


def _extract(text: str, symbol: str) -> tuple[float, float, float] | None:
    """Pull one symbol out of a ~500KB pipe-delimited daily file."""
    for line in text.splitlines():
        if not line.startswith(("Date|", "20")):
            continue
        parts = line.split("|")
        if len(parts) < 5 or parts[1].strip().upper() != symbol:
            continue
        try:
            return float(parts[2]), float(parts[3]), float(parts[4])
        except ValueError:
            return None
    return None


def warnings_for(rows: list[dict[str, Any]]) -> list[str]:
    return [
        "Short volume is not short interest. This counts shares sold short during "
        "the session, including market-maker hedging that is flat by the close — "
        "it is a flow measure, not a measure of outstanding bearish positioning.",
        f"Covers consolidated-tape venues only; off-exchange activity is partial. "
        f"{len(rows)} session(s) returned.",
    ]
