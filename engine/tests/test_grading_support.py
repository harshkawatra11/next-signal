from datetime import datetime, timezone

from next_signal.grading.admiralty import classify
from next_signal.grading.contradictions import (
    aggregator_vs_primary,
    cross_channel_mismatch,
    narrative_vs_number,
    numeric_conflict,
    temporal_guidance_miss,
)
from next_signal.grading.independence import independent_origins, origin_mix
from next_signal.grading.novelty import novelty
from next_signal.schemas import Anchor, EvidenceItem


def ev(origin, publisher, days_ago=0, quote="example quote text here"):
    return EvidenceItem(
        ev_id=f"ev-{publisher}-{days_ago}",
        doc_id="d1",
        title="t",
        url="https://example.com",
        publisher=publisher,
        origin_class=origin,
        reliability="A",
        published_at=datetime(2026, 7, 22 - days_ago, tzinfo=timezone.utc),
        supports=[],
        contradicts=[],
        anchor=Anchor(doc_id="d1", quote=quote, verified=True),
    )


def test_classify_nse_is_company_filing_grade_a():
    origin, grade = classify("https://nsearchives.nseindia.com/corporate/CIPLA_result.pdf")
    assert origin == "company_filing"
    assert grade == "A"


def test_classify_fda_is_regulator_us():
    origin, grade = classify("https://www.fda.gov/inspections/warning-letters/cipla-123")
    assert origin == "regulator_us"
    assert grade == "A"


def test_classify_press_domain():
    origin, grade = classify("https://www.livemint.com/companies/cipla-news")
    assert origin == "press"
    assert grade == "C"


def test_classify_peer_filing_flag():
    origin, _ = classify("https://nsearchives.nseindia.com/corporate/DRREDDY_result.pdf", is_peer=True)
    assert origin == "peer_filing"


def test_independent_origins_collapses_same_publisher():
    items = [ev("company_filing", "Cipla"), ev("company_ir", "Cipla")]
    assert independent_origins(items) == 1  # both collapse to "company"


def test_independent_origins_counts_distinct_classes():
    items = [
        ev("company_filing", "Cipla"),
        ev("regulator_us", "FDA"),
        ev("peer_filing", "Dr Reddy's"),
    ]
    assert independent_origins(items) == 3


def test_press_restating_filing_does_not_add_an_origin():
    quote = "North America revenue of $162 Mn during the quarter"
    filing = ev("company_filing", "Cipla", days_ago=0, quote=quote)
    press = ev("press", "Economic Times", days_ago=1, quote=quote)
    items = [filing, press]
    assert independent_origins(items) == 1


def test_origin_mix_counts():
    items = [ev("company_filing", "Cipla"), ev("company_filing", "Cipla"), ev("regulator_us", "FDA")]
    mix = origin_mix(items)
    by_label = {m["label"]: m["v"] for m in mix}
    assert by_label["company_filing"] == 2
    assert by_label["regulator_us"] == 1


def test_novelty_high_when_no_coverage_no_narrative_long_lead():
    n = novelty(mainstream_hits_90d=0, management_stated=False, lead_days=90)
    assert n == 1.0


def test_novelty_low_when_widely_covered_and_stated():
    n = novelty(mainstream_hits_90d=20, management_stated=True, lead_days=0)
    assert n == 0.0


def test_numeric_conflict_detects_real_discrepancy():
    hit = numeric_conflict("net_profit", "Q1FY27", "DRREDDY", 1290.0, "Aggregator X", "C", 443.0, "Company filing", "A")
    assert hit is not None
    assert hit.type == "numeric"
    assert "Company filing" in hit.ruling


def test_numeric_conflict_none_when_equal():
    assert numeric_conflict("revenue", "Q1FY27", "CIPLA", 100.0, "A", "A", 100.0, "B", "A") is None


def test_narrative_vs_number_threshold():
    assert narrative_vs_number("revenue", 0.2) is None
    hit = narrative_vs_number("revenue", 0.8)
    assert hit is not None and hit.type == "narrative_vs_number"


def test_temporal_guidance_miss_detects_shortfall():
    hit = temporal_guidance_miss("us_revenue_usd_mn", 1000.0, 600.0)
    assert hit is not None and hit.type == "temporal"


def test_temporal_guidance_within_tolerance_no_hit():
    assert temporal_guidance_miss("us_revenue_usd_mn", 1000.0, 950.0) is None


def test_cross_channel_mismatch_detected():
    hit = cross_channel_mismatch("net_profit", 443.0, 450.0)
    assert hit is not None and hit.type == "cross_channel"


def test_aggregator_vs_primary_catches_the_worked_discrepancy():
    hit = aggregator_vs_primary("net_profit", "Q1FY27", 1290.0, "Aggregator", 443.0, "Company filing")
    assert hit is not None
    assert hit.type == "aggregator_vs_primary"
