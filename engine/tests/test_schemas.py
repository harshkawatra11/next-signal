import json
from pathlib import Path

from next_signal.schemas import Report

FIXTURE = Path(__file__).parent / "fixtures" / "report_min.json"


def test_report_round_trip():
    data = json.loads(FIXTURE.read_text(encoding="utf-8"))
    report = Report.model_validate(data)
    assert report.meta.symbol == "CIPLA"
    assert report.discovery is not None
    assert report.discovery.strength.label == "Strong"
    assert 3 <= len(report.discovery.why_it_matters) <= 5

    dumped = json.loads(report.model_dump_json())
    report2 = Report.model_validate(dumped)
    assert report2.meta.run_id == report.meta.run_id
    assert report2.discovery.sentence == report.discovery.sentence


def test_why_it_matters_bounds():
    data = json.loads(FIXTURE.read_text(encoding="utf-8"))
    data["discovery"]["why_it_matters"] = ["only one"]
    import pytest
    from pydantic import ValidationError

    with pytest.raises(ValidationError):
        Report.model_validate(data)
