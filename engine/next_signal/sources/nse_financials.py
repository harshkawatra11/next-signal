"""NSE corporates-financial-results registry: selects the best XBRL-backed quarterly filing per period
for a company. Field names here are confirmed against a live NSE response (verified 16 Oct 2026, see
build-log.md), not assumed from documentation: period, cumulative, consolidated, fromDate, toDate,
broadCastDate, xbrl, financialYear, seqNumber. This is the primary, deterministic data backbone the rest
of the pipeline depends on: an Ind AS XBRL instance carries machine-readable, point-in-time-stamped P&L
line items that need no PDF parsing and no LLM call to extract.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from typing import Any, Optional

_DATE_FMT = "%d-%b-%Y"
_BROADCAST_FMT = "%d-%b-%Y %H:%M:%S"


@dataclass
class FilingRef:
    symbol: str
    from_date: date
    to_date: date
    consolidated: bool
    broadcast_at: datetime
    xbrl_url: str
    financial_year: str
    seq_number: str


def _parse_date(raw: str) -> Optional[date]:
    raw = (raw or "").strip()
    if not raw:
        return None
    try:
        return datetime.strptime(raw, _DATE_FMT).date()
    except ValueError:
        return None


def _parse_broadcast(raw: str) -> Optional[datetime]:
    raw = (raw or "").strip()
    if not raw:
        return None
    try:
        return datetime.strptime(raw, _BROADCAST_FMT)
    except ValueError:
        return None


def parse_financial_results(items: list[dict]) -> list[FilingRef]:
    """items: the raw list NSE's corporates-financial-results endpoint returns. Keeps only quarterly,
    non-cumulative filings that carry a usable XBRL URL and parse to valid dates: a filing missing any
    of these cannot become a verified Fact later, so it is dropped here rather than carried forward as a
    partial record. Does not yet choose between multiple filings for the same period; that is
    select_quarterly_filings's job, since a revision or a Standalone-versus-Consolidated choice needs the
    full candidate set to resolve correctly."""
    out = []
    for item in items:
        if item.get("period") != "Quarterly":
            continue
        if item.get("cumulative") != "Non-cumulative":
            continue
        xbrl_url = item.get("xbrl")
        if not xbrl_url:
            continue
        from_date = _parse_date(item.get("fromDate", ""))
        to_date = _parse_date(item.get("toDate", ""))
        broadcast_at = _parse_broadcast(item.get("broadCastDate", ""))
        if from_date is None or to_date is None or broadcast_at is None:
            continue
        out.append(FilingRef(
            symbol=item.get("symbol", ""), from_date=from_date, to_date=to_date,
            consolidated=item.get("consolidated") == "Consolidated", broadcast_at=broadcast_at,
            xbrl_url=xbrl_url, financial_year=item.get("financialYear", ""),
            seq_number=str(item.get("seqNumber", "")),
        ))
    return out


def select_quarterly_filings(filings: list[FilingRef], as_of: Optional[date] = None) -> list[FilingRef]:
    """One filing per reporting period (to_date): prefers Consolidated over Standalone, and within the
    same consolidation level prefers the later broadcast (a revised filing supersedes the original with
    the same period). Drops any filing broadcast after as_of, so a point-in-time replay never sees a
    filing from the future. Returns newest period first."""
    if as_of is not None:
        filings = [f for f in filings if f.broadcast_at.date() <= as_of]
    by_period: dict[date, FilingRef] = {}
    for f in filings:
        existing = by_period.get(f.to_date)
        if existing is None:
            by_period[f.to_date] = f
            continue
        if f.consolidated and not existing.consolidated:
            by_period[f.to_date] = f
        elif f.consolidated == existing.consolidated and f.broadcast_at > existing.broadcast_at:
            by_period[f.to_date] = f
    return sorted(by_period.values(), key=lambda f: f.to_date, reverse=True)


def _response_items(raw: Any) -> list[dict]:
    """NSE's financial-results endpoint returns a bare JSON array in the confirmed live probe; this also
    accepts a {"data": [...]} wrapper defensively, matching the same tolerant shape-handling already used
    for the announcements endpoint in pipeline/connect.py."""
    if isinstance(raw, list):
        return raw
    if isinstance(raw, dict):
        return raw.get("data") or []
    return []


async def fetch_filings(nse_client, symbol: str, as_of: Optional[date] = None, limit: int = 12) -> list[FilingRef]:
    """Fetches, parses and selects up to `limit` quarterly filings for `symbol`, newest first. Returns
    an empty list (never raises) if the client call fails, matching the honest-degrade pattern used
    throughout Connect: a company with no fetchable filing history still produces a valid, empty-handed
    report rather than aborting the run."""
    try:
        raw = await nse_client.financial_results(symbol)
    except Exception:
        return []
    parsed = parse_financial_results(_response_items(raw))
    return select_quarterly_filings(parsed, as_of=as_of)[:limit]
