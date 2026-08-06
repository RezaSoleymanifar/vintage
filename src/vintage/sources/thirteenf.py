"""SEC Form 13F, what the big managers held, and when you could have known it.

Every institution running over $100m in US equities files a holdings table
within 45 days of each quarter end. That 45-day gap is the entire point. The
holdings are dated to the quarter, the filing is dated to the day it was
accepted, and a backtest that reads the December positions in December is
trading on a document that did not exist yet. Both dates are kept, so `as_of`
returns the filing a researcher on that day would actually have had.

Two traps live in this data and both are handled here.

The first is the unit change. The SEC amended the form so that filings made from
3 January 2023 report market value in dollars; every filing before that reports
it in thousands. Nothing in the document says which. A series built across the
boundary jumps by a factor of a thousand, and it looks like a position change
rather than a units change. Everything here is normalised to dollars and the raw
unit is kept on the row.

The second is line duplication. A manager with several sub-advisers files one
row per manager per security, so Berkshire's spring 2026 table lists Ally three
times. Taking the first row understates the position; counting the rows
overstates the holding count. Rows sharing a security are summed and the count
of merged lines is kept.
"""

from __future__ import annotations

import re
import xml.etree.ElementTree as ET
from typing import Any

from .. import envelope
from ..http import SourceError, get_bytes, get_json

SOURCE = "sec-form-13f"
SUBMISSIONS = "https://data.sec.gov/submissions/{name}"
ARCHIVE = "https://www.sec.gov/Archives/edgar/data/{cik}/{acc}"
SEARCH = ("https://www.sec.gov/cgi-bin/browse-edgar?action=getcompany&company={q}"
          "&type=13F-HR&dateb=&owner=include&count=20&output=atom")
FILING_URL = "https://www.sec.gov/Archives/edgar/data/{cik}/{acc}/{doc}"

# Filings made on or after this date report market value in dollars. Earlier
# ones report thousands, and say nothing about it either way.
DOLLARS_FROM = "2023-01-03"

# The information table only became XML with the 2013 revision of the form.
# Older filings are a plain-text table with no fixed layout.
XML_FROM = "2013-06-30"

FIELDS = {
    "value": ("value", "USD"),
    "shares": ("shares", "shares"),
}

# Verified against EDGAR rather than remembered. Anything not here is found by
# name through `find`.
MANAGERS = {
    "BERKSHIRE": ("0001067983", "Berkshire Hathaway Inc"),
    "BRIDGEWATER": ("0001350694", "Bridgewater Associates, LP"),
    "RENAISSANCE": ("0001037389", "Renaissance Technologies LLC"),
    "CITADEL": ("0001423053", "Citadel Advisors LLC"),
    "TWOSIGMA": ("0001179392", "Two Sigma Investments, LP"),
    "MILLENNIUM": ("0001273087", "Millennium Management LLC"),
    "AQR": ("0001167557", "AQR Capital Management LLC"),
    "BAUPOST": ("0001061768", "Baupost Group LLC/MA"),
    "PERSHING": ("0001336528", "Pershing Square Capital Management, L.P."),
    "TIGERGLOBAL": ("0001167483", "Tiger Global Management LLC"),
    "SOROS": ("0001029160", "Soros Fund Management LLC"),
    "DESHAW": ("0001009268", "D. E. Shaw & Co, L.P."),
    "ELLIOTT": ("0001791786", "Elliott Investment Management L.P."),
    "APPALOOSA": ("0001656456", "Appaloosa LP"),
    "LONEPINE": ("0001061165", "Lone Pine Capital LLC"),
    "COATUE": ("0001135730", "Coatue Management LLC"),
    "VIKING": ("0001103804", "Viking Global Investors LP"),
    "DUQUESNE": ("0001536411", "Duquesne Family Office LLC"),
    "GREENLIGHT": ("0001079114", "Greenlight Capital Inc"),
    "THIRDPOINT": ("0001040273", "Third Point LLC"),
    "SCION": ("0001649339", "Scion Asset Management, LLC"),
    "ARK": ("0001697748", "ARK Investment Management LLC"),
    "HIMALAYA": ("0001709323", "Himalaya Capital Management LLC"),
    "MARSHALLWACE": ("0001318757", "Marshall Wace, LLP"),
    "MANGROUP": ("0001637460", "Man Group plc"),
}


