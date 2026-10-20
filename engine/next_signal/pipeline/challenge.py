"""Challenge stage: run the deterministic falsification tests (T1 to T6) against each main hypothesis,
apply the kill/downgrade rules, and build the Analysis of Competing Hypotheses matrix the Counterargument
comes from (PLAN.md §5.11). T7 (novelty) only downgrades and lives in grading/novelty.py; T8 (disconfirming
search) needs an LLM call and T9 (time-travel) needs a second pipeline run, so neither produces a
TestResult here yet, same stubbed-until-the-orchestrator-exists pattern as the other stages.
"""
from __future__ import annotations

from typing import Callable, Optional

from ..grading import ach as ach_module
from ..grading import falsify
from ..metrics.periods import period_sort_key
from ..schemas import Hypothesis, TestResult
from .context import RunContext

_DOWNGRADE_TESTS = {"T2", "T3", "T4"}


def run_core_tests(hyp: Hypothesis, inputs: dict) -> list[TestResult]:
    """inputs is keyed by test id ("T1".."T6") to a kwargs dict for that falsify.* function; a test id
    missing from inputs simply does not run for this hypothesis (the caller decides which tests have the
    data to apply, not this function)."""
    fns = {
        "T1": falsify.t1_peer, "T2": falsify.t2_fx, "T3": falsify.t3_one_off,
        "T4": falsify.t4_reclassification, "T5": falsify.t5_season, "T6": falsify.t6_persist,
    }
    results = []
    for test_id, kwargs in inputs.items():
        if test_id in fns:
            results.append(fns[test_id](hyp, **kwargs))
    return results


def apply_kill_rules(hyp: Hypothesis, results: list[TestResult], independent_origins: Optional[int] = None) -> Hypothesis:
    """KILL if T6 fails, or T1 fails on a sector-wide move, or independent_origins < 2 (when known).
    DOWNGRADE if T2, T3 or T4 fails but nothing killed it. Otherwise SURVIVED. Returns a new Hypothesis
    (pydantic models are immutable here); callers replace the list entry with the return value."""
    reasons = []
    by_id = {r.test_id: r for r in results}

    t6 = by_id.get("T6")
    if t6 is not None and t6.applicable and t6.passed is False:
        reasons.append(t6.plain or t6.detail)

    t1 = by_id.get("T1")
    if t1 is not None and t1.applicable and t1.passed is False and "sector-wide=True" in t1.detail:
        reasons.append(t1.plain or t1.detail)

    if independent_origins is not None and independent_origins < 2:
        reasons.append(f"Only {independent_origins} independent origin(s) support the finding, fewer than the 2 required.")

    if reasons:
        return hyp.model_copy(update={"status": "killed", "kill_reason": " ".join(reasons)})

    downgraded = any(
        by_id.get(t) is not None and by_id[t].applicable and by_id[t].passed is False for t in _DOWNGRADE_TESTS
    )
    return hyp.model_copy(update={"status": "downgraded" if downgraded else "survived"})


TestInputBuilder = Callable[[RunContext, Hypothesis], dict]


def _metric_series(ctx: RunContext, metric_id: str) -> list[tuple[str, float]]:
    rows = [(m.period, m.value) for m in ctx.metrics if m.metric_id == metric_id]
    return sorted(rows, key=lambda pv: period_sort_key(pv[0]))


