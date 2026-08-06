"""What exists, and which source answers for it.

`discover` is how breadth becomes usable: twenty sources behind one search
instead of twenty tool names the model has to read.
"""

from __future__ import annotations

from typing import Any

from .sources import fred, french

# Field prefix -> source. This is the router.
PREFIXES = {
    "price:": "prices",
    "fred:": "fred",
    "french:": "french",
    "filing:": "sec-edgar-filings",
    "us-gaap:": "sec-edgar-xbrl",
    "dei:": "sec-edgar-xbrl",
    "ifrs-full:": "sec-edgar-xbrl",
    "srt:": "sec-edgar-xbrl",
    "invest:": "sec-edgar-xbrl",
}

SOURCES = [
    {
        "source": "sec-edgar-xbrl",
        "covers": "US filer fundamentals, every XBRL concept",
        "field_form": "us-gaap:Assets (needs an entity)",
        "point_in_time": "yes — native filing dates",
        "key_required": False,
    },
    {
        "source": "sec-edgar-filings",
        "covers": "filing stream: 8-K, 10-K, 10-Q, Form 4, 13D/G",
        "field_form": "filing:* (needs an entity)",
        "point_in_time": "yes — exact filing timestamps",
        "key_required": False,
    },
    {
        "source": "yahoo-finance",
        "covers": "daily OHLCV and adjusted close, full history",
        "field_form": "price:close / price:adjclose (needs an entity)",
        "point_in_time": "partial — adjusted retroactively",
        "key_required": False,
        "note": "unofficial endpoint; Stooq is blocked behind a JS check as of 2026-08",
    },
    {
        "source": "ken-french-data-library",
        "covers": "Fama-French factors, momentum, industry portfolios",
        "field_form": "french:ff3, french:ff5, french:momentum",
        "point_in_time": "no — rebuilt on each release",
        "key_required": False,
    },
    {
        "source": "fred",
        "covers": "800k macro series, with ALFRED first-release vintages",
        "field_form": "fred:CPIAUCSL",
        "point_in_time": "yes — real-time vintages",
        "key_required": True,
    },
]

# Hand-picked series so `discover` answers well before FRED has a key.
CURATED = [
    {"field": "fred:DGS10", "label": "10-year Treasury constant maturity yield"},
    {"field": "fred:DGS2", "label": "2-year Treasury yield"},
    {"field": "fred:CPIAUCSL", "label": "CPI, all urban consumers"},
    {"field": "fred:UNRATE", "label": "Unemployment rate"},
    {"field": "fred:GDPC1", "label": "Real GDP"},
    {"field": "fred:FEDFUNDS", "label": "Effective federal funds rate"},
    {"field": "fred:T10Y2Y", "label": "10y-2y term spread"},
    {"field": "fred:BAMLH0A0HYM2", "label": "High-yield credit spread"},
    {"field": "fred:VIXCLS", "label": "VIX"},
    {"field": "fred:SOFR", "label": "Secured overnight financing rate"},
    {"field": "fred:M2SL", "label": "M2 money stock"},
    {"field": "fred:INDPRO", "label": "Industrial production"},
]


def route(field: str) -> str | None:
    for prefix, source in PREFIXES.items():
        if field.startswith(prefix):
            return source
    return "sec-edgar-xbrl" if ":" not in field else None


def static_catalog() -> list[dict[str, Any]]:
    return french.catalog() + [
        {**item, "source": "fred", "key_required": not fred.has_key()}
        for item in CURATED
    ]


def search_static(query: str, limit: int = 25) -> list[dict[str, Any]]:
    terms = [t for t in query.lower().split() if t]
    scored = []
    for item in static_catalog():
        haystack = f"{item.get('field','')} {item.get('label','')}".lower()
        score = sum(1 for t in terms if t in haystack)
        if score:
            scored.append((score, item))
    scored.sort(key=lambda pair: -pair[0])
    return [item for _, item in scored[:limit]]