def catalog() -> list[dict[str, Any]]:
    out = [
        {"field": "13f:value", "label": "13F position market value, USD",
         "source": SOURCE, "vintage": envelope.AS_FILED},
        {"field": "13f:shares", "label": "13F position size in shares",
         "source": SOURCE, "vintage": envelope.AS_FILED},
    ]
    out += [
        {"field": "13f:value", "entity": key, "label": f"13F holdings, {name}",
         "source": SOURCE, "vintage": envelope.AS_FILED}
        for key, (_, name) in MANAGERS.items()
    ]
    return out


# ------------------------------------------------------------------ the filer


def _digits(text: str) -> str | None:
    found = re.sub(r"\D", "", text or "")
    return found.zfill(10) if found else None


async def find(manager: str) -> dict[str, str]:
    """Resolve a manager to a CIK: a shortcut, a raw CIK, or a name search."""
    raw = (manager or "").strip()
    if not raw:
        raise SourceError(f"Name a manager. Shortcuts: {', '.join(sorted(MANAGERS))}.")

    key = re.sub(r"[^A-Z0-9]", "", raw.upper())
    if key in MANAGERS:
        cik, name = MANAGERS[key]
        return {"cik": cik, "name": name}

    if re.fullmatch(r"(CIK)?\d{1,10}", raw.upper().replace("-", "")):
        cik = _digits(raw)
        return {"cik": cik, "name": await _filer_name(cik)}

    url = SEARCH.format(q=re.sub(r"\s+", "+", raw.strip()))
    try:
        body = (await get_bytes(url, tier="monthly")).decode("utf-8", "replace")
    except SourceError as exc:
        raise SourceError(f"EDGAR company search failed for {raw!r}: {exc}") from exc

    ciks = [c.zfill(10) for c in re.findall(r"<cik>(\d+)</cik>", body, re.I)]
    if not ciks:
        raise SourceError(
            f"No 13F filer whose name starts with {raw!r}. EDGAR matches from the "
            "start of the registered name, so try the first word only. Shortcuts: "
            f"{', '.join(sorted(MANAGERS))}."
        )

    # A single hit carries its conformed name inline; a list does not, so the
    # name comes from the submissions file.
    exact = re.findall(r"<conformed-name>(.*?)</conformed-name>", body, re.I)
    if len(ciks) == 1 and exact:
        return {"cik": ciks[0], "name": exact[0].strip()}

    resolved = [{"cik": c, "name": await _filer_name(c)} for c in ciks[:6]]
    best = resolved[0]
    if len(resolved) > 1:
        best = {**best, "other_matches": [f"{r['name']} ({r['cik']})" for r in resolved[1:]]}
    return best


async def _filer_name(cik: str) -> str:
    payload = await get_json(
        SUBMISSIONS.format(name=f"CIK{cik}.json"), tier="monthly"
    )
    return payload.get("name") or cik


# --------------------------------------------------------------- the filings


async def filings(cik: str) -> list[dict[str, str]]:
    """Every 13F this filer has on record, newest first."""
    payload = await get_json(SUBMISSIONS.format(name=f"CIK{cik}.json"), tier="daily")
    blocks = [payload.get("filings", {}).get("recent", {})]

    # EDGAR pages a long history out into extra files. A prolific filer's 13Fs
    # can fall off the recent block entirely.
    for extra in payload.get("filings", {}).get("files", []) or []:
        if extra.get("name"):
            try:
                blocks.append(await get_json(
                    SUBMISSIONS.format(name=extra["name"]), tier="monthly"))
            except SourceError:
                continue

    out: list[dict[str, str]] = []
    for block in blocks:
        forms = block.get("form") or []
        for i, form in enumerate(forms):
            if not form.startswith("13F-HR"):
                continue
            out.append({
                "form": form,
                "accession": block["accessionNumber"][i],
                "filed": block["filingDate"][i],
                "period": block["reportDate"][i],
                "accepted": (block.get("acceptanceDateTime") or [None] * len(forms))[i],
            })

    if not out:
        raise SourceError(
            f"CIK {cik} has no 13F-HR filings. Only managers with over $100m in US "
            "equities file this form."
        )
    return sorted(out, key=lambda f: (f["period"], f["filed"]), reverse=True)


