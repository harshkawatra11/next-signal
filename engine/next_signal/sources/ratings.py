"""Rating-agency actions, extracted from the text of NSE 'credit_rating' filings (PLAN.md §5.5.4). A
company's rating-action PDFs are already classified as `kind="credit_rating"` by `sources/nse.py`'s
subject-regex table; this module pulls the agency name, action verb and outlook out of that PDF's text.
Admiralty grade B (rating_agency). Extracting the exact rating grade itself (e.g. "AA+") is left out: the
grade string format differs enough across CRISIL/ICRA/CARE/India Ratings bracket conventions that a
single regex would either miss real cases or mis-parse a false positive, and the filing's own excerpt
text (kept here) already carries the full grade in whatever form the agency used.
"""
from __future__ import annotations

import re

AGENCIES = ["CRISIL", "ICRA", "CARE", "India Ratings", "Ind-Ra", "Brickwork"]
ACTIONS = ["assigned", "reaffirmed", "upgraded", "downgraded", "withdrawn", "revised"]
OUTLOOKS = ["stable", "positive", "negative", "developing"]

_AGENCY_RE = re.compile(r"\b(" + "|".join(re.escape(a) for a in AGENCIES) + r")\b", re.I)
_ACTION_RE = re.compile(r"\b(" + "|".join(ACTIONS) + r")\b", re.I)
_OUTLOOK_RE = re.compile(r"\b(" + "|".join(OUTLOOKS) + r")\b", re.I)


def identify_agency(text: str) -> str | None:
    m = _AGENCY_RE.search(text)
    return m.group(1) if m else None


def identify_action(text: str) -> str | None:
    m = _ACTION_RE.search(text)
    return m.group(1).lower() if m else None


def identify_outlook(text: str) -> str | None:
    m = _OUTLOOK_RE.search(text)
    return m.group(1).capitalize() if m else None


def extract_rating_action(text: str, excerpt_chars: int = 500) -> dict:
    """Best-effort extraction from one filing's text: agency, action verb, outlook, and a rationale
    excerpt taken from the agency's first mention onward (Indian rating-action PDFs reliably open their
    substantive text at or just after the agency's name)."""
    agency = identify_agency(text)
    action = identify_action(text)
    outlook = identify_outlook(text)
    excerpt = None
    if agency:
        idx = text.lower().find(agency.lower())
        excerpt = text[idx: idx + excerpt_chars].strip()
    return {"agency": agency, "action": action, "outlook": outlook, "excerpt": excerpt}
