"""Congressional stock trades, from the House periodic transaction reports.

The STOCK Act makes every member of Congress disclose a securities trade within
45 days. The filings are public, free, and almost nobody reads them in bulk
because the Clerk publishes them as a year of PDFs behind a ZIP index.

Two dates, and the gap between them is the entire dataset:

- `observed_at` is the day the trade happened.
- `known_at` is the day the disclosure was filed, which is when anybody outside
  the member's household could have acted on it.

Those are routinely 30 to 45 days apart, and a backtest that ranks on the trade
date is reading mail that had not been delivered yet. Only `known_at` is
enforceable, which is why it is the one `as_of` filters on.

Amounts are bands, not figures. A member reporting "$15,001 - $50,000" has
complied fully, and no amount of parsing turns that into a dollar flow. The
band is carried through as-is and `value` is the midpoint, clearly labelled,
because a midpoint is a convenience and never a measurement.

The Senate runs a separate system at efdsearch.senate.gov. It sits behind a
click-through agreement quoting the Ethics in Government Act, 5 U.S.C. app.
§ 105(c), which makes it unlawful to obtain or use a report "for any
commercial purpose, other than by news and communications media for
dissemination to the general public". Vintage is open source and the data is
served for public research, which is the basis on which the Senate half is
included. That is a legal reading, not a technical one, and anyone putting
this behind a paywall needs their own advice rather than this docstring.

The same statute covers House reports, which the Clerk publishes without a
gate. Both chambers carry the restriction in their warnings.
"""

from __future__ import annotations

import csv
import datetime as dt
import io
import re
import zipfile
from typing import Any

from .. import envelope
from ..http import SourceError, get_bytes

SOURCE = "house-stock-watcher"
HOME = "https://disclosures-clerk.house.gov/PublicDisclosure"
INDEX = "https://disclosures-clerk.house.gov/public_disc/financial-pdfs/{year}FD.zip"
PTR_PDF = "https://disclosures-clerk.house.gov/public_disc/ptr-pdfs/{year}/{doc}.pdf"

# The Clerk's filing-type codes. `P` is the periodic transaction report, the
# only one that carries individual trades; the rest are annual disclosures,
# extensions and amendments that say nothing about timing.
PERIODIC = "P"

# "$15,001 - $50,000" and friends. The Clerk uses a fixed ladder, so the bands
# are parsed rather than matched against a hardcoded list that would rot when
# the thresholds are next revised.
AMOUNT = re.compile(r"\$([\d,]+)\s*-\s*\$?([\d,]+)")

# A ticker in parentheses at the end of an asset name: "Rollins, Inc. (ROL)".
# Bonds and treasuries carry a CUSIP in the same position, which is nine
# characters and alphanumeric, so the shape tells them apart.
TICKER = re.compile(r"\(([A-Z][A-Z.\-]{0,5})\)")

# Transaction codes as printed in the PTR table.
ACTIONS = {"P": "purchase", "S": "sale", "S (partial)": "partial sale", "E": "exchange"}

DATE = re.compile(r"(\d{2}/\d{2}/\d{4})")


def catalog() -> list[dict[str, Any]]:
    return [
        {"field": "congress:trades",
         "label": "Congressional stock trades, House and Senate STOCK Act reports",
         "source": SOURCE, "vintage": envelope.AS_FILED},
        {"field": "congress:house",
         "label": "US House stock trades, periodic transaction reports",
         "source": SOURCE, "vintage": envelope.AS_FILED},
        {"field": "congress:senate",
         "label": "US Senate stock trades, periodic transaction reports",
         "source": SENATE_SOURCE, "vintage": envelope.AS_FILED},
        {"field": "congress:filings",
         "label": "US House disclosure index, every filing type",
         "source": SOURCE, "vintage": envelope.AS_FILED},
    ]


def _to_iso(stamp: str) -> str | None:
    try:
        return dt.datetime.strptime(stamp, "%m/%d/%Y").date().isoformat()
    except ValueError:
        return None