def chain(found: list[dict[str, str]], *, quarter: str | None,
          as_of: str | None) -> list[dict[str, str]]:
    """Every document that makes up one quarter's record, oldest first.

    With `as_of` set, anything filed later is invisible, so the answer is the
    most recent quarter that had actually been reported by then, which in the
    six weeks after a quarter end is the *previous* quarter, not the one that
    just closed. That gap is the reason this source exists.

    A quarter is rarely one document. Amendments come in two kinds and the
    cover page is the only place that says which: a RESTATED amendment replaces
    the table, a NEW HOLDINGS amendment lists only what was added. Treating the
    second as the whole portfolio turns Pershing Square's December 2024 book
    into a single position, which is why this returns the chain rather than the
    last filing.
    """
    pool = [f for f in found if not as_of or f["filed"] <= as_of]
    if quarter:
        want = quarter.strip()
        pool = [f for f in pool
                if f["period"] == want or f["period"].startswith(want[:7])
                or f["period"][:4] == want]
    if not pool:
        periods = [f["period"] for f in found]
        span = f"{min(periods)} to {max(periods)}"
        raise SourceError(
            f"No 13F matches that request. This filer reported {span}"
            + (f", and nothing was on file by {as_of}." if as_of else ".")
        )

    period = max(f["period"] for f in pool)
    return sorted((f for f in pool if f["period"] == period), key=lambda f: f["filed"])


# ------------------------------------------------------- the holdings table


def _strip(tag: str) -> str:
    return tag.rsplit("}", 1)[-1]


def _text(node: ET.Element, name: str) -> str | None:
    for child in node.iter():
        if _strip(child.tag) == name and child.text:
            return child.text.strip()
    return None


async def cover(cik: str, accession: str) -> dict[str, Any]:
    """The filing's own account of itself.

    `amendmentType` decides whether the table replaces the quarter or adds to
    it, and `tableEntryTotal` is the filer's own line count, which is a free
    check that the parse did not lose rows.
    """
    acc = accession.replace("-", "")
    base = ARCHIVE.format(cik=int(cik), acc=acc)
    try:
        raw = await get_bytes(f"{base}/primary_doc.xml", tier="immutable")
    except SourceError:
        return {}

    text = raw.decode("utf-8", "replace")

    def tag(name: str) -> str | None:
        found = re.search(rf"<{name}>(.*?)</{name}>", text, re.S | re.I)
        return found.group(1).strip() if found else None

    entries = tag("tableEntryTotal")
    return {
        "amendment": (tag("isAmendment") or "").lower() == "true",
        "amendment_type": (tag("amendmentType") or "").upper() or None,
        "entry_total": int(entries) if (entries or "").isdigit() else None,
        "manager": tag("name"),
    }


async def _table_xml(cik: str, accession: str) -> bytes:
    acc = accession.replace("-", "")
    base = ARCHIVE.format(cik=int(cik), acc=acc)
    index = await get_json(f"{base}/index.json", tier="immutable")
    names = [item.get("name", "") for item in
             (index.get("directory", {}).get("item") or [])]

    # The table is named by the filing agent, so it can be anything from
    # form13fInfoTable.xml to 53405.xml. Everything but the cover page is a
    # candidate and the root element settles it.
    candidates = [n for n in names
                  if n.lower().endswith(".xml") and "primary_doc" not in n.lower()]
    for name in candidates:
        raw = await get_bytes(f"{base}/{name}", tier="immutable")
        if b"informationTable" in raw or b"infoTable" in raw:
            return raw

    raise SourceError(
        f"Filing {accession} carries no XML holdings table. Form 13F only became "
        f"structured XML in mid-{XML_FROM[:4]}; earlier filings are plain text with no "
        "fixed layout and are not parsed here."
    )


