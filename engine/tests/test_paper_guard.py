import json
from pathlib import Path

import pytest

from next_signal.paper.spec import build_spec
from next_signal.paper.writer import check_section
from next_signal.schemas import Report

FIXTURE_FULL = Path(__file__).parent / "fixtures" / "report_full.json"


@pytest.fixture
def spec():
    return build_spec(Report.model_validate(json.loads(FIXTURE_FULL.read_text(encoding="utf-8"))))


def test_flags_snake_case_identifier(spec):
    assert check_section("us_rev_usd_yoy rose sharply in the quarter.", spec)


def test_flags_comparison_operator(spec):
    assert check_section("The finding holds if x >= 0.04 for two quarters.", spec)


def test_flags_internal_id(spec):
    assert check_section("H1 survived every test applied to it.", spec)


def test_flags_software_talk(spec):
    assert check_section("the run read 14 documents in total.", spec)


def test_flags_number_not_in_allowed_set(spec):
    issues = check_section("Revenue grew by exactly 93827 per cent this quarter.", spec)
    assert any("not in the allowed set" in i for i in issues)


def test_flags_unknown_citation(spec):
    assert check_section("This is supported by the filing cited at [99].", spec)


def test_flags_dash_and_exclamation(spec):
    assert check_section("Revenue rose, this is remarkable!", spec)


def test_clean_sentence_from_spec_fact_passes(spec):
    fact = spec.facts["company"][0]
    text = fact.text + "."
    assert check_section(text, spec) == []