def default_test_inputs(ctx: RunContext, hyp: Hypothesis) -> dict:
    """Builds real kwargs for T1 (peer), T5 (seasonality) and T6 (persistence) from ctx.metrics,
    ctx.peer_metrics and ctx.anomalies, for the hypothesis's predicted metric. T2 (FX), T3 (one-off) and
    T4 (reclassification) stay not-applicable: they need dual-currency facts, an explicit one-off flag
    and segment-label tracking respectively, none of which Connect extracts yet, so leaving their test id
    out of the returned dict (rather than guessing an input) correctly marks them not-applicable per
    run_core_tests' own contract. Returns {} (no tests run) for a hypothesis with no prediction or whose
    metric has fewer than 2 computed periods, the same honest degrade as before."""
    if not hyp.predictions:
        return {}
    metric_id = hyp.predictions[0].metric_id
    direction = hyp.predictions[0].direction
    series = _metric_series(ctx, metric_id)
    if len(series) < 2:
        return {}

    inputs: dict = {}

    # T1: peer test. subject_change and each peer's own change are both the most recent quarter-on-
    # quarter move in the metric's own units, so the comparison is apples to apples regardless of
    # whether the metric itself is a level (gross_margin) or a growth rate (rev_yoy).
    subject_change = series[-1][1] - series[-2][1]
    latest_period = series[-1][0]
    peer_changes = []
    for peer_series_dict in ctx.peer_metrics.values():
        peer_periods = sorted(
            (p for p in peer_series_dict if metric_id in peer_series_dict[p]), key=period_sort_key
        )
        if len(peer_periods) < 2 or peer_periods[-1] != latest_period:
            continue
        prev_period = peer_periods[-2]
        peer_changes.append(
            peer_series_dict[latest_period][metric_id] - peer_series_dict[prev_period][metric_id]
        )
    if direction in ("up", "down"):
        inputs["T1"] = {"subject_change": subject_change, "peer_changes": peer_changes, "direction": direction}

    # T5: seasonality. Only meaningful for a metric that is itself already a year-on-year growth rate
    # (its name ends in "_yoy" by this registry's own naming convention): the last 4 values of such a
    # series already ARE same-quarter year-on-year comparisons, by construction.
    if metric_id.endswith("_yoy") and direction in ("up", "down"):
        yoy_values = [v for _, v in series[-4:]]
        if len(yoy_values) >= 2:
            inputs["T5"] = {"yoy_same_quarter": yoy_values, "direction": direction}

    # T6: persistence. Uses the change-point Calculate already found for this metric (if any); without
    # one, the test is not applicable (t6_persist itself requires a cp_index to score persistence from,
    # the same honest degrade as prove.py's own persistence count for the strength score).
    anomaly = next((a for a in ctx.anomalies if a.metric_id == metric_id), None)
    if anomaly is not None and anomaly.changepoint_period is not None and direction in ("up", "down"):
        cp_idx = next((i for i, (p, _) in enumerate(series) if p == anomaly.changepoint_period), None)
        if cp_idx is not None:
            inputs["T6"] = {
                "series": [v for _, v in series], "cp_index": cp_idx, "direction": direction,
                "dated_event": False,
            }

    return inputs


def run_ach(main_hyps: list[Hypothesis], rivals_by_main: dict[str, list[Hypothesis]], ev_ids: list[str], cell) -> dict:
    hyp_ids = []
    for h in main_hyps:
        hyp_ids.append(h.hyp_id)
        hyp_ids.extend(r.hyp_id for r in rivals_by_main.get(h.hyp_id, []))
    return ach_module.ach_matrix(hyp_ids, ev_ids, cell)


async def run(
    ctx: RunContext,
    test_inputs: Optional[TestInputBuilder] = None,
    ev_ids: Optional[list[str]] = None,
    cell: Optional[Callable[[str, str], str]] = None,
) -> None:
    build_inputs = test_inputs or default_test_inputs
    ev_ids = ev_ids if ev_ids is not None else []
    cell = cell or (lambda e, h: "N")

    main_hyps = [h for h in ctx.hypotheses if h.is_rival_of is None]
    rivals_by_main = {h.hyp_id: [r for r in ctx.hypotheses if r.is_rival_of == h.hyp_id] for h in main_hyps}

    updated_main: list[Hypothesis] = []
    all_tests: list[TestResult] = []
    for h in main_hyps:
        inputs = build_inputs(ctx, h)
        results = run_core_tests(h, inputs)
        all_tests.extend(results)
        updated_main.append(apply_kill_rules(h, results))

    by_id = {h.hyp_id: h for h in updated_main}
    ctx.hypotheses = [
        by_id.get(h.hyp_id, h) if h.is_rival_of is None else h for h in ctx.hypotheses
    ]
    ctx.tests.extend(all_tests)

    surviving_main = [h for h in updated_main if h.status != "killed"]
    if surviving_main:
        ctx.ach = run_ach(surviving_main, rivals_by_main, ev_ids, cell)

    ctx.trace.append({
        "stage": "challenge",
        "hypotheses_tested": len(main_hyps),
        "killed": sum(1 for h in updated_main if h.status == "killed"),
        "downgraded": sum(1 for h in updated_main if h.status == "downgraded"),
        "survived": sum(1 for h in updated_main if h.status == "survived"),
    })
