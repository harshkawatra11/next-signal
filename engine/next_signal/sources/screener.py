"""Screener.in client: a fast multi-year baseline of financials, ratios and shareholding, used for
quickpass data (Discover's angle scoring) and as peer-metric corroboration (PLAN.md §5.5.3). Admiralty
grade C (aggregator): any number that ends up in a final Discovery's Numbers block must also be anchored
in a primary document (results PDF, XBRL, presentation, annual report); screener only corroborates, and
is also the deliberate counterparty in the aggregator-vs-primary contradiction check.
"""
from __future__ import annotations

import calendar
import re
from datetime import date

import httpx
from bs4 import BeautifulSoup

BASE = "https://www.screener.in"
SECTIONS = ("quarters", "profit-loss", "balance-sheet", "cash-flow", "ratios", "shareholding")

_MONTHS = {m: i + 1 for i, m in enumerate(
    ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]
)}
_PERIOD = re.compile(r"^([A-Za-z]{3})\s+(\d{4})$")


def parse_period(header: str) -> date | None:
    """'Jun 2026' -> the last calendar day of that month. Non-period headers (blank, 'TTM', a row label
    that leaked into the header row) return None so callers drop that column rather than mis-dating it."""
    m = _PERIOD.match(header.strip())
    if not m:
        return None
    mon = _MONTHS.get(m.group(1).title())
    if mon is None:
        return None
    year = int(m.group(2))
    return date(year, mon, calendar.monthrange(year, mon)[1])


def clean_value(cell: str) -> float | None:
    """Screener renders negatives as '(123)', thousands with commas, and ratios with a trailing '%'.
    A blank cell or a bare dash means no data for that period, not zero."""
    s = cell.replace(",", "").replace("%", "").strip()
    if not s or s in ("-", "--"):
        return None
    negative = s.startswith("(") and s.endswith(")")
    s = s.strip("()").strip()
    try:
        value = float(s)
    except ValueError:
        return None
    return -value if negative else value


def parse_section(table) -> list[dict]:
    """table: a bs4 Tag for one section's <table>. Returns tidy rows [{item, period_end, value}], one per
    (line item, period) cell that actually has a numeric value. The first <tr> (whether it uses <th> or
    <td> cells, screener's markup has used both over the years) is treated as the period header row."""
    trs = table.find_all("tr")
    if not trs:
        return []
    header_cells = [c.get_text(strip=True) for c in trs[0].find_all(["th", "td"])]
    periods = [(p, idx) for idx, h in enumerate(header_cells) if (p := parse_period(h)) is not None]
    rows: list[dict] = []
    for tr in trs[1:]:
        cells = [c.get_text(strip=True) for c in tr.find_all(["td", "th"])]
        if not cells:
            continue
        item = cells[0].rstrip(" \t+").strip()
        if not item:
            continue
        for period, idx in periods:
            if idx >= len(cells):
                continue
            value = clean_value(cells[idx])
            if value is None:
                continue
            rows.append({"item": item, "period_end": period, "value": value})
    return rows


def parse_page(html: str) -> dict[str, list[dict]]:
    """Returns {section_id: rows} for every section in SECTIONS present on the page; a missing section
    (some companies have no shareholding table, for instance) maps to an empty list rather than a
    KeyError."""
    soup = BeautifulSoup(html, "html.parser")
    out: dict[str, list[dict]] = {}
    for section_id in SECTIONS:
        section = soup.find(id=section_id)
        table = section.find("table") if section is not None else None
        out[section_id] = parse_section(table) if table is not None else []
    return out


async def fetch_company_page(client: httpx.AsyncClient, symbol: str, consolidated: bool = True) -> str:
    """Live fetch: one request per company, the caller is expected to cache the result for 24 hours
    per PLAN.md §5.3 spike S09's rate-limit finding."""
    path = f"/company/{symbol}/consolidated/" if consolidated else f"/company/{symbol}/"
    r = await client.get(BASE + path, headers={"User-Agent": "Mozilla/5.0", "Accept-Language": "en-IN,en;q=0.9"})
    r.raise_for_status()
    return r.text
