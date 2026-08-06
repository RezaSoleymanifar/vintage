"""US Treasury par yield curve, the risk-free curve, free and without a key.

Fourteen tenors from one month to thirty years, published each business day by
the Treasury and not revised. FRED carries the same series but needs a key for
anything beyond the curated shortlist, so this is the keyless route to a full
curve rather than a duplicate.

The CSV is published per calendar year, so a multi-year request is one call per
year. Closed years never change and cache under `immutable`.
"""

from __future__ import annotations

import csv
import io
from typing import Any

from .. import envelope
from ..http import SourceError, get_bytes

SOURCE = "us-treasury"
CSV_URL = ("https://home.treasury.gov/resource-center/data-chart-center/interest-rates/"
           "daily-treasury-rates.csv/{year}/all?type=daily_treasury_yield_curve"
           "&field_tdr_date_value={year}&page&_format=csv")
HOME = ("https://home.treasury.gov/resource-center/data-chart-center/interest-rates/"
        "TextView?type=daily_treasury_yield_curve")

# Column header -> the tenor people actually name.
TENORS = {
    "1 Mo": "1m", "1.5 Month": "6w", "2 Mo": "2m", "3 Mo": "3m", "4 Mo": "4m",
    "6 Mo": "6m", "1 Yr": "1y", "2 Yr": "2y", "3 Yr": "3y", "5 Yr": "5y",
    "7 Yr": "7y", "10 Yr": "10y", "20 Yr": "20y", "30 Yr": "30y",
}
ALIASES = {v: k for k, v in TENORS.items()}
FIRST_YEAR = 1990


def catalog() -> list[dict[str, Any]]:
    return [
        {"field": f"ust:{short}", "label": f"US Treasury par yield, {header}",
         "source": SOURCE, "vintage": envelope.AS_FILED}
        for header, short in TENORS.items()
    ]


def _iso(day: str) -> str | None:
    day = day.strip()
    if "/" in day:
        try:
            month, dom, year = day.split("/")
            return f"{int(year):04d}-{int(month):02d}-{int(dom):02d}"
        except ValueError:
            return None
    return day if day[:4].isdigit() else None


async def curve(year: int) -> list[dict[str, Any]]:
    """Every tenor, every business day of one year."""
    raw = await get_bytes(CSV_URL.format(year=year), tier="immutable")
    reader = csv.DictReader(io.StringIO(raw.decode("utf-8-sig")))
    if not reader.fieldnames:
        raise SourceError(f"Treasury returned no curve for {year}")

    rows = []
    for record in reader:
        day = _iso(record.get("Date") or "")
        if not day:
            continue
        for header, short in TENORS.items():
            cell = (record.get(header) or "").strip()
            if not cell:
                continue
            try:
                value = float(cell)
            except ValueError:
                continue
            rows.append(
                envelope.row(
                    entity=short,
                    field=f"ust:{short}",
                    observed_at=day,
                    # Published that afternoon, never revised.
                    known_at=day,
                    value=value,
                    unit="percent",
                    source=SOURCE,
                    source_url=HOME,
                    vintage=envelope.AS_FILED,
                    tenor=header,
                )
            )
    if not rows:
        raise SourceError(f"Treasury curve for {year} contained no rates")
    return rows


async def yields(tenor: str = "10y", *, start: str | None = None,
                 end: str | None = None) -> list[dict[str, Any]]:
    """One tenor across a date range, or the whole curve with tenor='all'."""
    key = tenor.strip().lower()
    if key not in ALIASES and key != "all":
        raise SourceError(
            f"No Treasury tenor {tenor!r}. Available: {', '.join(ALIASES)} or 'all'."
        )

    first = int((start or f"{FIRST_YEAR}-01-01")[:4])
    last = int((end or "2026-12-31")[:4])
    if first > last:
        raise SourceError("start is after end")

    rows: list[dict[str, Any]] = []
    for year in range(max(first, FIRST_YEAR), last + 1):
        try:
            found = await curve(year)
        except SourceError:
            continue
        for r in found:
            if key != "all" and r["entity"] != key:
                continue
            if (start and r["observed_at"] < start) or (end and r["observed_at"] > end):
                continue
            rows.append(r)

    if not rows:
        raise SourceError(f"No Treasury {tenor} yields in that window")
    return sorted(rows, key=lambda r: (r["observed_at"], r["entity"]))
