"""Guards the LLM writer stage runs against before a Discovery is shown to anyone.

1. stray_numbers: every numeric token in generated text must trace to an allowed number (from numbers[],
   evidence quotes, or small structural constants like years/strength-score components). This is the port of
   ai-healthcare platform/backend/app/services/briefing_service.py::stray_numbers.
2. copy_issues: dashes, exclamation marks, investment language (buy/sell/target price etc. are banned per the
   case rule "you should not give an investment recommendation").
"""
from __future__ import annotations

import re

NUM = re.compile(r"(?<![A-Za-z])[-+]?\d[\d,]*(?:\.\d+)?")
# No letter-lookbehind: used only to pull every digit run out of our OWN structured fields (periods
# like "Q1FY27", ISO dates) when building the allowed-number set, never to scan model output. The
# lookbehind in NUM exists specifically to stop model output like "page12" counting as the number 12;
# that protection would be wrong here, since we WANT "27" out of "Q1FY27" even though it follows "FY".
_DIGITS = re.compile(r"\d+")
BANNED_INVEST = re.compile(
    r"\b(buy rating|sell rating|hold rating|buy the (stock|shares)|sell the (stock|shares)|"
    r"target price|price target|undervalued|overvalued|investors should|"
    r"we recommend (buying|selling|holding))\b",
    re.I,
)


def numbers_in(text: str) -> set[str]:
    return {m.group().replace(",", "").lstrip("+") for m in NUM.finditer(text)}


def repr_num(v: float) -> str:
    return str(int(v)) if float(v).is_integer() else f"{v:.2f}".rstrip("0").rstrip(".")


def allowed_numbers_from_discovery(discovery) -> set[str]:
    """discovery: a next_signal.schemas.Discovery instance.

    Found by the voice eval (engine/next_signal/voice/eval_voice.py) against a real Sarvam call, not
    guessed: a live reply correctly paraphrased a NumberBlock's own `period` field ("Q1FY27") as
    "...in fiscal year 27..." and correctly spoke a Timeline point's date as "15 April 2026", and both
    were wrongly flagged as stray because this function only scanned `n.display` (not `n.period`) and
    only the timeline date's year (not its full ISO string, which also covers the day and month
    digits). Both are now scanned, so a genuinely grounded paraphrase of a period or a full date no
    longer trips the guard.
    """
    allowed: set[str] = set()
    for n in discovery.numbers:
        allowed |= numbers_in(n.display) | set(_DIGITS.findall(n.period)) | {repr_num(n.value)}
    for e in discovery.evidence:
        allowed |= numbers_in(e.anchor.quote)
    for t in discovery.timeline:
        allowed |= numbers_in(t.label)
        # numbers_in(str(t.date)) was tried and does NOT work: numbers_in's regex includes a
        # leading "-+" sign in the match, so "2026-04-15" tokenizes to {"2026","-04","-15"}, not
        # {"2026","04","15"} - the hyphen (ISO date separator, not a minus sign) gets swallowed into
        # the token. Verified directly against a live Sarvam reply that spoke "15 April 2026" and was
        # wrongly flagged as a stray "15". Fixed by adding the date's own numeric fields directly
        # instead of re-deriving them from a regex over the formatted string.
        allowed |= {str(t.date.year), str(t.date.month), f"{t.date.month:02d}", str(t.date.day), f"{t.date.day:02d}"}
    s = discovery.strength
    allowed |= {repr_num(x) for x in (s.independence, s.reliability, s.corroboration, s.survival, s.persistence, s.total)}
    allowed |= numbers_in(discovery.falsification.statement) | {repr_num(discovery.falsification.threshold)}
    nc = discovery.falsification.next_check
    allowed |= {str(nc.year), str(nc.month), f"{nc.month:02d}", str(nc.day), f"{nc.day:02d}"}
    allowed |= numbers_in(discovery.counterargument)
    for c in discovery.claims:
        allowed |= numbers_in(c.text)
    allowed |= {str(y) for y in range(1990, 2036)}
    allowed |= {str(i) for i in range(0, 11)}
    return allowed


def stray_numbers(text: str, allowed: set[str]) -> list[str]:
    out = []
    for n in numbers_in(text):
        stripped = n.rstrip("0").rstrip(".") if "." in n else n
        if n not in allowed and stripped not in allowed:
            out.append(n)
    return sorted(set(out))


def copy_issues(text: str) -> list[str]:
    out = []
    if re.search("[—–]", text):
        out.append("dash")
    if "!" in text:
        out.append("exclamation")
    if BANNED_INVEST.search(text):
        out.append("investment language")
    return out
