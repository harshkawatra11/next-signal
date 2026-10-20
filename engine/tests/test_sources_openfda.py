from next_signal.sources.openfda import (
    build_firm_query,
    build_sponsor_query,
    count_anda_approvals_ttm,
    count_recalls_by_classification,
    parse_approvals,
    parse_recalls,
)

DRUGSFDA_RESULTS = [
    {
        "application_number": "ANDA123456",
        "sponsor_name": "CIPLA LTD",
        "submissions": [
            {"submission_type": "ORIG", "submission_status": "AP", "submission_status_date": "20260215"},
            {"submission_type": "SUPPL", "submission_status": "AP", "submission_status_date": "20260601"},
        ],
    },
    {
        "application_number": "NDA987654",
        "sponsor_name": "CIPLA LTD",
        "submissions": [
            {"submission_type": "ORIG", "submission_status": "AP", "submission_status_date": "20200101"},
        ],
    },
    {
        "application_number": "ANDA555555",
        "sponsor_name": "CIPLA LTD",
        "submissions": [
            {"submission_type": "ORIG", "submission_status": "TA", "submission_status_date": "20260901"},
        ],
    },
]

ENFORCEMENT_RESULTS = [
    {"recalling_firm": "Cipla Ltd", "classification": "Class II", "reason_for_recall": "labeling error",
     "recall_initiation_date": "20260301", "report_date": "20260310", "status": "Ongoing",
     "product_description": "Tablet, 10mg"},
    {"recalling_firm": "Cipla Ltd", "classification": "Class I", "reason_for_recall": "contamination",
     "recall_initiation_date": "20250601", "report_date": "20250610", "status": "Terminated",
     "product_description": "Injection"},
]


def test_build_sponsor_query_ors_quoted_stems():
    q = build_sponsor_query(["Cipla", "Cipla Ltd"])
    assert q == '(sponsor_name:"Cipla" OR sponsor_name:"Cipla Ltd")'


def test_build_firm_query_ors_quoted_stems():
    q = build_firm_query(["Cipla"])
    assert q == '(recalling_firm:"Cipla")'


def test_parse_approvals_flattens_one_row_per_submission():
    rows = parse_approvals(DRUGSFDA_RESULTS)
    assert len(rows) == 4  # 2 + 1 + 1 submissions across 3 applications
    anda_rows = [r for r in rows if r["is_anda"]]
    assert len(anda_rows) == 3
    assert all(r["sponsor"] == "CIPLA LTD" for r in rows)


def test_parse_approvals_handles_missing_submissions_gracefully():
    assert parse_approvals([{"application_number": "ANDA1", "sponsor_name": "X"}]) == []


def test_parse_recalls_extracts_expected_fields():
    rows = parse_recalls(ENFORCEMENT_RESULTS)
    assert len(rows) == 2
    assert rows[0]["classification"] == "Class II"
    assert rows[1]["reason"] == "contamination"


def test_count_recalls_by_classification():
    rows = parse_recalls(ENFORCEMENT_RESULTS)
    assert count_recalls_by_classification(rows, "Class I") == 1
    assert count_recalls_by_classification(rows, "Class II") == 1
    assert count_recalls_by_classification(rows, "Class III") == 0


def test_count_anda_approvals_ttm_only_counts_orig_ap_within_window():
    rows = parse_approvals(DRUGSFDA_RESULTS)
    # as_of 2026-10-15: trailing 365 days back to 2025-10-15.
    # ANDA123456's ORIG/AP is 2026-02-15 (in window); its SUPPL/AP must not count (not ORIG).
    # NDA987654 is not an ANDA, excluded regardless of date.
    # ANDA555555's ORIG is status TA (tentative approval), not AP, excluded.
    assert count_anda_approvals_ttm(rows, "20261015") == 1


def test_count_anda_approvals_ttm_excludes_dates_outside_window():
    rows = parse_approvals(DRUGSFDA_RESULTS)
    assert count_anda_approvals_ttm(rows, "20260301") == 1  # the Feb 2026 approval is in window
    assert count_anda_approvals_ttm(rows, "20260101") == 0  # Feb 2026 approval is in the future, excluded
