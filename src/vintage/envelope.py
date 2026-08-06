"""The one response shape every verb returns.

Two time columns are the whole product:
    observed_at  what date the value describes
    known_at     when you could first have seen it

A source that cannot supply `known_at` gets vintage="UNKNOWN_VINTAGE" and a
null. Never a guess.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any, Iterable

AS_FILED = "as-filed"
UNKNOWN_VINTAGE = "UNKNOWN_VINTAGE"
IMMUTABLE = "immutable"


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def row(
    *,
    entity: str,
    field: str,
    observed_at: str | None,
    value: Any,
    source: str,
    source_url: str,
    known_at: str | None = None,
    unit: str | None = None,
    vintage: str | None = None,
    **extra: Any,
) -> dict[str, Any]:
    """One observation, in the shape every source normalizes to."""
    if vintage is None:
        vintage = AS_FILED if known_at else UNKNOWN_VINTAGE
    out = {
        "entity": entity,
        "field": field,
        "observed_at": observed_at,
        "known_at": known_at,
        "value": value,
        "unit": unit,
        "source": source,
        "source_url": source_url,
        "vintage": vintage,
    }
    out.update(extra)
    return out


def visible_at(rows: Iterable[dict[str, Any]], as_of: str | None) -> list[dict[str, Any]]:
    """Drop anything that was not knowable on `as_of`.

    Rows with an unknown vintage are kept but they are the reason
    `warn_unknown_vintage` exists — the caller must surface that.
    """
    if not as_of:
        return list(rows)
    kept = []
    for r in rows:
        known = r.get("known_at")
        if known and known > as_of:
            continue
        kept.append(r)
    return kept


def warn_unknown_vintage(rows: list[dict[str, Any]]) -> list[str]:
    bad = {r["source"] for r in rows if r.get("vintage") == UNKNOWN_VINTAGE}
    if not bad:
        return []
    return [
        f"{len(bad)} source(s) carry no filing date ({', '.join(sorted(bad))}). "
        "Point-in-time filtering cannot be enforced on those rows."
    ]


def restatements(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Periods reported more than once with a different value."""
    grouped: dict[tuple, list[dict[str, Any]]] = {}
    for r in rows:
        if not r.get("known_at"):
            continue
        grouped.setdefault((r["entity"], r["field"], r["observed_at"]), []).append(r)

    out = []
    for (entity, field, observed), group in grouped.items():
        if len({g["value"] for g in group}) > 1:
            ordered = sorted(group, key=lambda g: g["known_at"] or "")
            out.append(
                {
                    "entity": entity,
                    "field": field,
                    "observed_at": observed,
                    "versions": [
                        {"value": g["value"], "known_at": g["known_at"]} for g in ordered
                    ],
                }
            )
    return sorted(out, key=lambda o: o["observed_at"] or "")


def respond(
    verb: str,
    *,
    rows: list[dict[str, Any]] | None = None,
    warnings: list[str] | None = None,
    suggested_next: list[dict[str, str]] | None = None,
    **payload: Any,
) -> str:
    """Serialize a successful response.

    `warnings` make the product look like it is paying attention.
    `suggested_next` is what keeps the conversation going — models follow them.
    """
    body: dict[str, Any] = {"ok": True, "verb": verb, "retrieved_at": now_iso()}
    body.update(payload)
    if rows is not None:
        body["row_count"] = len(rows)
        body["rows"] = rows
        body["sources"] = sorted({r["source"] for r in rows})
    if warnings:
        body["warnings"] = warnings
    if suggested_next:
        body["suggested_next"] = suggested_next
    return json.dumps(body, indent=2, default=str)


def fail(verb: str, message: str, *, did_you_mean: Any = None, **payload: Any) -> str:
    """Serialize a failure. Errors teach — never a bare 'not found'."""
    body: dict[str, Any] = {"ok": False, "verb": verb, "error": message}
    if did_you_mean:
        body["did_you_mean"] = did_you_mean
    body.update(payload)
    return json.dumps(body, indent=2, default=str)
