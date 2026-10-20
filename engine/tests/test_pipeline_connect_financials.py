"""Tests for pipeline/connect.py's financials fetch and peer selection, added alongside the Wave 2
NSE-financials wiring (fetch_financials, build FinancialRow, select_peers). Every network-shaped call is
either a fake client or an isolated-cache respx mock, never the real engine HTTP cache or network.
"""
from datetime import date, datetime

import pytest
import respx
from httpx import Response

from next_signal import http as http_module
from next_signal.pipeline import connect
from next_signal.pipeline.connect import fetch_financials, select_peers
from next_signal.pipeline.context import RunContext

XBRL_SAMPLE = """<?xml version="1.0" encoding="UTF-8"?>
<xbrli:xbrl xmlns:xbrli="http://www.xbrl.org/2003/instance"
            xmlns:in-bse-fin="http://www.bseindia.com/xbrl/fin/2020-03-31/in-bse-fin">
  <xbrli:context id="OneD">
    <xbrli:entity><xbrli:identifier>CIPLA</xbrli:identifier></xbrli:entity>
    <xbrli:period>
      <xbrli:startDate>2026-04-01</xbrli:startDate>
      <xbrli:endDate>2026-06-30</xbrli:endDate>
    </xbrli:period>
  </xbrli:context>
  <in-bse-fin:RevenueFromOperations contextRef="OneD" unitRef="INR" decimals="-6">61420000000</in-bse-fin:RevenueFromOperations>
  <in-bse-fin:OtherIncome contextRef="OneD" unitRef="INR" decimals="-6">1030000000</in-bse-fin:OtherIncome>
  <in-bse-fin:ProfitBeforeTax contextRef="OneD" unitRef="INR" decimals="-6">14280000000</in-bse-fin:ProfitBeforeTax>
  <in-bse-fin:TaxExpense contextRef="OneD" unitRef="INR" decimals="-6">3400000000</in-bse-fin:TaxExpense>
  <in-bse-fin:ProfitLossForPeriod contextRef="OneD" unitRef="INR" decimals="-6">10880000000</in-bse-fin:ProfitLossForPeriod>
</xbrli:xbrl>
"""

FILING_ITEM = {
    "symbol": "CIPLA", "period": "Quarterly", "cumulative": "Non-cumulative", "consolidated": "Consolidated",
    "fromDate": "01-Apr-2026", "toDate": "30-Jun-2026", "broadCastDate": "20-Jul-2026 18:00:00",
    "financialYear": "01-Apr-2026 To 31-Mar-2027", "seqNumber": "1",
    "xbrl": "https://nsearchives.nseindia.com/corporate/xbrl/CIPLA_Q1FY27.xml",
}


class FakeFinancialsClient:
    def __init__(self, items):
        self.items = items

    async def financial_results(self, symbol):
        return self.items


@pytest.fixture(autouse=True)
def isolated_http_cache(tmp_path, monkeypatch):
    monkeypatch.setattr(http_module, "_cache", http_module.DiskCache(tmp_path))


@respx.mock
async def test_fetch_financials_builds_documents_facts_and_financial_rows():
    respx.get("https://nsearchives.nseindia.com/corporate/xbrl/CIPLA_Q1FY27.xml").mock(
        return_value=Response(200, content=XBRL_SAMPLE.encode())
    )
    client = FakeFinancialsClient([FILING_ITEM])
    docs, facts, rows = await fetch_financials(client, "CIPLA", date(2026, 10, 15))

    assert len(docs) == 1
    assert docs[0].kind == "results_xbrl"
    assert docs[0].origin_class == "company_filing"

    assert any(f.metric == "revenue" and f.entity == "CIPLA" for f in facts)
    revenue_fact = next(f for f in facts if f.metric == "revenue")
    assert revenue_fact.period == "Q1FY27"
    assert revenue_fact.value == 6142.0
    assert revenue_fact.anchor.verified is True

    assert len(rows) == 1
    assert rows[0].period == "Q1FY27"
    assert rows[0].period_end == date(2026, 6, 30)
    assert rows[0].values["revenue"] == 6142.0
    assert rows[0].doc_id == docs[0].doc_id


