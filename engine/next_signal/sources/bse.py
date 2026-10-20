"""BSE corporate announcements client: the fallback exchange when NSE is down or rate-limited, and the
counterparty for the cross-exchange consistency check (PLAN.md §5.5.2). Admiralty grade A (company_filing,
same as NSE): a BSE filing is as primary as its NSE counterpart, they are two copies of the same
disclosure, not independent corroboration of each other (see grading/independence.py's collapsing rule).
"""
from __future__ import annotations

from datetime import datetime

import httpx
from rapidfuzz import fuzz

BASE = "https://api.bseindia.com/BseIndiaAPI/api/AnnSubCategoryGetData/w"
REFERER = "https://www.bseindia.com/"


def build_params(scrip_code: str, from_date: str, to_date: str) -> dict:
    """from_date/to_date in 'YYYYMMDD' form, matching BSE's own query convention (confirmed in spike S02)."""
    return {
        "pageno": 1, "strCat": -1, "strPrevDate": from_date, "strScrip": scrip_code,
        "strSearch": "P", "strToDate": to_date, "strType": "C", "subcategory": -1,
    }


def _parse_bse_datetime(raw) -> datetime | None:
    if not raw:
        return None
    raw = str(raw).strip()
    for fmt in ("%Y-%m-%dT%H:%M:%S", "%Y-%m-%d %H:%M:%S", "%d-%b-%Y %H:%M:%S"):
        try:
            return datetime.strptime(raw, fmt)
        except ValueError:
            continue
    return None


def parse_announcements(payload: dict) -> list[dict]:
    """payload: the parsed JSON body; BSE nests announcement rows under 'Table'. A row whose date string
    does not match a known format gets `published_at=None` rather than raising, since a malformed date
    on one row should not drop the rest of the response."""
    rows = []
    for row in payload.get("Table", []) or []:
        rows.append({
            "subject": row.get("NEWSSUB") or row.get("HEADLINE"),
            "category": row.get("CATEGORYNAME"),
            "published_at": _parse_bse_datetime(row.get("NEWS_DT") or row.get("News_submission_dt")),
            "attachment_name": row.get("ATTACHMENTNAME"),
            "scrip_code": row.get("SCRIP_CD"),
        })
    return rows


def cross_exchange_consistency(nse_item: dict, bse_item: dict, title_threshold: int = 85) -> dict:
    """Compares one NSE announcement ({'title', 'published_at'}) against the BSE item it is believed to
    match ({'subject', 'published_at'}). Flags a contradiction when the titles disagree below
    `title_threshold` token-set similarity, or the two dates differ by more than 1 day; otherwise reports
    consistent. This is the mechanical half of the cross_channel contradiction type (grading/contradictions.py
    applies the judgement half: whether a flagged pair is actually worth surfacing)."""
    title_a = (nse_item.get("title") or "").upper()
    title_b = (bse_item.get("subject") or "").upper()
    similarity = fuzz.token_set_ratio(title_a, title_b)

    date_a = nse_item.get("published_at")
    date_b = bse_item.get("published_at")
    day_diff = abs((date_a - date_b).days) if date_a and date_b else None

    inconsistent = similarity < title_threshold or (day_diff is not None and day_diff > 1)
    if not inconsistent:
        return {"consistent": True, "title_similarity": similarity, "day_diff": day_diff}
    return {
        "consistent": False, "title_similarity": similarity, "day_diff": day_diff,
        "nse_title": nse_item.get("title"), "bse_title": bse_item.get("subject"),
    }


async def fetch_announcements(client: httpx.AsyncClient, scrip_code: str, from_date: str, to_date: str) -> list[dict]:
    r = await client.get(BASE, params=build_params(scrip_code, from_date, to_date), headers={"Referer": REFERER})
    r.raise_for_status()
    return r.json().get("Table", []) or []
