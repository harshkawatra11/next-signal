from next_signal.grading.falsify import (
    t1_peer,
    t2_fx,
    t3_one_off,
    t4_reclassification,
    t5_season,
    t6_persist,
)
from next_signal.schemas import Hypothesis

H = Hypothesis(hyp_id="H1", angle_id="P2", statement="x", mechanism="y")


def test_t1_peer_not_applicable_with_few_peers():
    r = t1_peer(H, 0.1, [0.05, 0.06], "up")
    assert r.applicable is False


def test_t1_peer_passes_when_subject_diverges_from_peers():
    r = t1_peer(H, 0.20, [0.01, 0.02, 0.015, 0.0], "up")
    assert r.applicable is True
    assert r.passed is True


def test_t1_peer_fails_when_sector_wide():
    r = t1_peer(H, 0.20, [0.19, 0.21, 0.20, 0.18], "up")
    assert r.passed is False  # everyone moved together: sector story, not company-specific


def test_t2_fx_not_applicable_when_flagged_false():
    r = t2_fx(H, 0.08, 0.02, applies=False, direction="up")
    assert r.applicable is False


def test_t2_fx_passes_when_usd_terms_confirm():
    r = t2_fx(H, 0.08, 0.06, applies=True, direction="up")
    assert r.applicable is True and r.passed is True


def test_t2_fx_fails_when_usd_terms_contradict():
    r = t2_fx(H, 0.08, -0.01, applies=True, direction="up")
    assert r.passed is False


def test_t3_one_off_not_applicable_without_disclosed_item():
    r = t3_one_off(H, 100.0, 100.0, 90.0, "up", has_disclosed_one_off=False)
    assert r.applicable is False


def test_t3_one_off_passes_when_change_survives_exclusion():
    r = t3_one_off(H, 120.0, 105.0, 90.0, "up", has_disclosed_one_off=True)
    assert r.applicable is True and r.passed is True


def test_t3_one_off_fails_when_change_disappears_after_exclusion():
    r = t3_one_off(H, 120.0, 90.0, 90.0, "up", has_disclosed_one_off=True)
    assert r.passed is False


def test_t4_reclassification_not_applicable_when_labels_stable():
    r = t4_reclassification(H, labels_changed=False, restated_available=False, change_on_restated=None, direction="up")
    assert r.applicable is False


def test_t4_reclassification_fails_without_restated_data():
    r = t4_reclassification(H, labels_changed=True, restated_available=False, change_on_restated=None, direction="up")
    assert r.applicable is True and r.passed is False


def test_t4_reclassification_passes_with_confirming_restated_data():
    r = t4_reclassification(H, labels_changed=True, restated_available=True, change_on_restated=5.0, direction="up")
    assert r.passed is True


def test_t5_season_not_applicable_for_annual():
    r = t5_season(H, [0.1], "up")
    assert r.applicable is False


def test_t6_persist_dated_event_always_passes():
    r = t6_persist(H, [], None, "up", dated_event=True)
    assert r.passed is True


def test_t6_persist_fails_without_persistence():
    r = t6_persist(H, [10, 10, 10, 10], None, "up", dated_event=False)
    assert r.passed is False
