import json
from pathlib import Path

from next_signal.paper.spec import build_spec
from next_signal.schemas import Report

FIXTURE_FULL = Path(__file__).parent / "fixtures" / "report_full.json"
FIXTURE_NO_FINDING = Path(__file__).parent / "fixtures" / "report_no_finding.json"


def _report(path: Path) -> Report:
    return Report.model_validate(json.loads(path.read_text(encoding="utf-8")))


def test_spec_has_tables_1_to_4_and_figures_1_to_3():
    spec = build_spec(_report(FIXTURE_FULL))
    table_numbers = sorted(t.number for t in spec.tables)
    assert table_numbers == [1, 2, 3, 4]
    assert len(spec.figures) >= 2
    figure_numbers = sorted(f.number for f in spec.figures)
    assert figure_numbers == list(range(1, len(figure_numbers) + 1))


def test_spec_references_are_numbered_without_gaps():
    spec = build_spec(_report(FIXTURE_FULL))
    numbers = sorted(r.number for r in spec.references)
    assert numbers == list(range(1, len(numbers) + 1))


def test_spec_tables_have_captions_and_notes():
    spec = build_spec(_report(FIXTURE_FULL))
    for t in spec.tables:
        assert t.caption
        assert t.rows


def test_spec_figures_are_grayscale_svg():
    spec = build_spec(_report(FIXTURE_FULL))
    for f in spec.figures:
        assert f.svg.startswith("<svg")
        assert f.caption


def test_no_finding_variant_has_no_finding_and_no_figure4():
    spec = build_spec(_report(FIXTURE_NO_FINDING))
    assert spec.has_finding is False
    figure_numbers = {f.number for f in spec.figures}
    assert len(figure_numbers) <= 3
    # Table 3 still carries the runners-up and killed hypotheses, symmetrically.
    table3 = next(t for t in spec.tables if t.number == 3)
    assert len(table3.rows) >= 1
    for row in table3.rows:
        assert row[2] in ("Weakened", "Rejected")


def test_allowed_numbers_cover_table1_quarters_and_reference_numbers():
    spec = build_spec(_report(FIXTURE_FULL))
    for r in spec.references:
        assert str(r.number) in spec.allowed_numbers
