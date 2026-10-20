"""FDA Orange Book data files: the ANDA/NDA product list, patents and exclusivities, filtered to a
company's name stems (PLAN.md §5.5.4). The files are `~`-delimited text, refreshed monthly by FDA; cache
the download for a month, per the spike S06 finding. Admiralty grade A (regulator_us).
"""
from __future__ import annotations

from datetime import date, datetime

from rapidfuzz import fuzz

PRODUCTS_FIELDS = [
    "Ingredient", "DF_Route", "Trade_Name", "Applicant", "Strength", "Appl_Type", "Appl_No",
    "Product_No", "TE_Code", "Approval_Date", "RLD", "RS", "Type", "Applicant_Full_Name",
]
PATENT_FIELDS = [
    "Appl_Type", "Appl_No", "Product_No", "Patent_No", "Patent_Expire_Date_Text",
    "Drug_Substance_Flag", "Drug_Product_Flag", "Patent_Use_Code", "Delist_Flag", "Submission_Date",
]
EXCLUSIVITY_FIELDS = ["Appl_Type", "Appl_No", "Product_No", "Exclusivity_Code", "Exclusivity_Date"]

_DAYS_IN_MONTH = [31, 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31]


def parse_delimited(text: str, fields: list[str]) -> list[dict]:
    """Orange Book's row format: a header line (ignored; field names are fixed per FDA's documentation,
    not read from the file) then one `~`-delimited record per line. Extra or missing trailing columns on
    a row are tolerated rather than raising."""
    lines = [line for line in text.splitlines() if line.strip()]
    if not lines:
        return []
    rows = []
    for line in lines[1:]:
        cells = line.split("~")
        rows.append({fields[i]: cells[i].strip() for i in range(min(len(fields), len(cells)))})
    return rows


def matches_stem(applicant_full_name: str, stems: list[str], threshold: int = 90) -> bool:
    name = (applicant_full_name or "").upper()
    return any(fuzz.partial_ratio(name, stem.upper()) >= threshold for stem in stems)


def products_for(products: list[dict], stems: list[str]) -> list[dict]:
    return [p for p in products if matches_stem(p.get("Applicant_Full_Name", ""), stems)]


def appl_nos_for(products: list[dict]) -> set[str]:
    return {p["Appl_No"] for p in products if p.get("Appl_No")}


def _parse_date(raw: str) -> date | None:
    raw = (raw or "").strip()
    if not raw:
        return None
    for fmt in ("%b %d, %Y", "%m/%d/%Y"):
        try:
            return datetime.strptime(raw, fmt).date()
        except ValueError:
            continue
    return None


def _is_leap(year: int) -> bool:
    return year % 4 == 0 and (year % 100 != 0 or year % 400 == 0)


def months_from(d: date, months: int) -> date:
    total = d.month - 1 + months
    year = d.year + total // 12
    month = total % 12 + 1
    max_day = _DAYS_IN_MONTH[month - 1] + (1 if month == 2 and _is_leap(year) else 0)
    return date(year, month, min(d.day, max_day))


def patents_expiring(patents: list[dict], appl_nos: set[str], as_of: date, months: int = 24) -> list[dict]:
    horizon = months_from(as_of, months)
    out = []
    for p in patents:
        if p.get("Appl_No") not in appl_nos:
            continue
        expiry = _parse_date(p.get("Patent_Expire_Date_Text", ""))
        if expiry is not None and as_of <= expiry <= horizon:
            out.append({**p, "expire_date": expiry})
    return out


def exclusivities_expiring(exclusivities: list[dict], appl_nos: set[str], as_of: date, months: int = 24) -> list[dict]:
    horizon = months_from(as_of, months)
    out = []
    for e in exclusivities:
        if e.get("Appl_No") not in appl_nos:
            continue
        expiry = _parse_date(e.get("Exclusivity_Date", ""))
        if expiry is not None and as_of <= expiry <= horizon:
            out.append({**e, "expire_date": expiry})
    return out
