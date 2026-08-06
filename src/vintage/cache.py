"""Tiered disk cache.

Data that cannot change should never be refetched. Immutability is a property
of the data, not the file, so callers declare a tier rather than a TTL.
"""

from __future__ import annotations

import gzip
import hashlib
import json
import os
import time
from pathlib import Path
from typing import Any

HOUR = 3600
DAY = 24 * HOUR

TIERS = {
    "never": -1,          # closed periods, historical filings
    "monthly": 30 * DAY,  # French, JKP, academic datasets
    "daily": DAY,         # current-quarter fundamentals, macro
    "session": 4 * HOUR,  # prices, news, events
}


def cache_dir() -> Path:
    override = os.environ.get("VINTAGE_CACHE_DIR")
    path = Path(override) if override else Path.home() / ".cache" / "vintage"
    path.mkdir(parents=True, exist_ok=True)
    return path


def _path(key: str) -> Path:
    return cache_dir() / f"{hashlib.sha256(key.encode()).hexdigest()[:32]}.json.gz"


def get(key: str, tier: str = "daily") -> Any | None:
    path = _path(key)
    if not path.exists():
        return None
    ttl = TIERS.get(tier, DAY)
    if ttl >= 0 and (time.time() - path.stat().st_mtime) > ttl:
        return None
    try:
        with gzip.open(path, "rt", encoding="utf-8") as fh:
            return json.load(fh)
    except (OSError, EOFError, json.JSONDecodeError):
        path.unlink(missing_ok=True)  # torn write from an interrupted run
        return None


def put(key: str, value: Any) -> None:
    path = _path(key)
    tmp = path.with_suffix(".tmp")
    with gzip.open(tmp, "wt", encoding="utf-8") as fh:
        json.dump(value, fh)
    os.replace(tmp, path)


def stats() -> dict[str, Any]:
    files = list(cache_dir().glob("*.json.gz"))
    return {
        "dir": str(cache_dir()),
        "entries": len(files),
        "megabytes": round(sum(f.stat().st_size for f in files) / 1e6, 2),
    }


def clear() -> int:
    removed = 0
    for path in cache_dir().glob("*.json.gz"):
        path.unlink(missing_ok=True)
        removed += 1
    return removed
