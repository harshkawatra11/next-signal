from next_signal.sources.ratings import (
    extract_rating_action,
    identify_action,
    identify_agency,
    identify_outlook,
)

CRISIL_TEXT = (
    "CRISIL Ratings has reaffirmed its 'CRISIL AA+/Stable' rating on the bank facilities of Cipla "
    "Limited. The rating continues to reflect the company's strong market position in the domestic "
    "pharmaceutical industry and robust financial risk profile."
)

ICRA_TEXT = (
    "ICRA has revised the outlook on the long-term rating to Positive from Stable and reaffirmed the "
    "rating at [ICRA]AA for the long-term bank facilities, factoring in the improved profitability."
)

CARE_DOWNGRADE_TEXT = (
    "CARE Ratings has downgraded the rating on the long-term bank facilities to CARE A+ from CARE AA- "
    "with a Negative outlook, following a review of the company's debt metrics."
)

NO_MATCH_TEXT = "This filing does not mention any rating agency at all."


def test_identify_agency_variants():
    assert identify_agency(CRISIL_TEXT) == "CRISIL"
    assert identify_agency(ICRA_TEXT) == "ICRA"
    assert identify_agency(CARE_DOWNGRADE_TEXT) == "CARE"
    assert identify_agency(NO_MATCH_TEXT) is None


def test_identify_action_variants():
    assert identify_action(CRISIL_TEXT) == "reaffirmed"
    assert identify_action(CARE_DOWNGRADE_TEXT) == "downgraded"


def test_identify_outlook_variants():
    assert identify_outlook(CRISIL_TEXT) == "Stable"
    assert identify_outlook(CARE_DOWNGRADE_TEXT) == "Negative"


def test_extract_rating_action_full_record():
    result = extract_rating_action(CRISIL_TEXT)
    assert result["agency"] == "CRISIL"
    assert result["action"] == "reaffirmed"
    assert result["outlook"] == "Stable"
    assert result["excerpt"].startswith("CRISIL Ratings")


def test_extract_rating_action_outlook_revision_case():
    result = extract_rating_action(ICRA_TEXT)
    assert result["agency"] == "ICRA"
    assert result["action"] == "revised"
    # the first outlook word in the text is "Positive" (the direction of the revision)
    assert result["outlook"] == "Positive"


def test_extract_rating_action_no_agency_found():
    result = extract_rating_action(NO_MATCH_TEXT)
    assert result == {"agency": None, "action": None, "outlook": None, "excerpt": None}
