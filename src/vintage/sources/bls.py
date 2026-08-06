"""Bureau of Labor Statistics, CPI, employment, wages, straight from the source.

FRED mirrors the headline BLS series, but only the headline ones, and it needs a
key. BLS itself is keyless and carries the detail underneath: CPI broken out to
several hundred item strata, employment by industry down to six-digit NAICS,
wages by occupation and metro. That detail is the reason this exists alongside
`fred:`.

What it does not carry is a release date. The payload gives the reference period
and the value, never the day that value was published, so these rows have no
`known_at` and say so. For a point-in-time CPI, ALFRED via `fred:CPIAUCSL` has
the vintages and this does not. Guessing a publication date to make the column
look full would be the one thing this project is built not to do.
"""

from __future__ import annotations

import calendar
import datetime as dt
import os
from typing import Any

from .. import envelope
from ..http import SourceError, post_json

SOURCE = "bls"
V1 = "https://api.bls.gov/publicAPI/v1/timeseries/data/"
V2 = "https://api.bls.gov/publicAPI/v2/timeseries/data/"
HOME = "https://data.bls.gov/timeseries/{series}"

# Years per request. BLS enforces these, and the GET route quietly ignores a
# window it does not like rather than refusing it, which is why every call here
# goes through POST.
SPAN_KEYLESS = 10
SPAN_KEYED = 20
MAX_CHUNKS = 5

# The keyless tier is capped at 25 series and 10 years per day, which is why
# `discover` leans on this shortlist rather than a search endpoint.
CURATED = [
    {"field": "bls:CUUR0000SA0", "label": "CPI-U, all items, not seasonally adjusted"},
    {"field": "bls:CUSR0000SA0", "label": "CPI-U, all items, seasonally adjusted"},
    {"field": "bls:CUSR0000SA0L1E", "label": "Core CPI, less food and energy"},
    {"field": "bls:CUUR0000SAF1", "label": "CPI, food"},
    {"field": "bls:CUUR0000SAH1", "label": "CPI, shelter"},
    {"field": "bls:CUUR0000SETB01", "label": "CPI, gasoline (all types)"},
    {"field": "bls:WPUFD4", "label": "PPI, final demand"},
    {"field": "bls:LNS14000000", "label": "Unemployment rate, 16 and over"},
    {"field": "bls:LNS11300000", "label": "Labor force participation rate"},
    {"field": "bls:LNS12300060", "label": "Employment-population ratio, 25-54"},
    {"field": "bls:CES0000000001", "label": "Total nonfarm payrolls"},
    {"field": "bls:CES0500000003", "label": "Average hourly earnings, private"},
    {"field": "bls:CES0500000002", "label": "Average weekly hours, private"},
    {"field": "bls:JTS000000000000000JOL", "label": "Job openings, total nonfarm (JOLTS)"},
    {"field": "bls:JTS000000000000000QUR", "label": "Quits rate, total nonfarm (JOLTS)"},
    {"field": "bls:PRS85006092", "label": "Nonfarm labor productivity, percent change"},
    {"field": "bls:CIU1010000000000A", "label": "Employment cost index, compensation"},
]

# Periods that are not a month: BLS folds annual and quarterly figures into the
# same series, and M13 in particular is the annual average masquerading as a
# thirteenth month. Reading it as a monthly print double-counts the year.
ANNUAL_PERIODS = {"M13", "A01", "Q05"}
QUARTER_END = {"Q01": 3, "Q02": 6, "Q03": 9, "Q04": 12}
SEMI_END = {"S01": 6, "S02": 12, "S03": 12}


def has_key() -> bool:
    return bool(os.environ.get("BLS_API_KEY"))


def catalog() -> list[dict[str, Any]]:
    return [
        {**item, "source": SOURCE, "vintage": envelope.UNKNOWN_VINTAGE}
        for item in CURATED
    ]


def period_end(year: str, period: str) -> tuple[str | None, str]:
    """Map a BLS (year, period) pair to a date and a frequency label."""
    try:
        y = int(year)
    except (TypeError, ValueError):
        return None, "unknown"

    if period in ANNUAL_PERIODS:
        return f"{y:04d}-12-31", "annual"
    if period in QUARTER_END:
        month = QUARTER_END[period]
        return f"{y:04d}-{month:02d}-{calendar.monthrange(y, month)[1]:02d}", "quarterly"
    if period in SEMI_END:
        month = SEMI_END[period]
        return f"{y:04d}-{month:02d}-{calendar.monthrange(y, month)[1]:02d}", "semiannual"
    if period.startswith("M") and period[1:].isdigit():
        month = int(period[1:])
        if 1 <= month <= 12:
            last = calendar.monthrange(y, month)[1]
            return f"{y:04d}-{month:02d}-{last:02d}", "monthly"
    return None, "unknown"


