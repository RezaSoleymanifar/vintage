"""Form 4 insider transactions, opened rather than merely counted.

The filing stream already reports that a Form 4 landed. That is a calendar of
paperwork, not a signal: most Form 4s record an option exercising itself or
shares withheld to pay the tax on a vest, and neither is a decision anybody
made that morning. The first Form 4 tested against this parser was Apple's, and
its two transactions were coded `M` and `F` -- exercise and tax withholding.
Nothing was bought or sold by choice.

What separates the two is `transactionCode`, one letter in the XML the filing
stream never opens. `P` and `S` are open-market purchases and sales: someone
decided. Everything else is the machinery of compensation.

Two dates, as always. `observed_at` is the transaction date; `known_at` is when
the SEC accepted the filing, due within two business days. That two-day lag is
the reason this source is worth having next to 13F's forty-five.

Vintage does not classify insiders as routine or opportunistic in the sense of
Cohen, Malloy & Pomorski (2012) -- that requires years of an individual's filing
history, not one document. What is offered here is the narrower, checkable fact:
whether a transaction happened on the open market or was compensation
mechanics. `open_market` carries that, and it is a fact from the filing rather
than an inference on top of it.
"""

from __future__ import annotations

import datetime as dt
import re
import xml.etree.ElementTree as ET
from typing import Any

from .. import envelope
from ..http import SourceError, get_bytes, get_json
from . import edgar

SOURCE = "sec-form-4"
ARCHIVE = "https://www.sec.gov/Archives/edgar/data/{cik}/{accession}/{document}"

# EDGAR's primaryDocument for an ownership form points at the styled rendering,
# `xslF345X06/form4.xml`. Stripping the transform directory gives the machine
# readable original underneath it.
XSL_PREFIX = re.compile(r"^xsl[^/]*/")

# Table I of the form. Codes are defined in the Form 4 instructions.
CODES = {
    "P": ("purchase", "open-market purchase", True),
    "S": ("sale", "open-market sale", True),
    "A": ("grant", "grant or award", False),
    "M": ("option exercise", "exercise of a derivative", False),
    "F": ("tax withholding", "shares withheld to pay tax", False),
    "G": ("gift", "bona fide gift", False),
    "D": ("disposition to issuer", "returned to the issuer", False),
    "C": ("conversion", "conversion of a derivative", False),
    "X": ("option exercise", "in-the-money option exercised", False),
    "J": ("other", "other, described in a footnote", False),
    "I": ("discretionary", "discretionary transaction", False),
    "W": ("inheritance", "acquired or disposed by will", False),
}


def catalog() -> list[dict[str, Any]]:
    return [
        {"field": "insider:trades",
         "label": "Form 4 insider transactions, with the code that says why",
         "source": SOURCE, "vintage": envelope.AS_FILED},
        {"field": "insider:open_market",
         "label": "Form 4 open-market buys and sells only, the discretionary subset",
         "source": SOURCE, "vintage": envelope.AS_FILED},
    ]


def _text(node: ET.Element | None) -> str | None:
    """Value of a Form 4 field, which wraps most leaves in <value>."""
    if node is None:
        return None
    inner = node.find("value")
    target = inner if inner is not None else node
    return (target.text or "").strip() or None


def _number(node: ET.Element | None) -> float | None:
    raw = _text(node)
    if raw is None:
        return None
    try:
        return float(raw)
    except ValueError:
        return None


def parse(xml: bytes) -> dict[str, Any]:
    """One Form 4 document into its owner and its transactions."""
    try:
        root = ET.fromstring(xml)
    except ET.ParseError as exc:
        raise SourceError(f"Form 4 was not parseable XML: {exc}") from exc

    owner = root.find("reportingOwner")
    name = title = None
    roles: list[str] = []
    if owner is not None:
        name = _text(owner.find("reportingOwnerId/rptOwnerName"))
        relation = owner.find("reportingOwnerRelationship")
        if relation is not None:
            title = _text(relation.find("officerTitle"))
            for tag, label in (("isDirector", "director"),
                               ("isOfficer", "officer"),
                               ("isTenPercentOwner", "10% owner")):
                flag = _text(relation.find(tag))
                if flag and flag.lower() in ("1", "true"):
                    roles.append(label)

    issuer = root.find("issuer")
    ticker = _text(issuer.find("issuerTradingSymbol")) if issuer is not None else None
    company = _text(issuer.find("issuerName")) if issuer is not None else None

    transactions = []
    for node in root.findall("nonDerivativeTable/nonDerivativeTransaction"):
        code = _text(node.find("transactionCoding/transactionFormType"))
        letter = _text(node.find("transactionCoding/transactionCode"))
        if not letter:
            continue
        action, gloss, open_market = CODES.get(
            letter, ("other", f"code {letter}, not in the standard table", False))

        shares = _number(node.find("transactionAmounts/transactionShares"))
        price = _number(node.find("transactionAmounts/transactionPricePerShare"))
        disposed = _text(
            node.find("transactionAmounts/transactionAcquiredDisposedCode"))
        traded = _text(node.find("transactionDate"))
        if not traded:
            continue

        transactions.append({
            "observed_at": traded,
            "code": letter,
            "form_type": code,
            "action": action,
            "gloss": gloss,
            "open_market": open_market,
            "direction": "acquired" if disposed == "A" else "disposed",
            "shares": shares,
            "price": price,
            # Price is absent on a grant and on an exercise priced by footnote,
            # so the dollar value is None rather than zero. Zero would sum.
            "usd": round(shares * price, 2) if shares and price else None,
            "security": _text(node.find("securityTitle")),
            "held_after": _number(
                node.find("postTransactionAmounts/sharesOwnedFollowingTransaction")),
        })

    return {
        "owner": name, "title": title, "roles": roles,
        "ticker": ticker, "company": company, "transactions": transactions,
    }


