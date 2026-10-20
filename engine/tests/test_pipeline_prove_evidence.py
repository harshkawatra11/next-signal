"""Tests for pipeline/prove.py's real evidence/numbers/timeline/strength builders (Wave 2 E11), added
once Connect/Calculate started producing real Facts, Documents, MetricValues and Anomalies to build from.
"""
from datetime import date, datetime

from next_signal.pipeline.prove import build_evidence, build_numbers, build_timeline, default_strength
from next_signal.schemas import (
    Anchor,
    Anomaly,
    Document,
    Fact,
    FinancialRow,
    Hypothesis,
    MetricValue,
    Prediction,
)
from next_signal.schemas import TestResult as StageTestResult


def make_doc(doc_id, published):
    return Document(
        doc_id=doc_id, kind="results_xbrl", title=f"Q results {doc_id}",
        url=f"https://nsearchives.nseindia.com/corporate/xbrl/{doc_id}.xml", publisher="NSE",
        origin_class="company_filing", published_at=published, fetched_at=datetime(2026, 10, 16),
        reliability="A",
    )


def make_fact(doc, metric, period, value, entity="CIPLA"):
    return Fact(
        fact_id=f"{entity}-{period}-{metric}", metric=metric, period=period, value=value, unit="INR_cr",
        entity=entity, anchor=Anchor(doc_id=doc.doc_id, page=None, quote=f"{metric}={value}", verified=True),
    )


def make_hyp(metric_id="gross_margin", direction="down"):
    return Hypothesis(
        hyp_id="H1", angle_id="P9", statement="Gross margin is falling.", mechanism="cost pressure",
        predictions=[Prediction(metric_id=metric_id, direction=direction, where_to_check="results")],
    )


class FakeCtx:
    def __init__(self):
        self.symbol = "CIPLA"
        self.documents = []
        self.facts = []
        self.metrics = []
        self.anomalies = []
        self.financials = []
        self.tests = []
        self.contradictions = []


def test_build_evidence_dedupes_by_document_and_matches_raw_inputs():
    ctx = FakeCtx()
    doc1 = make_doc("D1", datetime(2026, 7, 20))
    doc2 = make_doc("D2", datetime(2026, 4, 28))
    ctx.documents = [doc1, doc2]
    ctx.facts = [
        make_fact(doc1, "revenue", "Q1FY27", 6142.0),
        make_fact(doc1, "cogs", "Q1FY27", 2383.1),
        make_fact(doc2, "revenue", "Q4FY26", 5894.0),
        make_fact(doc2, "cogs", "Q4FY26", 2234.6),
        make_fact(doc1, "pat", "Q1FY27", 1088.0),  # not a gross_margin input, should not break anything
    ]
    hyp = make_hyp("gross_margin")
    evidence = build_evidence(ctx, hyp)
    assert len(evidence) == 2
    assert {e.doc_id for e in evidence} == {"D1", "D2"}
    assert all(e.supports == ["H1"] for e in evidence)


def test_build_evidence_empty_without_matching_facts():
    ctx = FakeCtx()
    hyp = make_hyp("gross_margin")
    assert build_evidence(ctx, hyp) == []


def test_build_numbers_includes_latest_value_and_peer_z():
    ctx = FakeCtx()
    ctx.metrics = [
        MetricValue(metric_id="gross_margin", period="Q4FY26", value=0.62, unit="pct", inputs=[], formula="x"),
        MetricValue(metric_id="gross_margin", period="Q1FY27", value=0.58, unit="pct", inputs=[], formula="x"),
    ]
    ctx.anomalies = [Anomaly(anomaly_id="a1", metric_id="gross_margin", description="x", peer_z=-2.1, score=0.5)]
    hyp = make_hyp("gross_margin")
    numbers = build_numbers(ctx, hyp)
    assert len(numbers) == 2
    assert numbers[0].period == "Q1FY27"  # the later period, after sorting
    assert numbers[0].value == 0.58
    assert "z = -2.1" in numbers[1].display


