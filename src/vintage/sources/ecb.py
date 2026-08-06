"""European Central Bank reference rates — free foreign exchange, no key.

The ECB publishes one set of reference rates each working day at about 16:00
CET and never revises them, so these are genuinely point-in-time: `known_at` is
the publication date and the number never changes afterwards. That is rarer
than it sounds, and it makes FX one of the cleaner corners of this project.

Everything is quoted against the euro. A cross rate such as USD/JPY is derived
the way the ECB itself describes: divide one euro leg by the other. Doing that
in one place keeps the convention from being reinvented, backwards, in a
notebook.

The full history is a single 640 KB zip going back to 1999, which is one
request rather than one per currency.
"""

from __future__ import annotations

import csv
import io
import zipfile
from typing import Any

from .. import envelope
from ..http import SourceError, get_bytes

SOURCE = "ecb-reference-rates"
HIST_ZIP = "https://www.ecb.europa.eu/stats/eurofxref/eurofxref-hist.zip"
HOME = "https://www.ecb.europa.eu/stats/policy_and_exchange_rates/euro_reference_exchange_rates/html/index.en.html"

BASE = "EUR"

# The majors, so `discover` answers before anyone reads the currency list.
MAJORS = ["USD", "JPY", "GBP", "CHF", "AUD", "CAD", "CNY", "SEK", "NOK", "NZD"]


async def table() -> tuple[list[str], dict[str, dict[str, float]]]:
    """(currencies, {date: {currency: rate}}) for the full history."""
    raw = await get_bytes(HIST_ZIP, tier="daily")
    try:
        with zipfile.ZipFile(io.BytesIO(raw)) as zf:
            name = next(n for n in zf.namelist() if n.lower().endswith(".csv"))
            text = zf.read(name).decode("utf-8-sig")
    except (zipfile.BadZipFile, StopIteration) as exc:
        raise SourceError(f"ECB history archive was unreadable: {exc}") from exc

    reader = csv.reader(io.StringIO(text))
    header = [h.strip() for h in next(reader)]
    currencies = [h for h in header[1:] if h]

    out: dict[str, dict[str, float]] = {}
    for row in reader:
        if not row or not row[0].strip():
            continue
        day = row[0].strip()
        rates: dict[str, float] = {}
        for currency, cell in zip(header[1:], row[1:]):
            cell = (cell or "").strip()
            if not currency or cell in ("", "N/A"):
                continue
            try:
                rates[currency] = float(cell)
            except ValueError:
                continue
        if rates:
            out[day] = rates
    if not out:
        raise SourceError("ECB history archive contained no rates")
    return currencies, out


def catalog(currencies: list[str] | None = None) -> list[dict[str, Any]]:
    codes = currencies or MAJORS
    return [
        {"field": f"fx:EUR{code}", "label": f"Euro to {code}, ECB reference rate",
         "source": SOURCE, "vintage": envelope.AS_FILED}
        for code in codes
    ]


def parse_pair(pair: str) -> tuple[str, str]:
    """'EURUSD', 'usd', 'USD/JPY' and 'USDJPY' all resolve to a base and quote."""
    text = pair.strip().upper().replace("/", "").replace("-", "")
    if len(text) == 3:
        return BASE, text                       # a bare code is quoted against EUR
    if len(text) != 6:
        raise SourceError(
            f"Cannot read currency pair {pair!r}. Use EURUSD, USDJPY or a bare code."
        )
    return text[:3], text[3:]


async def rates(pair: str = "EURUSD", *, start: str | None = None,
                end: str | None = None) -> list[dict[str, Any]]:
    """Daily rates for one pair, quoted as base/quote.

    Cross rates are computed from the two euro legs, which is how the ECB
    documents it: EUR/quote divided by EUR/base.
    """
    base, quote = parse_pair(pair)
    currencies, history = await table()

    known = set(currencies) | {BASE}
    for code in (base, quote):
        if code not in known:
            near = sorted(c for c in known if c.startswith(code[:1]))[:8]
            raise SourceError(
                f"ECB publishes no rate for {code!r}. "
                f"{len(known)} currencies available"
                + (f", nearby: {', '.join(near)}" if near else "") + "."
            )

    rows = []
    for day in sorted(history):
        if (start and day < start) or (end and day > end):
            continue
        legs = history[day]
        num = 1.0 if quote == BASE else legs.get(quote)
        den = 1.0 if base == BASE else legs.get(base)
        if not num or not den:
            continue
        rows.append(
            envelope.row(
                entity=f"{base}{quote}",
                field=f"fx:{base}{quote}",
                observed_at=day,
                # Published that afternoon and never revised.
                known_at=day,
                value=round(num / den, 8),
                unit=f"{quote} per {base}",
                source=SOURCE,
                source_url=HOME,
                vintage=envelope.AS_FILED,
            )
        )

    if not rows:
        raise SourceError(f"ECB has no {base}{quote} rates in that window")
    return rows


def warnings_for(pair: str) -> list[str]:
    base, quote = parse_pair(pair)
    if BASE in (base, quote):
        return []
    return [
        f"{base}{quote} is a cross rate derived from EUR{base} and EUR{quote}. "
        "The ECB quotes only against the euro, so this is arithmetic on two "
        "reference rates rather than a traded quote, and it will not match a "
        "broker's fix exactly."
    ]
