"""Five contradiction types (PLAN.md §5.11). Pure detection rules operating on plain dicts/values so they
are testable without network access; pipeline/challenge.py wires these against real Fact/Event objects.
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass
class ContradictionHit:
    type: str
    claim: str
    side_a: str
    side_b: str
    ruling: str


def numeric_conflict(
    metric: str, period: str, entity: str,
    value_a: float, source_a: str, grade_a: str,
    value_b: float, source_b: str, grade_b: str,
    rounding_unit: float = 0.0,
) -> ContradictionHit | None:
    """Same metric, period, entity, two sources disagree by more than a rounding tolerance."""
    if value_a == value_b:
        return None
    denom = max(abs(value_a), abs(value_b), 1e-9)
    rel_diff = abs(value_a - value_b) / denom
    abs_diff = abs(value_a - value_b)
    if rel_diff <= 0.005 and abs_diff <= rounding_unit:
        return None
    # primary precedence: grade A beats a lower grade; if tied, prefer the later-dated source (restated)
    order = {"A": 4, "B": 3, "C": 2, "D": 1, "E": 0, "F": 0}
    if order.get(grade_a, 0) > order.get(grade_b, 0):
        ruling = f"primary precedence: {source_a} (grade {grade_a}) over {source_b} (grade {grade_b})"
    elif order.get(grade_b, 0) > order.get(grade_a, 0):
        ruling = f"primary precedence: {source_b} (grade {grade_b}) over {source_a} (grade {grade_a})"
    else:
        ruling = f"equal grade; flagged for manual review between {source_a} and {source_b}"
    return ContradictionHit(
        type="numeric",
        claim=f"{entity} {metric} for {period}",
        side_a=f"{source_a}: {value_a}",
        side_b=f"{source_b}: {value_b}",
        ruling=ruling,
    )


def narrative_vs_number(metric: str, narrative_divergence: float, threshold: float = 0.5) -> ContradictionHit | None:
    if narrative_divergence < threshold:
        return None
    return ContradictionHit(
        type="narrative_vs_number",
        claim=f"management narrative on {metric}",
        side_a="management's stated framing",
        side_b="the computed trend in the disclosed numbers",
        ruling=f"narrative divergence score {narrative_divergence:.2f} exceeds the {threshold} threshold",
    )


def temporal_guidance_miss(
    metric: str, guided_value: float, actual_value: float, rel_threshold: float = 0.10
) -> ContradictionHit | None:
    denom = max(abs(guided_value), 1e-9)
    rel_diff = (actual_value - guided_value) / denom
    wrong_sign = (guided_value > 0) != (actual_value > 0)
    if abs(rel_diff) <= rel_threshold and not wrong_sign:
        return None
    return ContradictionHit(
        type="temporal",
        claim=f"guidance versus actual for {metric}",
        side_a=f"guided {guided_value}",
        side_b=f"actual {actual_value}",
        ruling=f"missed by {rel_diff * 100:.1f}% relative to guidance" + (" and wrong sign" if wrong_sign else ""),
    )


def cross_channel_mismatch(metric: str, nse_value: float | None, sec_value: float | None) -> ContradictionHit | None:
    if nse_value is None or sec_value is None or nse_value == sec_value:
        return None
    return ContradictionHit(
        type="cross_channel",
        claim=f"{metric} across disclosure channels",
        side_a=f"NSE/BSE filing: {nse_value}",
        side_b=f"SEC filing: {sec_value}",
        ruling="both are primary filings; both values kept, flagged as a disclosure inconsistency",
    )


def aggregator_vs_primary(
    metric: str, period: str, aggregator_value: float, aggregator_name: str,
    primary_value: float, primary_name: str, rel_threshold: float = 0.01,
) -> ContradictionHit | None:
    denom = max(abs(primary_value), 1e-9)
    rel_diff = abs(aggregator_value - primary_value) / denom
    if rel_diff <= rel_threshold:
        return None
    return ContradictionHit(
        type="aggregator_vs_primary",
        claim=f"{metric} for {period}",
        side_a=f"{aggregator_name}: {aggregator_value}",
        side_b=f"{primary_name} (primary): {primary_value}",
        ruling=f"primary precedence: {primary_name} is the source of record; {aggregator_name} differs by {rel_diff * 100:.1f}%",
    )
