"""What exists, and which source answers for it.

`discover` is how breadth becomes usable: twenty sources behind one search
instead of twenty tool names the model has to read.
"""

from __future__ import annotations

import os
from typing import Any

from .sources import (apewisdom, bea, bls, cboe, cftc, ecb, fred, french,
                      thirteenf, treasury)

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
    "frame:": "frames",
    "ust:": "treasury",
    "cot:": "cftc",
    "13f:": "thirteenf",
    "bls:": "bls",
    "bea:": "bea",
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
        "point_in_time": "yes, native filing dates",
        "key_required": False,
    },
    {
        "source": "sec-edgar-filings",
        "covers": "filing stream: 8-K, 10-K, 10-Q, Form 4, 13D/G",
        "field_form": "filing:* (needs an entity)",
        "point_in_time": "yes, exact filing timestamps",
        "key_required": False,
    },
    {
        "source": "yahoo-finance",
        "covers": "daily OHLCV and adjusted close, full history",
        "field_form": "price:close / price:adjclose (needs an entity)",
        "point_in_time": "partial, adjusted retroactively",
        "key_required": False,
        "note": "unofficial endpoint; Stooq is blocked behind a JS check as of 2026-08",
    },
    {
        "source": "ken-french-data-library",
        "covers": "Fama-French factors, momentum, industry portfolios",
        "field_form": "french:ff3, french:ff5, french:momentum",
        "point_in_time": "no, rebuilt on each release",
        "key_required": False,
    },
    {
        "source": "open-source-asset-pricing",
        "covers": "331 published anomalies with the return and t-stat each paper claimed",
        "field_form": "openap:Mom12m, or openap:* for all of them",
        "point_in_time": "yes, claims are dated to their publication year",
        "key_required": False,
        "note": "Chen & Zimmermann. 56 of the 331 are price-only and replicable with Vintage today.",
    },
    {
        "source": "coinbase-exchange",
        "covers": "crypto OHLCV, every listed pair, no key",
        "field_form": "crypto:close (needs an entity like BTC-USD)",
        "point_in_time": "yes, trade prints are never restated",
        "key_required": False,
        "note": "Currently-listed products only; dead tokens are absent, so crypto survivorship is worse than equities.",
    },
    {
        "source": "finra-short-volume",
        "covers": "daily short volume and short ratio per symbol",
        "field_form": "short:short_ratio (needs an entity)",
        "point_in_time": "yes, published after the close, never revised",
        "key_required": False,
    },
    {
        "source": "apewisdom",
        "covers": "retail forum mention ranks across ~15 stock and crypto subreddits",
        "field_form": "ape:all-stocks, ape:wallstreetbets, ape:all-crypto",
        "point_in_time": "only forward, known_at is when Vintage fetched it",
        "key_required": False,
        "note": "No history endpoint upstream. Backtestable history starts the day you record it.",
    },
    {
        "source": "ecb-reference-rates",
        "covers": "daily FX reference rates against the euro, 1999 onward, plus cross rates",
        "field_form": "fx:EURUSD, fx:USDJPY",
        "point_in_time": "yes, published each afternoon and never revised",
        "key_required": False,
    },
    {
        "source": "cboe-indices",
        "covers": "VIX and the volatility family: term structure, VVIX, SKEW",
        "field_form": "vol:VIX, vol:VIX3M, vol:SKEW",
        "point_in_time": "yes, index levels are not revised",
        "key_required": False,
        "note": "Index levels only. Historical option chains are paid everywhere.",
    },
    {
        "source": "sec-form-25",
        "covers": "every delisting on record: 36,830 filings, 11,614 companies, 2003 on",
        "field_form": "delisting:form25",
        "point_in_time": "yes, filing dates, never revised",
        "key_required": False,
        "note": "The survivorship correction. Complete from April 2006, partial before.",
    },
    {
        "source": "sec-xbrl-frames",
        "covers": "one concept across every filer in one call, the cross-section",
        "field_form": "frame:us-gaap/Assets/CY2023Q1I",
        "point_in_time": "no, carries the accession but not its filing date",
        "key_required": False,
        "note": "6,289 filers in one 840KB request. Use fetch per entity when the date matters.",
    },
    {
        "source": "us-treasury",
        "covers": "par yield curve, 14 tenors from 1 month to 30 years",
        "field_form": "ust:10y, ust:2y, ust:all",
        "point_in_time": "yes, published daily and never revised",
        "key_required": False,
    },
    {
        "source": "cftc-cot",
        "covers": "weekly futures positioning by trader class",
        "field_form": "cot:noncommercial_net (needs an entity like SP500)",
        "point_in_time": "yes, Tuesday positions, released Friday, lag preserved",
        "key_required": False,
    },
    {
        "source": "sec-form-13f",
        "covers": "institutional equity holdings for every manager over $100m",
        "field_form": "13f:value, 13f:shares (needs an entity like BERKSHIRE)",
        "point_in_time": "yes, quarter end and filing date, up to 45 days apart",
        "key_required": False,
        "note": "Long US equity only. Values normalised across the 2023 thousands-to-dollars change.",
    },
    {
        "source": "bls",
        "covers": "CPI to item level, payrolls, JOLTS, wages, productivity",
        "field_form": "bls:CUUR0000SA0",
        "point_in_time": "no, BLS ships no release date with the value",
        "key_required": False,
        "note": "Keyless tier is 25 queries a day. Use fred: when the vintage matters.",
    },
    {
        "source": "bea",
        "covers": "the national accounts, every line of a NIPA table at once",
        "field_form": "bea:T10101",
        "point_in_time": "no, current estimate only, never the first print",
        "key_required": True,
        "note": "GDP is revised at least three times. ALFRED via fred: has the vintages.",
    },
    {
        "source": "fred",
        "covers": "800k macro series, with ALFRED first-release vintages",
        "field_form": "fred:CPIAUCSL",
        "point_in_time": "yes, real-time vintages",
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


# --------------------------------------------------------------- capability

# The adapters `fetch` actually branches on. A prefix routing to anything else
# is not fetchable, whatever the router says, `test_capabilities` enforces it.
FETCH_ADAPTERS = {
    "sec-edgar-xbrl", "prices", "fred", "french", "openap", "apewisdom",
    "crypto", "finra", "ecb", "cboe", "delistings", "frames", "treasury",
    "cftc", "thirteenf", "bls", "bea",
}

# route() returns the adapter that answers; SOURCES names the publisher. They
# are deliberately different vocabularies, so the join lives here rather than
# being guessed at the call site.
ADAPTER_SOURCE = {
    "sec-edgar-xbrl": "sec-edgar-xbrl",
    "sec-edgar-filings": "sec-edgar-filings",
    "prices": "yahoo-finance",
    "fred": "fred",
    "french": "ken-french-data-library",
    "openap": "open-source-asset-pricing",
    "apewisdom": "apewisdom",
    "crypto": "coinbase-exchange",
    "finra": "finra-short-volume",
    "ecb": "ecb-reference-rates",
    "cboe": "cboe-indices",
    "delistings": "sec-form-25",
    "frames": "sec-xbrl-frames",
    "treasury": "us-treasury",
    "cftc": "cftc-cot",
    "thirteenf": "sec-form-13f",
    "bls": "bls",
    "bea": "bea",
}

# One row per prefix: the verb that serves it, whether it needs an entity, and
# an example that runs as written. This is the whole surface, machine-readable,
# so an agent never has to infer the grammar from a docstring.
#
#   as_of: "enforced", rows filed after as_of are dropped
#          "partial", filtered, but the source cannot date every row
#          "none". The source carries no filing date at all
PREFIX_SPECS: dict[str, dict[str, Any]] = {
    "us-gaap:": dict(verb="fetch", answers="US GAAP fundamentals, any tagged concept",
                     needs_entity=True, entity_example="AAPL",
                     example_field="us-gaap:Assets", as_of="enforced"),
    "dei:": dict(verb="fetch", answers="cover-page facts: shares outstanding, filer status",
                 needs_entity=True, entity_example="AAPL",
                 example_field="dei:EntityCommonStockSharesOutstanding", as_of="enforced"),
    "ifrs-full:": dict(verb="fetch", answers="IFRS fundamentals, foreign private issuers",
                       needs_entity=True, entity_example="RELX",
                       example_field="ifrs-full:Assets", as_of="enforced",
                       note="Only filers that report under IFRS. US filers use us-gaap:."),
    "srt:": dict(verb="fetch", answers="SEC reporting taxonomy: segments, ranges, axes",
                 needs_entity=True, entity_example="AAPL",
                 example_field="srt:ScheduleOfEquityMethodInvestmentsTable", as_of="enforced"),
    "invest:": dict(verb="fetch", answers="investment-company taxonomy concepts",
                    needs_entity=True, entity_example="BRK-B",
                    example_field="invest:InvestmentOwnedAtFairValue", as_of="enforced"),
    "filing:": dict(verb="events", answers="the filing stream itself: 8-K, 10-K, Form 4, 13D/G",
                    needs_entity=True, entity_example="AAPL",
                    example_field="filing:8-K", as_of="enforced",
                    note="Served by `events`, not `fetch`. A filing is a timestamp, not a value."),
    "price:": dict(verb="fetch", answers="daily OHLCV and adjusted close",
                   needs_entity=True, entity_example="AAPL",
                   example_field="price:close", as_of="partial",
                   note="price:pit_adjclose rebuilds the unadjusted series as of a date."),
    "index:": dict(verb="fetch", answers="index levels, same adapter as price:",
                   needs_entity=True, entity_example="^GSPC",
                   example_field="index:close", as_of="partial"),
    "fred:": dict(verb="fetch", answers="800k macro series with ALFRED first-release vintages",
                  needs_entity=False, entity_example=None,
                  example_field="fred:CPIAUCSL", as_of="enforced"),
    "french:": dict(verb="fetch", answers="Fama-French factors, momentum, industry portfolios",
                    needs_entity=False, entity_example=None,
                    example_field="french:ff3", as_of="none"),
    "openap:": dict(verb="fetch", answers="331 published anomalies with the claim each paper made",
                    needs_entity=False, entity_example=None,
                    example_field="openap:Mom12m", as_of="enforced",
                    note="openap:* returns the whole scoreboard."),
    "ape:": dict(verb="fetch", answers="retail forum mention ranks, right now",
                 needs_entity=False, entity_example=None,
                 example_field="ape:all-stocks", as_of="none",
                 note="No upstream history. known_at is the moment Vintage fetched it."),
    "crypto:": dict(verb="fetch", answers="crypto OHLCV from Coinbase",
                    needs_entity=True, entity_example="BTC-USD",
                    example_field="crypto:close", as_of="enforced"),
    "short:": dict(verb="fetch", answers="daily short volume and short ratio",
                   needs_entity=True, entity_example="AAPL",
                   example_field="short:short_ratio", as_of="enforced"),
    "fx:": dict(verb="fetch", answers="ECB daily reference rates and cross rates",
                needs_entity=False, entity_example=None,
                example_field="fx:EURUSD", as_of="enforced"),
    "vol:": dict(verb="fetch", answers="the VIX family: term structure, VVIX, SKEW",
                 needs_entity=False, entity_example=None,
                 example_field="vol:VIX", as_of="enforced"),
    "delisting:": dict(verb="fetch", answers="every Form 25 delisting since 2003",
                       needs_entity=False, entity_example=None,
                       example_field="delisting:form25", as_of="enforced",
                       note="The survivorship correction for any historical universe."),
    "frame:": dict(verb="fetch", answers="one concept across every filer at once",
                   needs_entity=False, entity_example=None,
                   example_field="frame:us-gaap/Assets/CY2023Q1I", as_of="none",
                   note="Grammar is taxonomy/tag[/unit]/period. Fast, but undated."),
    "ust:": dict(verb="fetch", answers="Treasury par yield curve, 14 tenors",
                 needs_entity=False, entity_example=None,
                 example_field="ust:10y", as_of="enforced"),
    "cot:": dict(verb="fetch", answers="weekly futures positioning by trader class",
                 needs_entity=True, entity_example="SP500",
                 example_field="cot:noncommercial_net", as_of="enforced"),
    "13f:": dict(verb="fetch", answers="institutional equity holdings, every manager over $100m",
                 needs_entity=True, entity_example="BERKSHIRE",
                 example_field="13f:value", as_of="enforced",
                 note="Entity is a manager, not a stock. `quarter` selects the period."),
    "bls:": dict(verb="fetch", answers="CPI to item level, payrolls, JOLTS, wages",
                 needs_entity=False, entity_example=None,
                 example_field="bls:CUUR0000SA0", as_of="none",
                 note="25 queries a day without a key. Prefer fred: when vintage matters."),
    "bea:": dict(verb="fetch", answers="the national accounts, a whole NIPA table at a time",
                 needs_entity=False, entity_example=None,
                 example_field="bea:T10101", as_of="none",
                 note="Current estimate only. ALFRED via fred: has the first prints."),
}


def _source_meta(name: str) -> dict[str, Any]:
    for s in SOURCES:
        if s["source"] == name:
            return s
    return {}


def capabilities() -> list[dict[str, Any]]:
    """Every prefix an agent can call, with the arguments it needs.

    Built by joining the router (PREFIXES), the per-prefix grammar
    (PREFIX_SPECS) and the publisher metadata (SOURCES), so the map cannot
    describe a prefix the router does not have or a source that does not exist.
    """
    out: list[dict[str, Any]] = []
    for prefix, adapter in PREFIXES.items():
        spec = PREFIX_SPECS[prefix]
        source = ADAPTER_SOURCE[adapter]
        meta = _source_meta(source)

        args: dict[str, Any] = {"field": spec["example_field"]}
        if spec["needs_entity"]:
            args["entity"] = spec["entity_example"]

        out.append({
            "prefix": prefix,
            "verb": spec["verb"],
            "answers": spec["answers"],
            "source": source,
            "publisher_covers": meta.get("covers"),
            "needs_entity": spec["needs_entity"],
            "entity_example": spec["entity_example"],
            "as_of": spec["as_of"],
            "point_in_time": meta.get("point_in_time"),
            "key_required": meta.get("key_required", False),
            "example": {"verb": spec["verb"], "args": args},
            "note": spec.get("note") or meta.get("note"),
        })
    return out


def capability_for(field: str) -> dict[str, Any] | None:
    """The capability row that owns `field`, if any."""
    for cap in capabilities():
        if field.startswith(cap["prefix"]):
            return cap
    return None


def nearest_prefixes(field: str, limit: int = 4) -> list[dict[str, Any]]:
    """Prefixes worth trying for a field that routed nowhere.

    Scored on shared leading characters, then on whether any word of the field
    appears in what the prefix answers, enough to turn a dead end into a next
    call the model can actually make.
    """
    head = field.split(":", 1)[0].lower()
    words = [w for w in head.replace("-", " ").replace("_", " ").split() if w]

    def score(cap: dict[str, Any]) -> int:
        p = cap["prefix"].rstrip(":").lower()
        shared = len(os.path.commonprefix([p, head]))
        hit = sum(2 for w in words if w in cap["answers"].lower())
        return shared * 3 + hit

    ranked = sorted(capabilities(), key=score, reverse=True)
    return [
        {"prefix": c["prefix"], "answers": c["answers"], "example": c["example"]}
        for c in ranked[:limit]
    ]


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


def capability_catalog() -> list[dict[str, Any]]:
    """The capability map, in the shape `discover` searches.

    Without this, asking `discover` for "holdings" or "short interest" finds
    nothing unless some source happened to spell it that way in a label, the
    prefixes themselves were invisible to search even though they are the
    thing the caller needs.
    """
    return [
        {
            "field": cap["example"]["args"]["field"],
            "label": cap["answers"],
            "source": cap["source"],
            "kind": "prefix",
            "prefix": cap["prefix"],
            "verb": cap["verb"],
            "needs_entity": cap["needs_entity"],
            "entity_example": cap["entity_example"],
            "key_required": cap["key_required"],
        }
        for cap in capabilities()
    ]


def static_catalog() -> list[dict[str, Any]]:
    items = (french.catalog() + apewisdom.catalog() + ecb.catalog()
             + cboe.catalog() + treasury.catalog() + cftc.catalog()
             + thirteenf.catalog() + bls.catalog() + bea.catalog()) + [
        {**item, "source": "yahoo-finance", "kind": "index"} for item in INDICES
    ] + [
        {**item, "source": "fred", "key_required": not fred.has_key()}
        for item in CURATED
    ]
    # Prefix rows go last and only where a source has not already named the
    # field, so a specific catalog entry always outranks the generic example.
    seen = {i.get("field") for i in items}
    return items + [c for c in capability_catalog() if c["field"] not in seen]


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
