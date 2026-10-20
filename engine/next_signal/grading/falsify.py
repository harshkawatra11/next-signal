"""Deterministic falsification tests T1 to T6 (PLAN.md §5.11 table). T7 (novelty) is scored by
grading/novelty.py and only downgrades, never kills, so it is not a TestResult-returning function here.
T8 (disconfirming search) and T9 (time-travel) require an LLM call and a second pipeline run respectively;
those are implemented in pipeline/challenge.py and eval/timetravel.py once real run data exists.
"""
from __future__ import annotations

from statistics import median

from .. import plain
from ..schemas import Hypothesis, TestResult


def mad(xs: list[float]) -> float:
    m = median(xs)
    return median([abs(x - m) for x in xs]) or 1e-9


def t1_peer(hyp: Hypothesis, subject_change: float | None, peer_changes: list[float], direction: str) -> TestResult:
    if subject_change is None or len(peer_changes) < 3:
        return TestResult(
            hyp_id=hyp.hyp_id, test_id="T1", applicable=False, passed=None, detail="fewer than 3 peers",
            plain="Fewer than three peers had comparable data, so this check could not be made.",
        )
    z = (subject_change - median(peer_changes)) / (1.4826 * mad(peer_changes))
    signed = z if direction == "up" else -z
    n = len(peer_changes)
    sector_same = all((c > 0) == (subject_change > 0) for c in peer_changes) and abs(z) < 0.5
    passed = signed >= 1.0 and not sector_same
    if sector_same:
        t1_plain = f"The {n} peers moved the same way, so the change looks sector-wide rather than specific to the company."
    elif passed:
        t1_plain = f"The company moved {abs(z):.1f} robust standard deviations away from the median of {n} peers, so the change is specific to it."
    else:
        t1_plain = f"The company's change was within {abs(z):.1f} robust standard deviations of the peer median, which is too close to call company-specific."
    return TestResult(
        hyp_id=hyp.hyp_id, test_id="T1", applicable=True, passed=passed,
        detail=f"robust peer z {z:.2f} vs {len(peer_changes)} peers; sector-wide={sector_same}",
        plain=t1_plain,
    )


def t5_season(hyp: Hypothesis, yoy_same_quarter: list[float], direction: str) -> TestResult:
    if len(yoy_same_quarter) < 2:
        return TestResult(
            hyp_id=hyp.hyp_id, test_id="T5", applicable=False, passed=None, detail="not quarterly",
            plain="Fewer than two comparable quarters were available.",
        )
    recent = yoy_same_quarter[-4:]
    agree = sum(1 for v in recent if (v > 0) == (direction == "up"))
    passed = agree >= 3 or agree == len(recent)
    t5_plain = f"In {agree} of the last {len(recent)} years the same quarter moved in the predicted direction."
    t5_plain += " A seasonal pattern does not explain it." if passed else " The pattern is not consistent enough to rule out seasonality."
    return TestResult(
        hyp_id=hyp.hyp_id, test_id="T5", applicable=True,
        passed=passed,
        detail=f"{agree} of last {len(recent)} same-quarter YoY moves agree",
        plain=t5_plain,
    )


def t2_fx(
    hyp: Hypothesis, inr_yoy: float | None, usd_yoy: float | None, applies: bool, direction: str
) -> TestResult:
    """Applicable only when the metric is an INR-reported figure for a USD-earning segment. Passes
    when the change survives in USD terms at >= 50% of its INR-terms magnitude and the same sign."""
    if not applies or inr_yoy is None or usd_yoy is None:
        return TestResult(
            hyp_id=hyp.hyp_id, test_id="T2", applicable=False, passed=None, detail="not an FX-sensitive metric",
            plain="The measure is not exposed to currency movements.",
        )
    same_sign = (usd_yoy > 0) == (direction == "up")
    magnitude_ok = abs(usd_yoy) >= 0.5 * abs(inr_yoy) if inr_yoy != 0 else False
    passed = same_sign and magnitude_ok
    t2_plain = f"Measured in rupees the change was {inr_yoy * 100:.1f} per cent; in US dollars it was {usd_yoy * 100:.1f} per cent."
    t2_plain += " It survives the currency adjustment." if passed else " Much of it reflects the exchange rate."
    return TestResult(
        hyp_id=hyp.hyp_id, test_id="T2", applicable=True, passed=passed,
        detail=f"INR yoy {inr_yoy:.3f}, USD yoy {usd_yoy:.3f}, same sign={same_sign}",
        plain=t2_plain,
    )


