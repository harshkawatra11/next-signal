from next_signal.playbooks.angles import DIAGNOSTICS, GENERIC, HOSPITAL, PHARMA, PLAYBOOKS
from next_signal.playbooks.select import score_angle, select_angles


def test_all_playbooks_have_angles():
    for name, angles in PLAYBOOKS.items():
        assert len(angles) >= 3, f"{name} should have at least 3 angles"


def test_pharma_has_ten_angles_matching_brief_track_d():
    assert len(PHARMA) == 10
    ids = {a.angle_id for a in PHARMA}
    assert "P2" in ids  # the regulatory-before-mainstream angle, the brief's own Track D question


def test_hospital_has_six_angles():
    assert len(HOSPITAL) == 6
    ids = {a.angle_id for a in HOSPITAL}
    assert "H1" in ids  # announced vs commissioned beds


def test_score_angle_bounds_and_formula():
    a = PHARMA[0]
    s = score_angle(a, data_availability=1.0, anomaly_signal=1.0, novelty_prior=1.0)
    assert s.score == 1.0
    s2 = score_angle(a, data_availability=0.0, anomaly_signal=0.0, novelty_prior=0.0)
    assert s2.score == 0.0


def test_score_angle_clamps_out_of_range_inputs():
    a = PHARMA[0]
    s = score_angle(a, data_availability=1.5, anomaly_signal=-0.5, novelty_prior=0.5)
    assert 0.0 <= s.score <= 1.0


def test_select_angles_always_includes_anchor_when_available():
    # P2 scores lowest on purpose; it should still be forced in because it's the anchor angle
    scores = {}
    for a in PHARMA:
        da, anom, nov = (0.9, 0.9, 0.9) if a.angle_id != "P2" else (0.4, 0.1, 0.1)
        scores[a.angle_id] = score_angle(a, da, anom, nov)
    chosen = select_angles("pharma", list(PHARMA), scores, top_n=4)
    chosen_ids = {c.angle_id for c in chosen}
    assert "P2" in chosen_ids
    assert len(chosen) == 4


def test_select_angles_skips_anchor_when_data_too_thin():
    scores = {}
    for a in PHARMA:
        da, anom, nov = (0.9, 0.9, 0.9) if a.angle_id != "P2" else (0.05, 0.0, 0.0)  # below anchor_floor
        scores[a.angle_id] = score_angle(a, da, anom, nov)
    chosen = select_angles("pharma", list(PHARMA), scores, top_n=4, anchor_floor=0.3)
    chosen_ids = {c.angle_id for c in chosen}
    assert "P2" not in chosen_ids


def test_select_angles_generic_has_no_forced_anchor():
    scores = {a.angle_id: score_angle(a, 0.5, 0.5, 0.5) for a in GENERIC}
    chosen = select_angles("generic", list(GENERIC), scores, top_n=3)
    assert len(chosen) == 3
