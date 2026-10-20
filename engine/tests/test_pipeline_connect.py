from datetime import date, datetime

from next_signal.pipeline.connect import (
    anchor_fact,
    classify_document,
    document_from_nse_item,
    documents_from_nse_announcements,
    evidence_item_from_fact,
    fetch_documents,
    point_in_time_filter,
    run,
)
from next_signal.pipeline.context import RunContext


def make_doc(url, published):
    return classify_document(url, "Q1 FY27 results", "results", "NSE", published)


def test_classify_document_sets_origin_and_reliability_from_url():
    doc = classify_document(
        "https://nsearchives.nseindia.com/corporate/CIPLA_results.pdf", "Q1 FY27 results",
        "results", "NSE", datetime(2026, 7, 20),
    )
    assert doc.origin_class == "company_filing"
    assert doc.reliability == "A"
    assert len(doc.doc_id) == 12


def test_classify_document_peer_filing_flag():
    doc = classify_document(
        "https://nsearchives.nseindia.com/corporate/SUNPHARMA_results.pdf", "Peer results",
        "results", "NSE", datetime(2026, 7, 20), is_peer=True,
    )
    assert doc.origin_class == "peer_filing"


def test_point_in_time_filter_drops_future_documents():
    as_of = date(2026, 7, 1)
    docs = [make_doc("https://nseindia.com/a.pdf", datetime(2026, 6, 15)), make_doc("https://nseindia.com/b.pdf", datetime(2026, 8, 1))]
    kept = point_in_time_filter(docs, as_of)
    assert len(kept) == 1
    assert kept[0].url.endswith("a.pdf")


def test_point_in_time_filter_drops_unstamped_documents():
    docs = [make_doc("https://nseindia.com/a.pdf", None)]
    assert point_in_time_filter(docs, date(2026, 7, 1)) == []


def test_anchor_fact_verified_quote_produces_fact():
    doc = make_doc("https://nseindia.com/a.pdf", datetime(2026, 7, 20))
    page_text = "North America revenue was USD 162 million in Q1 FY27, down from the prior year."
    fact = anchor_fact("f1", "us_revenue", "Q1FY27", 162.0, "USD_mn", "CIPLA", doc, 3,
                       page_text, "North America revenue was USD 162 million in Q1 FY27")
    assert fact is not None
    assert fact.anchor.verified is True
    assert fact.anchor.page == 3


def test_anchor_fact_unverified_quote_returns_none():
    doc = make_doc("https://nseindia.com/a.pdf", datetime(2026, 7, 20))
    page_text = "North America revenue was USD 162 million in Q1 FY27."
    fact = anchor_fact("f1", "us_revenue", "Q1FY27", 999.0, "USD_mn", "CIPLA", doc, 3,
                       page_text, "North America revenue was USD 999 million")
    assert fact is None


def test_evidence_item_from_fact_carries_doc_fields():
    doc = make_doc("https://nseindia.com/a.pdf", datetime(2026, 7, 20))
    page_text = "Gross margin improved to 65 percent in Q1 FY27."
    fact = anchor_fact("f1", "gross_margin", "Q1FY27", 65.0, "pct", "CIPLA", doc, 5, page_text,
                       "Gross margin improved to 65 percent in Q1 FY27")
    ev = evidence_item_from_fact("ev1", fact, doc, supports=["hyp1"])
    assert ev.origin_class == "company_filing"
    assert ev.reliability == "A"
    assert ev.supports == ["hyp1"]
    assert ev.anchor.quote == fact.anchor.quote


async def test_run_degrades_to_zero_documents_without_live_fetch():
    ctx = RunContext(run_id="r1", symbol="CIPLA", company="Cipla Limited", sub_industry="pharma", as_of=date(2026, 10, 15))
    await run(ctx)
    assert ctx.documents == []
    assert ctx.trace[-1]["stage"] == "connect"
    assert ctx.trace[-1]["documents_fetched"] == 0


