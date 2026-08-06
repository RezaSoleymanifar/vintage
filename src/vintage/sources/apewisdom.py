"""ApeWisdom — how often retail forums are talking about each ticker.

Free, no key, ~15 stock and crypto subreddits plus a 4chan /biz beta.

The important thing about this source is what it *cannot* give you: there is
no history endpoint. It reports right now, and nothing else. Every vendor
selling "historical sentiment" produced it by re-scoring archived posts with
a model built later, which is a measurement contaminated by hindsight.

So `known_at` here is the moment Vintage fetched the row, not a date the
upstream asserts. That is the honest stamp, and it means a snapshot taken
today is genuinely point-in-time a year from now — which is the only way a
sentiment history can be trustworthy. Backtestable history starts the day
you begin recording, and the response says so rather than implying depth
that does not exist.
"""

from __future__ import annotations

from typing import Any

from .. import envelope
from ..http import SourceError, get_json

SOURCE = "apewisdom"
HOME = "https://apewisdom.io/"
BASE = "https://apewisdom.io/api/v1.0/filter"

FILTERS = {
    "all-stocks": "every tracked stock subreddit",
    "all-crypto": "every tracked crypto subreddit",
    "wallstreetbets": "r/wallstreetbets only",
    "stocks": "r/stocks only",
    "investing": "r/investing only",
    "cryptocurrency": "r/CryptoCurrency only",
    "4chan": "4chan /biz (beta)",
}

MAX_PAGES = 11


def catalog() -> list[dict[str, Any]]:
    return [
        {
            "field": f"ape:{key}",
            "label": f"Forum mention ranks — {label}",
            "source": SOURCE,
            "vintage": "observed-at-fetch",
        }
        for key, label in FILTERS.items()
    ]


async def mentions(scope: str = "all-stocks", limit: int = 100) -> list[dict[str, Any]]:
    """Current mention ranks for `scope`.

    Rows carry `mentions_24h_ago` and `rank_24h_ago` because ApeWisdom returns
    them — that one-day delta is the only history the API offers, and change in
    attention is usually more interesting than its level.
    """
    key = scope.strip().lower()
    if key not in FILTERS:
        raise SourceError(
            f"No ApeWisdom filter called {scope!r}. Available: {', '.join(FILTERS)}."
        )

    # `known_at` is when we looked, not when they published. That is the whole
    # point of recording this source.
    seen = envelope.now_iso()

    rows: list[dict[str, Any]] = []
    for page in range(1, MAX_PAGES + 1):
        if len(rows) >= limit:
            break
        # Never cache: a cached snapshot would carry a known_at that lies.
        payload = await get_json(f"{BASE}/{key}/page/{page}", tier="session")
        results = payload.get("results") or []
        if not results:
            break

        for r in results:
            ticker = (r.get("ticker") or "").strip()
            if not ticker:
                continue
            rows.append(
                envelope.row(
                    entity=ticker,
                    field=f"ape:{key}",
                    observed_at=seen[:10],
                    known_at=seen,
                    value=r.get("mentions"),
                    unit="mentions",
                    source=SOURCE,
                    source_url=f"{HOME}filter/{key}",
                    vintage="observed-at-fetch",
                    name=r.get("name"),
                    rank=r.get("rank"),
                    upvotes=r.get("upvotes"),
                    rank_24h_ago=r.get("rank_24h_ago"),
                    mentions_24h_ago=r.get("mentions_24h_ago"),
                    mention_change=_delta(r.get("mentions"), r.get("mentions_24h_ago")),
                )
            )
            if len(rows) >= limit:
                break

    if not rows:
        raise SourceError(f"ApeWisdom returned nothing for {scope!r}")
    return rows


def _delta(now: Any, before: Any) -> float | None:
    try:
        now, before = float(now), float(before)
    except (TypeError, ValueError):
        return None
    if before <= 0:
        return None
    return round((now - before) / before, 4)


def warnings_for(rows: list[dict[str, Any]]) -> list[str]:
    return [
        "ApeWisdom has no history endpoint — this is a snapshot of right now, "
        f"stamped known_at={rows[0]['known_at'] if rows else 'n/a'}. Backtestable "
        "history begins the day you start recording it. Any vendor selling you "
        "years of 'historical sentiment' built it by re-scoring old posts with a "
        "model that already knew what happened next.",
        "Forum mentions are a crowd attention measure, not a filing. Do not read "
        "them with the same confidence as SEC or Federal Reserve rows.",
    ]
