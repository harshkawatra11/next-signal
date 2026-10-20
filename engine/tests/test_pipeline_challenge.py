from datetime import date

from next_signal.pipeline.challenge import apply_kill_rules, default_test_inputs, run, run_core_tests
from next_signal.pipeline.context import RunContext
from next_signal.schemas import Hypothesis, Prediction


def make_hyp(hyp_id="h1"):
    return Hypothesis(
        hyp_id=hyp_id, angle_id="P2", statement="North America revenue fell for a company-specific reason.",
        mechanism="partner site compliance issue",
        predictions=[Prediction(metric_id="us_revenue", direction="down", where_to_check="presentation")],
    )


def test_run_core_tests_only_runs_supplied_test_ids():
    hyp = make_hyp()
    results = run_core_tests(hyp, {"T6": {"series": [10, 10, 10, 4, 3, 2], "cp_index": 3, "direction": "down", "dated_event": False}})
    assert len(results) == 1
    assert results[0].test_id == "T6"
    assert results[0].passed is True


def test_apply_kill_rules_kills_on_t6_failure():
    hyp = make_hyp()
    # direction is "down" but the series rises after the change-point: the opposite of the predicted move
    results = run_core_tests(hyp, {"T6": {"series": [5, 5, 5, 8, 9, 10], "cp_index": 3, "direction": "down", "dated_event": False}})
    updated = apply_kill_rules(hyp, results)
    assert updated.status == "killed"
    assert "quarters against an earlier average" in updated.kill_reason


def test_apply_kill_rules_kills_on_sector_wide_peer_test():
    hyp = make_hyp()
    results = run_core_tests(hyp, {"T1": {"subject_change": -5.0, "peer_changes": [-5.1, -4.9, -5.0], "direction": "down"}})
    updated = apply_kill_rules(hyp, results)
    assert updated.status == "killed"
    assert "sector-wide" in updated.kill_reason


def test_apply_kill_rules_kills_on_too_few_independent_origins():
    hyp = make_hyp()
    updated = apply_kill_rules(hyp, [], independent_origins=1)
    assert updated.status == "killed"
    assert "1 independent origin" in updated.kill_reason


def test_apply_kill_rules_downgrades_on_fx_failure_without_killing():
    hyp = make_hyp()
    results = run_core_tests(hyp, {"T2": {"inr_yoy": -0.10, "usd_yoy": 0.02, "applies": True, "direction": "down"}})
    updated = apply_kill_rules(hyp, results, independent_origins=3)
    assert updated.status == "downgraded"
    assert updated.kill_reason is None


def test_apply_kill_rules_survives_with_no_failing_tests():
    hyp = make_hyp()
    results = run_core_tests(hyp, {
        "T1": {"subject_change": -8.0, "peer_changes": [1.0, 0.5, -0.2], "direction": "down"},
        "T6": {"series": [10, 10, 10, 6, 5, 4], "cp_index": 3, "direction": "down", "dated_event": False},
    })
    updated = apply_kill_rules(hyp, results, independent_origins=3)
    assert updated.status == "survived"


def test_default_test_inputs_is_empty_stub():
    ctx = RunContext(run_id="r1", symbol="CIPLA", company="Cipla Limited", sub_industry="pharma", as_of=date(2026, 10, 15))
    assert default_test_inputs(ctx, make_hyp()) == {}


async def test_run_with_no_data_leaves_hypotheses_surviving_and_builds_ach():
    ctx = RunContext(run_id="r2", symbol="CIPLA", company="Cipla Limited", sub_industry="pharma", as_of=date(2026, 10, 15))
    main = make_hyp("h1")
    from next_signal.pipeline.reason import generate_rivals
    ctx.hypotheses = [main] + generate_rivals(main, ctx.company)
    await run(ctx)
    updated_main = next(h for h in ctx.hypotheses if h.hyp_id == "h1")
    assert updated_main.status == "survived"  # no test inputs supplied, nothing fails, nothing kills
    assert ctx.ach["hypotheses"][0] == "h1"
    assert len(ctx.ach["hypotheses"]) == 6  # main + 5 rivals
    assert ctx.trace[-1]["stage"] == "challenge"
    assert ctx.trace[-1]["survived"] == 1


async def test_run_kills_hypothesis_via_injected_test_inputs():
    ctx = RunContext(run_id="r3", symbol="CIPLA", company="Cipla Limited", sub_industry="pharma", as_of=date(2026, 10, 15))
    main = make_hyp("h1")
    ctx.hypotheses = [main]

    def inputs(c, h):
        return {"T6": {"series": [5, 5, 5, 8, 9, 10], "cp_index": 3, "direction": "down", "dated_event": False}}

    await run(ctx, test_inputs=inputs)
    updated_main = next(h for h in ctx.hypotheses if h.hyp_id == "h1")
    assert updated_main.status == "killed"
    assert ctx.ach == {}  # no surviving main hypothesis, no ACH matrix built
    assert ctx.trace[-1]["killed"] == 1
