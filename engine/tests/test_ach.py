from next_signal.grading.ach import ach_matrix, counterargument, main_holds


def test_ach_main_hypothesis_survives_when_consistent():
    hyps = ["MAIN", "SECTOR", "FX"]
    evs = ["E1", "E2", "E3"]
    table = {
        ("E1", "MAIN"): "CC", ("E1", "SECTOR"): "I", ("E1", "FX"): "N",
        ("E2", "MAIN"): "C", ("E2", "SECTOR"): "N", ("E2", "FX"): "I",
        ("E3", "MAIN"): "CC", ("E3", "SECTOR"): "II", ("E3", "FX"): "N",
    }
    m = ach_matrix(hyps, evs, lambda e, h: table[(e, h)])
    assert main_holds(m, "MAIN")
    rival = counterargument(m, "MAIN")
    assert rival in ("SECTOR", "FX")


def test_ach_counterargument_is_second_best():
    hyps = ["MAIN", "RIVAL_WEAK", "RIVAL_STRONG"]
    evs = ["E1", "E2"]
    table = {
        ("E1", "MAIN"): "CC", ("E1", "RIVAL_WEAK"): "II", ("E1", "RIVAL_STRONG"): "C",
        ("E2", "MAIN"): "CC", ("E2", "RIVAL_WEAK"): "II", ("E2", "RIVAL_STRONG"): "N",
    }
    m = ach_matrix(hyps, evs, lambda e, h: table[(e, h)])
    assert counterargument(m, "MAIN") == "RIVAL_STRONG"


def test_ach_empty_matrix_handles_gracefully():
    m = ach_matrix([], [], lambda e, h: "N")
    assert counterargument(m, "MAIN") is None
