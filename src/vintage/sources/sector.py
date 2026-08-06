"""What industry a company is in, from the record it files under.

A cross-sectional transform needs something the caller holding one ticker does
not have. Ranking a name against its peers needs every peer's number for that
date, which `frame:` already answers. Neutralizing a signal by sector needs a
label per company, which nothing here answered until now.

EDGAR carries one on every filer: the SIC code the company files under, plus
the SEC's own description of it. It is free, it is already fetched when a
ticker is resolved, and it is the classification the regulator actually uses.

The honest part is the date. EDGAR shows the *current* code with no history and
no record of when it changed, so a company that reclassified in 2015 looks like
it was always in the new industry. That is exactly the drift this project
exists to refuse to paper over, so every row is `UNKNOWN_VINTAGE` with a null
`known_at`. Use it to group today's cross-section. Do not use it to claim what
sector a company was in ten years ago.

SIC is coarse and dated next to GICS, and that is the trade: GICS is licensed,
this is not.
"""

from __future__ import annotations

from typing import Any

from .. import envelope
from ..http import get_json
from . import edgar

SOURCE = "sec-edgar-sic"

FIELDS = {
    "sector:sic": ("sic", "SIC code"),
    "sector:name": ("sicDescription", "industry description"),
}

# The first digits of a SIC code are its division. Coarse, but it is the
# grouping most neutralizations actually want, and deriving it here saves every
# caller from writing the same lookup table.
DIVISIONS = [
    (100, 999, "agriculture, forestry and fishing"),
    (1000, 1499, "mining"),
    (1500, 1799, "construction"),
    (2000, 3999, "manufacturing"),
    (4000, 4999, "transport and utilities"),
    (5000, 5199, "wholesale trade"),
    (5200, 5999, "retail trade"),
    (6000, 6799, "finance, insurance and real estate"),
    (7000, 8999, "services"),
    (9100, 9999, "public administration"),
]


def division(sic: str | int | None) -> str | None:
    """The SIC division a code falls in, or None if it is not a usable code."""
    try:
        code = int(str(sic).strip())
    except (TypeError, ValueError):
        return None
    for low, high, label in DIVISIONS:
        if low <= code <= high:
            return label
    return None


async def _submissions(cik: str) -> dict[str, Any]:
    return await get_json(edgar.SUBMISSIONS_URL.format(cik=cik), tier="monthly")


async def classification(entity: str, field: str = "sector:sic") -> list[dict[str, Any]]:
    """One company's industry classification, as EDGAR currently states it."""
    if field not in FIELDS:
        raise ValueError(
            f"Unknown sector field {field!r}. Try: {', '.join(sorted(FIELDS))}."
        )
    key, unit = FIELDS[field]

    resolved = await edgar.resolve(entity)
    cik = resolved["cik"]
    data = await _submissions(cik)
    value = data.get(key) or None
    if field == "sector:sic" and value is not None:
        value = str(value).strip() or None

    return [
        envelope.row(
            entity=f"CIK{cik}",
            field=field,
            observed_at=None,
            known_at=None,
            value=value,
            unit=unit,
            source=SOURCE,
            source_url=f"https://www.sec.gov/cgi-bin/browse-edgar?action=getcompany&CIK={cik}",
            vintage=envelope.UNKNOWN_VINTAGE,
            ticker=resolved.get("ticker"),
            name=data.get("name") or resolved.get("name"),
            sic=str(data.get("sic") or "").strip() or None,
            sic_description=data.get("sicDescription") or None,
            division=division(data.get("sic")),
            note="EDGAR states the current classification only, with no date "
                 "of change. Group today's cross-section with it; do not "
                 "backdate it.",
        )
    ]


async def classifications(entities: list[str]) -> list[dict[str, Any]]:
    """The same, for a list of names, so a neutralizer asks once.

    Sequential on purpose: the shared HTTP client already rate-limits per host
    and SEC asks callers not to hammer it. A name that cannot be resolved is
    returned as a row with a null value rather than dropped, so the caller can
    see the hole instead of silently neutralizing against a smaller universe.
    """
    out: list[dict[str, Any]] = []
    for entity in entities:
        try:
            out.extend(await classification(entity, "sector:sic"))
        except Exception as exc:  # noqa: BLE001 - one bad name must not sink the set
            out.append(
                envelope.row(
                    entity=entity.upper(),
                    field="sector:sic",
                    observed_at=None,
                    known_at=None,
                    value=None,
                    unit="SIC code",
                    source=SOURCE,
                    source_url="https://www.sec.gov/cgi-bin/browse-edgar",
                    vintage=envelope.UNKNOWN_VINTAGE,
                    error=type(exc).__name__,
                )
            )
    return out
