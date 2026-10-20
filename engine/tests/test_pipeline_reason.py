import json
from datetime import date

import respx
from httpx import Response

from next_signal.pipeline.context import RunContext
from next_signal.pipeline.reason import RIVAL_KINDS, generate_rivals, propose_hypotheses_llm, run
from next_signal.schemas import Anomaly, Hypothesis, Prediction


def make_hyp(hyp_id="h1", metric="us_revenue"):
    return Hypothesis(
        hyp_id=hyp_id, angle_id="P2", statement="North America revenue fell because of a compliance issue.",
        mechanism="A partner site's FDA status disrupted supply.",
        predictions=[Prediction(metric_id=metric, direction="down", where_to_check="investor presentation")],
        disconfirmers=["peers show the same decline"],
    )


def test_generate_rivals_produces_one_per_kind():
    hyp = make_hyp()
    rivals = generate_rivals(hyp, "Cipla Limited")
    assert len(rivals) == len(RIVAL_KINDS)
    assert all(r.is_rival_of == "h1" for r in rivals)
    assert all(r.hyp_id.startswith("h1-R-") for r in rivals)
    assert {r.hyp_id.split("-R-")[1] for r in rivals} == set(RIVAL_KINDS)


def test_generate_rivals_statement_mentions_the_metric():
    hyp = make_hyp(metric="us_revenue")
    rivals = generate_rivals(hyp, "Cipla Limited")
    assert all("_" not in r.statement for r in rivals)
    assert all("us revenue" in r.statement for r in rivals)


def test_generate_rivals_empty_without_predictions():
    hyp = Hypothesis(hyp_id="h2", angle_id="P2", statement="x", mechanism="y")
    assert generate_rivals(hyp, "Cipla Limited") == []


async def test_propose_hypotheses_llm_returns_empty_without_anomalies():
    ctx = RunContext(run_id="r1", symbol="CIPLA", company="Cipla Limited", sub_industry="pharma", as_of=date(2026, 10, 15))
    assert await propose_hypotheses_llm(ctx) == []


async def test_run_with_no_proposer_degrades_honestly():
    ctx = RunContext(run_id="r2", symbol="CIPLA", company="Cipla Limited", sub_industry="pharma", as_of=date(2026, 10, 15))
    await run(ctx)
    assert ctx.hypotheses == []
    assert ctx.trace[-1]["stage"] == "reason"
    assert ctx.trace[-1]["main_hypotheses"] == 0


@respx.mock
async def test_propose_hypotheses_llm_calls_sarvam_and_parses_result():
    ctx = RunContext(run_id="r4", symbol="CIPLA", company="Cipla Limited", sub_industry="pharma", as_of=date(2026, 10, 15))
    ctx.anomalies = [Anomaly(anomaly_id="a1", metric_id="us_revenue", description="drop", score=0.8, peer_z=-2.1)]
    ctx.angles_considered = [{"angle_id": "P2", "score": 0.8, "reason": "compliance angle", "chosen": True}]

    sarvam_payload = {
        "items": [{
            "hyp_id": "h1", "angle_id": "P2",
            "statement": "North America revenue fell because of a partner site compliance issue.",
            "mechanism": "A partner manufacturing site lost FDA good standing, disrupting supply.",
            "predictions": [{"metric_id": "us_revenue", "direction": "down", "where_to_check": "investor presentation"}],
            "disconfirmers": ["peers show the same decline in the same quarter"],
        }]
    }
    route = respx.post("https://api.sarvam.ai/v1/chat/completions").mock(
        return_value=Response(200, json={
            "choices": [{"message": {"content": json.dumps(sarvam_payload)}}], "usage": {},
        })
    )

    result = await propose_hypotheses_llm(ctx)
    assert route.called
    assert len(result) == 1
    assert result[0].hyp_id == "h1"
    assert result[0].predictions[0].metric_id == "us_revenue"
    sent_body = json.loads(route.calls[0].request.content)
    assert "CIPLA" in sent_body["messages"][1]["content"]
    assert "us_revenue" in sent_body["messages"][1]["content"]


@respx.mock
async def test_propose_hypotheses_llm_degrades_on_api_failure():
    ctx = RunContext(run_id="r5", symbol="CIPLA", company="Cipla Limited", sub_industry="pharma", as_of=date(2026, 10, 15))
    ctx.anomalies = [Anomaly(anomaly_id="a1", metric_id="us_revenue", description="drop", score=0.8)]
    respx.post("https://api.sarvam.ai/v1/chat/completions").mock(return_value=Response(500))
    respx.post("https://generativelanguage.googleapis.com/v1beta/models/gemini-3.5-flash-lite:generateContent").mock(
        return_value=Response(500)
    )
    assert await propose_hypotheses_llm(ctx) == []


async def test_run_with_injected_proposer_attaches_rivals():
    ctx = RunContext(run_id="r3", symbol="CIPLA", company="Cipla Limited", sub_industry="pharma", as_of=date(2026, 10, 15))
    ctx.anomalies = [Anomaly(anomaly_id="a1", metric_id="us_revenue", description="drop", score=0.8)]

    async def fake_propose(c):
        return [make_hyp()]

    await run(ctx, propose=fake_propose)
    assert ctx.trace[-1]["main_hypotheses"] == 1
    assert ctx.trace[-1]["rivals_generated"] == len(RIVAL_KINDS)
    assert len(ctx.hypotheses) == 1 + len(RIVAL_KINDS)
    main = [h for h in ctx.hypotheses if h.hyp_id == "h1"]
    assert len(main) == 1
