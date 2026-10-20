from datetime import date

from bs4 import BeautifulSoup

from next_signal.sources.screener import clean_value, parse_page, parse_period, parse_section

PROFIT_LOSS_HTML = """
<table>
  <tr><th>Metric</th><th>Mar 2024</th><th>Mar 2025</th><th>TTM</th></tr>
  <tr><td>Sales +</td><td>21,234</td><td>23,456</td><td>24,000</td></tr>
  <tr><td>Expenses +</td><td>(18,000)</td><td>(19,500)</td><td>-</td></tr>
  <tr><td>Net Profit</td><td>1,200</td><td></td><td>1,500</td></tr>
</table>
"""

PAGE_HTML = f"""
<html><body>
<section id="profit-loss">{PROFIT_LOSS_HTML}</section>
<section id="ratios"><table><tr><th>Metric</th><th>Mar 2025</th></tr><tr><td>ROCE %</td><td>18.5%</td></tr></table></section>
</body></html>
"""


def test_parse_period_valid():
    assert parse_period("Jun 2026") == date(2026, 6, 30)
    assert parse_period("Mar 2025") == date(2025, 3, 31)


def test_parse_period_rejects_non_period_headers():
    assert parse_period("TTM") is None
    assert parse_period("") is None
    assert parse_period("Metric") is None


def test_clean_value_handles_commas_parens_and_percent():
    assert clean_value("21,234") == 21234.0
    assert clean_value("(18,000)") == -18000.0
    assert clean_value("18.5%") == 18.5
    assert clean_value("-") is None
    assert clean_value("") is None


def test_parse_section_builds_tidy_rows():
    table = BeautifulSoup(PROFIT_LOSS_HTML, "html.parser").find("table")
    rows = parse_section(table)
    sales_2025 = next(r for r in rows if r["item"] == "Sales" and r["period_end"] == date(2025, 3, 31))
    assert sales_2025["value"] == 23456.0
    expenses_2024 = next(r for r in rows if r["item"] == "Expenses" and r["period_end"] == date(2024, 3, 31))
    assert expenses_2024["value"] == -18000.0
    # "Net Profit" has a blank Mar 2025 cell: no row should be emitted for that (item, period) pair
    assert not any(r["item"] == "Net Profit" and r["period_end"] == date(2025, 3, 31) for r in rows)
    # the TTM column is not a period, so it must never appear
    assert all(r["period_end"] != "TTM" for r in rows)


def test_parse_section_strips_trailing_plus_from_item_labels():
    table = BeautifulSoup(PROFIT_LOSS_HTML, "html.parser").find("table")
    rows = parse_section(table)
    assert any(r["item"] == "Sales" for r in rows)
    assert not any(r["item"] == "Sales +" for r in rows)


def test_parse_page_returns_all_sections_with_missing_ones_empty():
    out = parse_page(PAGE_HTML)
    assert set(out.keys()) == {"quarters", "profit-loss", "balance-sheet", "cash-flow", "ratios", "shareholding"}
    assert out["balance-sheet"] == []
    assert out["cash-flow"] == []
    roce = next(r for r in out["ratios"] if r["item"] == "ROCE %")
    assert roce["value"] == 18.5
    assert len(out["profit-loss"]) > 0
