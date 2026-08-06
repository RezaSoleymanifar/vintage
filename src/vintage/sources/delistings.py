"""SEC Form 25 — every delisting, dated. The survivorship fix.

A universe built from currently-listed names is a universe of survivors. The
companies that failed are not merely under-weighted, they are absent, and a
momentum short leg is exactly where they would have been. Every free dataset
has this problem and most do not mention it.

The regulator already keeps the answer. Removing a security from an exchange
requires a Form 25 (or 25-NSE, filed by the exchange), so EDGAR holds a dated
record of essentially every delisting since 1994. Nothing needs scraping and no
web archive is involved.

Two things make this cheap rather than a 7 GB download.

`form.idx` is **sorted by form type**, and "25" sorts early. Streaming the file
and stopping once the cursor passes 25-NSE reads about 7 MB of a 58 MB index,
which is where the eightfold saving comes from.

Quarterly indexes for closed quarters never change, so they cache under the
`immutable` tier and a rebuild costs nothing.

What this gives you is the *event*: company name, CIK, filing date. Turning a
CIK into the ticker it used to trade under needs a second lookup, because the
current ticker map contains only live filers — `former_tickers` does that, one
company at a time.
"""

from __future__ import annotations

import datetime as dt
import re
from typing import Any, Iterable

import httpx

from .. import envelope
from ..http import SourceError, get_json, user_agent

SOURCE = "sec-form-25"
INDEX = "https://www.sec.gov/Archives/edgar/full-index/{year}/QTR{qtr}/form.idx"
SUBMISSIONS = "https://data.sec.gov/submissions/CIK{cik}.json"

# Coverage, measured rather than assumed. The SEC made electronic Form 25
# filing mandatory in April 2006 and the counts show exactly that step:
#   2003-2005  ~450/year   paper filings dominate, EDGAR sees a fraction
#   2006        1,421      the rule takes effect mid-year
#   2007-2025  1,300-2,300/year, stable
# So this is complete from 2006 and partial before it. A backtest starting
# earlier than 2006 is still survivor-biased and the warning says so.
FIRST_YEAR = 2003
COMPLETE_FROM = "2006-04-01"
FORMS = ("25", "25-NSE")
STOP_AFTER = "25-NSE"      # once the sorted cursor passes this, we are done

_LINE = re.compile(
    r"^(?P<form>\S+(?:\s\S+)*?)\s{2,}"
    r"(?P<name>.+?)\s{2,}"
    r"(?P<cik>\d+)\s+"
    r"(?P<date>\d{4}-\d{2}-\d{2})\s+"
    r"(?P<path>\S+)\s*$"
)


def quarters(start_year: int = FIRST_YEAR, until: dt.date | None = None):
    """Every (year, quarter) from `start_year` to now, oldest first."""
    until = until or dt.date.today()
    for year in range(start_year, until.year + 1):
        for qtr in (1, 2, 3, 4):
            if year == until.year and (qtr - 1) * 3 + 1 > until.month:
                break
            yield year, qtr


def _parse(line: str) -> dict[str, Any] | None:
    m = _LINE.match(line.rstrip())
    if not m or m.group("form") not in FORMS:
        return None
    return {
        "form": m.group("form"),
        "company": m.group("name").strip(),
        "cik": m.group("cik").zfill(10),
        "filed": m.group("date"),
        "url": "https://www.sec.gov/Archives/" + m.group("path"),
    }


