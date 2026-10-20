from datetime import date

from next_signal.metrics.periods import (
    fiscal_label,
    period_sort_key,
    quarter_before,
    same_quarter_prior_year,
    ttm_quarters,
)


def test_fiscal_label_q3_matches_real_glenmark_filing():
    # Confirmed against a live NSE probe: the filing for 01-Oct-2024 to 31-Dec-2024 is Q3 FY25.
    assert fiscal_label(date(2024, 12, 31)) == "Q3FY25"


def test_fiscal_label_q1_crosses_calendar_year_into_next_fy():
    assert fiscal_label(date(2026, 6, 30)) == "Q1FY27"


def test_fiscal_label_q4_stays_in_the_calendar_year_it_ends():
    assert fiscal_label(date(2026, 3, 31)) == "Q4FY26"


def test_fiscal_label_q2():
    assert fiscal_label(date(2025, 9, 30)) == "Q2FY26"


def test_period_sort_key_orders_quarters_correctly():
    periods = ["Q1FY27", "Q4FY26", "Q2FY26", "Q3FY26", "Q1FY26"]
    assert sorted(periods, key=period_sort_key) == ["Q1FY26", "Q2FY26", "Q3FY26", "Q4FY26", "Q1FY27"]


def test_period_sort_key_mixed_annual_and_quarterly_never_raises():
    periods = ["Q1FY27", "FY26", "Q3FY26", "unrecognised"]
    # Must not raise TypeError from comparing int to str (the bug in calculate.py's ordered_periods).
    result = sorted(periods, key=period_sort_key)
    assert result[0] == "FY26"  # FY26 (quarter 0) sorts before any quarter of FY26
    assert result[-1] == "unrecognised"


def test_quarter_before_within_same_fy():
    assert quarter_before("Q3FY26") == "Q2FY26"


def test_quarter_before_crosses_fy_boundary():
    assert quarter_before("Q1FY27") == "Q4FY26"


def test_quarter_before_unrecognised_returns_none():
    assert quarter_before("FY26") is None


def test_same_quarter_prior_year():
    assert same_quarter_prior_year("Q1FY27") == "Q1FY26"


def test_ttm_quarters_returns_four_oldest_first():
    assert ttm_quarters("Q1FY27") == ["Q2FY26", "Q3FY26", "Q4FY26", "Q1FY27"]


def test_ttm_quarters_unrecognised_returns_none():
    assert ttm_quarters("FY26") is None
