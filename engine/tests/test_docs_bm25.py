from next_signal.docs.bm25 import PageIndex, candidate_pages_for_metric, tokenize
from next_signal.metrics.fx import fx_effect, usd_from_inr, yoy_from_series


def test_tokenize_lowercases_and_splits():
    assert tokenize("North America Revenue: $162 Mn") == ["north", "america", "revenue", "162", "mn"]


def test_page_index_ranks_relevant_page_highest():
    pages = [
        "This page discusses corporate governance and the board of directors.",
        "North America revenue grew to $162 million during the quarter, driven by Albuterol.",
        "Risk factors include currency fluctuation and regulatory changes.",
    ]
    idx = PageIndex(pages)
    top = idx.top_pages(["north america revenue"], k=2)
    assert top[0][0] == 2  # page 2 (1-indexed) is the most relevant


def test_candidate_pages_for_metric_returns_page_numbers():
    # BM25's IDF term is log((N - freq + 0.5) / (freq + 0.5)); with only 2 pages and a term in exactly
    # 1 of them, that collapses to exactly log(1) = 0 regardless of term frequency, which is a real
    # property of BM25 on tiny corpora, not a bug. A realistic PDF has many pages, so the fixture here
    # uses 6 to actually discriminate, matching real usage.
    pages = [
        "Cover page with the company logo and report title.",
        "Table of contents and list of abbreviations used in this report.",
        "Chairman's letter discussing the overall business environment.",
        "Receivable days increased from 28 to 46 over the last eight quarters, alongside falling volumes.",
        "Risk factors include currency fluctuation and regulatory changes across jurisdictions.",
        "Auditor's report and signatures of the board of directors.",
    ]
    pages_found = candidate_pages_for_metric(pages, ["receivable days", "trade receivables"], k=1)
    assert pages_found == [4]


def test_page_index_empty_pages_does_not_crash():
    idx = PageIndex([])
    assert idx.top_pages(["anything"]) == []


def test_fx_effect_positive_when_inr_outpaces_usd():
    assert round(fx_effect(0.08, 0.02), 4) == 0.06


def test_usd_from_inr_conversion():
    assert round(usd_from_inr(8300.0, 83.0), 2) == 100.0


def test_usd_from_inr_zero_rate_returns_none():
    assert usd_from_inr(100.0, 0.0) is None


def test_yoy_from_series_computes_correctly():
    values = {"Q1FY27": 162.0, "Q1FY26": 150.0}
    assert round(yoy_from_series(values, "Q1FY27", "Q1FY26"), 4) == round((162.0 - 150.0) / 150.0, 4)


def test_yoy_from_series_missing_period_returns_none():
    assert yoy_from_series({"Q1FY27": 162.0}, "Q1FY27", "Q1FY26") is None
