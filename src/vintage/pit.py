"""Point-in-time prices: the adjusted series as it stood on a chosen date.

An adjusted close is not a fact about the past, it is a fact about today. Every
split and dividend since rewrites it, so a series pulled now shows Apple near
$2 in 2006. A number no screen ever displayed and no order was ever filled at.
Backtests built on it inherit a subtle look-ahead, because the adjustment
encodes corporate actions the trader had not seen yet.

The raw close does not have this problem. It is what printed that day and it
never changes. Corporate actions are separately dated. So the honest adjusted
series is reconstructible:

    adjusted(t | as_of) = raw_close(t) x product of factors for every corporate
                          action e with t < e.date <= as_of

Only actions that had already happened by `as_of` are applied. Ask for
2010-01-01 and you get what a 2010 screen showed, including the four-for-one
split in 2020 being absent, because in 2010 it had not happened.

Two conventions worth stating, since both are choices:

- Splits use the ratio directly. A 2:1 divides pre-split prices by two.
- Dividends use the standard proportional method: the factor is
  1 - amount / close_on_the_day_before_ex. That is what Yahoo and CRSP do,
  and it keeps returns continuous across the ex-date.
"""

from __future__ import annotations

import datetime as dt
from typing import Any, Iterable

from . import envelope

SOURCE = "yahoo-finance"


def _iso(stamp: int) -> str:
    return dt.datetime.fromtimestamp(stamp, dt.timezone.utc).date().isoformat()


def actions(result: dict[str, Any]) -> list[dict[str, Any]]:
    """Splits and dividends, dated, oldest first."""
    events = result.get("events") or {}
    out: list[dict[str, Any]] = []

    for raw in (events.get("splits") or {}).values():
        num, den = raw.get("numerator"), raw.get("denominator")
        if not num or not den:
            continue
        out.append({"date": _iso(raw["date"]), "kind": "split",
                    "ratio": float(num) / float(den),
                    "label": raw.get("splitRatio") or f"{num}:{den}"})

    for raw in (events.get("dividends") or {}).values():
        amount = raw.get("amount")
        if not amount:
            continue
        out.append({"date": _iso(raw["date"]), "kind": "dividend",
                    "amount": float(amount), "label": f"{amount}"})

    return sorted(out, key=lambda e: e["date"])


def unadjust(closes: dict[str, float],
             corporate_actions: Iterable[dict[str, Any]]) -> dict[str, float]:
    """Undo the split adjustment already baked into the feed.

    Yahoo's `quote.close` is not the raw print. It is split-adjusted but not
    dividend-adjusted, which is easy to miss because it looks like a close.
    Building a point-in-time series on top of it would silently inherit the
    retroactive adjustment it is meant to remove: Apple's 2009 close comes back
    as 7.53 rather than 210.73, because the 7:1 in 2014 and 4:1 in 2020 are
    already folded in.

    Multiplying back every split *after* a bar recovers the number that
    actually printed.
    """
    splits = sorted((e for e in corporate_actions if e["kind"] == "split"),
                    key=lambda e: e["date"])
    if not splits:
        return dict(closes)

    out, factor = {}, 1.0
    remaining = list(splits)
    for date in sorted(closes, reverse=True):
        while remaining and remaining[-1]["date"] > date:
            factor *= remaining.pop()["ratio"]
        out[date] = closes[date] * factor
    return out


def adjust(
    closes: dict[str, float],
    corporate_actions: Iterable[dict[str, Any]],
    as_of: str | None = None,
) -> dict[str, float]:
    """Back-adjust raw closes using only actions knowable on `as_of`.

    Walking backwards from the most recent date keeps this one pass: the
    running factor accumulates each action as it is passed, and every earlier
    price is multiplied by the factor standing at that point.
    """
    if not closes:
        return {}

    dates = sorted(closes)
    # Scope is set by `as_of` alone. An earlier version also dropped actions
    # dated after the last bar, which made the adjustment depend on where the
    # requested window happened to end: asking for 2009 only would return the
    # unadjusted print, while asking for 2009-2026 returned it divided by 28.
    live = [e for e in corporate_actions if as_of is None or e["date"] <= as_of]
    if not live:
        return dict(closes)

    by_date: dict[str, list[dict[str, Any]]] = {}
    for e in live:
        by_date.setdefault(e["date"], []).append(e)

    out: dict[str, float] = {}
    factor = 1.0
    previous: str | None = None

    for date in reversed(dates):
        # Actions dated *after* this bar but at or before the one we just
        # handled have now been passed, so they apply from here backwards.
        for stamp, events in by_date.items():
            if date < stamp and (previous is None or stamp <= previous):
                for e in events:
                    if e["kind"] == "split":
                        factor /= e["ratio"]
                    else:
                        base = closes.get(_previous_date(dates, stamp))
                        if base:
                            factor *= max(0.0, 1.0 - e["amount"] / base)
        out[date] = round(closes[date] * factor, 6)
        previous = date

    return out


def _previous_date(dates: list[str], stamp: str) -> str | None:
    """The last trading day strictly before an ex-date."""
    lo, hi = 0, len(dates)
    while lo < hi:
        mid = (lo + hi) // 2
        if dates[mid] < stamp:
            lo = mid + 1
        else:
            hi = mid
    return dates[lo - 1] if lo else None


def rows(
    symbol: str,
    closes: dict[str, float],
    corporate_actions: list[dict[str, Any]],
    *,
    as_of: str | None = None,
    currency: str = "USD",
) -> list[dict[str, Any]]:
    """Point-in-time adjusted closes, as envelope rows.

    `closes` is the feed's close, which arrives split-adjusted; it is
    un-adjusted back to the printed number first, then re-adjusted using only
    the actions knowable on `as_of`.

    These carry `AS_FILED` rather than `adjusted-retroactively`, because that
    is now true: nothing in the level depends on information published after
    `known_at`.
    """
    raw = unadjust(closes, corporate_actions)
    adjusted = adjust(raw, corporate_actions, as_of=as_of)
    applied = sum(1 for e in corporate_actions if as_of is None or e["date"] <= as_of)

    return [
        envelope.row(
            entity=symbol,
            field="price:pit_adjclose",
            observed_at=date,
            known_at=date,
            value=value,
            unit=currency,
            source=SOURCE,
            source_url=f"https://finance.yahoo.com/quote/{symbol}/history",
            vintage=envelope.AS_FILED,
            as_of=as_of,
            actions_applied=applied,
            actions_known=len(corporate_actions),
        )
        for date, value in sorted(adjusted.items())
    ]


def warnings_for(corporate_actions: list[dict[str, Any]], as_of: str | None) -> list[str]:
    if as_of is None:
        return []
    later = [e for e in corporate_actions if e["date"] > as_of]
    if not later:
        return []
    splits = [e for e in later if e["kind"] == "split"]
    note = (f"{len(later)} corporate action(s) after {as_of} were excluded, "
            f"including {len(splits)} split(s)")
    if splits:
        note += f" ({', '.join(e['label'] + ' on ' + e['date'] for e in splits[:3])})"
    return [note + ". This series is what a screen showed on that date, not what "
                   "a chart shows today."]