async def index(year: int) -> list[dict[str, str]]:
    """Every filing the House recorded for one year, from the bulk ZIP.

    The archive holds a tab-separated index and an XML twin. The TSV is
    parsed because it is the one the Clerk keeps stable.
    """
    raw = await get_bytes(INDEX.format(year=year), tier="daily")
    try:
        archive = zipfile.ZipFile(io.BytesIO(raw))
    except zipfile.BadZipFile as exc:
        raise SourceError(f"House index for {year} was not a ZIP: {exc}") from exc

    names = [n for n in archive.namelist() if n.lower().endswith(".txt")]
    if not names:
        raise SourceError(f"House index for {year} had no TSV: {archive.namelist()}")

    text = archive.read(names[0]).decode("utf-8", "replace")
    return list(csv.DictReader(io.StringIO(text), delimiter="\t"))


class MissingDependency(Exception):
    """pypdf is absent. Distinct from a bad PDF, and not per-filing.

    A missing library fails identically on all 515 filings, so it must not be
    caught by the per-filing handler: doing that downloads the entire year to
    discover an import error, which is exactly what happened the first time
    this ran.
    """


def _require_reader():
    try:
        from pypdf import PdfReader
    except ImportError as exc:
        raise MissingDependency(
            "Reading House PTRs needs pypdf. Install vintage-mcp with its "
            "dependencies rather than the bare package."
        ) from exc
    return PdfReader


def _pdf_text(raw: bytes) -> str:
    """Text of a PTR PDF. The import is local so the dependency only loads
    when a PDF is actually opened."""
    reader_class = _require_reader()
    try:
        reader = reader_class(io.BytesIO(raw))
        return "\n".join(page.extract_text() or "" for page in reader.pages)
    except Exception as exc:  # noqa: BLE001 - any malformed PDF is the same story
        raise SourceError(f"Could not read a House PTR PDF: {exc}") from exc


def parse_ptr(text: str) -> list[dict[str, Any]]:
    """Pull transactions out of one PTR's extracted text.

    The layout is a table flattened into a stream, so a row is recognised by
    its shape: an asset line carrying a ticker, then a transaction code, then
    two dates, then an amount band. Anything that does not present all of that
    is skipped rather than guessed at.
    """
    out: list[dict[str, Any]] = []
    lines = [ln.strip() for ln in text.splitlines() if ln.strip()]

    for i, line in enumerate(lines):
        ticker_match = TICKER.search(line)
        if not ticker_match:
            continue
        ticker = ticker_match.group(1)
        # A nine-character alphanumeric in that slot is a CUSIP, not a ticker.
        if len(ticker) == 9:
            continue

        # The transaction block follows within a few lines of the asset name.
        window = " ".join(lines[i:i + 4])
        dates = DATE.findall(window)
        amount = AMOUNT.search(window)
        if len(dates) < 2 or not amount:
            continue

        action = None
        for code in ("S (partial)", "P", "S", "E"):
            if re.search(rf"(?<![A-Za-z]){re.escape(code)}\s+\d{{2}}/", window):
                action = ACTIONS[code]
                break
        if action is None:
            continue

        traded, disclosed = _to_iso(dates[0]), _to_iso(dates[1])
        if not traded or not disclosed:
            continue

        low = float(amount.group(1).replace(",", ""))
        high = float(amount.group(2).replace(",", ""))

        out.append({
            "ticker": ticker,
            "action": action,
            "observed_at": traded,
            "known_at": disclosed,
            "amount_low": low,
            "amount_high": high,
            "asset": line[:120],
        })
    return out


