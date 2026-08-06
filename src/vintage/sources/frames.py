"""SEC XBRL frames — one concept, every company, one request.

This is the difference between a lookup and a factor engine. `companyfacts`
answers "what were Apple's assets"; frames answers "what were assets for all
6,289 filers in Q1 2023", which is the shape a cross-sectional sort needs. One
840 KB call replaces six thousand.

One honest caveat, and it is the reason these rows do not claim a vintage. The
frame carries the accession number of the filing each value came from but not
its filing date, so `known_at` is unavailable from the payload alone. Rather
than invent one, rows are flagged `UNKNOWN_VINTAGE` and keep the accession, so
anyone who needs the date can resolve it. Inventing a date here would quietly
undo the point of the project.
"""

from __future__ import annotations

import re
from typing import Any

from .. import envelope
from ..http import SourceError, get_json

SOURCE = "sec-xbrl-frames"
URL = "https://data.sec.gov/api/xbrl/frames/{taxonomy}/{tag}/{unit}/{period}.json"

# CY2023Q1  flow over the quarter
# CY2023Q1I instant, i.e. a balance-sheet date
# CY2023     flow over the year
PERIOD = re.compile(r"^CY\d{4}(Q[1-4]I?)?$")

INSTANT_HINTS = ("Assets", "Liabilities", "StockholdersEquity", "Cash",
                 "Inventory", "Goodwill", "Debt", "Shares")


def period_for(year: int, quarter: int | None = None, *, instant: bool = False) -> str:
    """Build the period key the API expects."""
    if quarter is None:
        return f"CY{year}"
    return f"CY{year}Q{quarter}" + ("I" if instant else "")


def guess_instant(tag: str) -> bool:
    """Balance-sheet concepts are instants; income and cash-flow are durations.

    Getting this backwards returns an empty frame rather than an error, which
    is a confusing way to learn the convention, so the default guesses from the
    tag and the caller can override.
    """
    return any(h.lower() in tag.lower() for h in INSTANT_HINTS)


async def cross_section(
    tag: str,
    period: str,
    *,
    taxonomy: str = "us-gaap",
    unit: str = "USD",
    limit: int = 10_000,
) -> list[dict[str, Any]]:
    """Every filer's value for one concept in one period."""
    if not PERIOD.match(period):
        raise SourceError(
            f"Period {period!r} is not a frame key. Use CY2023, CY2023Q1 for a flow, "
            "or CY2023Q1I for a balance-sheet instant."
        )

    url = URL.format(taxonomy=taxonomy, tag=tag, unit=unit, period=period)
    try:
        payload = await get_json(url, tier="immutable")
    except SourceError as exc:
        alt = period + "I" if not period.endswith("I") else period[:-1]
        raise SourceError(
            f"No frame for {taxonomy}:{tag} {unit} {period}. "
            f"Balance-sheet concepts need the instant form — try {alt}. ({exc})"
        ) from exc

    data = payload.get("data") or []
    if not data:
        raise SourceError(f"Frame {taxonomy}:{tag} {period} came back empty")

    label = payload.get("label") or tag
    rows = []
    for item in data[:limit]:
        rows.append(
            envelope.row(
                entity=str(item.get("cik", "")).zfill(10),
                field=f"{taxonomy}:{tag}",
                observed_at=item.get("end"),
                # The frame gives the accession but not its filing date, so
                # there is no honest known_at here. Flagged, never guessed.
                known_at=None,
                value=item.get("val"),
                unit=unit,
                source=SOURCE,
                source_url=url,
                vintage=envelope.UNKNOWN_VINTAGE,
                company=item.get("entityName"),
                cik=str(item.get("cik", "")).zfill(10),
                accession=item.get("accn"),
                period=period,
                label=label,
            )
        )
    return rows


def warnings_for(period: str, rows: list[dict[str, Any]]) -> list[str]:
    return [
        f"{len(rows):,} filers reported this concept for {period}. Frames carry the "
        "accession number of each value but not its filing date, so these rows have no "
        "known_at and cannot be filtered point-in-time. A frame may also contain a "
        "restated figure rather than the one first published. Use fetch on a single "
        "entity when the filing date matters."
    ]
