"""Bureau of Economic Analysis — GDP and the national accounts, at table level.

FRED carries the headline series one at a time. BEA serves the whole NIPA table,
so a single call returns every line of the GDP decomposition — consumption,
investment, net exports, government, each with its contribution to growth — in
the shape a macro overlay actually needs.

The vintage story here is the sharpest in the product, and it is a warning
rather than a feature. GDP is published three times: an advance estimate about a
month after the quarter, a second estimate, a third estimate, and then revised
again in every annual and five-yearly benchmark revision. This endpoint returns
only the current estimate. A backtest that trades on the number in this response
is trading on figures that did not exist for months or years. These rows carry no
`known_at` and say exactly that; ALFRED via `fred:GDPC1` is the free source that
does have the vintages.

Needs a free key: https://apps.bea.gov/API/signup/
"""

from __future__ import annotations

import calendar
import os
import re
from typing import Any

from .. import envelope
from ..http import SourceError, get_json

SOURCE = "bea"
BASE = "https://apps.bea.gov/api/data"
HOME = "https://apps.bea.gov/iTable/?reqid=19&step=2"

# The tables people mean when they say "GDP". A bare `bea:T10101` resolves
# through here so nobody has to know that NIPA is the dataset name.
TABLES = {
    "T10101": ("NIPA", "Real GDP, percent change from preceding period"),
    "T10102": ("NIPA", "Contributions to percent change in real GDP"),
    "T10105": ("NIPA", "GDP in current dollars, by component"),
    "T10106": ("NIPA", "Real GDP in chained dollars, by component"),
    "T10104": ("NIPA", "GDP price indexes, by component"),
    "T20100": ("NIPA", "Personal income and its disposition"),
    "T20600": ("NIPA", "Personal income and outlays, monthly"),
    "T20804": ("NIPA", "Real PCE price index, by type of product"),
    "T50100": ("NIPA", "Saving and investment"),
    "T30100": ("NIPA", "Government current receipts and expenditures"),
    "T40100": ("NIPA", "Foreign transactions"),
}

QUARTER_END = {"Q1": 3, "Q2": 6, "Q3": 9, "Q4": 12}
PERIOD = re.compile(r"^(\d{4})(?:(Q[1-4])|M(\d{2}))?$")


def has_key() -> bool:
    return bool(os.environ.get("BEA_API_KEY"))


def _key() -> str:
    key = os.environ.get("BEA_API_KEY")
    if not key:
        raise SourceError(
            "BEA needs a free API key. Sign up at https://apps.bea.gov/API/signup/ "
            "and set BEA_API_KEY."
        )
    return key


def catalog() -> list[dict[str, Any]]:
    return [
        {"field": f"bea:{table}", "label": label, "source": SOURCE,
         "vintage": envelope.UNKNOWN_VINTAGE, "key_required": not has_key()}
        for table, (_, label) in TABLES.items()
    ]


def parse_spec(spec: str) -> tuple[str, str, str | None]:
    """Read `T10101`, or the long form `NIPA/T10101/Q`."""
    parts = [p for p in spec.strip().split("/") if p]
    if len(parts) == 1:
        table = parts[0].upper()
        dataset = TABLES.get(table, ("NIPA",))[0]
        return dataset, table, None
    if len(parts) == 2:
        return parts[0].upper(), parts[1].upper(), None
    return parts[0].upper(), parts[1].upper(), parts[2].upper()


def period_end(raw: str) -> tuple[str | None, str]:
    match = PERIOD.match((raw or "").strip().upper())
    if not match:
        return None, "unknown"
    year, quarter, month = match.groups()
    y = int(year)
    if quarter:
        m = QUARTER_END[quarter]
        return f"{y:04d}-{m:02d}-{calendar.monthrange(y, m)[1]:02d}", "quarterly"
    if month:
        m = int(month)
        if 1 <= m <= 12:
            return f"{y:04d}-{m:02d}-{calendar.monthrange(y, m)[1]:02d}", "monthly"
        return None, "unknown"
    return f"{y:04d}-12-31", "annual"


async def table(spec: str = "T10101", *, frequency: str | None = None,
                year: str = "ALL") -> list[dict[str, Any]]:
    """Every line of one NIPA table, across every period."""
    dataset, name, embedded = parse_spec(spec)
    freq = (frequency or embedded or "Q").upper()
    if freq not in ("A", "Q", "M"):
        raise SourceError(f"BEA frequency is A, Q or M — not {freq!r}.")

    url = (f"{BASE}?&UserID={_key()}&method=GetData&DataSetName={dataset}"
           f"&TableName={name}&Frequency={freq}&Year={year}&ResultFormat=JSON")
    payload = await get_json(url, tier="daily")

    api = payload.get("BEAAPI") or {}
    results = api.get("Results") or {}
    error = results.get("Error") or api.get("Error")
    if error:
        detail = error.get("APIErrorDescription") or error.get("ErrorDetail") or str(error)
        raise SourceError(
            f"BEA refused {dataset}/{name} at frequency {freq}: {detail}. "
            f"Known tables: {', '.join(TABLES)}."
        )

    data = results.get("Data") or []
    if not data:
        raise SourceError(
            f"BEA returned no rows for {dataset}/{name}. Monthly data exists only for "
            "a few tables such as T20600 — most NIPA tables are quarterly or annual."
        )

    unit_label = results.get("UnitOfMeasure")
    rows = []
    for item in data:
        observed, kind = period_end(item.get("TimePeriod") or "")
        if not observed:
            continue
        raw = (item.get("DataValue") or "").replace(",", "")
        try:
            value = float(raw)
        except ValueError:
            continue

        # UNIT_MULT is a power of ten held back from DataValue. Ignoring it is
        # how a $28 trillion economy gets reported as 28 million.
        try:
            value *= 10 ** int(item.get("UNIT_MULT") or 0)
        except (TypeError, ValueError):
            pass

        line = str(item.get("LineNumber") or "").strip()
        rows.append(
            envelope.row(
                entity=f"{name}:L{line}" if line else name,
                field=f"bea:{name}",
                observed_at=observed,
                # BEA serves the current estimate only, never the one first
                # published. There is no honest known_at to put here.
                known_at=None,
                value=value,
                unit=item.get("CL_UNIT") or unit_label,
                source=SOURCE,
                source_url=HOME,
                vintage=envelope.UNKNOWN_VINTAGE,
                table=name,
                dataset=dataset,
                line=line,
                line_description=item.get("LineDescription"),
                series_code=item.get("SeriesCode"),
                period=item.get("TimePeriod"),
                frequency=kind,
            )
        )

    if not rows:
        raise SourceError(f"BEA table {name} returned no parseable periods")
    return sorted(rows, key=lambda r: (r["observed_at"], r["entity"]))


def warnings_for(spec: str, rows: list[dict[str, Any]]) -> list[str]:
    lines = len({r["entity"] for r in rows})
    return [
        f"{lines} table line(s) across {len({r['observed_at'] for r in rows})} periods. "
        "Every figure is the current estimate. GDP is published as an advance estimate "
        "about a month after the quarter, revised twice more within three months, then "
        "again at every annual and benchmark revision — so the number here was not "
        "public on the date it describes, and often differs from the first print by more "
        "than a percentage point. These rows carry no known_at for that reason. Use "
        "fred:GDPC1 with ALFRED vintages when the backtest has to be honest.",
    ]