def parse(raw: bytes) -> list[dict[str, Any]]:
    """Read one information table into line items, before any aggregation."""
    try:
        root = ET.fromstring(raw)
    except ET.ParseError as exc:
        raise SourceError(f"13F information table would not parse: {exc}") from exc

    items = []
    for node in root.iter():
        if _strip(node.tag) != "infoTable":
            continue

        def number(name: str) -> float:
            text = (_text(node, name) or "0").replace(",", "")
            try:
                return float(text)
            except ValueError:
                return 0.0

        cusip = (_text(node, "cusip") or "").strip().upper()
        if not cusip:
            continue
        items.append({
            "cusip": cusip,
            "issuer": _text(node, "nameOfIssuer"),
            "title_of_class": _text(node, "titleOfClass"),
            "value_raw": number("value"),
            "shares": number("sshPrnamt"),
            "share_type": _text(node, "sshPrnamtType"),
            "put_call": _text(node, "putCall"),
            "discretion": _text(node, "investmentDiscretion"),
            "sole_voting": number("Sole"),
        })

    if not items:
        raise SourceError("13F information table contained no holdings")
    return items


def merge(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Sum the line items a manager splits across its sub-advisers.

    Values arrive already scaled to dollars, because a quarter can be made of
    filings from either side of the 2023 units change.
    """
    grouped: dict[tuple, dict[str, Any]] = {}
    for item in items:
        key = (item["cusip"], item["title_of_class"], item["put_call"])
        holding = grouped.get(key)
        if holding is None:
            grouped[key] = {**item, "line_items": 1}
            continue
        holding["value_usd"] += item["value_usd"]
        holding["shares"] += item["shares"]
        holding["sole_voting"] += item["sole_voting"]
        holding["line_items"] += 1
        # A position amended later was not fully known until that amendment.
        if item.get("filed", "") > holding.get("filed", ""):
            holding["filed"] = item["filed"]
            holding["form"] = item["form"]
            holding["accession"] = item["accession"]
    return sorted(grouped.values(), key=lambda h: -h["value_usd"])


async def assemble(cik: str, documents: list[dict[str, str]]) -> dict[str, Any]:
    """Fold a quarter's filings into one holdings table, oldest first."""
    items: list[dict[str, Any]] = []
    parts: list[dict[str, Any]] = []
    skipped: list[str] = []

    for filing in documents:
        page = await cover(cik, filing["accession"])
        kind = page.get("amendment_type")
        try:
            lines = parse(await _table_xml(cik, filing["accession"]))
        except SourceError as exc:
            # A confidential-treatment amendment can carry no table at all.
            skipped.append(f"{filing['form']} {filing['filed']}: {exc}")
            continue

        # Thousands before the 2023 amendment, dollars after. The document does
        # not say which, so the filing date decides, per document, because a
        # quarter can straddle the boundary.
        scale = 1.0 if filing["filed"] >= DOLLARS_FROM else 1_000.0
        for line in lines:
            line["value_usd"] = line.pop("value_raw") * scale
            line["filed"] = filing["filed"]
            line["form"] = filing["form"]
            line["accession"] = filing["accession"]

        if kind == "RESTATED":
            items = lines            # a restatement replaces the quarter
        else:
            items += lines           # an original, or NEW HOLDINGS on top

        parts.append({
            "form": filing["form"], "filed": filing["filed"],
            "accession": filing["accession"], "amendment_type": kind,
            "lines": len(lines), "entry_total": page.get("entry_total"),
            "reported_unit": "USD" if scale == 1.0 else "USD thousands",
        })

    if not items:
        detail = " ".join(skipped) or "no holdings table could be read"
        raise SourceError(f"No 13F holdings for that quarter: {detail}")

    return {"holdings": merge(items), "parts": parts, "skipped": skipped}


async def holdings(manager: str, *, field: str = "value", quarter: str | None = None,
                   as_of: str | None = None, limit: int = 400) -> list[dict[str, Any]]:
    """One manager's reported positions for one quarter."""
    if field not in FIELDS:
        raise SourceError(
            f"No 13F field {field!r}. Available: {', '.join(FIELDS)}."
        )

    filer = await find(manager)
    found = await filings(filer["cik"])
    documents = chain(found, quarter=quarter, as_of=as_of)
    period = documents[0]["period"]

    built = await assemble(filer["cik"], documents)
    merged = built["holdings"]
    total = sum(h["value_usd"] for h in merged)
    _, unit = FIELDS[field]

    # One short string rather than the whole chain on every row. The cover page
    # states its own line count, so a mismatch means the parse lost rows and
    # says so rather than quietly returning a smaller portfolio.
    def describe(part: dict[str, Any]) -> str:
        text = part["form"] + " " + part["filed"]
        if part["amendment_type"]:
            text += " " + part["amendment_type"]
        expected = part["entry_total"]
        if expected is not None and expected != part["lines"]:
            text += f" (cover page says {expected} lines, {part['lines']} parsed)"
        return text

    trail = "; ".join(describe(p) for p in built["parts"])

    rows = []
    for holding in merged[:limit]:
        dollars = holding["value_usd"]
        rows.append(
            envelope.row(
                entity=holding["cusip"],
                field=f"13f:{field}",
                observed_at=period,
                # Reported up to 45 days after the quarter it describes, and
                # per document, so an amended line carries its later date.
                known_at=holding["filed"],
                value=dollars if field == "value" else holding["shares"],
                unit=unit,
                source=SOURCE,
                source_url=ARCHIVE.format(
                    cik=int(filer["cik"]),
                    acc=holding["accession"].replace("-", "")),
                vintage=envelope.AS_FILED,
                issuer=holding["issuer"],
                cusip=holding["cusip"],
                title_of_class=holding["title_of_class"],
                shares=holding["shares"],
                share_type=holding["share_type"],
                market_value_usd=dollars,
                weight=round(dollars / total, 6) if total else None,
                put_call=holding["put_call"],
                discretion=holding["discretion"],
                line_items=holding["line_items"],
                filer=filer["name"],
                filer_cik=filer["cik"],
                form=holding["form"],
                accession=holding["accession"],
                filed=holding["filed"],
                reported_unit=next(
                    (p["reported_unit"] for p in built["parts"]
                     if p["accession"] == holding["accession"]), "USD"),
                filing_chain=trail,
            )
        )
    return rows


def warnings_for(rows: list[dict[str, Any]], as_of: str | None = None) -> list[str]:
    if not rows:
        return []
    head = rows[0]
    lag = _days_between(head["observed_at"], head["known_at"])
    notes = [
        f"{head['filer']} reported these positions as of {head['observed_at']} and filed "
        f"them on {head['known_at']}, {lag} days later. Nothing here was public before "
        "that filing date, which is why known_at carries it."
        + (f" as_of={as_of} selected this filing accordingly."
           if as_of else " Pass as_of to see the filing that was current on a given day."),
        "13F covers long US equity, ADRs, convertibles and listed options only. Short "
        "positions, cash, bonds, commodities and foreign listings are not reported, so "
        "this is one side of a book and never the book.",
    ]
    trail = head.get("filing_chain") or ""
    if "/A" in trail:
        kind = ("adds positions to the original rather than replacing it"
                if "NEW HOLDINGS" in trail else "replaces the original table")
        notes.append(
            f"This quarter is made of more than one document, {trail}. The amendment "
            f"{kind}, so the two are combined here. Each row's known_at is the date of "
            "the document that row came from, which is why they are not all the same."
        )
    if head["reported_unit"] != "USD":
        notes.append(
            "Filed before January 2023, when the form reported market value in "
            "thousands. Values here are multiplied by 1,000 to keep the series in "
            "dollars across that boundary."
        )
    merged = sum(1 for r in rows if r.get("line_items", 1) > 1)
    if merged:
        notes.append(
            f"{merged} position(s) were filed as several lines across sub-advisers and "
            "have been summed. `line_items` records how many."
        )
    return notes


def _days_between(start: str | None, end: str | None) -> int:
    import datetime as dt
    try:
        return (dt.date.fromisoformat(end) - dt.date.fromisoformat(start)).days
    except (TypeError, ValueError):
        return 0
