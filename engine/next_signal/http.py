"""Shared HTTP client: disk cache with point-in-time-safe keys, polite per-host rate limiting, retries.

Cache safety for time-travel (as_of) runs: this cache stores *fetch* time, not document publish time. Point-in-time
filtering is always done downstream on each Document/Event's own published_at/date field against ctx.as_of, never on
when the HTTP response was cached. So caching here never leaks future information into a past-dated run, provided
every caller filters by published_at after fetching (pipeline/*.py and sources/*.py do this).
"""
from __future__ import annotations

import asyncio
import hashlib
import json
import time
from contextvars import ContextVar
from pathlib import Path
from typing import Any, Callable, Optional

import httpx
from tenacity import retry, retry_if_exception, stop_after_attempt, wait_exponential

from .config import settings

UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/129.0 Safari/537.36"
)
DEFAULT_HEADERS = {"User-Agent": UA, "Accept-Language": "en-IN,en;q=0.9"}

# TTL in seconds by cache "kind". None is the "forever" sentinel: a cached entry of that kind
# never expires on freshness grounds (it can still be evicted by hand by clearing the cache dir).
TTL = {
    "listing": 6 * 3600,
    "document": None,  # forever (PDFs/XBRL do not change once published)
    "price": 12 * 3600,
    "news": 2 * 3600,
    "filing": None,  # forever: a filed document's content never changes after it is filed
    "xbrl": None,  # forever: XBRL facts for a filed period never change after filing
    "screener": 24 * 3600,
}

# Polite per-host rate limits: minimum seconds between requests to a host family
HOST_INTERVAL = {
    "www.nseindia.com": 1 / 3,
    "nsearchives.nseindia.com": 1 / 3,
    "www.bseindia.com": 0.5,
    "api.bseindia.com": 0.5,
    "www.fda.gov": 0.5,
    "www.accessdata.fda.gov": 0.5,
    "api.fda.gov": 0.25,
    "data.sec.gov": 0.125,
    "www.sec.gov": 0.125,
    "api.gdeltproject.org": 1.0,
    "www.screener.in": 2.0,
    "news.google.com": 0.5,
}


def _retryable(exc: BaseException) -> bool:
    if isinstance(exc, httpx.TimeoutException):
        return True
    if isinstance(exc, httpx.HTTPStatusError):
        return exc.response.status_code in (429, 500, 502, 503, 504)
    return False


class RateLimiter:
    def __init__(self) -> None:
        self._last: dict[str, float] = {}
        self._locks: dict[str, asyncio.Lock] = {}

    async def wait(self, host: str) -> None:
        interval = HOST_INTERVAL.get(host, 0.2)
        lock = self._locks.setdefault(host, asyncio.Lock())
        async with lock:
            now = time.monotonic()
            last = self._last.get(host, 0.0)
            delta = interval - (now - last)
            if delta > 0:
                await asyncio.sleep(delta)
            self._last[host] = time.monotonic()


class DiskCache:
    def __init__(self, root: Path) -> None:
        self.root = root

    def _path(self, host: str, key: str) -> Path:
        return self.root / "http" / host / f"{key}.json"

    def get(self, host: str, key: str, kind: str) -> Optional[dict]:
        p = self._path(host, key)
        if not p.exists():
            return None
        try:
            data = json.loads(p.read_text(encoding="utf-8"))
        except Exception:
            return None
        ttl = TTL.get(kind)
        if ttl is not None and (time.time() - data.get("fetched_at", 0)) > ttl:
            return None
        return data

    def set(self, host: str, key: str, body: str, status: int, headers: dict) -> None:
        p = self._path(host, key)
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(
            json.dumps({"body": body, "status": status, "headers": dict(headers), "fetched_at": time.time()}),
            encoding="utf-8",
        )

    # --- binary variants, for content (PDFs, XBRL archives, ...) that a text round-trip would
    # corrupt. Same host-partitioned directory layout and cache-key scheme as the text cache
    # above; the body goes to a sibling `.bin` file and the small status/headers/fetched_at
    # metadata goes to a `.meta.json` sidecar, so the raw bytes are never passed through
    # `json.dumps`/`.read_text`.

    def _path_bin(self, host: str, key: str) -> Path:
        return self.root / "http" / host / f"{key}.bin"

    def _path_meta(self, host: str, key: str) -> Path:
        return self.root / "http" / host / f"{key}.meta.json"

    def get_bytes(self, host: str, key: str, kind: str) -> Optional[dict]:
        meta_p = self._path_meta(host, key)
        bin_p = self._path_bin(host, key)
        if not meta_p.exists() or not bin_p.exists():
            return None
        try:
            meta = json.loads(meta_p.read_text(encoding="utf-8"))
        except Exception:
            return None
        ttl = TTL.get(kind)
        if ttl is not None and (time.time() - meta.get("fetched_at", 0)) > ttl:
            return None
        try:
            body = bin_p.read_bytes()
        except Exception:
            return None
        return {
            "body": body,
            "status": meta.get("status"),
            "headers": meta.get("headers", {}),
            "fetched_at": meta.get("fetched_at"),
        }

    def set_bytes(self, host: str, key: str, body: bytes, status: int, headers: dict) -> None:
        bin_p = self._path_bin(host, key)
        meta_p = self._path_meta(host, key)
        bin_p.parent.mkdir(parents=True, exist_ok=True)
        bin_p.write_bytes(body)
        meta_p.write_text(
            json.dumps({"status": status, "headers": dict(headers), "fetched_at": time.time()}),
            encoding="utf-8",
        )