async def trades(year: int | None = None, *, limit: int = 400,
                 member: str | None = None) -> list[dict[str, Any]]:
    """House trades for a year, newest disclosure first.

    Each PTR is a separate PDF, so this fetches only as many as `limit` needs.
    A filed disclosure never changes, which is what makes them cacheable.
    """
    year = year or dt.date.today().year
    filings = await index(year)
    periodic = [f for f in filings if (f.get("FilingType") or "").strip() == PERIODIC]
    if member:
        needle = member.strip().lower()
        periodic = [f for f in periodic
                    if needle in f"{f.get('First','')} {f.get('Last','')}".lower()]
    if not periodic:
        raise SourceError(
            f"No House periodic transaction reports for {year}"
            + (f" matching {member!r}" if member else "")
            + f". The index held {len(filings)} filings of all types."
        )

    # Newest disclosures first, so a truncated read is the recent end.
    periodic.sort(key=lambda f: _to_iso(f.get("FilingDate", "")) or "", reverse=True)

    # Check the PDF reader once, before any downloading. Without this the
    # import error is indistinguishable from 515 corrupt filings and costs a
    # full year of requests to find out.
    try:
        _require_reader()
    except MissingDependency as exc:
        raise SourceError(str(exc)) from exc

    rows: list[dict[str, Any]] = []
    unreadable = 0
    for filing in periodic:
        if len(rows) >= limit:
            break
        doc = (filing.get("DocID") or "").strip()
        if not doc:
            continue
        url = PTR_PDF.format(year=year, doc=doc)
        try:
            raw = await get_bytes(url, tier="monthly")
            transactions = parse_ptr(_pdf_text(raw))
        except SourceError:
            unreadable += 1
            continue

        name = " ".join(
            p for p in (filing.get("First"), filing.get("Last")) if p
        ).strip()
        for txn in transactions:
            rows.append(envelope.row(
                entity=txn["ticker"],
                field="congress:trades",
                observed_at=txn["observed_at"],
                # The trade was invisible until the disclosure was filed. This
                # is the only date an outsider could have acted on.
                known_at=txn["known_at"],
                value=(txn["amount_low"] + txn["amount_high"]) / 2.0,
                unit="USD, midpoint of a disclosed band",
                source=SOURCE,
                source_url=url,
                vintage=envelope.AS_FILED,
                member=name,
                chamber="House",
                district=(filing.get("StateDst") or "").strip() or None,
                action=txn["action"],
                amount_low=txn["amount_low"],
                amount_high=txn["amount_high"],
                asset=txn["asset"],
                doc_id=doc,
                disclosure_lag_days=_lag(txn["observed_at"], txn["known_at"]),
            ))

    if not rows:
        raise SourceError(
            f"Read {len(periodic)} House PTRs for {year} and parsed no "
            f"transactions from them ({unreadable} unreadable)."
        )
    return sorted(rows, key=lambda r: r["known_at"], reverse=True)[:limit]


# ------------------------------------------------------------------ senate

SENATE_SOURCE = "senate-efd"
SENATE_HOME = "https://efdsearch.senate.gov/search/home/"
SENATE_SEARCH = "https://efdsearch.senate.gov/search/"
SENATE_DATA = "https://efdsearch.senate.gov/search/report/data/"
SENATE_VIEW = "https://efdsearch.senate.gov/search/view/ptr/{key}/"

# Report type 11 is the periodic transaction report in EFD's own numbering.
SENATE_PTR_TYPE = "[11]"

CSRF_FIELD = re.compile(r'name="csrfmiddlewaretoken" value="([^"]+)"')
ROW = re.compile(r"<tr[^>]*>(.*?)</tr>", re.S)
CELL = re.compile(r"<t[dh][^>]*>(.*?)</t[dh]>", re.S)
PTR_KEY = re.compile(r"/search/view/ptr/([0-9a-f-]+)/")
TAGS = re.compile(r"<[^>]+>")

SENATE_ACTIONS = {
    "purchase": "purchase",
    "sale (full)": "sale",
    "sale (partial)": "partial sale",
    "sale": "sale",
    "exchange": "exchange",
}


def _clean(html: str) -> str:
    import html as html_module

    return re.sub(r"\s+", " ", html_module.unescape(TAGS.sub("", html))).strip()


