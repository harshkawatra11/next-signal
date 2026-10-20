import re

from next_signal.export.svg import ach_heat_svg, bars_svg, strength_bar_svg, timeline_svg

SVG_TAG = re.compile(r"^<svg[^>]*>.*</svg>$", re.S)


def test_timeline_svg_well_formed_and_marks_changepoint():
    points = [
        {"date_frac": 0.1, "label": "Regulator record", "kind": "regulator_us", "is_changepoint": False},
        {"date_frac": 0.5, "label": "Change emerges", "kind": "metric", "is_changepoint": True},
        {"date_frac": 0.9, "label": "First press coverage", "kind": "press", "is_changepoint": False},
    ]
    svg = timeline_svg(points)
    assert SVG_TAG.match(svg)
    assert "#C8102E" in svg  # the change-point gets the signal colour
    assert "Change emerges" in svg


def test_timeline_svg_empty_input_does_not_crash():
    assert "<svg" in timeline_svg([])


def test_bars_svg_highlights_largest_value_in_signal_colour():
    numbers = [{"label": "Killed", "value": 12}, {"label": "Survived", "value": 40}, {"label": "Downgraded", "value": 3}]
    svg = bars_svg(numbers)
    assert SVG_TAG.match(svg)
    assert svg.count("#C8102E") == 1  # exactly one bar (the largest) in signal red


def test_bars_svg_escapes_html_in_labels():
    svg = bars_svg([{"label": "<script>alert(1)</script>", "value": 1}])
    assert "<script>" not in svg
    assert "&lt;script&gt;" in svg


def test_ach_heat_svg_renders_all_cells():
    matrix = {
        "hypotheses": ["MAIN", "SECTOR"],
        "evidence": ["E1", "E2"],
        "cells": [["CC", "I"], ["C", "N"]],
    }
    svg = ach_heat_svg(matrix)
    assert SVG_TAG.match(svg)
    for glyph in ("CC", "I", "C", "N"):
        assert f">{glyph}<" in svg


def test_ach_heat_svg_empty_matrix_does_not_crash():
    assert "<svg" in ach_heat_svg({"hypotheses": [], "evidence": [], "cells": []})


def test_strength_bar_svg_marks_both_thresholds():
    breakdown = {"independence": 2, "reliability": 1.8, "corroboration": 1.5, "survival": 1.2, "persistence": 1.0, "total": 7.5, "label": "Strong"}
    svg = strength_bar_svg(breakdown)
    assert SVG_TAG.match(svg)
    assert "Moderate" in svg and "Strong" in svg
