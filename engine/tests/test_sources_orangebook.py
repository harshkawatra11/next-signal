from datetime import date

from next_signal.sources.orangebook import (
    EXCLUSIVITY_FIELDS,
    PATENT_FIELDS,
    PRODUCTS_FIELDS,
    appl_nos_for,
    exclusivities_expiring,
    matches_stem,
    months_from,
    parse_delimited,
    patents_expiring,
    products_for,
)

PRODUCTS_TEXT = (
    "Ingredient~DF;Route~Trade_Name~Applicant~Strength~Appl_Type~Appl_No~Product_No~TE_Code~"
    "Approval_Date~RLD~RS~Type~Applicant_Full_Name\n"
    "LENALIDOMIDE~CAPSULE;ORAL~REVLIMID~CELGENE~10MG~N~021880~001~~Jun 29, 2005~Yes~Yes~RX~CELGENE CORP\n"
    "LANREOTIDE~INJECTABLE;SUBCUTANEOUS~SOMATULINE~CIPLA~60MG~A~204162~001~AB~Mar 15, 2018~No~No~RX~CIPLA LTD\n"
)

PATENT_TEXT = (
    "Appl_Type~Appl_No~Product_No~Patent_No~Patent_Expire_Date_Text~Drug_Substance_Flag~Drug_Product_Flag~"
    "Patent_Use_Code~Delist_Flag~Submission_Date\n"
    "A~204162~001~9876543~Dec 27, 2027~Y~N~U-1234~N~Jan 01, 2018\n"
    "A~204162~001~1112223~Jan 05, 2024~N~Y~~N~Jan 01, 2018\n"
)

EXCLUSIVITY_TEXT = (
    "Appl_Type~Appl_No~Product_No~Exclusivity_Code~Exclusivity_Date\n"
    "A~204162~001~NCE~Aug 15, 2027\n"
)


def test_parse_delimited_products():
    rows = parse_delimited(PRODUCTS_TEXT, PRODUCTS_FIELDS)
    assert len(rows) == 2
    assert rows[1]["Applicant_Full_Name"] == "CIPLA LTD"
    assert rows[1]["Appl_No"] == "204162"


def test_matches_stem_fuzzy():
    assert matches_stem("CIPLA LTD", ["Cipla"])
    assert not matches_stem("CELGENE CORP", ["Cipla"])


def test_products_for_filters_by_stem():
    rows = parse_delimited(PRODUCTS_TEXT, PRODUCTS_FIELDS)
    cipla_rows = products_for(rows, ["Cipla"])
    assert len(cipla_rows) == 1
    assert cipla_rows[0]["Trade_Name"] == "SOMATULINE"


def test_appl_nos_for():
    rows = parse_delimited(PRODUCTS_TEXT, PRODUCTS_FIELDS)
    cipla_rows = products_for(rows, ["Cipla"])
    assert appl_nos_for(cipla_rows) == {"204162"}


def test_months_from_handles_year_rollover():
    assert months_from(date(2026, 10, 15), 24) == date(2028, 10, 15)
    assert months_from(date(2026, 11, 30), 3) == date(2027, 2, 28)  # Feb 2027 is not a leap year


def test_months_from_leap_year():
    assert months_from(date(2024, 1, 31), 1) == date(2024, 2, 29)


def test_patents_expiring_filters_by_appl_no_and_window():
    rows = parse_delimited(PATENT_TEXT, PATENT_FIELDS)
    expiring = patents_expiring(rows, {"204162"}, as_of=date(2026, 10, 15), months=24)
    # Dec 2027 patent is within 24 months of Oct 2026; Jan 2024 patent already expired before as_of
    assert len(expiring) == 1
    assert expiring[0]["Patent_No"] == "9876543"
    assert expiring[0]["expire_date"] == date(2027, 12, 27)


def test_patents_expiring_excludes_other_applications():
    rows = parse_delimited(PATENT_TEXT, PATENT_FIELDS)
    assert patents_expiring(rows, {"999999"}, as_of=date(2026, 10, 15)) == []


def test_exclusivities_expiring_within_window():
    rows = parse_delimited(EXCLUSIVITY_TEXT, EXCLUSIVITY_FIELDS)
    expiring = exclusivities_expiring(rows, {"204162"}, as_of=date(2026, 10, 15), months=24)
    assert len(expiring) == 1
    assert expiring[0]["Exclusivity_Code"] == "NCE"


def test_exclusivities_expiring_outside_window_excluded():
    rows = parse_delimited(EXCLUSIVITY_TEXT, EXCLUSIVITY_FIELDS)
    assert exclusivities_expiring(rows, {"204162"}, as_of=date(2026, 10, 15), months=3) == []
