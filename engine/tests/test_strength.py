from next_signal.grading.strength import strength


def test_worked_example_moderate():
    """The brief's own worked example: 'Moderate: consistent across several primary sources, but partly
    explained by sector-wide conditions.'"""
    s = strength(
        independent_origins=3, grades=["A", "A", "B"], corroborated_numbers=3, total_numbers=4,
        tests_passed=5, tests_applicable=7, persistent_periods=3,
        unresolved_contradictions=0, sector_partial=True, single_document=False,
    )
    assert s.label == "Moderate"
    assert s.total < 7


def test_single_document_forces_weak():
    s = strength(
        independent_origins=3, grades=["A", "A", "A"], corroborated_numbers=4, total_numbers=4,
        tests_passed=7, tests_applicable=7, persistent_periods=3,
        unresolved_contradictions=0, sector_partial=False, single_document=True,
    )
    assert s.label == "Weak"


def test_strong_all_pass_four_origins():
    s = strength(
        independent_origins=4, grades=["A", "A", "A", "B"], corroborated_numbers=4, total_numbers=4,
        tests_passed=8, tests_applicable=8, persistent_periods=4,
        unresolved_contradictions=0, sector_partial=False, single_document=False,
    )
    assert s.label == "Strong"
    assert s.total >= 7


def test_one_unresolved_contradiction_applies_penalty():
    # At the maximum possible pre-penalty score (9.0), a single -2 penalty lands exactly at the Strong
    # boundary (7.0 >= 7), which is correct per the formula: one contradiction alone does not have to
    # sink an otherwise-maximal discovery below Strong. Two contradictions should.
    s1 = strength(
        independent_origins=3, grades=["A", "A", "A"], corroborated_numbers=4, total_numbers=4,
        tests_passed=7, tests_applicable=7, persistent_periods=3,
        unresolved_contradictions=1, sector_partial=False, single_document=False,
    )
    assert s1.penalties == -2.0
    assert s1.total == 7.0
    assert s1.label == "Strong"

    s2 = strength(
        independent_origins=3, grades=["A", "A", "A"], corroborated_numbers=4, total_numbers=4,
        tests_passed=7, tests_applicable=7, persistent_periods=3,
        unresolved_contradictions=2, sector_partial=False, single_document=False,
    )
    assert s2.total < s1.total
    assert s2.label != "Strong"


def test_zero_origins_is_weak():
    s = strength(
        independent_origins=0, grades=["C"], corroborated_numbers=0, total_numbers=1,
        tests_passed=1, tests_applicable=4, persistent_periods=0,
        unresolved_contradictions=0, sector_partial=False, single_document=False,
    )
    assert s.label == "Weak"


def test_reasoning_always_present():
    s = strength(2, ["B", "B"], 2, 2, 4, 6, 2, 0, False, False)
    assert len(s.reasoning) >= 5
