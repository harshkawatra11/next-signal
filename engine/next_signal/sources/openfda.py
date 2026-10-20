"""openFDA client: drug approvals (drugsfda) and recalls (enforcement) for a company's name stems
(PLAN.md §5.5.4). No API key required; openFDA allows 240 requests/minute without one. Admiralty grade A
(regulator_us): this is the primary-source data the brief's own worked example (P2, a compliance issue
hitting the financials before the headline) needs.
"""
from __future__ import annotations

from datetime import datetime, timedelta

import httpx

BASE = "https://api.fda.gov"


def build_sponsor_query(stems: list[str]) -> str:
    """openFDA search syntax: quoted exact-phrase terms OR'd together inside one grouped clause."""
    return "(" + " OR ".join(f'sponsor_name:"{s}"' for s in stems) + ")"


def build_firm_query(stems: list[str]) -> str:
    return "(" + " OR ".join(f'recalling_firm:"{s}"' for s in stems) + ")"


def parse_approvals(results: list[dict]) -> list[dict]:
    """results: the 'results' array of a drugsfda.json response. One row per submission (not per
    application), since a single ANDA/NDA/BLA carries many submissions over its life and the angle
    questions (P5: are new launches masking price erosion) care about submission-level approval dates."""
    rows = []
    for app in results:
        app_no = app.get("application_number", "") or ""
        sponsor = app.get("sponsor_name", "")
        for sub in app.get("submissions", []) or []:
            rows.append({
                "application_number": app_no,
                "sponsor": sponsor,
                "submission_type": sub.get("submission_type"),
                "submission_status": sub.get("submission_status"),
                "submission_status_date": sub.get("submission_status_date"),
                "is_anda": app_no.startswith("ANDA"),
            })
    return rows


def parse_recalls(results: list[dict]) -> list[dict]:
    """results: the 'results' array of an enforcement.json response."""
    return [
        {
            "recalling_firm": r.get("recalling_firm"),
            "classification": r.get("classification"),
            "reason": r.get("reason_for_recall"),
            "recall_initiation_date": r.get("recall_initiation_date"),
            "report_date": r.get("report_date"),
            "status": r.get("status"),
            "product_description": r.get("product_description"),
        }
        for r in results
    ]


def count_anda_approvals_ttm(approval_rows: list[dict], as_of: str) -> int:
    """Counts ORIG+AP (originally approved, not a supplement) ANDA submissions whose
    submission_status_date falls in the 365 days up to and including as_of (both openFDA dates in
    "YYYYMMDD" form, matching the API's own format)."""
    as_of_dt = datetime.strptime(as_of, "%Y%m%d")
    window_start = as_of_dt - timedelta(days=365)
    count = 0
    for row in approval_rows:
        if not row.get("is_anda") or row.get("submission_status") != "AP":
            continue
        if row.get("submission_type") != "ORIG":
            continue
        raw_date = row.get("submission_status_date")
        if not raw_date:
            continue
        try:
            dt = datetime.strptime(raw_date, "%Y%m%d")
        except ValueError:
            continue
        if window_start <= dt <= as_of_dt:
            count += 1
    return count


def count_recalls_by_classification(recall_rows: list[dict], classification: str) -> int:
    return sum(1 for r in recall_rows if r.get("classification") == classification)


async def fetch_approvals(client: httpx.AsyncClient, stems: list[str], limit: int = 100) -> list[dict]:
    r = await client.get(
        f"{BASE}/drug/drugsfda.json", params={"search": build_sponsor_query(stems), "limit": limit}
    )
    r.raise_for_status()
    return r.json().get("results", [])


async def fetch_recalls(client: httpx.AsyncClient, stems: list[str], limit: int = 100) -> list[dict]:
    r = await client.get(
        f"{BASE}/drug/enforcement.json", params={"search": build_firm_query(stems), "limit": limit}
    )
    r.raise_for_status()
    return r.json().get("results", [])
