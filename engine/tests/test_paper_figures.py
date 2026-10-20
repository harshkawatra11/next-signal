from datetime import date

from next_signal.paper import figures


def _assert_svg_grayscale(svg: str) -> None:
    assert svg.startswith("<svg")
    assert "#c8102e" not in svg.lower()
    assert "#1f77b4" not in svg.lower()


def test_revenue_ebitda_is_grayscale_svg():
    svg = figures.revenue_ebitda(["Q1FY26", "Q2FY26"], [100.0, 110.0], [20.0, 22.0])
    _assert_svg_grayscale(svg)


def test_metric_vs_peers_is_grayscale_svg():
    svg = figures.metric_vs_peers(
        ["Q1FY26", "Q2FY26", "Q3FY26"], [0.1, 0.12, 0.05], [0.08, 0.09, 0.09],
        [0.05, 0.06, 0.06], [0.11, 0.12, 0.12], "Cipla Limited", "Per cent",
        2, "Change point: Q3FY26", pct=True,
    )
    _assert_svg_grayscale(svg)


def test_peer_bars_is_grayscale_svg():
    svg = figures.peer_bars(["Cipla", "Sun Pharma", "Lupin"], [0.42, 0.40, 0.38], 0, "Gross margin", pct=True)
    _assert_svg_grayscale(svg)


def test_event_timeline_is_grayscale_svg():
    svg = figures.event_timeline(
        [date(2026, 1, 15), date(2026, 4, 1)], ["Q3 FY26 results", "Analyst day"],
        changepoint_date=date(2026, 4, 1),
    )
    _assert_svg_grayscale(svg)
