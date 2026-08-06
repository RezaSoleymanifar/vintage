"""What exists, and which source answers for it.

`discover` is how breadth becomes usable: twenty sources behind one search
instead of twenty tool names the model has to read.
"""

from __future__ import annotations

from typing import Any

from .sources import apewisdom, cboe, ecb, fred, french

# Field prefix -> source. This is the router.
PREFIXES = {
    "price:": "prices",
    "fred:": "fred",
    "french:": "french",
    "openap:": "openap",
    "ape:": "apewisdom",
    "crypto:": "crypto",
    "short:": "finra",
    "fx:": "ecb",
    "vol:": "cboe",
    "delisting:": "delistings",
    "index:": "prices",
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
        "source": "open-source-asset-pricing",
        "covers": "331 published anomalies with the return and t-stat each paper claimed",
        "field_form": "openap:Mom12m, or openap:* for all of them",
        "point_in_time": "yes — claims are dated to their publication year",
        "key_required": False,
        "note": "Chen & Zimmermann. 56 of the 331 are price-only and replicable with Vintage today.",
    },
    {
        "source": "coinbase-exchange",
        "covers": "crypto OHLCV, every listed pair, no key",
        "field_form": "crypto:close (needs an entity like BTC-USD)",
        "point_in_time": "yes — trade prints are never restated",
        "key_required": False,
        "note": "Currently-listed products only; dead tokens are absent, so crypto survivorship is worse than equities.",
    },
    {
        "source": "finra-short-volume",
        "covers": "daily short volume and short ratio per symbol",
        "field_form": "short:short_ratio (needs an entity)",
        "point_in_time": "yes — published after the close, never revised",
        "key_required": False,
    },
    {
        "source": "apewisdom",
        "covers": "retail forum mention ranks across ~15 stock and crypto subreddits",
        "field_form": "ape:all-stocks, ape:wallstreetbets, ape:all-crypto",
        "point_in_time": "only forward — known_at is when Vintage fetched it",
        "key_required": False,
        "note": "No history endpoint upstream. Backtestable history starts the day you record it.",
    },
    {
        "source": "ecb-reference-rates",
        "covers": "daily FX reference rates against the euro, 1999 onward, plus cross rates",
        "field_form": "fx:EURUSD, fx:USDJPY",
        "point_in_time": "yes — published each afternoon and never revised",
        "key_required": False,
    },
    {
        "source": "cboe-indices",
        "covers": "VIX and the volatility family: term structure, VVIX, SKEW",
        "field_form": "vol:VIX, vol:VIX3M, vol:SKEW",
        "point_in_time": "yes — index levels are not revised",
        "key_required": False,
        "note": "Index levels only. Historical option chains are paid everywhere.",
    },
    {
        "source": "sec-form-25",
        "covers": "every delisting on record: 36,830 filings, 11,614 companies, 2003 on",
        "field_form": "delisting:form25",
        "point_in_time": "yes — filing dates, never revised",
        "key_required": False,
        "note": "The survivorship correction. Complete from April 2006, partial before.",
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


# Index tickers route through the price adapter; they are listed so `discover`
# can find them, since nobody guesses "^GSPC" unprompted.
INDICES = [
    {"field": "price:close", "entity": "^GSPC", "label": "S&P 500 index"},
    {"field": "price:close", "entity": "^DJI", "label": "Dow Jones Industrial Average"},
    {"field": "price:close", "entity": "^IXIC", "label": "Nasdaq Composite"},
    {"field": "price:close", "entity": "^NDX", "label": "Nasdaq-100"},
    {"field": "price:close", "entity": "^RUT", "label": "Russell 2000"},
    {"field": "price:close", "entity": "^VIX", "label": "VIX (see also vol:VIX)"},
    {"field": "price:close", "entity": "^FTSE", "label": "FTSE 100"},
    {"field": "price:close", "entity": "^GDAXI", "label": "DAX"},
    {"field": "price:close", "entity": "^N225", "label": "Nikkei 225"},
    {"field": "price:close", "entity": "^STOXX50E", "label": "Euro Stoxx 50"},
    {"field": "price:close", "entity": "^HSI", "label": "Hang Seng"},
    {"field": "price:close", "entity": "^TNX", "label": "US 10-year yield"},
]


def static_catalog() -> list[dict[str, Any]]:
    return french.catalog() + apewisdom.catalog() + ecb.catalog() + cboe.catalog() + [
        {**item, "source": "yahoo-finance", "kind": "index"} for item in INDICES
    ] + [
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
