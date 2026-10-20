import json
from pathlib import Path

import pytest

from next_signal.paper import fallback
from next_signal.paper.spec import build_spec
from next_signal.paper.writer import check_section
from next_signal.schemas import Report

FIXTURE_FULL = Path(__file__).parent / "fixtures" / "report_full.json"
FIXTURE_NO_FINDING = Path(__file__).parent / "fixtures" / "report_no_finding.json"


@pytest.fixture(params=[FIXTURE_FULL, FIXTURE_NO_FINDING])
def spec(request):
    return build_spec(Report.model_validate(json.loads(request.param.read_text(encoding="utf-8"))))


def test_fallback_title_has_no_issues(spec):
    assert spec.has_finding in (True, False)
    assert fallback.title(spec)


def test_fallback_abstract_passes_guard(spec):
    ab = fallback.abstract(spec)
    assert check_section(ab, spec, is_abstract=True) == []


@pytest.mark.parametrize("fn_name", [
    "introduction", "company_and_data", "findings", "explanations", "outlook", "conclusion",
])
def test_fallback_section_paragraphs_pass_guard(spec, fn_name):
    fn = getattr(fallback, fn_name)
    for para in fn(spec):
        assert check_section(para, spec) == []
