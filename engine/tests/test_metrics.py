import pytest

from next_signal.metrics.changepoint import best_changepoint, changepoints, cp_strength
from next_signal.metrics.eventstudy import event_study
from next_signal.metrics.peers import classical_z, robust_z


def test_changepoint_detects_step():
    y = [10, 10, 10, 10, 20, 20, 20, 20]
    idxs = changepoints(y)
    assert idxs, "expected at least one change-point in an obvious step series"
    assert any(3 <= i <= 5 for i in idxs)


def test_changepoint_strength_is_scale_invariant_for_same_shape():
    """cp_strength is a Cohen's-d-style effect size: a purely proportional rescaling of the same step
    shape should NOT change the score, since both the mean jump and the spread scale together."""
    y_small = [10, 10, 10, 10, 11, 11, 11, 11]
    y_big = [10, 10, 10, 10, 40, 40, 40, 40]  # same shape, 40x the jump size
    idx_small, s_small = best_changepoint(y_small)
    idx_big, s_big = best_changepoint(y_big)
    assert idx_big is not None and idx_small is not None
    assert idx_big == idx_small
    assert s_big == pytest.approx(s_small, rel=1e-9)


def test_changepoint_no_signal_on_flat_series():
    y = [10.0] * 10
    assert changepoints(y) == []


def test_cp_strength_bounds():
    y = [1, 1, 1, 1, 1000, 1000, 1000, 1000]
    s = cp_strength(y, 4)
    assert 0.0 <= s <= 1.0


def test_robust_z_peer_outlier():
    peers = [10.0, 11.0, 9.5, 10.5]
    z = robust_z(50.0, peers)
    assert z is not None and z > 3


def test_robust_z_needs_three_peers():
    assert robust_z(10.0, [1.0, 2.0]) is None


def test_classical_z_sign():
    peers = [10.0, 12.0, 11.0, 9.0]
    z = classical_z(5.0, peers)
    assert z is not None and z < 0


def test_event_study_detects_abnormal_return():
    import random

    random.seed(42)
    n = 300
    market = [100.0]
    for _ in range(n):
        market.append(market[-1] * (1 + random.gauss(0, 0.01)))
    stock = [100.0]
    for i in range(1, n + 1):
        drift = 0.0
        if i == 280:  # event day: a real abnormal jump
            drift = 0.08
        ret = (market[i] / market[i - 1] - 1) * 1.0 + drift
        stock.append(stock[-1] * (1 + ret))

    result = event_study(stock, market, event_index=280, window=(-1, 1))
    assert result is not None
    assert result.car > 0.03
    assert abs(result.t_stat) > 1.5
