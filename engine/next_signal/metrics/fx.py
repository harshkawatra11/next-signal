"""FX neutralisation for US-dollar-denominated revenue lines reported in INR (PLAN.md §5.9.3).

fx_effect_us = us_rev_inr_yoy - us_rev_usd_yoy

A positive value means INR-terms growth looks better than USD-terms growth because the rupee weakened
over the period (translation gain, not operating performance); a negative value means INR strength is
masking real USD growth.
"""
from __future__ import annotations


def fx_effect(us_rev_inr_yoy: float, us_rev_usd_yoy: float) -> float:
    return us_rev_inr_yoy - us_rev_usd_yoy


def usd_from_inr(inr_value: float, usd_inr_rate: float) -> float | None:
    if usd_inr_rate <= 0:
        return None
    return inr_value / usd_inr_rate


def yoy_from_series(values: dict[str, float], period: str, prior_period: str) -> float | None:
    """values keyed by period label (e.g. 'Q1FY27' -> 'Q1FY26' for same-quarter YoY)."""
    if period not in values or prior_period not in values or values[prior_period] == 0:
        return None
    return (values[period] - values[prior_period]) / values[prior_period]
