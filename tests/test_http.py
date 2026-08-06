"""The transport layer: retry what is temporary, refuse what is not.

A backtest fans out over a whole universe, so one 503 used to drop a name into
`excluded` and quietly change the sample the result was computed on. These
tests pin the difference between "the source is busy" and "the source said no".
"""

import asyncio

import httpx
import pytest

from vintage import cache, http


@pytest.fixture(autouse=True)
def isolated_cache(tmp_path, monkeypatch):
    """Never read or write the developer's real cache while testing."""
    monkeypatch.setenv("VINTAGE_CACHE_DIR", str(tmp_path))
    yield
    cache.clear()


@pytest.fixture
def no_waiting(monkeypatch):
    """Backoff is correctness, not something to sit through.

    Deliberately opt-in: the throttling test needs the clock to be real.
    """
    async def instant(_seconds):
        return None
    monkeypatch.setattr(http.asyncio, "sleep", instant)


class FakeClient:
    """Replays a scripted list of responses or exceptions, one per request."""

    script: list = []
    calls: int = 0

    def __init__(self, *args, **kwargs):
        pass

    async def __aenter__(self):
        return self

    async def __aexit__(self, *exc):
        return False

    async def _next(self, url):
        item = FakeClient.script[min(FakeClient.calls, len(FakeClient.script) - 1)]
        FakeClient.calls += 1
        if isinstance(item, Exception):
            raise item
        status, body = item
        return httpx.Response(
            status, json=body, request=httpx.Request("GET", url)
        )

    async def get(self, url, **kwargs):
        return await self._next(url)

    async def post(self, url, **kwargs):
        return await self._next(url)


@pytest.fixture
def fake(monkeypatch):
    FakeClient.script = []
    FakeClient.calls = 0
    monkeypatch.setattr(http.httpx, "AsyncClient", FakeClient)
    return FakeClient


URL = "https://example.test/data.json"


@pytest.mark.asyncio
async def test_a_transient_failure_is_retried_not_surfaced(fake, no_waiting):
    fake.script = [(503, None), (503, None), (200, {"ok": 1})]
    assert await http.get_json(URL) == {"ok": 1}
    assert fake.calls == 3


@pytest.mark.asyncio
async def test_a_timeout_is_retried(fake, no_waiting):
    fake.script = [httpx.ConnectTimeout("slow"), (200, {"ok": 1})]
    assert await http.get_json(URL) == {"ok": 1}
    assert fake.calls == 2


@pytest.mark.asyncio
async def test_a_refusal_is_not_retried(fake, no_waiting):
    """403 and 404 will say the same thing next time. Do not waste the wait."""
    for status in (403, 404):
        fake.script = [(status, None)]
        fake.calls = 0
        with pytest.raises(http.SourceError):
            await http.get_json(URL)
        assert fake.calls == 1


@pytest.mark.asyncio
async def test_persistent_failure_gives_up_with_an_explanation(fake, no_waiting):
    fake.script = [(500, None)]
    with pytest.raises(http.SourceError) as exc:
        await http.get_json(URL)
    assert fake.calls == http.MAX_ATTEMPTS
    assert "attempts" in str(exc.value)


@pytest.mark.asyncio
async def test_html_error_page_names_the_source_not_the_parser(
    fake, no_waiting, monkeypatch
):
    """A degraded source answers 200 with HTML more often than it answers 500."""
    class HtmlClient(FakeClient):
        async def _next(self, url):
            FakeClient.calls += 1
            return httpx.Response(200, text="<html>down for maintenance</html>",
                                  request=httpx.Request("GET", url))

    monkeypatch.setattr(http.httpx, "AsyncClient", HtmlClient)
    with pytest.raises(http.SourceError) as exc:
        await http.get_json(URL)
    assert "rather than JSON" in str(exc.value)


@pytest.mark.asyncio
async def test_a_cached_answer_makes_no_request(fake):
    fake.script = [(200, {"ok": 1})]
    await http.get_json(URL)
    before = fake.calls
    await http.get_json(URL)
    assert fake.calls == before


@pytest.mark.asyncio
async def test_throttling_is_per_host(monkeypatch):
    """A slow host must not hold a lock that an unrelated host is waiting on."""
    monkeypatch.setitem(http.RATE_LIMITS, "slow.test", 0.25)
    monkeypatch.setitem(http.RATE_LIMITS, "quick.test", 0.0)
    http._last_call.clear()

    order: list[str] = []

    async def call(host):
        await http._throttle(host)
        order.append(host)

    # Prime the slow host so the next call to it has to wait out the gap.
    await http._throttle("slow.test")
    await asyncio.gather(call("slow.test"), call("quick.test"))

    assert order[0] == "quick.test", "the fast host waited on the slow one"


def test_retry_after_is_honoured_only_when_it_is_short():
    def response(value):
        return httpx.Response(429, headers={"Retry-After": value},
                              request=httpx.Request("GET", URL))

    assert http._retry_after(response("2")) == 2.0
    assert http._retry_after(response("3600")) is None
    assert http._retry_after(response("Wed, 21 Oct 2026 07:28:00 GMT")) is None
    assert http._retry_after(httpx.Response(429, request=httpx.Request("GET", URL))) is None