async def test_fetch_financials_returns_empty_without_a_client():
    docs, facts, rows = await fetch_financials(None, "CIPLA", date(2026, 10, 15))
    assert (docs, facts, rows) == ([], [], [])


@respx.mock
async def test_fetch_financials_skips_a_filing_whose_xbrl_fetch_fails():
    respx.get("https://nsearchives.nseindia.com/corporate/xbrl/CIPLA_Q1FY27.xml").mock(
        return_value=Response(500)
    )
    client = FakeFinancialsClient([FILING_ITEM])
    docs, facts, rows = await fetch_financials(client, "CIPLA", date(2026, 10, 15))
    assert (docs, facts, rows) == ([], [], [])


@respx.mock
async def test_fetch_financials_skips_a_filing_whose_xbrl_body_is_not_valid_xml():
    # Observed live: a peer's xbrl URL returned a 200 with an HTML error/cookie-wall page instead of an
    # XBRL instance. quarter_facts() raising XMLSyntaxError on that body must not crash the whole
    # fetch_financials call (and, transitively, the whole Connect stage for every remaining peer).
    # A boolean HTML5 attribute with no value ("defer") is invalid XML and lxml raises XMLSyntaxError on
    # it, exactly the shape of body an HTML error or cookie-wall page served with a 200 status produces.
    respx.get("https://nsearchives.nseindia.com/corporate/xbrl/CIPLA_Q1FY27.xml").mock(
        return_value=Response(200, content=b"<html><script defer>not an xbrl instance</script></html>")
    )
    client = FakeFinancialsClient([FILING_ITEM])
    docs, facts, rows = await fetch_financials(client, "CIPLA", date(2026, 10, 15))
    assert (docs, facts, rows) == ([], [], [])


async def test_select_peers_same_playbook_excludes_subject(monkeypatch):
    from next_signal import universe as universe_module

    class Row:
        def __init__(self, symbol, name, industry):
            self.symbol, self.company_name, self.industry = symbol, name, industry

    fake_uni = {
        "nifty50": [Row("CIPLA", "Cipla Ltd.", "Healthcare"), Row("APOLLOHOSP", "Apollo Hospitals Enterprise Ltd.", "Healthcare")],
        "niftypharma": [Row("CIPLA", "Cipla Ltd.", "Healthcare"), Row("SUNPHARMA", "Sun Pharmaceutical Industries Ltd.", "Healthcare")],
        "niftyhealthcare": [],
    }

    async def fake_load_universe():
        return fake_uni

    monkeypatch.setattr(universe_module, "load_universe", fake_load_universe)
    ctx = RunContext(run_id="r1", symbol="CIPLA", company="Cipla Ltd.", sub_industry="pharma", as_of=date(2026, 10, 15))
    peers = await select_peers(ctx, k=5)
    assert "CIPLA" not in peers
    assert "SUNPHARMA" in peers
    assert "APOLLOHOSP" not in peers  # different playbook (hospital, from its name), not a peer


async def test_select_peers_returns_empty_for_unknown_subject(monkeypatch):
    from next_signal import universe as universe_module

    async def fake_load_universe():
        return {"nifty50": [], "niftypharma": [], "niftyhealthcare": []}

    monkeypatch.setattr(universe_module, "load_universe", fake_load_universe)
    ctx = RunContext(run_id="r2", symbol="NOTACOMPANY", company="x", sub_industry="generic", as_of=date(2026, 10, 15))
    assert await select_peers(ctx) == []


async def test_run_injects_select_peers_fn_and_skips_the_real_universe_loader(monkeypatch):
    called = {}

    async def fake_select_peers(ctx):
        called["yes"] = True
        return ["SUNPHARMA", "DRREDDY"]

    class EmptyClient:
        async def announcements(self, sym, frm, to):
            return []

        async def financial_results(self, sym):
            return []

    ctx = RunContext(run_id="r3", symbol="CIPLA", company="Cipla Ltd.", sub_industry="pharma", as_of=date(2026, 10, 15))
    await connect.run(ctx, nse_client=EmptyClient(), select_peers_fn=fake_select_peers)
    assert called.get("yes") is True
    assert ctx.peers == ["SUNPHARMA", "DRREDDY"]
