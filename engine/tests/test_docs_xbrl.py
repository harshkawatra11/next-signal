from datetime import date

from next_signal.docs.xbrl import local_name, parse_contexts, quarter_facts, quarter_items

# Shape confirmed by a live probe (16 Oct 2026, see build-log.md) against a real NSE XBRL instance: a
# single quarter's broadcast can carry two non-dimensional contexts ("OneD" and "FourD" in the real
# filing) whose period dates, entity and scenario are byte-for-byte identical, with genuinely different
# reported values for the same tag (NSE's standalone-plus-consolidated bundling; see docs/xbrl.py's
# module docstring). This fixture reproduces that exact shape (not a YTD-vs-quarter difference, which
# the probe ruled out directly) plus a dimensioned (segment-level) context, to test that quarter_facts()
# keeps only the plain quarter-exact, non-dimensional numbers, taking the first-in-document-order value
# when a genuine same-date duplicate exists.
XBRL_SAMPLE = """<?xml version="1.0" encoding="UTF-8"?>
<xbrli:xbrl xmlns:xbrli="http://www.xbrl.org/2003/instance"
            xmlns:xbrldi="http://xbrl.org/2006/xbrldi"
            xmlns:in-bse-fin="http://www.bseindia.com/xbrl/fin/2020-03-31/in-bse-fin">
  <xbrli:context id="OneD">
    <xbrli:entity><xbrli:identifier>GLENMARK</xbrli:identifier></xbrli:entity>
    <xbrli:period>
      <xbrli:startDate>2024-10-01</xbrli:startDate>
      <xbrli:endDate>2024-12-31</xbrli:endDate>
    </xbrli:period>
  </xbrli:context>
  <xbrli:context id="FourD">
    <xbrli:entity><xbrli:identifier>GLENMARK</xbrli:identifier></xbrli:entity>
    <xbrli:period>
      <xbrli:startDate>2024-10-01</xbrli:startDate>
      <xbrli:endDate>2024-12-31</xbrli:endDate>
    </xbrli:period>
  </xbrli:context>
  <xbrli:context id="OneD_Segment">
    <xbrli:entity>
      <xbrli:identifier>GLENMARK</xbrli:identifier>
      <xbrli:segment><xbrldi:explicitMember dimension="in-bse-fin:SegmentsAxis">in-bse-fin:IndiaFormulationsMember</xbrldi:explicitMember></xbrli:segment>
    </xbrli:entity>
    <xbrli:period>
      <xbrli:startDate>2024-10-01</xbrli:startDate>
      <xbrli:endDate>2024-12-31</xbrli:endDate>
    </xbrli:period>
  </xbrli:context>
  <xbrli:context id="AsOfQ3">
    <xbrli:entity><xbrli:identifier>GLENMARK</xbrli:identifier></xbrli:entity>
    <xbrli:period><xbrli:instant>2024-12-31</xbrli:instant></xbrli:period>
  </xbrli:context>
  <in-bse-fin:RevenueFromOperations contextRef="OneD" unitRef="INR" decimals="-6">33875520000</in-bse-fin:RevenueFromOperations>
  <in-bse-fin:RevenueFromOperations contextRef="FourD" unitRef="INR" decimals="-6">100655330000</in-bse-fin:RevenueFromOperations>
  <in-bse-fin:RevenueFromOperations contextRef="OneD_Segment" unitRef="INR" decimals="-6">18000000000</in-bse-fin:RevenueFromOperations>
  <in-bse-fin:OtherIncome contextRef="OneD" unitRef="INR" decimals="-6">311280000</in-bse-fin:OtherIncome>
  <in-bse-fin:CostOfMaterialsConsumed contextRef="OneD" unitRef="INR" decimals="-6">8500000000</in-bse-fin:CostOfMaterialsConsumed>
  <in-bse-fin:Expenses contextRef="OneD" unitRef="INR" decimals="-6">29311920000</in-bse-fin:Expenses>
  <in-bse-fin:ProfitBeforeTax contextRef="OneD" unitRef="INR" decimals="-6" sign="-">4563260000</in-bse-fin:ProfitBeforeTax>
  <in-bse-fin:ProfitLossForPeriod contextRef="OneD" unitRef="INR" decimals="-6">3480310000</in-bse-fin:ProfitLossForPeriod>
  <in-bse-fin:TaxExpense contextRef="OneD" unitRef="INR" decimals="-6">1082950000</in-bse-fin:TaxExpense>
</xbrli:xbrl>
"""


