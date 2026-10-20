"""FDA warning letters and Import Alert 66-40 (PLAN.md §5.5.4, spike S05). There is no stable FDA search
API for warning letters, so discovery goes through web search; the import alert list is one HTML page FDA
updates directly and needs no search step. Admiralty grade A (regulator_us): together with openfda.py and
orangebook.py, this completes the 483-to-OAI-to-warning-letter-to-import-alert compliance pipeline angle
P2 (the brief's own worked example) needs.
"""
from __future__ import annotations

import re
from datetime import date, datetime

from bs4 import BeautifulSoup
from rapidfuzz import fuzz

IMPORT_ALERT_URL = "https://www.accessdata.fda.gov/cms_ia/importalert_189.html"
WARNING_LETTER_PATH_HINT = "/inspections-compliance-enforcement-and-criminal-investigations/warning-letters/"


def is_warning_letter_url(url: str) -> bool:
    return WARNING_LETTER_PATH_HINT in url


def build_warning_letter_query(stem: str) -> str:
    return f'site:fda.gov "warning letter" "{stem}"'


def _parse_month_day_year(raw: str) -> date | None:
    raw = (raw or "").strip()
    if not raw:
        return None
    for fmt in ("%B %d, %Y", "%b %d, %Y", "%m/%d/%Y"):
        try:
            return datetime.strptime(raw, fmt).date()
        except ValueError:
            continue
    return None


def parse_warning_letter_page(html: str) -> dict:
    """Extracts what is findable on an FDA warning letter page: issue date, recipient firm, FEI number
    if present, CFR citations, and the first 600 characters of the body as an excerpt. Any field not
    found stays None rather than being guessed."""
    soup = BeautifulSoup(html, "html.parser")
    text = soup.get_text("\n")

    issue_date = None
    m = re.search(r"Issue Date:\s*([A-Za-z]+\s+\d{1,2},\s*\d{4})", text)
    if m:
        issue_date = _parse_month_day_year(m.group(1))

    firm = None
    m = re.search(r"(?:Recipient|Issued to):\s*([^\n]+)", text)
    if m:
        firm = m.group(1).strip()

    fei = None
    m = re.search(r"FEI\s*(?:Number|#)?\s*[:\-]?\s*(\d{6,10})", text)
    if m:
        fei = m.group(1)

    cfr_citations = sorted(set(re.findall(r"21\s*CFR\s*(?:§\s*)?[\d.]+(?:\([a-z0-9]+\))*", text)))

    return {
        "issue_date": issue_date, "firm": firm, "fei": fei, "cfr_citations": cfr_citations,
        "excerpt": text.strip()[:600],
    }


def parse_import_alert_page(html: str) -> list[dict]:
    """The IA 66-40 page is an HTML table with a header row naming its own columns (firm name, firm
    address, country, date published); column order has shifted between FDA site revisions, so columns
    are matched by substring on the header text rather than by fixed position."""
    soup = BeautifulSoup(html, "html.parser")
    table = soup.find("table")
    if table is None:
        return []
    trs = table.find_all("tr")
    if not trs:
        return []
    header = [c.get_text(strip=True).lower() for c in trs[0].find_all(["th", "td"])]
    col = {name: idx for idx, name in enumerate(header)}

    def get(cells: list[str], key_substr: str):
        for name, idx in col.items():
            if key_substr in name and idx < len(cells):
                return cells[idx]
        return None

    rows = []
    for tr in trs[1:]:
        cells = [c.get_text(strip=True) for c in tr.find_all(["td", "th"])]
        if not cells:
            continue
        rows.append({
            "firm_name": get(cells, "firm name") or get(cells, "firm"),
            "firm_address": get(cells, "address"),
            "country": get(cells, "country"),
            "date_published": _parse_month_day_year(get(cells, "date")),
        })
    return rows


def filter_import_alert_by_stem(rows: list[dict], stems: list[str], threshold: int = 85) -> list[dict]:
    return [
        r for r in rows
        if r.get("firm_name") and any(fuzz.partial_ratio(r["firm_name"].upper(), s.upper()) >= threshold for s in stems)
    ]
