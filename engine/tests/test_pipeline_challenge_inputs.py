"""Tests for pipeline/challenge.py's default_test_inputs (Wave 2 E10): building real T1/T5/T6 kwargs
from ctx.metrics/ctx.peer_metrics/ctx.anomalies once Calculate started producing real series.
"""
from next_signal.pipeline.challenge import default_test_inputs
from next_signal.schemas import Anomaly, Hypothesis, MetricValue, Prediction


def make_hyp(metric_id, direction="down"):
    return Hypothesis(
        hyp_id="H1", angle_id="P9", statement="x", mechanism="y",
        predictions=[Prediction(metric_id=metric_id, direction=direction, where_to_check="z")],
    )


class FakeCtx:
    def __init__(self):
        self.metrics = []
        self.peer_metrics = {}
        self.anomalies = []


def mv(metric_id, period, value):
    return MetricValue(metric_id=metric_id, period=period, value=value, unit="pct", inputs=[], formula="x")


def test_default_test_inputs_empty_without_predictions():
    ctx = FakeCtx()
    hyp = Hypothesis(hyp_id="H1", angle_id="P9", statement="x", mechanism="y")
    assert default_test_inputs(ctx, hyp) == {}


def test_default_test_inputs_empty_with_fewer_than_two_periods():
    ctx = FakeCtx()
    ctx.metrics = [mv("gross_margin", "Q1FY27", 0.58)]
    hyp = make_hyp("gross_margin")
    assert default_test_inputs(ctx, hyp) == {}


def test_default_test_inputs_t1_uses_qoq_change_for_subject_and_peers():
    ctx = FakeCtx()
    ctx.metrics = [mv("gross_margin", "Q4FY26", 0.62), mv("gross_margin", "Q1FY27", 0.58)]
    ctx.peer_metrics = {
        "SUNPHARMA": {"Q4FY26": {"gross_margin": 0.68}, "Q1FY27": {"gross_margin": 0.679}},
        "DRREDDY": {"Q4FY26": {"gross_margin": 0.70}, "Q1FY27": {"gross_margin": 0.699}},
    }
    hyp = make_hyp("gross_margin", direction="down")
    inputs = default_test_inputs(ctx, hyp)
    assert "T1" in inputs
    assert inputs["T1"]["subject_change"] == 0.58 - 0.62
    assert len(inputs["T1"]["peer_changes"]) == 2
    assert inputs["T1"]["direction"] == "down"


def test_default_test_inputs_t1_skips_a_peer_whose_latest_period_does_not_match():
    ctx = FakeCtx()
    ctx.metrics = [mv("gross_margin", "Q4FY26", 0.62), mv("gross_margin", "Q1FY27", 0.58)]
    ctx.peer_metrics = {
        "SUNPHARMA": {"Q4FY26": {"gross_margin": 0.68}, "Q1FY27": {"gross_margin": 0.679}},
        "STALEPEER": {"Q2FY26": {"gross_margin": 0.50}, "Q3FY26": {"gross_margin": 0.51}},  # behind
    }
    hyp = make_hyp("gross_margin")
    inputs = default_test_inputs(ctx, hyp)
    assert len(inputs["T1"]["peer_changes"]) == 1


def test_default_test_inputs_t5_only_for_a_yoy_metric():
    ctx = FakeCtx()
    ctx.metrics = [
        mv("rev_yoy", "Q4FY25", -0.10), mv("rev_yoy", "Q1FY26", -0.05),
        mv("rev_yoy", "Q4FY26", 0.07), mv("rev_yoy", "Q1FY27", 0.08),
    ]
    hyp = make_hyp("rev_yoy", direction="up")
    inputs = default_test_inputs(ctx, hyp)
    assert "T5" in inputs
    assert inputs["T5"]["yoy_same_quarter"] == [-0.10, -0.05, 0.07, 0.08]


def test_default_test_inputs_t5_absent_for_a_level_metric():
    ctx = FakeCtx()
    ctx.metrics = [mv("gross_margin", "Q4FY26", 0.62), mv("gross_margin", "Q1FY27", 0.58)]
    hyp = make_hyp("gross_margin")
    inputs = default_test_inputs(ctx, hyp)
    assert "T5" not in inputs


def test_default_test_inputs_t6_uses_the_real_changepoint():
    ctx = FakeCtx()
    ctx.metrics = [
        mv("gross_margin", "Q2FY26", 0.65), mv("gross_margin", "Q3FY26", 0.64),
        mv("gross_margin", "Q4FY26", 0.62), mv("gross_margin", "Q1FY27", 0.58),
    ]
    ctx.anomalies = [Anomaly(anomaly_id="a1", metric_id="gross_margin", description="x", changepoint_period="Q4FY26", score=0.5)]
    hyp = make_hyp("gross_margin", direction="down")
    inputs = default_test_inputs(ctx, hyp)
    assert "T6" in inputs
    assert inputs["T6"]["cp_index"] == 2  # Q4FY26 is index 2 in the sorted series
    assert inputs["T6"]["series"] == [0.65, 0.64, 0.62, 0.58]


def test_default_test_inputs_t6_absent_without_a_changepoint():
    ctx = FakeCtx()
    ctx.metrics = [mv("gross_margin", "Q4FY26", 0.62), mv("gross_margin", "Q1FY27", 0.58)]
    hyp = make_hyp("gross_margin")
    inputs = default_test_inputs(ctx, hyp)
    assert "T6" not in inputs


def test_default_test_inputs_t2_t3_t4_never_present():
    # None of these are wired yet (need dual-currency facts, a one-off flag, and segment-label tracking
    # respectively); they must stay absent, not guessed, so run_core_tests marks them not-applicable.
    ctx = FakeCtx()
    ctx.metrics = [mv("gross_margin", "Q4FY26", 0.62), mv("gross_margin", "Q1FY27", 0.58)]
    hyp = make_hyp("gross_margin")
    inputs = default_test_inputs(ctx, hyp)
    assert "T2" not in inputs
    assert "T3" not in inputs
    assert "T4" not in inputs
