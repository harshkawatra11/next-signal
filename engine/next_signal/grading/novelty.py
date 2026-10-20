"""Novelty scoring: would a conventional finance dashboard or simple summariser likely miss this?
(brief judging criterion: Novelty)
"""
from __future__ import annotations


def novelty(mainstream_hits_90d: int, management_stated: bool, lead_days: int) -> float:
    coverage_term = 0.5 * (1 - min(1.0, mainstream_hits_90d / 20))
    narrative_term = 0.3 * (0.0 if management_stated else 1.0)
    lead_term = 0.2 * min(1.0, max(0, lead_days) / 90)
    return round(coverage_term + narrative_term + lead_term, 3)
