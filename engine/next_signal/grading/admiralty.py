"""Origin classification and Admiralty/NATO-style source reliability grading.

Table from PLAN.md §5.8 step 5: host/publisher pattern -> origin_class -> reliability grade A-F.
"""
from __future__ import annotations

import re
from urllib.parse import urlparse

from ..schemas import OriginClass

# (host-or-publisher regex, origin_class, reliability grade)
_RULES: list[tuple[re.Pattern, OriginClass, str]] = [
    (re.compile(r"nseindia\.com|bseindia\.com|nsearchives\.nseindia\.com", re.I), "company_filing", "A"),
    (re.compile(r"fda\.gov|accessdata\.fda\.gov", re.I), "regulator_us", "A"),
    (re.compile(r"cdsco\.gov\.in|nppaindia\.nic\.in|sebi\.gov\.in|pib\.gov\.in|mohfw\.gov\.in", re.I), "regulator_in", "A"),
    (re.compile(r"sec\.gov", re.I), "sec", "A"),
    (re.compile(r"crisilratings\.com|icra\.in|careratings\.com|indiaratings\.co\.in", re.I), "rating_agency", "B"),
    (re.compile(r"pharmexcil|ipaindia|iqvia", re.I), "industry_body", "B"),
    (re.compile(r"mcp\.nseindia\.in|upstox\.com|angelone\.in|smartapi", re.I), "market_data", "A"),
    (re.compile(
        r"economictimes\.indiatimes\.com|livemint\.com|business-standard\.com|moneycontrol\.com|"
        r"thehindubusinessline\.com|financialexpress\.com|reuters\.com|bloomberg\.com|cnbctv18\.com|"
        r"ndtvprofit\.com|fiercepharma\.com|endpts\.com",
        re.I,
    ), "press", "C"),
    (re.compile(r"screener\.in|trendlyne\.com|tickertape\.in", re.I), "aggregator", "C"),
]

_IR_HINT = re.compile(r"investor|/ir/|ir-|annualreport|presentation", re.I)


def classify(url: str, is_peer: bool = False) -> tuple[OriginClass, str]:
    host = urlparse(url).netloc.lower()
    for pattern, origin, grade in _RULES:
        if pattern.search(host) or pattern.search(url):
            if is_peer and origin == "company_filing":
                return "peer_filing", grade
            return origin, grade
    if _IR_HINT.search(url):
        origin: OriginClass = "peer_filing" if is_peer else "company_ir"
        return origin, "B"
    return "aggregator", "D"


GRADE_DEFINITIONS = {
    "A": "Primary record from the entity itself, a regulator, the exchange, or raw market data.",
    "B": "Reputable secondary institution (rating agency, industry body, company IR page not filed with an exchange).",
    "C": "Mainstream press or a data aggregator reproducing primary figures.",
    "D": "Unverified aggregator or a page that could not be matched to a known publisher class.",
    "E": "Low-reliability source used only as a lead, never as sole support for a number.",
    "F": "Source could not be verified at all; excluded from any claim.",
}
