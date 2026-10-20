"""Guard against company-specific hard-coding (PLAN.md §5.16, §0.3 rule 7, case rule: "Hard-coding
analysis or results for specific companies is not allowed"). Greps every engine source file for the
five NIFTY 50 Track D symbols and their company names; only test fixtures and the eval harness are
allowed to name them, since those exist specifically to exercise the engine against named companies,
not to special-case behaviour for them.
"""
from __future__ import annotations

import re
from pathlib import Path

ENGINE_ROOT = Path(__file__).resolve().parents[1] / "next_signal"

# These are the only files allowed to mention a Track D company by name: the universe loader itself
# (which only matches them generically via live index data, these strings never appear literally in
# its source code, so nothing here actually exempts it; listed for clarity) would fail this test too
# if it ever did reference them by name.
ALLOWED_DIRS = {"eval"}

SYMBOLS = ["SUNPHARMA", "CIPLA", "DRREDDY", "APOLLOHOSP", "MAXHEALTH"]
NAMES = [
    "Sun Pharma", "Sun Pharmaceutical",
    "Cipla",
    "Dr. Reddy", "Dr Reddy",
    "Apollo Hospitals",
    "Max Healthcare",
]

ALL_PATTERNS = [re.compile(re.escape(s), re.I) for s in SYMBOLS + NAMES]


def _py_files():
    return [p for p in ENGINE_ROOT.rglob("*.py") if "__pycache__" not in p.parts]


def test_no_company_names_hardcoded_outside_eval():
    hits = []
    for f in _py_files():
        rel = f.relative_to(ENGINE_ROOT)
        if rel.parts and rel.parts[0] in ALLOWED_DIRS:
            continue
        text = f.read_text(encoding="utf-8", errors="ignore")
        for pattern in ALL_PATTERNS:
            if pattern.search(text):
                hits.append((str(rel), pattern.pattern))
    assert hits == [], (
        "Company-specific strings found outside the eval/ directory (not allowed - "
        "PLAN.md §0.3 rule 7 and the case's own no-hard-coding rule): " + repr(hits)
    )


def test_playbooks_are_generic_not_per_company():
    """playbooks/angles.py must key angles by sub-industry (pharma/hospital/diagnostics/generic),
    never by a specific company. This re-asserts the same guarantee structurally, not just by name
    absence: no module anywhere should import a per-symbol dict keyed by one of the five symbols."""
    from next_signal.playbooks.angles import PLAYBOOKS

    assert set(PLAYBOOKS.keys()) == {"pharma", "hospital", "diagnostics", "generic"}
    for symbol in SYMBOLS:
        assert symbol not in PLAYBOOKS
