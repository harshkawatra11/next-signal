"""Tests for next_signal/http.py's disk cache, focused on the binary (cached_bytes) path.

Each test points the module's shared `_cache` at a throwaway temp directory (via monkeypatch)
so these tests never read or write the real .cache/http directory on disk.
"""
from __future__ import annotations

import httpx
import pytest
import respx

from next_signal import http as http_module


@pytest.fixture(autouse=True)
def isolated_cache(tmp_path, monkeypatch):
    monkeypatch.setattr(http_module, "_cache", http_module.DiskCache(tmp_path))
    yield


async def test_cached_bytes_round_trips_binary_content_byte_for_byte():
    raw = b"%PDF-1.4\x00\x01\x02binary-content-not-valid-utf8\xff\xfe"
    with respx.mock(assert_all_called=True) as mock:
        route = mock.get("https://example.com/report.pdf").mock(
            return_value=httpx.Response(200, content=raw, headers={"content-type": "application/pdf"})
        )
        body, ev = await http_module.cached_bytes("https://example.com/report.pdf", kind="filing")
        assert body == raw
        assert ev.cached is False
        assert ev.status == 200
        assert route.call_count == 1


async def test_cached_bytes_second_call_is_a_cache_hit_not_a_second_request():
    raw = b"\x89PNG\r\n\x1a\nfake-binary-payload"
    with respx.mock(assert_all_called=True) as mock:
        route = mock.get("https://example.com/chart.png").mock(
            return_value=httpx.Response(200, content=raw)
        )
        body1, ev1 = await http_module.cached_bytes("https://example.com/chart.png", kind="document")
        body2, ev2 = await http_module.cached_bytes("https://example.com/chart.png", kind="document")
        assert body1 == raw
        assert body2 == raw
        assert ev1.cached is False
        assert ev2.cached is True
        # Only one real HTTP call despite two cached_bytes() calls for the same URL.
        assert route.call_count == 1


async def test_cached_bytes_respects_kind_specific_cache_key_and_params():
    raw_a = b"payload-a"
    raw_b = b"payload-b"
    with respx.mock(assert_all_called=True) as mock:
        route = mock.get("https://example.com/doc").mock(
            side_effect=lambda request: httpx.Response(
                200, content=raw_a if request.url.params.get("v") == "1" else raw_b
            )
        )
        body_a, _ = await http_module.cached_bytes("https://example.com/doc", params={"v": "1"}, kind="xbrl")
        body_b, _ = await http_module.cached_bytes("https://example.com/doc", params={"v": "2"}, kind="xbrl")
        assert body_a == raw_a
        assert body_b == raw_b
        assert route.call_count == 2


def test_ttl_forever_kinds_use_the_none_sentinel():
    # "document" already used None to mean "never expires" (PDFs/XBRL do not change once
    # published); the new binary-content kinds follow the same convention.
    assert http_module.TTL["filing"] is None
    assert http_module.TTL["xbrl"] is None
    assert http_module.TTL["document"] is None


def test_ttl_screener_is_24_hours():
    assert http_module.TTL["screener"] == 86400


async def test_cached_bytes_forever_kind_never_expires_even_long_after_fetch(monkeypatch):
    raw = b"old-but-still-valid-filing-bytes"
    with respx.mock(assert_all_called=True) as mock:
        route = mock.get("https://example.com/old-filing.pdf").mock(
            return_value=httpx.Response(200, content=raw)
        )
        body1, ev1 = await http_module.cached_bytes("https://example.com/old-filing.pdf", kind="filing")
        assert ev1.cached is False

        # Simulate the entry being very old by rewinding its fetched_at far into the past.
        from urllib.parse import urlparse

        host = urlparse("https://example.com/old-filing.pdf").netloc
        key = http_module._cache_key("GET", "https://example.com/old-filing.pdf", None)
        meta_p = http_module._cache._path_meta(host, key)
        import json

        meta = json.loads(meta_p.read_text(encoding="utf-8"))
        meta["fetched_at"] = 0.0  # effectively year-1970
        meta_p.write_text(json.dumps(meta), encoding="utf-8")

        body2, ev2 = await http_module.cached_bytes("https://example.com/old-filing.pdf", kind="filing")
        assert body2 == raw
        assert ev2.cached is True  # still a hit, despite the ancient fetched_at
        assert route.call_count == 1


async def test_cached_bytes_non_forever_kind_expires_after_ttl():
    raw = b"screener-snapshot-bytes"
    with respx.mock(assert_all_called=True) as mock:
        route = mock.get("https://example.com/screener-data").mock(
            return_value=httpx.Response(200, content=raw)
        )
        body1, ev1 = await http_module.cached_bytes("https://example.com/screener-data", kind="screener")
        assert ev1.cached is False

        from urllib.parse import urlparse
        import json

        host = urlparse("https://example.com/screener-data").netloc
        key = http_module._cache_key("GET", "https://example.com/screener-data", None)
        meta_p = http_module._cache._path_meta(host, key)
        meta = json.loads(meta_p.read_text(encoding="utf-8"))
        meta["fetched_at"] = 0.0  # far older than the 24h screener TTL
        meta_p.write_text(json.dumps(meta), encoding="utf-8")

        body2, ev2 = await http_module.cached_bytes("https://example.com/screener-data", kind="screener")
        assert body2 == raw
        assert ev2.cached is False  # expired, so this is a fresh fetch, not a hit
        assert route.call_count == 2