def test_local_name_strips_namespace():
    assert local_name("{http://www.xbrl.org/2003/instance}context") == "context"
    assert local_name("context") == "context"


def test_parse_contexts_extracts_dates_and_dimension_flag():
    from lxml import etree

    root = etree.fromstring(XBRL_SAMPLE.encode())
    contexts = parse_contexts(root)
    assert contexts["OneD"]["start"] == date(2024, 10, 1)
    assert contexts["OneD"]["end"] == date(2024, 12, 31)
    assert contexts["OneD"]["has_dimension"] is False
    assert contexts["FourD"]["start"] == date(2024, 10, 1)
    assert contexts["FourD"]["end"] == date(2024, 12, 31)
    assert contexts["OneD_Segment"]["has_dimension"] is True
    assert contexts["AsOfQ3"]["instant"] == date(2024, 12, 31)


def test_quarter_facts_dedupes_same_date_duplicate_contexts_keeping_the_first():
    # OneD and FourD are genuine same-date duplicates (NSE's standalone-plus-consolidated bundling);
    # quarter_facts must emit exactly one row per item, taking the first one in document order.
    rows = quarter_facts(XBRL_SAMPLE.encode(), date(2024, 10, 1), date(2024, 12, 31))
    revenue_rows = [r for r in rows if r["item"] == "revenue"]
    assert len(revenue_rows) == 1
    assert revenue_rows[0]["context_id"] == "OneD"


def test_quarter_facts_excludes_dimensioned_segment_context():
    rows = quarter_facts(XBRL_SAMPLE.encode(), date(2024, 10, 1), date(2024, 12, 31))
    assert all(r["context_id"] != "OneD_Segment" for r in rows)


def test_quarter_facts_converts_rupees_to_crore():
    rows = quarter_facts(XBRL_SAMPLE.encode(), date(2024, 10, 1), date(2024, 12, 31))
    revenue = next(r for r in rows if r["item"] == "revenue")
    assert revenue["value"] == 3387.552  # 33875520000 / 1e7


def test_quarter_facts_applies_sign_attribute():
    rows = quarter_facts(XBRL_SAMPLE.encode(), date(2024, 10, 1), date(2024, 12, 31))
    pbt = next(r for r in rows if r["item"] == "pbt")
    assert pbt["value"] < 0


def test_quarter_facts_maps_expenses_tag_not_totalexpenses():
    # The real NSE XBRL tag for total expenses is "Expenses", confirmed by a live probe; a parser that
    # mapped the plausible-sounding "TotalExpenses" tag instead would silently extract nothing.
    rows = quarter_facts(XBRL_SAMPLE.encode(), date(2024, 10, 1), date(2024, 12, 31))
    assert any(r["item"] == "total_expenses" and r["tag"] == "Expenses" for r in rows)


def test_quarter_facts_builds_anchor_quote_with_both_dates():
    rows = quarter_facts(XBRL_SAMPLE.encode(), date(2024, 10, 1), date(2024, 12, 31))
    revenue = next(r for r in rows if r["item"] == "revenue")
    assert revenue["anchor_quote"] == "RevenueFromOperations=33875520000 (context OneD, 2024-10-01 to 2024-12-31)"


def test_quarter_facts_empty_for_a_period_with_no_matching_context():
    rows = quarter_facts(XBRL_SAMPLE.encode(), date(2020, 1, 1), date(2020, 3, 31))
    assert rows == []


def test_quarter_items_builds_flat_item_value_dict():
    rows = quarter_facts(XBRL_SAMPLE.encode(), date(2024, 10, 1), date(2024, 12, 31))
    items = quarter_items(rows)
    assert items["revenue"] == 3387.552
    assert items["other_income"] == 31.128
    assert items["materials"] == 850.0
    assert "pat" in items
    assert "pat_owners" not in items  # not present in this filing's sample, must not be invented