_limiter = RateLimiter()
_cache = DiskCache(settings.cache_dir)
_client: Optional[httpx.AsyncClient] = None


def _cache_key(method: str, url: str, params: Optional[dict]) -> str:
    raw = method + "|" + url + "|" + json.dumps(params or {}, sort_keys=True)
    return hashlib.sha1(raw.encode()).hexdigest()


def get_client() -> httpx.AsyncClient:
    global _client
    if _client is None:
        _client = httpx.AsyncClient(
            http2=False,
            timeout=httpx.Timeout(20, connect=10),
            follow_redirects=True,
            headers=DEFAULT_HEADERS,
        )
    return _client


class FetchEvent:
    """Populated by cached_get for the caller to forward to the run's event bus."""

    def __init__(self, host: str, url: str, status: int, ms: int, cached: bool):
        self.host = host
        self.url = url
        self.status = status
        self.ms = ms
        self.cached = cached

    def as_dict(self) -> dict:
        return {"host": self.host, "url": self.url, "status": self.status, "ms": self.ms, "cached": self.cached}


fetch_listener: ContextVar[Optional[Callable[["FetchEvent"], None]]] = ContextVar("fetch_listener", default=None)


def notify_fetch(ev: "FetchEvent") -> None:
    cb = fetch_listener.get()
    if cb is None:
        return
    try:
        cb(ev)
    except Exception:
        pass


@retry(
    retry=retry_if_exception(_retryable),
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=0.5, max=4),
    reraise=True,
)
async def _do_request(client: httpx.AsyncClient, method: str, url: str, **kw) -> httpx.Response:
    r = await client.request(method, url, **kw)
    if r.status_code in (429, 500, 502, 503, 504):
        raise httpx.HTTPStatusError(f"{r.status_code}", request=r.request, response=r)
    return r


async def cached_get(
    url: str,
    params: Optional[dict] = None,
    kind: str = "listing",
    headers: Optional[dict] = None,
    client: Optional[httpx.AsyncClient] = None,
) -> tuple[httpx.Response | None, FetchEvent]:
    """GET with disk cache + rate limit + retry. Returns (response_or_None, FetchEvent).

    response is None when served entirely from cache; callers should branch on event.cached and read
    event-supplied status/body via the cache dict when response is None (use cached_text / cached_json helpers
    below instead of calling this directly in most cases).
    """
    from urllib.parse import urlparse

    host = urlparse(url).netloc
    key = _cache_key("GET", url, params)
    cached = _cache.get(host, key, kind)
    t0 = time.perf_counter()
    if cached is not None:
        ev = FetchEvent(host, url, cached["status"], 0, True)
        notify_fetch(ev)
        return None, ev
    await _limiter.wait(host)
    c = client or get_client()
    r = await _do_request(c, "GET", url, params=params, headers=headers)
    ms = int((time.perf_counter() - t0) * 1000)
    _cache.set(host, key, r.text, r.status_code, dict(r.headers))
    ev = FetchEvent(host, url, r.status_code, ms, False)
    notify_fetch(ev)
    return r, ev


async def cached_text(url: str, params: Optional[dict] = None, kind: str = "listing", **kw) -> tuple[str, FetchEvent]:
    from urllib.parse import urlparse

    host = urlparse(url).netloc
    key = _cache_key("GET", url, params)
    r, ev = await cached_get(url, params, kind, **kw)
    if r is not None:
        return r.text, ev
    data = _cache.get(host, key, kind)
    return (data or {}).get("body", ""), ev


async def cached_json(url: str, params: Optional[dict] = None, kind: str = "listing", **kw) -> tuple[Any, FetchEvent]:
    text, ev = await cached_text(url, params, kind, **kw)
    return (json.loads(text) if text else None), ev


async def cached_bytes(
    url: str,
    params: Optional[dict] = None,
    kind: str = "document",
    headers: Optional[dict] = None,
    client: Optional[httpx.AsyncClient] = None,
) -> tuple[bytes, FetchEvent]:
    """GET with disk cache + rate limit + retry, for binary content (PDFs, XBRL archives, and
    anything else a text decode would corrupt). Same per-host rate limiter and retry behavior as
    cached_get/cached_text/cached_json; the difference is purely in how the body is cached and
    returned, as raw bytes rather than `str`, so a cached PDF round-trips byte for byte instead of
    going through a text decode/encode that can silently mangle it.
    """
    from urllib.parse import urlparse

    host = urlparse(url).netloc
    key = _cache_key("GET", url, params)
    cached = _cache.get_bytes(host, key, kind)
    t0 = time.perf_counter()
    if cached is not None:
        ev = FetchEvent(host, url, cached["status"], 0, True)
        notify_fetch(ev)
        return cached["body"], ev
    await _limiter.wait(host)
    c = client or get_client()
    r = await _do_request(c, "GET", url, params=params, headers=headers)
    ms = int((time.perf_counter() - t0) * 1000)
    _cache.set_bytes(host, key, r.content, r.status_code, dict(r.headers))
    ev = FetchEvent(host, url, r.status_code, ms, False)
    notify_fetch(ev)
    return r.content, ev
