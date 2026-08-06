"""FRED / ALFRED — 800k macro series, and the only free source of macro vintages.

ALFRED's `realtime_start` is when a value first appeared, which is a genuine
`known_at`. Most people use FRED and quietly backtest on revised GDP. This
does not.

Needs a free key: https://fred.stlouisfed.org/docs/api/api_key.html
"""

from __future__ import annotations

import os
from typing import Any

from .. import envelope
from ..http import SourceError, get_json

SOURCE = "fred"
BASE = "https://api.stlouisfed.org/fred"


def has_key() -> bool:
    return bool(os.environ.get("FRED_API_KEY"))


def _key() -> str:
    key = os.environ.get("FRED_API_KEY")
    if not key:
        raise SourceError(
            "FRED needs a free API key. Get one at "
            "https://fred.stlouisfed.org/docs/api/api_key.html and set FRED_API_KEY."
        )
    return key


async def search(query: str, limit: int = 20) -> list[dict[str, Any]]:
    url = (
        f"{BASE}/series/search?search_text={query}&api_key={_key()}"
        f"&file_type=json&limit={limit}&order_by=popularity&sort_order=desc"
    )
    payload = await get_json(url, tier="monthly")
    return [
        {
            "field": f"fred:{s['id']}",
            "label": s.get("title"),
            "units": s.get("units_short"),
            "frequency": s.get("frequency_short"),
            "start": s.get("observation_start"),
            "end": s.get("observation_end"),
            "source": SOURCE,
        }
        for s in payload.get("seriess", [])
    ]


async def observations(
    series_id: str,
    *,
    start: str | None = None,
    end: str | None = None,
    vintages: bool = True,
) -> list[dict[str, Any]]:
    """Fetch a series.

    With `vintages=True` this asks ALFRED for every revision, so each row
    carries the date that value first existed. That is what lets a macro
    backtest avoid trading on numbers revised years later.
    """
    params = [
        f"series_id={series_id}",
        f"api_key={_key()}",
        "file_type=json",
    ]
    if start:
        params.append(f"observation_start={start}")
    if end:
        params.append(f"observation_end={end}")
    if vintages:
        # The full real-time span returns one row per (date, revision).
        params.append("realtime_start=1776-07-04")
        params.append("realtime_end=9999-12-31")

    url = f"{BASE}/series/observations?" + "&".join(params)
    payload = await get_json(url, tier="daily")

    rows = []
    for obs in payload.get("observations", []):
        if obs.get("value") in (".", "", None):
            continue
        try:
            value = float(obs["value"])
        except ValueError:
            continue
        known = obs.get("realtime_start") if vintages else None
        rows.append(
            envelope.row(
                entity=f"fred:{series_id}",
                field=f"fred:{series_id}",
                observed_at=obs["date"],
                known_at=known,
                value=value,
                unit=None,
                source=SOURCE,
                source_url=f"https://fred.stlouisfed.org/series/{series_id}",
                vintage="first-release" if known else envelope.UNKNOWN_VINTAGE,
            )
        )

    if not rows:
        raise SourceError(f"FRED returned no observations for {series_id!r}")
    return rows
