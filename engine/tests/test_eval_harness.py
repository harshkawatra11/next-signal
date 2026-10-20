from datetime import date

from next_signal.eval.harness import metrics_from_report, run_harness, summarize
from next_signal.schemas import (
    Anomaly,
    Discovery,
    Falsification,
    Hypothesis,
    NumberBlock,
    Report,
    RunMeta,
    StrengthBreakdown,
)


def make_meta(symbol, runtime_s=120.0, status="done", documents=5, llm_calls=0, llm_provider_mix=None):
    return RunMeta(
        run_id=f"{symbol}-1", symbol=symbol, company=f"{symbol} Ltd", sub_industry="pharma",
        as_of=date(2026, 10, 15), started_at="2026-10-15T00:00:00+00:00",
        runtime_s=runtime_s, documents=documents, status=status,
        llm_calls=llm_calls, llm_provider_mix=llm_provider_mix or {},
    )


def make_strength(label="Moderate", total=5.0):
    return StrengthBreakdown(independence=1, reliability=1.5, corroboration=1, survival=1, persistence=0.5,
                             penalties=0, total=total, label=label, reasoning=["x"])


def make_falsification():
    return Falsification(statement="x", metric_id="us_revenue", comparator=">=", threshold=0.0,
                         periods_required=2, next_check=date(2027, 1, 1), check_source="x")


def make_discovery(label="Moderate", n_numbers=2, traced_inputs=0):
    """`traced_inputs` is how many of the numbers (from the front) carry a non-empty `inputs` list, i.e.
    are traced back to a fact rather than left as a bare computed figure."""
    return Discovery(
        sentence="A discovery sentence.", why_it_matters=["a", "b", "c"], evidence=[], timeline=[],
        numbers=[NumberBlock(number_id=f"n{i}", label="x", value=1.0, unit="pct", period="Q1FY27",
                             formula="x", display="1%", inputs=["f1"] if i < traced_inputs else [])
                 for i in range(n_numbers)],
        counterargument="x", falsification=make_falsification(), strength=make_strength(label), claims=[],
        novelty=0.6, angle_id="P2",
    )


def make_anomaly(metric_id="rev_yoy", score=0.4):
    return Anomaly(anomaly_id=f"anom-{metric_id}", metric_id=metric_id, description="x", score=score)


def test_metrics_from_report_with_a_discovery():
    report = Report(
        meta=make_meta("CIPLA", llm_calls=3, llm_provider_mix={"sarvam": 2, "gemini": 1}),
        discovery=make_discovery(traced_inputs=1),
        runners_up=[Hypothesis(hyp_id="h2", angle_id="P2", statement="x", mechanism="y")],
        killed=[Hypothesis(hyp_id="h3", angle_id="P2", statement="x", mechanism="y", status="killed")],
        tests=[], ach={}, contradictions=[], documents=[], events=[], metrics=[],
        anomalies=[make_anomaly("rev_yoy"), make_anomaly("gross_margin")],
        angles_considered=[{"angle_id": "P2", "score": 0.8, "reason": "x", "chosen": True}], trace=[],
        facts_count=120,
    )
    m = metrics_from_report(report)
    assert m.symbol == "CIPLA"
    assert m.hypotheses_total == 3  # discovery + 1 runner-up + 1 killed
    assert m.killed == 1
    assert m.survived == 2
    assert m.discovery_label == "Moderate"
    assert m.numbers_total == 2
    assert m.angle_chosen == "P2"
    assert m.run_id == "CIPLA-1"
    assert m.facts_count == 120
    assert m.anomalies == 2
    assert m.numbers_traced == 1  # only one of the two numbers carries non-empty inputs
    assert m.llm_calls == 3
    assert m.llm_provider == "sarvam"  # the larger count in the provider mix


def test_metrics_from_report_with_no_discovery():
    report = Report(
        meta=make_meta("SUNPHARMA"), discovery=None, runners_up=[],
        killed=[Hypothesis(hyp_id="h1", angle_id="P2", statement="x", mechanism="y", status="killed")],
        tests=[], ach={}, contradictions=[], documents=[], events=[], metrics=[], anomalies=[],
        angles_considered=[], trace=[],
    )
    m = metrics_from_report(report)
    assert m.hypotheses_total == 1
    assert m.discovery_label is None
    assert m.numbers_total == 0
    assert m.angle_chosen is None
    assert m.facts_count == 0
    assert m.anomalies == 0
    assert m.numbers_traced == 0
    assert m.llm_calls == 0
    assert m.llm_provider == ""


