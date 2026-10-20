from datetime import date

import respx

from next_signal.pipeline.context import RunContext
from next_signal.pipeline.prove import (
    build_falsification,
    choose_discovery,
    deterministic_discovery_text,
    run,
    validate_text,
)
from next_signal.schemas import Discovery, DiscoveryText, Falsification, Hypothesis, Prediction
from next_signal.schemas import TestResult as StageTestResult


def make_hyp(hyp_id="h1", status="survived", is_rival_of=None):
    return Hypothesis(
        hyp_id=hyp_id, angle_id="P2", statement="North America revenue fell for a company-specific reason.",
        mechanism="partner site compliance issue", status=status, is_rival_of=is_rival_of,
        predictions=[Prediction(metric_id="us_revenue", direction="down", where_to_check="presentation")],
        disconfirmers=["peers show the same decline"],
    )


def test_choose_discovery_returns_none_without_survivors():
    hyps = [make_hyp("h1", status="killed"), make_hyp("h2", status="killed", is_rival_of="h1")]
    assert choose_discovery(hyps, lambda h: 1.0) is None


def test_choose_discovery_ignores_rivals():
    hyps = [make_hyp("h1", status="survived"), make_hyp("h2", status="survived", is_rival_of="h1")]
    chosen = choose_discovery(hyps, lambda h: 1.0)
    assert chosen.hyp_id == "h1"


def test_choose_discovery_picks_highest_score():
    hyps = [make_hyp("h1", status="survived"), make_hyp("h2", status="downgraded")]
    chosen = choose_discovery(hyps, lambda h: 5.0 if h.hyp_id == "h2" else 1.0)
    assert chosen.hyp_id == "h2"


def test_build_falsification_down_direction_uses_gte_comparator():
    hyp = make_hyp()
    fals = build_falsification(hyp, threshold=150.0, next_check=date(2027, 1, 20), check_source="Q2 FY27 results")
    assert fals.comparator == ">="
    assert fals.metric_id == "us_revenue"
    assert "150.0" in fals.statement or "150" in fals.statement
    assert "2027-01-20" in fals.statement


def test_build_falsification_up_direction_uses_lte_comparator():
    hyp = make_hyp()
    hyp.predictions[0].direction = "up"
    fals = build_falsification(hyp, threshold=10.0, next_check=date(2027, 1, 20), check_source="x")
    assert fals.comparator == "<="


def test_deterministic_discovery_text_has_at_least_three_bullets():
    hyp = make_hyp()
    text = deterministic_discovery_text(hyp)
    assert 3 <= len(text.why_it_matters) <= 5
    assert text.sentence == hyp.statement


def test_validate_text_flags_stray_number():
    hyp = make_hyp()
    text = DiscoveryText(sentence="Revenue fell by 47 percent, a figure not computed anywhere.",
                         why_it_matters=["a", "b", "c"], claims=[], counterargument="no numbers here")
    fals = Falsification(statement="x", metric_id="us_revenue", comparator=">=", threshold=0.0,
                         periods_required=2, next_check=date(2027, 1, 1), check_source="x")
    from next_signal.grading.strength import strength
    sb = strength(0, [], 0, 0, 0, 0, 0, 0, False, True)
    partial = Discovery(sentence="", why_it_matters=["x", "y", "z"], evidence=[], timeline=[], numbers=[],
                        counterargument="", falsification=fals, strength=sb, claims=[], novelty=0.5, angle_id="P2")
    issues = validate_text(text, partial)
    assert "47" in issues


def test_validate_text_clean_text_has_no_issues():
    hyp = make_hyp()
    text = deterministic_discovery_text(hyp)
    fals = Falsification(statement="x", metric_id="us_revenue", comparator=">=", threshold=0.0,
                         periods_required=2, next_check=date(2027, 1, 1), check_source="x")
    from next_signal.grading.strength import strength
    sb = strength(0, [], 0, 0, 0, 0, 0, 0, False, True)
    partial = Discovery(sentence="", why_it_matters=["x", "y", "z"], evidence=[], timeline=[], numbers=[],
                        counterargument=text.counterargument, falsification=fals, strength=sb, claims=[],
                        novelty=0.5, angle_id="P2")
    assert validate_text(text, partial) == []


