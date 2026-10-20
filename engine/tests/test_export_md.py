import json
from pathlib import Path

import pytest

from next_signal.export.md import render_markdown
from next_signal.schemas import Report

FIXTURE = Path(__file__).parent / "fixtures" / "report_min.json"

REQUIRED_HEADINGS = [
    "## The Discovery", "## Why It Matters", "## Evidence", "## Timeline", "## Numbers",
    "## Counterargument", "## Falsification Condition", "## Evidence Strength",
]


@pytest.fixture
def report() -> Report:
    return Report.model_validate(json.loads(FIXTURE.read_text(encoding="utf-8")))


def test_markdown_contains_all_eight_brief_sections(report):
    md = render_markdown(report)
    for heading in REQUIRED_HEADINGS:
        assert heading in md, f"missing section: {heading}"


def test_markdown_has_no_dashes_or_exclamations_outside_quotes(report):
    md = render_markdown(report)
    assert "—" not in md and "–" not in md


def test_markdown_includes_disclaimer(report):
    md = render_markdown(report)
    assert "Not investment advice" in md


def test_markdown_evidence_table_has_clickable_links(report):
    md = render_markdown(report)
    assert "[source](https://" in md


def test_markdown_no_discovery_renders_honest_message():
    data = json.loads(FIXTURE.read_text(encoding="utf-8"))
    data["discovery"] = None
    report = Report.model_validate(data)
    md = render_markdown(report)
    assert "No discovery survived" in md
    # the eight brief-required headings should NOT be falsely claimed present when there is no discovery
    assert "## The Discovery" not in md
