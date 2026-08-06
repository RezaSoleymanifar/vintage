"""One polite HTTP client for every source.

Per-source rate limits live here so a user cannot get themselves banned by
asking an enthusiastic question.
"""

from __future__ import annotations

import asyncio
import os
import time
from typing import Any

import httpx

from . import cache

DEFAULT_USER_AGENT = "vintage-mcp reza@soleymanifar.com"

# Minimum seconds between calls to the same host.
RATE_LIMITS = {
    "data.sec.gov": 0.12,
    "www.sec.gov": 0.12,
    "efts.sec.gov": 0.12,
    "api.stlouisfed.org": 0.05,
    "stooq.com": 0.5,
    "query1.finance.yahoo.com": 0.6,
    "mba.tuck.dartmouth.edu": 1.0,
    "raw.githubusercontent.com": 0.3,
    "api.openfigi.com": 2.5,
}

_last_call: dict[str, float] = {}
_lock = asyncio.Lock()


class SourceError(RuntimeError):
    """An upstream source refused, or has nothing."""


def user_agent() -> str:
    return os.environ.get("VINTAGE_USER_AGENT", DEFAULT_USER_AGENT)


async def _throttle(host: str) -> None:
    gap = RATE_LIMITS.get(host)
    if not gap:
        return
    async with _lock:
        elapsed = time.monotonic() - _last_call.get(host, 0.0)
        if elapsed < gap:
            await asyncio.sleep(gap - elapsed)
        _last_call[host] = time.monotonic()


async def get_bytes(url: str, *, tier: str = "daily", headers: dict | None = None) -> bytes:
    """Fetch raw bytes, cached as latin-1 text so gzip/zip payloads survive."""
    cached = cache.get("bytes:" + url, tier=tier)
    if cached is not None:
        return cached.encode("latin-1")

    host = httpx.URL(url).host
    await _throttle(host)

    merged = {"User-Agent": user_agent(), "Accept-Encoding": "gzip, deflate"}
    merged.update(headers or {})
    async with httpx.AsyncClient(timeout=90.0, follow_redirects=True) as client:
        response = await client.get(url, headers=merged)

    _raise_for(response, url)
    cache.put("bytes:" + url, response.content.decode("latin-1"))
    return response.content


async def get_json(url: str, *, tier: str = "daily", headers: dict | None = None) -> Any:
    cached = cache.get(url, tier=tier)
    if cached is not None:
        return cached

    host = httpx.URL(url).host
    await _throttle(host)

    merged = {"User-Agent": user_agent(), "Accept-Encoding": "gzip, deflate"}
    merged.update(headers or {})
    async with httpx.AsyncClient(timeout=90.0, follow_redirects=True) as client:
        response = await client.get(url, headers=merged)

    _raise_for(response, url)
    payload = response.json()
    cache.put(url, payload)
    return payload


def _raise_for(response: httpx.Response, url: str) -> None:
    if response.status_code == 404:
        raise SourceError(f"Nothing at {url}")
    if response.status_code == 403:
        raise SourceError(
            f"{httpx.URL(url).host} rejected the request (403). If this is SEC, set "
            "VINTAGE_USER_AGENT to 'Your Name your@email.com'."
        )
    if response.status_code == 429:
        raise SourceError(f"{httpx.URL(url).host} rate-limited us. Wait and retry.")
    response.raise_for_status()
