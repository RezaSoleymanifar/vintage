"""One polite HTTP client for every source.

Per-source rate limits live here so a user cannot get themselves banned by
asking an enthusiastic question.

Two properties matter more than they look:

Retries are not a nicety. A backtest fans out over thirty tickers, and a
single 503 used to drop a name into `excluded` — silently changing the
universe the result was computed on, which is survivorship bias arriving by
way of a flaky network. Transient failures are retried; refusals are not.

Throttling is per host. It used to hold one global lock across the sleep, so
a slow Dartmouth download stalled an unrelated SEC request that had no reason
to wait. Each host now waits only on itself.
"""

from __future__ import annotations

import asyncio
import json as _json
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

# Worth trying again: the source is up but momentarily unwilling. A 403 or a
# 404 means the answer will not change, so retrying only wastes the user's time.
RETRY_STATUS = {429, 500, 502, 503, 504}
MAX_ATTEMPTS = 3
BACKOFF = 0.75          # seconds, doubled each attempt
MAX_RETRY_AFTER = 10.0  # never honour a Retry-After longer than this; fail instead

_last_call: dict[str, float] = {}
_locks: dict[str, asyncio.Lock] = {}
_locks_guard = asyncio.Lock()


class SourceError(RuntimeError):
    """An upstream source refused, or has nothing."""


def user_agent() -> str:
    return os.environ.get("VINTAGE_USER_AGENT", DEFAULT_USER_AGENT)


async def _host_lock(host: str) -> asyncio.Lock:
    async with _locks_guard:
        return _locks.setdefault(host, asyncio.Lock())


async def _throttle(host: str) -> None:
    gap = RATE_LIMITS.get(host)
    if not gap:
        return
    lock = await _host_lock(host)
    async with lock:
        elapsed = time.monotonic() - _last_call.get(host, 0.0)
        if elapsed < gap:
            await asyncio.sleep(gap - elapsed)
        _last_call[host] = time.monotonic()


def _retry_after(response: httpx.Response) -> float | None:
    """Honour Retry-After when the source names a short, sane wait."""
    raw = response.headers.get("Retry-After")
    if not raw:
        return None
    try:
        wait = float(raw)
    except ValueError:
        return None  # HTTP-date form; our own backoff is close enough
    return wait if 0 <= wait <= MAX_RETRY_AFTER else None


async def _send(method: str, url: str, *, headers: dict | None, body: dict | None) -> httpx.Response:
    """One request, retried while the failure still looks temporary."""
    host = httpx.URL(url).host
    merged = {"User-Agent": user_agent(), "Accept-Encoding": "gzip, deflate"}
    if body is not None:
        merged["Content-Type"] = "application/json"
    merged.update(headers or {})

    last: Exception | None = None
    for attempt in range(MAX_ATTEMPTS):
        await _throttle(host)
        try:
            async with httpx.AsyncClient(timeout=90.0, follow_redirects=True) as client:
                if body is None:
                    response = await client.get(url, headers=merged)
                else:
                    response = await client.post(url, json=body, headers=merged)
        except (httpx.TimeoutException, httpx.TransportError) as exc:
            last = exc
        else:
            if response.status_code not in RETRY_STATUS:
                return response
            last = None
            if attempt == MAX_ATTEMPTS - 1:
                return response  # let _raise_for explain it
            wait = _retry_after(response)
            if wait is not None:
                await asyncio.sleep(wait)
                continue

        if attempt == MAX_ATTEMPTS - 1:
            break
        await asyncio.sleep(BACKOFF * (2 ** attempt))

    raise SourceError(
        f"{host} did not respond after {MAX_ATTEMPTS} attempts"
        + (f": {last}" if last else "")
    )


async def get_bytes(url: str, *, tier: str = "daily", headers: dict | None = None) -> bytes:
    """Fetch raw bytes, cached as latin-1 text so gzip/zip payloads survive."""
    cached = cache.get("bytes:" + url, tier=tier)
    if cached is not None:
        return cached.encode("latin-1")

    response = await _send("GET", url, headers=headers, body=None)
    _raise_for(response, url)
    cache.put("bytes:" + url, response.content.decode("latin-1"))
    return response.content


async def get_json(url: str, *, tier: str = "daily", headers: dict | None = None) -> Any:
    cached = cache.get(url, tier=tier)
    if cached is not None:
        return cached

    response = await _send("GET", url, headers=headers, body=None)
    _raise_for(response, url)
    payload = _decode(response, url)
    cache.put(url, payload)
    return payload


async def post_json(url: str, body: dict, *, tier: str = "daily",
                    headers: dict | None = None) -> Any:
    """POST a JSON body and cache on the body as well as the URL.

    Only used where an API takes its parameters no other way — BLS ignores
    query strings on its GET route and silently returns the default window,
    which is a worse failure than an error.
    """
    signature = url + "|" + _json.dumps(body, sort_keys=True)
    cached = cache.get(signature, tier=tier)
    if cached is not None:
        return cached

    response = await _send("POST", url, headers=headers, body=body)
    _raise_for(response, url)
    payload = _decode(response, url)
    cache.put(signature, payload)
    return payload


def _decode(response: httpx.Response, url: str) -> Any:
    """JSON, or a SourceError naming what arrived instead.

    Sources under load answer 200 with an HTML error page more often than they
    answer 500, and a raw JSONDecodeError several frames deep tells the caller
    nothing about which source broke.
    """
    try:
        return response.json()
    except ValueError:
        kind = response.headers.get("Content-Type", "unknown")
        raise SourceError(
            f"{httpx.URL(url).host} returned {kind} rather than JSON "
            f"({len(response.content)} bytes). The source is probably degraded."
        ) from None


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
    if response.status_code in RETRY_STATUS:
        raise SourceError(
            f"{httpx.URL(url).host} is failing ({response.status_code}) and did not "
            f"recover across {MAX_ATTEMPTS} attempts."
        )
    response.raise_for_status()
