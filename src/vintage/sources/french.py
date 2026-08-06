"""Ken French Data Library. The benchmark every factor claim is scored against.

Static ZIPs, no key, no rate drama. The parsing is fiddly because the files
carry a monthly block followed by an annual block under one header.
"""

from __future__ import annotations

import csv
import io
import zipfile
from typing import Any

from .. import envelope
from ..http import SourceError, get_bytes

SOURCE = "ken-french-data-library"
BASE = "https://mba.tuck.dartmouth.edu/pages/faculty/ken.french/ftp/"

DATASETS = {
    "ff3": {
        "file": "F-F_Research_Data_Factors_CSV.zip",
        "label": "Fama-French 3 factors (monthly)",
        "fields": ["Mkt-RF", "SMB", "HML", "RF"],
    },
    "ff5": {
        "file": "F-F_Research_Data_5_Factors_2x3_CSV.zip",
        "label": "Fama-French 5 factors (monthly)",
        "fields": ["Mkt-RF", "SMB", "HML", "RMW", "CMA", "RF"],
    },
    "momentum": {
        "file": "F-F_Momentum_Factor_CSV.zip",
        "label": "Momentum factor UMD (monthly)",
        "fields": ["Mom"],
    },
    "ff3_daily": {
        "file": "F-F_Research_Data_Factors_daily_CSV.zip",
        "label": "Fama-French 3 factors (daily)",
        "fields": ["Mkt-RF", "SMB", "HML", "RF"],
    },
    "industry49": {
        "file": "49_Industry_Portfolios_CSV.zip",
        "label": "49 industry portfolios (monthly)",
        "fields": ["industry portfolio returns"],
    },
}


def catalog() -> list[dict[str, Any]]:
    return [
        {
            "field": f"french:{key}",
            "label": meta["label"],
            "components": meta["fields"],
            "source": SOURCE,
            "vintage": envelope.IMMUTABLE,
        }
        for key, meta in DATASETS.items()
    ]


async def load(dataset: str) -> list[dict[str, Any]]:
    """Return envelope rows for one French dataset.

    French series are revised on rebuild rather than filed, so there is no
    honest `known_at`. They are flagged UNKNOWN_VINTAGE rather than given a
    fabricated date: but as a benchmark that is fine, since you compare
    against them rather than trade on them.
    """
    meta = DATASETS.get(dataset)
    if not meta:
        raise SourceError(
            f"Unknown French dataset {dataset!r}. Available: {', '.join(DATASETS)}"
        )

    url = BASE + meta["file"]
    raw = await get_bytes(url, tier="monthly")

    with zipfile.ZipFile(io.BytesIO(raw)) as archive:
        name = next(n for n in archive.namelist() if n.lower().endswith(".csv"))
        text = archive.read(name).decode("latin-1")

    return _parse(text, dataset, url)


def _parse(text: str, dataset: str, url: str) -> list[dict[str, Any]]:
    """Walk the CSV, keeping only the first (monthly or daily) data block.

    The header row is the first line whose leading cell is blank; data rows
    start with a 6- or 8-digit date. The annual block that follows repeats
    4-digit years, so we stop at the first blank line after data begins.
    """
    header: list[str] | None = None
    rows: list[dict[str, Any]] = []
    started = False

    for line in csv.reader(io.StringIO(text)):
        if not line or all(not c.strip() for c in line):
            if started:
                break  # blank line after data = end of the periodic block
            continue

        first = line[0].strip()

        if header is None:
            if not first and len(line) > 1:
                header = [c.strip() for c in line[1:]]
            continue

        if not (first.isdigit() and len(first) in (6, 8)):
            if started:
                break
            continue

        started = True
        observed = (
            f"{first[:4]}-{first[4:6]}-{first[6:]}"
            if len(first) == 8
            else _month_end(first)
        )

        for name, cell in zip(header, line[1:]):
            cell = cell.strip()
            if not cell or not name:
                continue
            try:
                value = float(cell)
            except ValueError:
                continue
            if value <= -99.0:  # French's missing-value sentinel
                continue
            rows.append(
                envelope.row(
                    entity=f"french:{dataset}",
                    field=name,
                    observed_at=observed,
                    known_at=None,
                    value=value / 100.0,
                    unit="return",
                    source=SOURCE,
                    source_url=url,
                    vintage=envelope.UNKNOWN_VINTAGE,
                )
            )

    if not rows:
        raise SourceError(f"Could not parse the French file for {dataset!r}")
    return rows


def _month_end(yyyymm: str) -> str:
    year, month = int(yyyymm[:4]), int(yyyymm[4:6])
    last = [31, 29 if _leap(year) else 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31][month - 1]
    return f"{year:04d}-{month:02d}-{last:02d}"


def _leap(year: int) -> bool:
    return year % 4 == 0 and (year % 100 != 0 or year % 400 == 0)