async def trades(entity: str, *, limit: int = 60,
                 open_market_only: bool = False) -> list[dict[str, Any]]:
    """Form 4 transactions for one issuer, newest acceptance first."""
    resolved = await edgar.resolve(entity)
    cik = resolved["cik"]

    data = await get_json(
        edgar.SUBMISSIONS_URL.format(cik=cik), tier="session")
    recent = data.get("filings", {}).get("recent", {})
    forms = recent.get("form", [])

    rows: list[dict[str, Any]] = []
    unreadable = 0
    for i, form in enumerate(forms):
        if len(rows) >= limit:
            break
        if form != "4":
            continue

        accession = recent["accessionNumber"][i].replace("-", "")
        document = XSL_PREFIX.sub("", recent["primaryDocument"][i])
        url = ARCHIVE.format(cik=int(cik), accession=accession, document=document)
        accepted = (recent["acceptanceDateTime"][i] or "")[:10] \
            or recent["filingDate"][i]

        try:
            filing = parse(await get_bytes(url, tier="monthly"))
        except SourceError:
            unreadable += 1
            continue

        for txn in filing["transactions"]:
            if open_market_only and not txn["open_market"]:
                continue
            rows.append(envelope.row(
                entity=(filing["ticker"] or resolved.get("ticker")
                        or entity).upper(),
                field="insider:trades",
                observed_at=txn["observed_at"],
                # Due within two business days of the trade. This is the whole
                # argument for the source: 13F says the same kind of thing 45
                # days after the fact.
                known_at=accepted,
                value=txn["usd"] if txn["usd"] is not None else txn["shares"],
                unit="USD" if txn["usd"] is not None else "shares",
                source=SOURCE,
                source_url=url,
                vintage=envelope.AS_FILED,
                company=filing["company"],
                insider=filing["owner"],
                insider_title=filing["title"],
                insider_roles=", ".join(filing["roles"]) or None,
                transaction_code=txn["code"],
                action=txn["action"],
                means=txn["gloss"],
                open_market=txn["open_market"],
                direction=txn["direction"],
                shares=txn["shares"],
                price_per_share=txn["price"],
                usd=txn["usd"],
                security=txn["security"],
                shares_held_after=txn["held_after"],
                filing_lag_days=_lag(txn["observed_at"], accepted),
            ))

    if not rows:
        where = "open-market " if open_market_only else ""
        raise SourceError(
            f"No {where}Form 4 transactions found for {entity!r}"
            + (f" ({unreadable} filings unreadable)" if unreadable else "")
        )
    return rows[:limit]


def _lag(traded: str, accepted: str) -> int | None:
    try:
        return (dt.date.fromisoformat(accepted)
                - dt.date.fromisoformat(traded)).days
    except ValueError:
        return None


def warnings_for(rows: list[dict[str, Any]]) -> list[str]:
    notes = [
        "transaction_code is the field that matters. `P` and `S` are decisions "
        "somebody made; `A`, `M` and `F` are a grant vesting, an option "
        "exercising and shares withheld to pay the tax on it. Counting Form 4s "
        "without reading the code counts payroll events.",
        "observed_at is the transaction date, known_at is SEC acceptance, due "
        "within two business days. Both are kept and only known_at is tradeable.",
    ]
    if not rows:
        return notes

    mechanical = [r for r in rows if not r.get("open_market")]
    if mechanical:
        notes.append(
            f"{len(mechanical)} of {len(rows)} transactions here were "
            "compensation mechanics rather than open-market trades. Pass "
            "insider:open_market to drop them."
        )
    priceless = [r for r in rows if r.get("usd") is None]
    if priceless:
        notes.append(
            f"{len(priceless)} transactions carry no price, usually because a "
            "grant has none or the form puts it in a footnote. Their value is "
            "reported in shares and must not be summed with the dollar rows."
        )
    lags = [r["filing_lag_days"] for r in rows if r.get("filing_lag_days") is not None]
    if lags:
        notes.append(
            f"Filing lag here runs {min(lags)} to {max(lags)} days against a "
            "two-business-day deadline."
        )
    return notes
