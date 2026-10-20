from datetime import date

from next_signal.pipeline.context import RunContext
from next_signal.pipeline.discover import (
    angle_anomaly_signal,
    angle_data_availability,
    angle_novelty_prior,
    run,
)


def test_angle_data_availability_full_coverage():
    series = {"m1": [1, 2, 3, 4, 5, 6], "m2": [1, 2, 3, 4, 5, 6, 7]}
    assert angle_data_availability(("m1", "m2"), series) == 1.0


def test_angle_data_availability_partial_coverage():
    series = {"m1": [1, 2, 3, 4, 5, 6]}  # m2 missing entirely
    assert angle_data_availability(("m1", "m2"), series) == 0.5


def test_angle_data_availability_short_series_does_not_count():
    series = {"m1": [1, 2, 3]}  # fewer than 6 periods
    assert angle_data_availability(("m1",), series) == 0.0


def test_angle_data_availability_no_metrics_is_neutral():
    assert angle_data_availability((), {}) == 0.5


def test_angle_novelty_prior_bounds():
    assert angle_novelty_prior("P1", mainstream_hits_90d=0) == 1.0
    assert angle_novelty_prior("P1", mainstream_hits_90d=20) == 0.0
    assert angle_novelty_prior("P1", mainstream_hits_90d=40) == 0.0  # clamped, not negative


def test_angle_anomaly_signal_is_zero_without_computed_data():
    assert angle_anomaly_signal(("m1",), {}) == 0.0


async def test_discover_run_populates_angles_considered_for_pharma():
    ctx = RunContext(run_id="r1", symbol="CIPLA", company="Cipla Limited", sub_industry="pharma", as_of=date(2026, 10, 15))
    await run(ctx)
    assert len(ctx.angles_considered) == 10  # all 10 pharma angles scored
    chosen = [a for a in ctx.angles_considered if a["chosen"]]
    assert len(chosen) == 4
    assert any(a["angle_id"] == "P2" for a in chosen)  # anchor angle forced in
    assert ctx.trace[-1]["stage"] == "discover"


async def test_discover_run_falls_back_to_generic_for_unknown_playbook():
    ctx = RunContext(run_id="r2", symbol="XYZ", company="Some Company", sub_industry="not_a_real_playbook", as_of=date(2026, 10, 15))
    await run(ctx)
    assert len(ctx.angles_considered) == 6  # generic playbook has 6 angles