async def _senate_session():
    """A client that has accepted the agreement, which EFD requires first.

    This is the one source that needs cookies, so it holds its own client
    rather than bending `http.py`'s stateless helpers into carrying session
    state for everybody else.
    """
    import httpx

    from ..http import user_agent

    client = httpx.AsyncClient(
        headers={"User-Agent": user_agent()}, timeout=60, follow_redirects=True
    )
    try:
        landing = await client.get(SENATE_HOME)
        token = CSRF_FIELD.search(landing.text)
        if not token:
            raise SourceError(
                "Senate EFD did not present its agreement form. The gate "
                "changed shape and the flow needs re-reading."
            )
        await client.post(
            SENATE_HOME,
            data={"prohibition_agreement": "1",
                  "csrfmiddlewaretoken": token.group(1)},
            headers={"Referer": SENATE_HOME},
        )
    except Exception:
        await client.aclose()
        raise
    return client


async def senate_reports(client, since: str, *, limit: int = 100) -> list[dict[str, str]]:
    """PTR filings disclosed on or after `since` (an ISO date)."""
    stamp = dt.date.fromisoformat(since).strftime("%m/%d/%Y 00:00:00")
    csrf = client.cookies.get("csrftoken")
    response = await client.post(
        SENATE_DATA,
        data={
            "start": "0", "length": str(int(limit)),
            "report_types": SENATE_PTR_TYPE, "filer_types": "[]",
            "submitted_start_date": stamp, "submitted_end_date": "",
            "candidate_state": "", "senator_state": "", "office_id": "",
            "first_name": "", "last_name": "",
            "csrfmiddlewaretoken": csrf,
        },
        headers={"Referer": SENATE_SEARCH, "X-CSRFToken": csrf or ""},
    )
    try:
        payload = response.json()
    except ValueError as exc:
        raise SourceError(f"Senate EFD returned no JSON: {exc}") from exc

    out = []
    for record in payload.get("data", []):
        if len(record) < 5:
            continue
        key = PTR_KEY.search(record[3])
        filed = _to_iso(_clean(record[4]))
        if not key or not filed:
            continue
        out.append({
            "key": key.group(1),
            "member": f"{_clean(record[0])} {_clean(record[1])}".strip(),
            "filed": filed,
        })
    return out


def parse_senate_ptr(html: str) -> list[dict[str, Any]]:
    """Transactions from one Senate PTR page.

    Unlike the House, this is a real HTML table with named columns, so it is
    read positionally off the header rather than pattern-matched out of a
    flattened PDF.
    """
    out: list[dict[str, Any]] = []
    for raw in ROW.findall(html):
        cells = [_clean(c) for c in CELL.findall(raw)]
        if len(cells) < 8 or cells[1].lower().startswith("transaction date"):
            continue

        traded = _to_iso(cells[1])
        ticker = cells[3].strip()
        action = SENATE_ACTIONS.get(cells[6].strip().lower())
        amount = AMOUNT.search(cells[7])
        # "--" is what EFD prints for a holding with no ticker, and a trade
        # without a symbol cannot be joined to a price series.
        if not traded or not action or not amount or ticker in ("", "--"):
            continue

        out.append({
            "ticker": ticker,
            "action": action,
            "observed_at": traded,
            "amount_low": float(amount.group(1).replace(",", "")),
            "amount_high": float(amount.group(2).replace(",", "")),
            "asset": cells[4][:120],
            "owner": cells[2],
        })
    return out


async def senate_trades(since: str | None = None, *,
                        limit: int = 200,
                        member: str | None = None) -> list[dict[str, Any]]:
    """Senate PTR transactions, newest disclosure first."""
    since = since or f"{dt.date.today().year}-01-01"
    client = await _senate_session()
    try:
        reports = await senate_reports(client, since, limit=max(limit, 100))
        if member:
            needle = member.strip().lower()
            reports = [r for r in reports if needle in r["member"].lower()]
        if not reports:
            raise SourceError(
                f"No Senate periodic transaction reports disclosed since {since}"
                + (f" for {member!r}" if member else "")
            )

        rows: list[dict[str, Any]] = []
        for report in reports:
            if len(rows) >= limit:
                break
            url = SENATE_VIEW.format(key=report["key"])
            page = await client.get(url)
            if page.status_code != 200:
                continue
            for txn in parse_senate_ptr(page.text):
                rows.append(envelope.row(
                    entity=txn["ticker"],
                    field="congress:trades",
                    observed_at=txn["observed_at"],
                    known_at=report["filed"],
                    value=(txn["amount_low"] + txn["amount_high"]) / 2.0,
                    unit="USD, midpoint of a disclosed band",
                    source=SENATE_SOURCE,
                    source_url=url,
                    vintage=envelope.AS_FILED,
                    member=report["member"],
                    chamber="Senate",
                    district=None,
                    action=txn["action"],
                    amount_low=txn["amount_low"],
                    amount_high=txn["amount_high"],
                    asset=txn["asset"],
                    owner=txn["owner"],
                    doc_id=report["key"],
                    disclosure_lag_days=_lag(txn["observed_at"], report["filed"]),
                ))
    finally:
        await client.aclose()

    return sorted(rows, key=lambda r: r["known_at"], reverse=True)[:limit]


