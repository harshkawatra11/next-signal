import json
from pathlib import Path

from next_signal.schemas import Report
from next_signal.voice.segmenter import SentenceSegmenter
from next_signal.voice.tools import TOOL_SCHEMAS, build_tool_functions

FIXTURE = Path(__file__).parent / "fixtures" / "report_min.json"


def _report() -> Report:
    return Report.model_validate(json.loads(FIXTURE.read_text(encoding="utf-8")))


def test_tool_schemas_has_ten_tools():
    assert len(TOOL_SCHEMAS) == 10
    names = {t["function"]["name"] for t in TOOL_SCHEMAS}
    assert "get_discovery" in names
    assert "get_falsification" in names


def test_get_discovery_returns_sentence():
    tools = build_tool_functions(_report())
    result = tools["get_discovery"]()
    assert "North America revenue" in result.llm["sentence"]
    assert result.card is not None


def test_get_numbers_filters_by_name():
    tools = build_tool_functions(_report())
    result = tools["get_numbers"](name="North America")
    assert len(result.llm["numbers"]) == 1
    assert result.llm["numbers"][0]["label"] == "North America revenue"

    empty = tools["get_numbers"](name="nonexistent metric")
    assert empty.llm["numbers"] == []


def test_get_falsification_returns_threshold():
    tools = build_tool_functions(_report())
    result = tools["get_falsification"]()
    assert result.llm["threshold"] == 0.0
    assert result.llm["comparator"] == "<"


def test_get_discovery_handles_no_discovery_honestly():
    data = json.loads(FIXTURE.read_text(encoding="utf-8"))
    data["discovery"] = None
    report = Report.model_validate(data)
    tools = build_tool_functions(report)
    result = tools["get_discovery"]()
    assert result.llm["discovery"] is None
    assert "no discovery survived" in result.llm["note"]


def test_segmenter_splits_on_sentence_boundaries():
    seg = SentenceSegmenter()
    out = seg.feed("Revenue grew 14 percent. Margins held steady. ")
    assert out == ["Revenue grew 14 percent.", "Margins held steady."]


def test_segmenter_does_not_split_decimals():
    seg = SentenceSegmenter()
    out = seg.feed("The multiple is 2.5 times. ")
    assert out == ["The multiple is 2.5 times."]


def test_segmenter_does_not_split_abbreviations():
    seg = SentenceSegmenter()
    out = seg.feed("This was confirmed by Dr. Reddy in the call. ")
    assert out == ["This was confirmed by Dr. Reddy in the call."]


def test_segmenter_flush_returns_remainder():
    seg = SentenceSegmenter()
    seg.feed("An unfinished sentence without a terminator")
    assert seg.flush() == "An unfinished sentence without a terminator"
    assert seg.flush() == ""
