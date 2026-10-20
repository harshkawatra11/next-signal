from datetime import date

from next_signal.sources.fda_web import (
    build_warning_letter_query,
    filter_import_alert_by_stem,
    is_warning_letter_url,
    parse_import_alert_page,
    parse_warning_letter_page,
)

WARNING_LETTER_HTML = """
<html><body>
<p>Issue Date: February 10, 2026</p>
<p>Issued to: Cipla Limited</p>
<p>FEI Number: 3003456789</p>
<p>This letter addresses violations of 21 CFR 211.100 and 21 CFR 211.192(a) found during an inspection.</p>
<p>During the inspection, your firm's quality unit failed to adequately investigate deviations.</p>
</body></html>
"""

IMPORT_ALERT_HTML = """
<html><body>
<table>
<tr><th>Firm Name</th><th>Firm Address</th><th>Country</th><th>Date Published</th></tr>
<tr><td>Cipla Limited</td><td>Plot 1, Industrial Area</td><td>India</td><td>03/15/2026</td></tr>
<tr><td>Other Pharma Co</td><td>Some Address</td><td>India</td><td>01/02/2025</td></tr>
</table>
</body></html>
"""


def test_is_warning_letter_url():
    assert is_warning_letter_url(
        "https://www.fda.gov/inspections-compliance-enforcement-and-criminal-investigations/warning-letters/cipla-123"
    )
    assert not is_warning_letter_url("https://www.fda.gov/drugs/some-other-page")


def test_build_warning_letter_query():
    q = build_warning_letter_query("Cipla")
    assert q == 'site:fda.gov "warning letter" "Cipla"'


def test_parse_warning_letter_page_extracts_fields():
    parsed = parse_warning_letter_page(WARNING_LETTER_HTML)
    assert parsed["issue_date"] == date(2026, 2, 10)
    assert parsed["firm"] == "Cipla Limited"
    assert parsed["fei"] == "3003456789"
    assert "21 CFR 211.100" in parsed["cfr_citations"]
    assert "21 CFR 211.192(a)" in parsed["cfr_citations"]
    assert len(parsed["excerpt"]) <= 600


def test_parse_warning_letter_page_missing_fields_are_none():
    parsed = parse_warning_letter_page("<html><body><p>Nothing useful here.</p></body></html>")
    assert parsed["issue_date"] is None
    assert parsed["firm"] is None
    assert parsed["fei"] is None
    assert parsed["cfr_citations"] == []


def test_parse_import_alert_page_extracts_rows():
    rows = parse_import_alert_page(IMPORT_ALERT_HTML)
    assert len(rows) == 2
    assert rows[0]["firm_name"] == "Cipla Limited"
    assert rows[0]["country"] == "India"
    assert rows[0]["date_published"] == date(2026, 3, 15)


def test_parse_import_alert_page_empty_without_table():
    assert parse_import_alert_page("<html><body>no table</body></html>") == []


def test_filter_import_alert_by_stem():
    rows = parse_import_alert_page(IMPORT_ALERT_HTML)
    filtered = filter_import_alert_by_stem(rows, ["Cipla"])
    assert len(filtered) == 1
    assert filtered[0]["firm_name"] == "Cipla Limited"
