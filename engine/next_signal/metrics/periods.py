"""Fiscal period labeling and ordering for Indian financial years (April to March). Shared by the XBRL
parser (which only has calendar dates) and the Calculate stage's series adapter (which needs to resolve
"the same quarter a year ago" and "the previous quarter" by calendar, not by list position).
"""
from __future__ import annotations

import re
from datetime import date

_QUARTER_MONTHS = {4: 1, 5: 1, 6: 1, 7: 2, 8: 2, 9: 2, 10: 3, 11: 3, 12: 3, 1: 4, 2: 4, 3: 4}


def fiscal_label(period_end: date) -> str:
    """A period ending 30 Jun 2026 is Q1 FY27 (the quarter opens the FY that ends March 2027). A period
    ending 31 Mar 2026 is Q4 FY26 (it closes the FY that started April 2025). Returns "Q1FY27" style,
    with no space, matching the period string convention already used throughout schemas.Fact.period and
    pipeline/calculate.py's ordered_periods."""
    q = _QUARTER_MONTHS[period_end.month]
    fy_end_year = period_end.year + 1 if period_end.month >= 4 else period_end.year
    return "Q%dFY%02d" % (q, fy_end_year % 100)


def period_sort_key(period: str) -> tuple[int, int, str]:
    """(fy, quarter, tiebreak) so a plain sort places periods in calendar order, with annual periods
    (quarter 0) sorting before any quarter of the same FY. fy and quarter are always int, unlike
    pipeline/calculate.py's old ordered_periods, whose unmatched-period fallback key mixed an int and a
    str in the same tuple position, which raises TypeError comparing int to str in Python 3 across a
    mixed list. An unrecognised period string sorts after every recognised one (fy=999999) and falls
    back to lexical order (via the string itself as the tiebreak) among other unrecognised strings."""
    m = re.match(r"Q(\d)FY(\d+)", period)
    if m:
        return (int(m.group(2)), int(m.group(1)), "")
    m = re.match(r"FY(\d+)", period)
    if m:
        return (int(m.group(1)), 0, "")
    return (999999, 0, period)


def quarter_before(period: str) -> str | None:
    """The immediately preceding quarter: Q1FY27 -> Q4FY26, Q3FY26 -> Q2FY26. Returns None for an
    unrecognised or annual period, since "the previous quarter" is undefined for those."""
    m = re.match(r"Q(\d)FY(\d+)", period)
    if not m:
        return None
    q, fy = int(m.group(1)), int(m.group(2))
    if q == 1:
        return "Q4FY%02d" % ((fy - 1) % 100)
    return "Q%dFY%02d" % (q - 1, fy)


def same_quarter_prior_year(period: str) -> str | None:
    """The same quarter one fiscal year earlier: Q1FY27 -> Q1FY26. Returns None for an unrecognised or
    annual period."""
    m = re.match(r"Q(\d)FY(\d+)", period)
    if not m:
        return None
    q, fy = int(m.group(1)), int(m.group(2))
    return "Q%dFY%02d" % (q, (fy - 1) % 100)


def ttm_quarters(period: str) -> list[str] | None:
    """The four quarters ending at and including `period`, oldest first, for a trailing-twelve-months
    sum. Returns None if `period` itself is not a recognised quarter."""
    quarters = [period]
    cur = period
    for _ in range(3):
        prev = quarter_before(cur)
        if prev is None:
            return None
        quarters.append(prev)
        cur = prev
    return list(reversed(quarters))