def windows(start: str | None, end: str | None, span: int) -> list[tuple[int, int]]:
    """Split a requested year range into chunks the API will accept."""
    if not start and not end:
        return []
    # BLS refuses a year it has not reached, so an open-ended request stops at
    # the current one rather than at some far horizon.
    this_year = dt.date.today().year
    first = int((start or "1913")[:4])
    last = min(int(end[:4]) if end else this_year, this_year)
    if first > last:
        raise SourceError("start is after end")

    out = []
    year = last
    while year >= first and len(out) < MAX_CHUNKS:
        lower = max(first, year - span + 1)
        out.append((lower, year))
        year = lower - 1
    return out


async def series(series_id: str, *, start: str | None = None,
                 end: str | None = None) -> list[dict[str, Any]]:
    """One BLS series, as rows."""
    sid = series_id.strip().upper()
    if not sid:
        raise SourceError("A BLS series id looks like CUUR0000SA0 or LNS14000000.")

    key = os.environ.get("BLS_API_KEY")
    url = V2 if key else V1
    span = SPAN_KEYED if key else SPAN_KEYLESS

    # No window asked for means the API default, which is the last three years.
    points: list[dict[str, Any]] = []
    for lower, upper in windows(start, end, span) or [(None, None)]:
        body: dict[str, Any] = {"seriesid": [sid]}
        if lower:
            body["startyear"], body["endyear"] = str(lower), str(upper)
        if key:
            body["registrationkey"] = key

        payload = await post_json(url, body, tier="daily")
        status = payload.get("status")
        if status != "REQUEST_SUCCEEDED":
            detail = "; ".join(payload.get("message") or []) or status or "no reason given"
            raise SourceError(
                f"BLS refused {sid}: {detail}. The keyless tier allows 25 queries a day "
                f"and {SPAN_KEYLESS} years of history per call; a free key at "
                "https://data.bls.gov/registrationEngine/ raises it to 500 and "
                f"{SPAN_KEYED}, and goes in BLS_API_KEY."
            )

        found = (payload.get("Results") or {}).get("series") or []
        if found:
            points.extend(found[0].get("data") or [])

    if not points:
        raise SourceError(
            f"BLS has no data for {sid!r} in that window. Series ids are structured, "
            "not guessable, browse them at https://www.bls.gov/help/hlpforma.htm."
        )

    rows = []
    for point in points:
        observed, freq = period_end(point.get("year"), point.get("period") or "")
        if not observed:
            continue
        try:
            value = float(str(point.get("value")).replace(",", ""))
        except (TypeError, ValueError):
            continue
        codes = [f.get("code") for f in (point.get("footnotes") or []) if f.get("code")]
        rows.append(
            envelope.row(
                entity=sid,
                field=f"bls:{sid}",
                observed_at=observed,
                # BLS publishes no release date with the value. Never invented.
                known_at=None,
                value=value,
                unit=None,
                source=SOURCE,
                source_url=HOME.format(series=sid),
                vintage=envelope.UNKNOWN_VINTAGE,
                period=point.get("period"),
                period_name=point.get("periodName"),
                frequency=freq,
                footnotes=codes or None,
            )
        )

    if not rows:
        raise SourceError(f"BLS returned only unparseable periods for {sid!r}")

    # A bare year as `end` must mean the end of that year, not its first day.
    floor = start if not start or len(start) > 4 else f"{start}-01-01"
    ceiling = end if not end or len(end) > 4 else f"{end}-12-31"
    kept = [
        r for r in rows
        if (not floor or r["observed_at"] >= floor)
        and (not ceiling or r["observed_at"] <= ceiling)
    ]
    if not kept:
        dates = [r["observed_at"] for r in rows]
        span = f"{min(dates)} to {max(dates)}"
        raise SourceError(
            f"BLS has {sid} for {span}, and nothing inside the window you asked for."
        )

    seen, unique = set(), []
    for row in sorted(kept, key=lambda r: (r["observed_at"], r["period"] or "")):
        key = (row["observed_at"], row["period"])
        if key not in seen:
            seen.add(key)
            unique.append(row)
    return unique


def warnings_for(series_id: str, rows: list[dict[str, Any]]) -> list[str]:
    notes = [
        "BLS ships the value but not its release date, so these rows carry no known_at "
        "and cannot be filtered point-in-time. Seasonally adjusted series are revised "
        "every year. For a first-release CPI or payrolls figure use fred:, ALFRED has "
        "the vintages and this endpoint does not."
    ]
    annual = sum(1 for r in rows if r.get("frequency") == "annual")
    if annual:
        notes.append(
            f"{annual} row(s) are annual averages that BLS files as period M13/Q05/A01, "
            "not monthly prints. They are labelled `frequency: annual`, summing them "
            "with the monthly rows counts the year twice."
        )
    if not has_key():
        notes.append(
            "No BLS_API_KEY set, so this used the keyless tier: 25 queries a day and "
            "10 years of history per call."
        )
    return notes