NSE_ITEM_RESULTS = {
    "desc": "Financial Results for the quarter ended 30 Jun 2026", "attchmntText": "",
    "attchmntFile": "https://nsearchives.nseindia.com/corporate/CIPLA_results.pdf",
    "an_dt": "20-Jul-2026 18:05:00",
}
NSE_ITEM_NO_ATTACHMENT = {"desc": "General update", "an_dt": "20-Jul-2026 18:05:00"}
NSE_ITEM_REGULATORY = {
    "desc": "Update on USFDA inspection observations", "attchmntText": "Form 483 issued",
    "attchmntFile": "https://nsearchives.nseindia.com/corporate/CIPLA_usfda.pdf",
    "sort_date": "2026-07-18 10:00:00",
}


def test_document_from_nse_item_builds_classified_document():
    doc = document_from_nse_item(NSE_ITEM_RESULTS)
    assert doc is not None
    assert doc.kind == "results"
    assert doc.origin_class == "company_filing"
    assert doc.published_at == datetime(2026, 7, 20, 18, 5, 0)
    assert doc.url == NSE_ITEM_RESULTS["attchmntFile"]


def test_document_from_nse_item_returns_none_without_attachment():
    assert document_from_nse_item(NSE_ITEM_NO_ATTACHMENT) is None


def test_document_from_nse_item_uses_sort_date_fallback_and_classifies_regulatory_kind():
    doc = document_from_nse_item(NSE_ITEM_REGULATORY)
    assert doc.kind == "regulatory_usfda"
    assert doc.published_at == datetime(2026, 7, 18, 10, 0, 0)


def test_documents_from_nse_announcements_filters_out_no_attachment_items():
    docs = documents_from_nse_announcements([NSE_ITEM_RESULTS, NSE_ITEM_NO_ATTACHMENT, NSE_ITEM_REGULATORY])
    assert len(docs) == 2
    assert {d.kind for d in docs} == {"results", "regulatory_usfda"}


class FakeNSEClient:
    def __init__(self, payload):
        self.payload = payload
        self.calls = []

    async def announcements(self, sym, frm, to):
        self.calls.append((sym, frm, to))
        return self.payload


async def test_fetch_documents_with_injected_client_bare_list_shape():
    client = FakeNSEClient([NSE_ITEM_RESULTS, NSE_ITEM_REGULATORY])
    ctx = RunContext(run_id="r2", symbol="CIPLA", company="Cipla Limited", sub_industry="pharma", as_of=date(2026, 10, 15))
    docs = await fetch_documents(ctx, nse_client=client)
    assert len(docs) == 2
    assert client.calls[0][0] == "CIPLA"


async def test_fetch_documents_with_injected_client_wrapped_data_shape():
    client = FakeNSEClient({"data": [NSE_ITEM_RESULTS]})
    ctx = RunContext(run_id="r3", symbol="CIPLA", company="Cipla Limited", sub_industry="pharma", as_of=date(2026, 10, 15))
    docs = await fetch_documents(ctx, nse_client=client)
    assert len(docs) == 1


async def test_fetch_documents_degrades_on_client_exception():
    class BoomClient:
        async def announcements(self, sym, frm, to):
            raise RuntimeError("network down")

    ctx = RunContext(run_id="r4", symbol="CIPLA", company="Cipla Limited", sub_industry="pharma", as_of=date(2026, 10, 15))
    docs = await fetch_documents(ctx, nse_client=BoomClient())
    assert docs == []


async def test_run_with_injected_client_populates_documents_in_window():
    client = FakeNSEClient([NSE_ITEM_RESULTS])
    ctx = RunContext(run_id="r5", symbol="CIPLA", company="Cipla Limited", sub_industry="pharma", as_of=date(2026, 10, 15))
    # select_peers_fn disabled: the fake client has no financial_results/quote methods, and this test is
    # only about the announcements path, so it must never touch the real (network-backed) universe loader.
    await run(ctx, nse_client=client, select_peers_fn=lambda c: _no_peers())
    assert len(ctx.documents) == 1
    assert ctx.trace[-1]["documents_fetched"] == 1
    assert ctx.trace[-1]["documents_in_window"] == 1


async def _no_peers():
    return []