async def test_run_returns_no_discovery_when_nothing_survives():
    ctx = RunContext(run_id="r1", symbol="CIPLA", company="Cipla Limited", sub_industry="pharma", as_of=date(2026, 10, 15))
    ctx.hypotheses = [make_hyp("h1", status="killed")]
    await run(ctx)
    assert ctx.discovery is None
    assert ctx.trace[-1]["discovery"] is None


@respx.mock
async def test_run_builds_discovery_from_survivor_with_fallback_writer():
    # No route registered: any network call default_writer attempts raises inside respx's mock context,
    # which default_writer catches and turns into a None return, exercising the real fallback path
    # without ever making a real network call.
    ctx = RunContext(run_id="r2", symbol="CIPLA", company="Cipla Limited", sub_industry="pharma", as_of=date(2026, 10, 15))
    ctx.hypotheses = [make_hyp("h1", status="survived")]
    ctx.tests = [StageTestResult(hyp_id="h1", test_id="T6", applicable=True, passed=True, detail="x")]
    await run(ctx)
    assert ctx.discovery is not None
    assert ctx.discovery.strength.label == "Weak"  # default_strength floors at Weak (single_document=True stub)
    assert ctx.trace[-1]["used_fallback_writer"] is True
    assert ctx.trace[-1]["discovery"] == "h1"


async def test_run_uses_injected_writer_when_clean():
    ctx = RunContext(run_id="r3", symbol="CIPLA", company="Cipla Limited", sub_industry="pharma", as_of=date(2026, 10, 15))
    ctx.hypotheses = [make_hyp("h1", status="survived")]

    async def clean_writer(c, h, partial):
        return DiscoveryText(sentence="A clean sentence with no stray numbers.",
                             why_it_matters=["a", "b", "c"], claims=[], counterargument="no numbers here")

    await run(ctx, writer=clean_writer)
    assert ctx.discovery.sentence == "A clean sentence with no stray numbers."
    assert ctx.trace[-1]["used_fallback_writer"] is False


async def test_run_falls_back_when_injected_writer_output_is_dirty():
    ctx = RunContext(run_id="r4", symbol="CIPLA", company="Cipla Limited", sub_industry="pharma", as_of=date(2026, 10, 15))
    ctx.hypotheses = [make_hyp("h1", status="survived")]

    async def dirty_writer(c, h, partial):
        return DiscoveryText(sentence="Revenue fell by 999 percent, an invented figure.",
                             why_it_matters=["a", "b", "c"], claims=[], counterargument="no numbers here")

    await run(ctx, writer=dirty_writer)
    assert ctx.discovery.sentence == make_hyp().statement
    assert ctx.trace[-1]["used_fallback_writer"] is True


@respx.mock
async def test_default_writer_calls_sarvam_and_parses_result():
    import json

    from httpx import Response

    from next_signal.grading.strength import strength as compute_strength
    from next_signal.pipeline.prove import default_writer

    ctx = RunContext(run_id="r6", symbol="CIPLA", company="Cipla Limited", sub_industry="pharma", as_of=date(2026, 10, 15))
    hyp = make_hyp("h1")
    ctx.hypotheses = [hyp]
    sb = compute_strength(0, [], 0, 0, 0, 0, 0, 0, False, True)
    fals = Falsification(statement="x", metric_id="us_revenue", comparator=">=", threshold=0.0,
                         periods_required=2, next_check=date(2027, 1, 1), check_source="x")
    partial = Discovery(sentence="", why_it_matters=["a", "b", "c"], evidence=[], timeline=[], numbers=[],
                        counterargument="", falsification=fals, strength=sb, claims=[], novelty=0.5, angle_id="P2")

    sarvam_payload = {
        "sentence": "North America revenue fell for a company-specific reason.",
        "why_it_matters": ["a", "b", "c"], "claims": [], "counterargument": "no numbers here",
    }
    route = respx.post("https://api.sarvam.ai/v1/chat/completions").mock(
        return_value=Response(200, json={"choices": [{"message": {"content": json.dumps(sarvam_payload)}}], "usage": {}})
    )

    result = await default_writer(ctx, hyp, partial)
    assert route.called
    assert result is not None
    assert result.sentence == sarvam_payload["sentence"]
