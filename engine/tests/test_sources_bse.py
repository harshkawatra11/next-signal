from datetime import datetime

from next_signal.sources.bse import build_params, cross_exchange_consistency, parse_announcements

PAYLOAD = {
    "Table": [
        {"NEWSSUB": "Outcome of Board Meeting - Financial Results", "CATEGORYNAME": "Result",
         "NEWS_DT": "2026-07-20T18:05:00", "ATTACHMENTNAME": "results.pdf", "SCRIP_CD": "500087"},
        {"NEWSSUB": "Investor Presentation", "CATEGORYNAME": "Presentation",
         "NEWS_DT": "2026-07-20T18:10:00", "ATTACHMENTNAME": "presentation.pdf", "SCRIP_CD": "500087"},
        {"NEWSSUB": "Malformed row", "NEWS_DT": "not-a-date", "SCRIP_CD": "500087"},
    ]
}


def test_build_params_uses_bse_field_names():
    params = build_params("500087", "20260101", "20261015")
    assert params["strScrip"] == "500087"
    assert params["strPrevDate"] == "20260101"
    assert params["strToDate"] == "20261015"
    assert params["strType"] == "C"


def test_parse_announcements_returns_tidy_rows():
    rows = parse_announcements(PAYLOAD)
    assert len(rows) == 3
    assert rows[0]["subject"] == "Outcome of Board Meeting - Financial Results"
    assert rows[0]["published_at"] == datetime(2026, 7, 20, 18, 5, 0)
    assert rows[0]["scrip_code"] == "500087"


def test_parse_announcements_malformed_date_becomes_none_not_a_crash():
    rows = parse_announcements(PAYLOAD)
    assert rows[2]["subject"] == "Malformed row"
    assert rows[2]["published_at"] is None


def test_parse_announcements_empty_table():
    assert parse_announcements({"Table": []}) == []
    assert parse_announcements({}) == []


def test_cross_exchange_consistency_matching_filing():
    nse_item = {"title": "Outcome of Board Meeting - Financial Results", "published_at": datetime(2026, 7, 20)}
    bse_item = {"subject": "Outcome of Board Meeting - Financial Results", "published_at": datetime(2026, 7, 20)}
    result = cross_exchange_consistency(nse_item, bse_item)
    assert result["consistent"] is True


def test_cross_exchange_consistency_flags_title_mismatch():
    nse_item = {"title": "Outcome of Board Meeting - Financial Results", "published_at": datetime(2026, 7, 20)}
    bse_item = {"subject": "Notice of Annual General Meeting", "published_at": datetime(2026, 7, 20)}
    result = cross_exchange_consistency(nse_item, bse_item)
    assert result["consistent"] is False
    assert result["day_diff"] == 0


def test_cross_exchange_consistency_flags_date_mismatch_beyond_one_day():
    nse_item = {"title": "Outcome of Board Meeting - Financial Results", "published_at": datetime(2026, 7, 20)}
    bse_item = {"subject": "Outcome of Board Meeting - Financial Results", "published_at": datetime(2026, 7, 23)}
    result = cross_exchange_consistency(nse_item, bse_item)
    assert result["consistent"] is False
    assert result["day_diff"] == 3


def test_cross_exchange_consistency_tolerates_one_day_gap():
    nse_item = {"title": "Outcome of Board Meeting - Financial Results", "published_at": datetime(2026, 7, 20)}
    bse_item = {"subject": "Outcome of Board Meeting - Financial Results", "published_at": datetime(2026, 7, 21)}
    result = cross_exchange_consistency(nse_item, bse_item)
    assert result["consistent"] is True