def test_metrics_from_report_angle_chosen_falls_back_to_first_when_none_flagged():
    report = Report(
        meta=make_meta("DRREDDY"), discovery=None, runners_up=[], killed=[],
        tests=[], ach={}, contradictions=[], documents=[], events=[], metrics=[], anomalies=[],
        angles_considered=[{"angle_id": "P1", "score": 0.5, "reason": "x"}, {"angle_id": "P5", "score": 0.3, "reason": "y"}],
        trace=[],
    )
    m = metrics_from_report(report)
    assert m.angle_chosen == "P1"  # no entry flagged chosen, so the first one wins


async def test_run_harness_collects_all_symbols():
    reports = {
        "CIPLA": Report(meta=make_meta("CIPLA"), discovery=make_discovery(), runners_up=[], killed=[],
                        tests=[], ach={}, contradictions=[], documents=[], events=[], metrics=[],
                        anomalies=[], angles_considered=[], trace=[]),
        "SUNPHARMA": Report(meta=make_meta("SUNPHARMA"), discovery=None, runners_up=[], killed=[],
                            tests=[], ach={}, contradictions=[], documents=[], events=[], metrics=[],
                            anomalies=[], angles_considered=[], trace=[]),
    }

    async def fake_runner(symbol, as_of=None):
        return reports[symbol]

    results = await run_harness(["CIPLA", "SUNPHARMA"], fake_runner)
    assert len(results) == 2
    assert {r.symbol for r in results} == {"CIPLA", "SUNPHARMA"}


async def test_run_harness_turns_an_exception_into_a_failed_row_not_a_crash():
    async def failing_runner(symbol, as_of=None):
        raise RuntimeError("synthetic network failure")

    results = await run_harness(["BADSYMBOL"], failing_runner)
    assert len(results) == 1
    assert results[0].status == "failed"
    assert results[0].symbol == "BADSYMBOL"


def test_summarize_computes_kill_rate_and_runtime_stats():
    report_a = Report(meta=make_meta("A", runtime_s=100.0, documents=4, llm_calls=2, llm_provider_mix={"sarvam": 2}),
                      discovery=make_discovery(traced_inputs=2), runners_up=[],
                      killed=[Hypothesis(hyp_id="k1", angle_id="P2", statement="x", mechanism="y", status="killed")],
                      tests=[], ach={}, contradictions=[], documents=[], events=[], metrics=[],
                      anomalies=[make_anomaly("rev_yoy")], angles_considered=[], trace=[], facts_count=80)
    report_b = Report(meta=make_meta("B", runtime_s=200.0, documents=6, llm_calls=1, llm_provider_mix={"gemini": 1}),
                      discovery=None, runners_up=[],
                      killed=[Hypothesis(hyp_id="k2", angle_id="P2", statement="x", mechanism="y", status="killed")],
                      tests=[], ach={}, contradictions=[], documents=[], events=[], metrics=[],
                      anomalies=[], angles_considered=[], trace=[], facts_count=40)
    results = [metrics_from_report(report_a), metrics_from_report(report_b)]
    summary = summarize(results)
    assert summary["n_companies"] == 2
    assert summary["hypotheses_total"] == 3  # (discovery+killed) + killed
    assert summary["killed_total"] == 2
    assert summary["kill_rate"] == round(2 / 3, 3)
    assert summary["median_runtime_s"] == 150.0
    assert summary["share_with_discovery"] == 0.5
    assert summary["label_counts"] == {"Moderate": 1}
    assert summary["documents_median"] == 5.0
    assert summary["facts_median"] == 60.0
    assert summary["anomalies_median"] == 0.5
    assert summary["discoveries"] == 1
    assert summary["numbers_traced_share"] == 1.0  # both numbers in report_a's discovery were traced
    assert summary["llm_calls_total"] == 3
    assert summary["llm_provider_counts"] == {"sarvam": 1, "gemini": 1}


def test_summarize_handles_empty_results():
    summary = summarize([])
    assert summary["n_companies"] == 0
    assert summary["kill_rate"] == 0.0
    assert summary["median_runtime_s"] == 0.0
    assert summary["documents_median"] == 0
    assert summary["facts_median"] == 0
    assert summary["anomalies_median"] == 0
    assert summary["discoveries"] == 0
    assert summary["numbers_traced_share"] == 0.0
    assert summary["llm_calls_total"] == 0
    assert summary["llm_provider_counts"] == {}
