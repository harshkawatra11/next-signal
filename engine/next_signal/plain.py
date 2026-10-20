"""Plain-language vocabulary: turns internal identifiers (metric ids, test ids, comparators, angle ids,
periods) into the words an analyst would write. Used by the engine wherever text reaches a reader, and
by the research paper. Never invents a number; formats the numbers it is given."""
from __future__ import annotations

import re
from datetime import date, datetime
from typing import Optional

from .metrics.library import REGISTRY

_OVERRIDES = {
    "rev_yoy": "revenue growth on the same quarter a year earlier",
    "revenue_yoy": "revenue growth on the same quarter a year earlier",
    "rev_qoq": "revenue growth on the previous quarter",
    "us_rev_usd_yoy": "growth in US revenue measured in US dollars, on the same quarter a year earlier",
    "gross_margin": "gross margin",
    "ebitda_margin": "EBITDA margin",
    "pat_margin": "net profit margin",
    "other_income_share": "other income as a share of profit before tax",
    "employee_pct": "employee costs as a share of revenue",
    "dna_pct": "depreciation as a share of revenue",
    "finance_cost_pct": "finance costs as a share of revenue",
}

_TEST_QUESTIONS = {
    "T1": "Is the change specific to the company rather than shared by its peers?",
    "T2": "Does the change survive once currency movements are removed?",
    "T3": "Does the change survive once disclosed one-off items are removed?",
    "T4": "Does the change survive a restatement of segment definitions?",
    "T5": "Is the change more than a seasonal pattern?",
    "T6": "Has the change persisted for at least two quarters?",
    "T7": "Had the change already been widely reported?",
    "T8": "Did a deliberate search for contrary evidence find any?",
    "T9": "Would the change have been visible using only information available at the time?",
}

_COMPARATOR_WORDS = {">=": "rises to or above", ">": "rises above", "<=": "falls to or below", "<": "falls below", "==": "returns to"}

_IDENT = re.compile(r"\b[a-z][a-z0-9]*(?:_[a-z0-9]+)+\b")


def metric_name(metric_id: str) -> str:
    """Title-case label for tables and figure axes."""
    if metric_id in REGISTRY:
        return REGISTRY[metric_id].name
    return metric_id.replace("_", " ").capitalize()


def metric_phrase(metric_id: str) -> str:
    """Lower-case noun phrase for prose."""
    if metric_id in _OVERRIDES:
        return _OVERRIDES[metric_id]
    name = metric_name(metric_id)
    return name[0].lower() + name[1:] if name and not name[:4].isupper() else name


def indian_group(n: float, decimals: int = 1) -> str:
    s = f"{abs(n):.{decimals}f}"
    whole, _, frac = s.partition(".")
    if len(whole) > 3:
        head, tail = whole[:-3], whole[-3:]
        parts = [head[max(0, i - 2):i] for i in range(len(head), 0, -2)][::-1]
        whole = ",".join(parts) + "," + tail
    return ("-" if n < 0 else "") + whole + ("." + frac if frac else "")


def crore(v: Optional[float], decimals: int = 1) -> str:
    return "" if v is None else f"Rs {indian_group(v, decimals)} crore"


def value_phrase(metric_id: str, value: Optional[float], *, table: bool = False) -> str:
    if value is None:
        return ""
    unit = REGISTRY[metric_id].unit if metric_id in REGISTRY else ""
    if unit == "pct":
        return f"{value * 100:.1f}%" if table else f"{value * 100:.1f} per cent"
    if unit == "pct_pts":
        return f"{value:.1f} pp" if table else f"{abs(value):.1f} percentage points"
    if unit == "days":
        return f"{value:.0f} days"
    if unit in ("INR_cr", "inr_cr", "crore"):
        return crore(value)
    if unit in ("count", "beds"):
        return f"{value:.0f}"
    return f"{value:.2f}"


def period_phrase(period: str) -> str:
    m = re.match(r"^(Q\d)FY(\d+)$", period or "")
    return f"{m.group(1)} FY{m.group(2)}" if m else (period or "")


def date_long(d) -> str:
    if d in (None, ""):
        return ""
    if isinstance(d, str):
        try:
            d = datetime.fromisoformat(d.replace("Z", "+00:00"))
        except ValueError:
            return d
    return f"{d.day} {d.strftime('%B %Y')}"


def test_question(test_id: str) -> str:
    return _TEST_QUESTIONS.get(test_id, "Additional check")


def falsification_plain(f, company: str) -> str:
    verb = _COMPARATOR_WORDS.get(f.comparator, "moves past")
    quarters = "quarter" if f.periods_required == 1 else f"{f.periods_required} consecutive quarters"
    return (
        f"The finding would be undermined if {metric_phrase(f.metric_id)} {verb} "
        f"{value_phrase(f.metric_id, f.threshold)} for {quarters}. The next test is {company}'s "
        f"{f.check_source}, expected around {date_long(f.next_check)}."
    )


def angle_question(angle_id: str) -> str:
    from .playbooks import angles as A
    for group in (getattr(A, n) for n in dir(A) if n.isupper()):
        if isinstance(group, tuple):
            for a in group:
                if getattr(a, "angle_id", None) == angle_id:
                    return a.question
    return "An additional line of enquiry"


def scrub_identifiers(text: str) -> str:
    """Replaces any registered metric id that leaked into prose with its plain phrase."""
    return _IDENT.sub(lambda m: metric_phrase(m.group(0)) if m.group(0) in REGISTRY or m.group(0) in _OVERRIDES else m.group(0), text or "")