def t3_one_off(
    hyp: Hypothesis, value_with_item: float, value_excl_item: float, prior_value: float, direction: str,
    has_disclosed_one_off: bool,
) -> TestResult:
    """Applicable when a disclosed exceptional item, acquisition, divestment or demerger falls within
    the window. Passes if the change still holds after excluding the disclosed item."""
    if not has_disclosed_one_off:
        return TestResult(
            hyp_id=hyp.hyp_id, test_id="T3", applicable=False, passed=None, detail="no disclosed one-off in window",
            plain="No one-off item was disclosed in the period examined.",
        )
    change_excl = value_excl_item - prior_value
    passed = (change_excl > 0) == (direction == "up") and abs(change_excl) > 0
    return TestResult(
        hyp_id=hyp.hyp_id, test_id="T3", applicable=True, passed=passed,
        detail=f"excluding the disclosed item, change is {change_excl:.2f} (direction {'up' if change_excl > 0 else 'down'})",
        plain="After removing the disclosed one-off item the change " + ("still holds." if passed else "no longer holds."),
    )


def t4_reclassification(
    hyp: Hypothesis, labels_changed: bool, restated_available: bool,
    change_on_restated: float | None, direction: str,
) -> TestResult:
    """Applicable when segment/geography labels differ across the compared periods. Passes if the
    change persists on restated comparatives, or trivially passes when labels did not change at all."""
    if not labels_changed:
        return TestResult(
            hyp_id=hyp.hyp_id, test_id="T4", applicable=False, passed=None, detail="labels unchanged across periods",
            plain="Segment definitions did not change across the quarters compared.",
        )
    if not restated_available or change_on_restated is None:
        return TestResult(
            hyp_id=hyp.hyp_id, test_id="T4", applicable=True, passed=False,
            detail="labels changed and no restated comparative was found to confirm the change survives",
            plain="Segment definitions changed and no restated comparative was published, so the change cannot be confirmed on a like-for-like basis.",
        )
    passed = (change_on_restated > 0) == (direction == "up")
    return TestResult(
        hyp_id=hyp.hyp_id, test_id="T4", applicable=True, passed=passed,
        detail=f"change on restated comparatives is {change_on_restated:.2f}",
        plain="On restated comparatives the change " + ("still holds." if passed else "does not hold."),
    )


def t6_persist(
    hyp: Hypothesis, series: list[float], cp_index: int | None, direction: str, dated_event: bool
) -> TestResult:
    if dated_event:
        return TestResult(
            hyp_id=hyp.hyp_id, test_id="T6", applicable=True, passed=True,
            detail="single dated, anchored event",
            plain="The change is tied to a single dated and documented event.",
        )
    if cp_index is None or cp_index >= len(series) - 1:
        return TestResult(
            hyp_id=hyp.hyp_id, test_id="T6", applicable=True, passed=False,
            detail="no change persisting 2+ periods",
            plain="The change has not persisted for two or more quarters.",
        )
    pre = sum(series[:cp_index]) / max(1, cp_index)
    post = series[cp_index:]
    ok = sum(1 for v in post if (v > pre) == (direction == "up")) >= 2
    if hyp.predictions:
        pre_display = plain.value_phrase(hyp.predictions[0].metric_id, pre)
    else:
        pre_display = f"{pre:.2f}"
    return TestResult(
        hyp_id=hyp.hyp_id, test_id="T6", applicable=True, passed=ok,
        detail=f"{len(post)} periods after the change; pre-change mean {pre:.2f}",
        plain=f"The change has held for {len(post)} quarters against an earlier average of {pre_display}.",
    )