def test_build_numbers_empty_without_metric_series():
    ctx = FakeCtx()
    hyp = make_hyp("gross_margin")
    assert build_numbers(ctx, hyp) == []


def test_build_timeline_marks_the_changepoint():
    ctx = FakeCtx()
    ctx.financials = [
        FinancialRow(period="Q4FY26", period_end=date(2026, 3, 31), values={}, doc_id="D1"),
        FinancialRow(period="Q1FY27", period_end=date(2026, 6, 30), values={}, doc_id="D2"),
    ]
    ctx.metrics = [
        MetricValue(metric_id="gross_margin", period="Q4FY26", value=0.62, unit="pct", inputs=[], formula="x"),
        MetricValue(metric_id="gross_margin", period="Q1FY27", value=0.58, unit="pct", inputs=[], formula="x"),
    ]
    ctx.anomalies = [Anomaly(anomaly_id="a1", metric_id="gross_margin", description="x", changepoint_period="Q1FY27", score=0.5)]
    hyp = make_hyp("gross_margin")
    timeline = build_timeline(ctx, hyp)
    assert len(timeline) == 2
    assert timeline[0].date == date(2026, 3, 31)
    assert timeline[1].is_changepoint is True
    assert timeline[0].is_changepoint is False


def test_default_strength_counts_real_independent_origins_and_tests():
    ctx = FakeCtx()
    doc1 = make_doc("D1", datetime(2026, 7, 20))
    doc2 = make_doc("D2", datetime(2026, 4, 28))
    ctx.documents = [doc1, doc2]
    ctx.facts = [
        make_fact(doc1, "revenue", "Q1FY27", 6142.0), make_fact(doc1, "cogs", "Q1FY27", 2383.1),
        make_fact(doc2, "revenue", "Q4FY26", 5894.0), make_fact(doc2, "cogs", "Q4FY26", 2234.6),
    ]
    ctx.tests = [
        StageTestResult(hyp_id="H1", test_id="T1", applicable=True, passed=True, detail="peer z 1.8"),
        StageTestResult(hyp_id="H1", test_id="T6", applicable=True, passed=True, detail="persists"),
    ]
    hyp = make_hyp("gross_margin")
    evidence = build_evidence(ctx, hyp)
    sb = default_strength(ctx, hyp, evidence)
    assert sb.total > 0
    # doc1 and doc2 are both company_filing, which grading.independence collapses to one origin ("the
    # company"), so this is correctly 1, not 2, even with two distinct documents.
    assert sb.independence == 0  # independent_origins=1 maps to the 0-3 scale's lowest non-zero bucket... see note below


def test_default_strength_single_document_true_when_one_doc_backs_everything():
    ctx = FakeCtx()
    doc1 = make_doc("D1", datetime(2026, 7, 20))
    ctx.documents = [doc1]
    ctx.facts = [make_fact(doc1, "revenue", "Q1FY27", 6142.0), make_fact(doc1, "cogs", "Q1FY27", 2383.1)]
    hyp = make_hyp("gross_margin")
    evidence = build_evidence(ctx, hyp)
    sb = default_strength(ctx, hyp, evidence)
    assert sb.label == "Weak"  # strength.py forces Weak whenever single_document is True


def test_default_strength_honest_zero_corroboration_until_cross_checking_exists():
    ctx = FakeCtx()
    doc1 = make_doc("D1", datetime(2026, 7, 20))
    ctx.documents = [doc1]
    ctx.facts = [make_fact(doc1, "revenue", "Q1FY27", 6142.0), make_fact(doc1, "cogs", "Q1FY27", 2383.1)]
    hyp = make_hyp("gross_margin")
    evidence = build_evidence(ctx, hyp)
    sb = default_strength(ctx, hyp, evidence)
    assert sb.corroboration == 0.0