def scan_quarter(year: int, qtr: int, *, timeout: float = 180.0) -> list[dict[str, Any]]:
    """Form 25 filings in one quarter, read from a partial stream.

    Synchronous on purpose: this is bulk history, run once and cached, and the
    early-exit logic reads far more clearly against a plain stream than against
    an async chunk loop.
    """
    url = INDEX.format(year=year, qtr=qtr)
    out: list[dict[str, Any]] = []
    passed = False

    try:
        with httpx.stream("GET", url, headers={"User-Agent": user_agent()},
                          timeout=timeout) as response:
            if response.status_code == 404:
                return []                       # quarter not published yet
            response.raise_for_status()

            buffer = ""
            for chunk in response.iter_text():
                buffer += chunk
                lines = buffer.split("\n")
                buffer = lines.pop()
                for line in lines:
                    form = line[:12].strip()
                    if form in FORMS:
                        row = _parse(line)
                        if row:
                            out.append(row)
                    elif out and form and form > STOP_AFTER and not form.startswith("25"):
                        passed = True
                        break
                if passed:
                    break
    except httpx.HTTPError as exc:
        raise SourceError(f"EDGAR index {year} QTR{qtr} failed: {exc}") from exc

    return out


def load(start_year: int = FIRST_YEAR, *, until: dt.date | None = None,
         progress: bool = False) -> list[dict[str, Any]]:
    """Every delisting on record, as envelope rows.

    `known_at` is the filing date, which is when the delisting became public.
    These are `IMMUTABLE`: a Form 25 filed in 2009 is not revised later.
    """
    rows: list[dict[str, Any]] = []
    for year, qtr in quarters(start_year, until):
        try:
            found = scan_quarter(year, qtr)
        except SourceError:
            continue
        for hit in found:
            rows.append(
                envelope.row(
                    entity=hit["cik"],
                    field="delisting:form25",
                    observed_at=hit["filed"],
                    known_at=hit["filed"],
                    value=hit["company"],
                    unit=None,
                    source=SOURCE,
                    source_url=hit["url"],
                    vintage=envelope.IMMUTABLE,
                    company=hit["company"],
                    cik=hit["cik"],
                    form=hit["form"],
                )
            )
        if progress:
            print(f"  {year} Q{qtr}: {len(found):>4} delistings "
                  f"({len(rows):,} total)")
    return rows


def listed_at(rows: Iterable[dict[str, Any]], as_of: str) -> set[str]:
    """CIKs that had *not* yet delisted on `as_of`.

    Applied to a current universe this is the survivorship correction: names
    whose Form 25 is dated after `as_of` were still trading then and belong in
    the universe, even though they are absent from any list built today.
    """
    return {r["cik"] for r in rows if r["known_at"] > as_of}


async def former_tickers(cik: str) -> dict[str, Any]:
    """Tickers a company used, including after it stopped filing.

    The current ticker map holds live filers only, so a delisted CIK resolves
    to nothing there. The submissions endpoint keeps the history.
    """
    payload = await get_json(SUBMISSIONS.format(cik=str(cik).zfill(10)), tier="monthly")
    former = payload.get("formerNames") or []
    return {
        "cik": str(cik).zfill(10),
        "name": payload.get("name"),
        "tickers": payload.get("tickers") or [],
        "exchanges": payload.get("exchanges") or [],
        "former_names": [f.get("name") for f in former if f.get("name")],
    }


def warnings_for(rows: list[dict[str, Any]], as_of: str | None) -> list[str]:
    if not rows:
        return ["No delisting history loaded, so any universe here is survivors-only."]

    notes = []
    if as_of is not None:
        # Count companies, not filings. A firm files a separate Form 25 for its
        # common stock, its warrants and each note, so rows overstate it roughly
        # threefold: 36,830 filings cover 11,614 companies.
        revived = len({r["cik"] for r in rows if r["known_at"] > as_of})
        notes.append(
            f"These rows are delistings already public on {as_of}. To build a universe "
            f"as it stood then, you want the complement: the {revived:,} companies that "
            f"delisted *after* {as_of} were still trading and belong in it. "
            "A universe built from a current listing omits all of them, which biases "
            "short legs and any test of failure in particular."
        )
        if as_of < COMPLETE_FROM:
            notes.append(
                f"Electronic Form 25 filing only became mandatory in April 2006, so "
                f"coverage before {COMPLETE_FROM} is partial — roughly 450 filings a "
                "year against 1,300 or more afterwards. A universe as of "
                f"{as_of} is corrected, but not fully."
            )
    return notes
