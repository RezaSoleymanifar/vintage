"""What Chen and Zimmermann actually got, month by month.

The `openap:` prefix next door serves what each paper *claimed*: one return,
one t-statistic, one sample window. This serves what the replication *produced*:
the monthly return of the long-short portfolio, for every predictor, from the
1920s to last year.

The difference matters when you are checking your own code. A claim is a single
number, and matching it tells you little, because your universe and weighting
and costs all differ from the paper's. A return series is thousands of numbers
in a known order, and correlating against it asks a sharper question: does my
implementation move when theirs moves? That is a question about the code rather
than about the sample, which is the only question a calibration should ask.

**The date is the honest part.** Chen and Zimmermann rebuild this file when they
release, and a rebuild can change an old month: the CRSP vintage underneath it
moves, delisting returns get restated, the code improves. So a row here is not
as-filed. Every row carries the month it describes as `observed_at`, a null
`known_at`, and `UNKNOWN_VINTAGE`, because we can say which month a number is
about and cannot say when this particular version of it became public.

One file covers every predictor, so the first call is a large download and every
call after it is served from the monthly cache.
"""

from __future__ import annotations

import csv
import io
from typing import Any

from .. import envelope
from ..http import SourceError, get_bytes

SOURCE = "open-source-asset-pricing-ports"

# The authors' own distribution link, taken from their `openassetpricing`
# package rather than guessed. It answers a plain GET with the CSV.
URL = ("https://drive.google.com/uc?id=1g7w-yQ6Cg2qbMEkER9Q3vgns4JszXQo6"
       "&export=download")
HOME = "https://www.openassetpricing.com/data/"

# The file holds every decile as well as the spread. LS is the long-short leg,
# which is the one the published t-statistic is computed on.
LONG_SHORT = "LS"

FIELDS = {
    "openapret:": "monthly long-short return of the published portfolio, in percent",
}


async def _rows() -> list[dict[str, str]]:
    """The whole file, parsed once and cached for a month."""
    raw = await get_bytes(URL, tier="monthly")
    text = raw.decode("utf-8", errors="replace")
    if not text.startswith("signalname,"):
        raise SourceError(
            "Open Source Asset Pricing returned something that is not the "
            "portfolio file. Their distribution link may have moved; see "
            f"{HOME}."
        )
    return list(csv.DictReader(io.StringIO(text)))


async def acronyms() -> list[str]:
    return sorted({row["signalname"] for row in await _rows()})


async def returns(acronym: str, *, port: str = LONG_SHORT,
                  limit: int = 2000) -> list[dict[str, Any]]:
    """One predictor's published monthly returns.

    `port` selects the leg: LS is the long-short spread, and 01 through 10 are
    the deciles for anyone who wants to see where the spread came from.
    """
    wanted = acronym.strip()
    rows = [r for r in await _rows()
            if r["signalname"].lower() == wanted.lower() and r["port"] == port]

    if not rows:
        names = await acronyms()
        near = [n for n in names if n.lower().startswith(wanted.lower()[:4])][:6]
        raise SourceError(
            f"No published portfolio for {acronym!r}"
            + (f" at leg {port!r}." if port != LONG_SHORT else ".")
            + (f" Close names: {', '.join(near)}." if near else
               f" {len(names)} predictors are in the file.")
        )

    rows.sort(key=lambda r: r["date"])
    out = []
    for row in rows[-limit:]:
        try:
            value = float(row["ret"])
        except (TypeError, ValueError):
            continue
        out.append(
            envelope.row(
                entity=wanted.upper(),
                field=f"openapret:{wanted}",
                observed_at=row["date"],
                known_at=None,
                value=round(value, 6),
                unit="percent per month",
                source=SOURCE,
                source_url=HOME,
                vintage=envelope.UNKNOWN_VINTAGE,
                leg=port,
                n_long=row.get("Nlong"),
                n_short=row.get("Nshort"),
            )
        )
    return out


def warnings_for() -> list[str]:
    return [
        "Open Source Asset Pricing rebuilds this file on each release, and a "
        "rebuild can change an old month, so every row is UNKNOWN_VINTAGE. Use "
        "it to check an implementation against theirs, not as a point-in-time "
        "series in a backtest.",
    ]