async def both(year: int | None = None, *, limit: int = 200,
               member: str | None = None) -> list[dict[str, Any]]:
    """House and Senate together, which is the only complete answer.

    One chamber failing does not sink the other; the gap is reported in the
    warnings instead, because a half-answer labelled as a whole one is the
    failure mode that matters here.
    """
    year = year or dt.date.today().year
    per_chamber = max(1, limit)

    house_rows: list[dict[str, Any]] = []
    senate_rows: list[dict[str, Any]] = []
    problems: list[str] = []

    try:
        house_rows = await trades(year, limit=per_chamber, member=member)
    except SourceError as exc:
        problems.append(f"House unavailable: {exc}")
    try:
        senate_rows = await senate_trades(f"{year}-01-01", limit=per_chamber,
                                          member=member)
    except (SourceError, Exception) as exc:  # noqa: BLE001 - reported, not raised
        problems.append(f"Senate unavailable: {type(exc).__name__}: {exc}")

    rows = house_rows + senate_rows
    if not rows:
        raise SourceError("; ".join(problems) or f"No congressional trades for {year}")

    # Which chamber is missing is readable from the rows themselves, so the
    # gap is reported by `warnings_for` rather than smuggled through a private
    # key on every row.
    return sorted(rows, key=lambda r: r["known_at"], reverse=True)[:limit]


def _lag(traded: str, disclosed: str) -> int | None:
    try:
        return (dt.date.fromisoformat(disclosed) - dt.date.fromisoformat(traded)).days
    except ValueError:
        return None


def warnings_for(rows: list[dict[str, Any]]) -> list[str]:
    notes = [
        "Amounts are disclosed as bands, not figures. `value` is the midpoint of "
        "the band and exists for sorting, not for sizing. Never sum it and call "
        "the total a flow.",
        "observed_at is the trade date; known_at is the disclosure date. They are "
        "routinely 30 to 45 days apart and only known_at was ever actionable.",
        "The Ethics in Government Act, 5 U.S.C. app. 105(c), makes it unlawful to "
        "use these reports for any commercial purpose other than news reporting, "
        "or to establish a credit rating, or to solicit money. That restriction "
        "follows the data, not the website it came from.",
    ]

    chambers = {r.get("chamber") for r in rows if r.get("chamber")}
    if rows and chambers != {"House", "Senate"}:
        missing = {"House", "Senate"} - chambers
        notes.append(
            f"{' and '.join(sorted(chambers)) or 'Neither chamber'} only. Nothing "
            f"from the {' or '.join(sorted(missing))}, so this is not all of "
            "Congress and a count taken from it will be short."
        )
    lags = [r.get("disclosure_lag_days") for r in rows if r.get("disclosure_lag_days")]
    if lags:
        notes.append(
            f"Disclosure lag in this batch runs {min(lags)} to {max(lags)} days, "
            f"median {sorted(lags)[len(lags) // 2]}."
        )
    late = [r for r in rows if (r.get("disclosure_lag_days") or 0) > 45]
    if late:
        notes.append(
            f"{len(late)} of {len(rows)} transactions were disclosed more than 45 "
            "days after the trade, which is past the STOCK Act deadline."
        )
    return notes
