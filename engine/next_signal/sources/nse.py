"""NSE website client: cookie-warmed session + JSON API wrapper (PLAN.md §5.5.1), plus document
classification regexes and a live resolve() for companies outside the cached Track D universe.
"""
from __future__ import annotations

import re
import time
from datetime import datetime, timezone
from typing import Any, Optional

import httpx

from ..http import FetchEvent, get_client, notify_fetch
from ..universe import ResolvedIdentity, playbook_for

BASE = "https://www.nseindia.com"
_WARM_PATHS = ["/", "/get-quotes/equity?symbol={sym}", "/companies-listing/corporate-filings-announcements"]

# Document-kind classification: first regex match wins (PLAN.md §5.5.1 table).
_KIND_RULES: list[tuple[re.Pattern, str]] = [
    (re.compile(r"financial result|outcome of board meeting.*result|results? for the quarter", re.I), "results"),
    (re.compile(r"investor presentation|earnings presentation|analyst.*presentation", re.I), "presentation"),
    (re.compile(r"transcript", re.I), "transcript"),
    (re.compile(r"audio|recording", re.I), "call_audio"),
    (re.compile(r"credit rating|rating", re.I), "credit_rating"),
    (re.compile(
        r"usfda|us fda|form 483|warning letter|import alert|establishment inspection|eir|observations", re.I
    ), "regulatory_usfda"),
    (re.compile(r"acquisition|amalgamation|demerger|scheme of arrangement|divest", re.I), "acquisition"),
    (re.compile(r"litigation|court|tribunal|settlement|penalty", re.I), "litigation"),
    (re.compile(r"commission|operational|beds|plant|facility|capacity", re.I), "capacity"),
]


def classify_kind(subject: str, attachment_text: str = "") -> str:
    text = f"{subject} {attachment_text}"
    for pattern, kind in _KIND_RULES:
        if pattern.search(text):
            return kind
    return "other"


class NSE:
    def __init__(self, client: Optional[httpx.AsyncClient] = None) -> None:
        self.c = client or get_client()
        self.warm = False

    async def refresh_cookies(self, sym: str = "RELIANCE") -> None:
        for p in _WARM_PATHS:
            try:
                await self.c.get(BASE + p.format(sym=sym), headers={"Accept": "text/html"})
            except httpx.HTTPError:
                pass
        self.warm = True

    async def _get_json_endpoint(self, path: str, params: dict) -> httpx.Response:
        url = f"{BASE}/api/{path}"
        t0 = time.perf_counter()
        r = await self.c.get(url, params=params, headers={"Accept": "application/json", "Referer": f"{BASE}/"})
        notify_fetch(FetchEvent("www.nseindia.com", str(r.url), r.status_code, int((time.perf_counter() - t0) * 1000), False))
        return r

    async def api(self, path: str, **params: Any) -> Any:
        if not self.warm:
            await self.refresh_cookies()
        try:
            r = await self._get_json_endpoint(path, params)
        except httpx.TimeoutException:
            # A cold/expired session on the live site does not reliably surface as 401/403; a
            # research pass (PLAN.md Phase R1, lane R-E) found it can simply hang until timeout
            # instead, on every one of NSE's own hosts tested (homepage, the HTML quote page, and
            # this JSON endpoint). Treat a timeout the same way as 401/403 below: refresh cookies
            # once and retry once, rather than surfacing the first timeout as a hard failure.
            await self.refresh_cookies()
            r = await self._get_json_endpoint(path, params)
            r.raise_for_status()
            return r.json()

        if r.status_code in (401, 403):
            await self.refresh_cookies()
            r = await self._get_json_endpoint(path, params)
        r.raise_for_status()
        return r.json()

    async def quote(self, sym: str) -> dict:
        return await self.api("quote-equity", symbol=sym)

    async def announcements(self, sym: str, frm: str, to: str) -> dict:
        return await self.api("corporate-announcements", index="equities", symbol=sym, from_date=frm, to_date=to)

    async def annual_reports(self, sym: str) -> dict:
        return await self.api("annual-reports", index="equities", symbol=sym)

    async def financial_results(self, sym: str, period: str = "Quarterly") -> dict:
        return await self.api("corporates-financial-results", index="equities", symbol=sym, period=period)

    async def results_comparison(self, sym: str) -> dict:
        return await self.api("results-comparision", symbol=sym)

    async def shareholding(self, sym: str) -> dict:
        return await self.api("corporate-share-holdings-master", index="equities", symbol=sym)

    async def board_meetings(self, sym: str) -> dict:
        return await self.api("corporate-board-meetings", index="equities", symbol=sym)

    async def insider(self, sym: str) -> dict:
        return await self.api("corporates-pit", index="equities", symbol=sym)


def parse_nse_date(s: str) -> Optional[datetime]:
    """NSE timestamps commonly look like '22-Jul-2026 17:03:12' or '22-Jul-2026'."""
    for fmt in ("%d-%b-%Y %H:%M:%S", "%d-%b-%Y", "%d-%m-%Y %H:%M:%S", "%d-%m-%Y"):
        try:
            return datetime.strptime(s.strip(), fmt).replace(tzinfo=timezone.utc)
        except ValueError:
            continue
    return None


async def resolve_live(query: str) -> Optional[ResolvedIdentity]:
    """Resolve a company outside the cached Track D universe via a live NSE lookup. Used only as a
    fallback by pipeline/resolve.py, for the tie-break robustness requirement."""
    nse = NSE()
    sym = query.strip().upper()
    try:
        data = await nse.quote(sym)
    except httpx.HTTPError:
        return None
    info = data.get("info", {}) if isinstance(data, dict) else {}
    industry_info = data.get("industryInfo", {}) if isinstance(data, dict) else {}
    symbol = info.get("symbol") or sym
    name = info.get("companyName") or symbol
    basic_industry = industry_info.get("basicIndustry", "")
    industry = industry_info.get("industry", "")
    return ResolvedIdentity(
        symbol=symbol,
        company_name=name,
        industry=industry,
        playbook=playbook_for(basic_industry, industry),
        in_nifty50=False,
        isin=info.get("isin", ""),
    )
