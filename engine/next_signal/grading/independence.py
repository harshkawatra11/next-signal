"""Count independent ORIGINS of evidence, not documents. Two items from the same publisher (or a press
item that merely restates a company release within days) collapse to one origin. company_filing and
company_ir always collapse to a single "the company" origin, since multiple company documents are never
independent confirmation of each other.
"""
from __future__ import annotations

from rapidfuzz import fuzz

from ..schemas import EvidenceItem

_COMPANY_ORIGINS = {"company_filing", "company_ir"}


def _collapsed_origin(item: EvidenceItem) -> str:
    if item.origin_class in _COMPANY_ORIGINS:
        return "company"
    return f"{item.origin_class}:{item.publisher.lower().strip()}"


def is_press_restating_filing(press_item: EvidenceItem, filing_items: list[EvidenceItem], days: int = 3) -> bool:
    """A press item that reproduces a company filing within `days` of it is dependent on that filing,
    not an independent confirmation."""
    if press_item.origin_class != "press" or press_item.published_at is None:
        return False
    for f in filing_items:
        if f.origin_class not in _COMPANY_ORIGINS or f.published_at is None:
            continue
        delta = abs((press_item.published_at - f.published_at).days)
        if delta <= days and fuzz.token_set_ratio(press_item.anchor.quote, f.anchor.quote) >= 90:
            return True
    return False


def independent_origins(items: list[EvidenceItem]) -> int:
    filings = [i for i in items if i.origin_class in _COMPANY_ORIGINS]
    origins: set[str] = set()
    for item in items:
        if item.origin_class == "press" and is_press_restating_filing(item, filings):
            origins.add("company")  # collapses into the filing it restates, not a separate origin
            continue
        origins.add(_collapsed_origin(item))
    return len(origins)


def origin_mix(items: list[EvidenceItem]) -> list[dict]:
    """Counts by broad origin class, for the deck's segmented-bar chart (V.origin_mix)."""
    counts: dict[str, int] = {}
    for item in items:
        counts[item.origin_class] = counts.get(item.origin_class, 0) + 1
    return [{"label": k, "v": v} for k, v in sorted(counts.items(), key=lambda kv: -kv[1])]
