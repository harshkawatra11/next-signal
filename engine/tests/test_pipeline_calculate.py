from datetime import date

from next_signal.pipeline.calculate import facts_by_entity_period, ordered_periods, run
from next_signal.pipeline.context import RunContext
from next_signal.schemas import Anchor, Fact


def make_fact(entity, period, metric, value) -> Fact:
    return Fact(
        fact_id=f"{entity}-{period}-{metric}", metric=metric, period=period, value=value, unit="INR_cr",
        anchor=Anchor(doc_id="d1", quote="some verbatim text", verified=True), entity=entity,
    )


def test_facts_by_entity_period_groups_correctly():
    facts = [make_fact("CIPLA", "Q1FY27", "revenue", 100.0), make_fact("CIPLA", "Q1FY27", "ebitda", 20.0),
             make_fact("CIPLA", "Q2FY27", "revenue", 110.0), make_fact("SUNPHARMA", "Q1FY27", "revenue", 200.0)]
    grouped = facts_by_entity_period(facts)
    assert grouped["CIPLA"]["Q1FY27"] == {"revenue": 100.0, "ebitda": 20.0}
    assert grouped["CIPLA"]["Q2FY27"] == {"revenue": 110.0}
    assert grouped["SUNPHARMA"]["Q1FY27"] == {"revenue": 200.0}


def test_ordered_periods_quarterly():
    periods = {"Q2FY26": 1, "Q1FY26": 1, "Q1FY27": 1, "Q4FY25": 1}
    assert ordered_periods(periods) == ["Q4FY25", "Q1FY26", "Q2FY26", "Q1FY27"]


def test_ordered_periods_annual():
    periods = {"FY26": 1, "FY24": 1, "FY25": 1}
    assert ordered_periods(periods) == ["FY24", "FY25", "FY26"]


def test_ordered_periods_unknown_format_falls_back_to_lexical():
    periods = {"2026-01-01": 1, "2024-06-01": 1}
    assert ordered_periods(periods) == ["2024-06-01", "2026-01-01"]


async def test_run_with_no_facts_produces_no_metrics():
    ctx = RunContext(run_id="r1", symbol="CIPLA", company="Cipla Limited", sub_industry="pharma", as_of=date(2026, 10, 15))
    await run(ctx)
    assert ctx.metrics == []
    assert ctx.anomalies == []
    assert ctx.trace[-1]["stage"] == "calculate"


async def test_run_computes_a_lagged_metric_from_raw_items_across_periods():
    # Facts now carry raw line-item names (revenue), not pre-lagged registry input names
    # (revenue_t/revenue_t_minus_4q): the series adapter resolves the lag by calendar, across the real
    # per-period revenue facts below, the same way a live XBRL-sourced run would.
    ctx = RunContext(run_id="r2", symbol="CIPLA", company="Cipla Limited", sub_industry="pharma", as_of=date(2026, 10, 15))
    periods = [f"Q{i % 4 + 1}FY{25 + i // 4}" for i in range(8)]
    ctx.facts = [make_fact("CIPLA", p, "revenue", 100.0 + i * 5) for i, p in enumerate(periods)]
    await run(ctx)
    assert any(m.metric_id == "rev_yoy" for m in ctx.metrics)
    assert ctx.trace[-1]["metrics_computed"] == len(ctx.metrics)


async def test_run_flags_anomaly_with_peer_z_on_divergent_series():
    # Peers now also need raw revenue/cogs facts: their gross_margin is computed the same way the
    # subject's is, through compute_metric_series, not looked up as if a Fact had already been tagged
    # with the registry's own metric id (which nothing in the real pipeline ever does for a peer).
    ctx = RunContext(run_id="r3", symbol="CIPLA", company="Cipla Limited", sub_industry="pharma",
                     as_of=date(2026, 10, 15), peers=["SUNPHARMA", "DRREDDY", "APOLLOHOSP"])
    periods = [f"Q{i % 4 + 1}FY{25 + i // 4}" for i in range(8)]
    subject_facts = []
    for i, p in enumerate(periods):
        subject_facts.append(make_fact("CIPLA", p, "revenue", 100.0))
        subject_facts.append(make_fact("CIPLA", p, "cogs", 60.0 - i * 2))  # gross_margin rises each period
    peer_facts = []
    for peer, cogs in [("SUNPHARMA", 60.0), ("DRREDDY", 59.0), ("APOLLOHOSP", 61.0)]:
        peer_facts.append(make_fact(peer, periods[-1], "revenue", 100.0))
        peer_facts.append(make_fact(peer, periods[-1], "cogs", cogs))
    ctx.facts = subject_facts + peer_facts
    await run(ctx)
    gm_anomaly = next((a for a in ctx.anomalies if a.metric_id == "gross_margin"), None)
    assert gm_anomaly is not None
    assert gm_anomaly.peer_z is not None
    assert gm_anomaly.score > 0
    assert gm_anomaly.materiality_pct == 100.0  # a margin metric touches the whole of revenue
