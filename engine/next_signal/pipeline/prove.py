"""Prove stage: pick the surviving hypothesis to report, grade its Evidence Strength, build its
Falsification Condition, and assemble the final Discovery (PLAN.md §5.12). The LLM only supplies prose
(DiscoveryText: sentence, why_it_matters, claims, counterargument) and every sentence it writes must pass
llm/guards.py before use; on failure (or if the LLM is not wired, which it is not yet) Prove falls back to
a deterministic template built straight from the hypothesis, never a fabricated narrative.
"""
from __future__ import annotations

from datetime import date, datetime, timedelta
from typing import Awaitable, Callable, Optional

from ..events import bus
from ..grading.independence import independent_origins
from ..grading.strength import strength
from .. import plain
from ..http import get_client
from ..llm import guards
from ..llm.router import llm_json
from ..metrics.periods import period_sort_key
from ..schemas import (
    Anomaly,
    Discovery,
    DiscoveryText,
    EvidenceItem,
    Falsification,
    Hypothesis,
    NumberBlock,
    StrengthBreakdown,
    TimelinePoint,
)
from .context import RunContext

_SYSTEM_PROMPT = (
    "Use only the data provided. Never compute new numbers; copy numbers exactly as given, using the "
    "exact display string provided for each number, not a reformatted version of it. Never give "
    "investment advice: never write \"buy\", \"sell\", \"hold\", a price target, \"undervalued\", "
    "\"overvalued\", or any recommendation. Plain English, no dashes, no exclamation marks, no "
    "rhetorical questions, no hooks. State the finding directly in the first sentence of everything you "
    "write; do not build up to it.\n\n"
    "You are writing the final discovery for a Track D research run, in exactly this shape:\n"
    "1. A single sentence (at most 45 words) stating the discovery plainly, with at least one number "
    "from the Numbers list, worded as a complete, declarative finding, not a topic label.\n"
    "2. 3 to 5 bullets explaining why this matters, each one sentence, each grounded in the evidence and "
    "numbers given, never introducing a new number not already provided.\n"
    "3. A set of claims, each a short, specific, cited statement.\n"
    "4. A counterargument paragraph (2 to 3 sentences) stating the rival hypothesis given to you as the "
    "strongest surviving alternative explanation, in its own terms, not dismissively.\n\n"
    "Never state a number, date, or percentage that does not appear in the Numbers list, the Evidence "
    "quotes, or the Timeline you were given."
)

ScoreFn = Callable[[Hypothesis], float]
StrengthFn = Callable[[RunContext, Hypothesis, list[EvidenceItem]], StrengthBreakdown]
FalsificationBuilder = Callable[[RunContext, Hypothesis], Falsification]
NoveltyFn = Callable[[RunContext, Hypothesis], float]
Writer = Callable[..., Awaitable[Optional[DiscoveryText]]]


def choose_discovery(hypotheses: list[Hypothesis], score_fn: ScoreFn) -> Optional[Hypothesis]:
    """Among main hypotheses (is_rival_of is None) that were not killed, pick the highest-scoring one.
    Returns None when nothing survived: an honest "no discovery survived the challenge stage" outcome is
    a legitimate result, not a failure to paper over. A hypothesis with no predictions is excluded even
    if it survived Challenge: build_falsification always reads predictions[0], and a hypothesis that
    names no checkable prediction cannot carry a falsification condition, so it cannot legitimately
    become the reported discovery."""
    survivors = [
        h for h in hypotheses
        if h.is_rival_of is None and h.status in ("survived", "downgraded") and h.predictions
    ]
    if not survivors:
        return None
    return max(survivors, key=score_fn)


def default_score(hyp: Hypothesis) -> float:
    """Live wiring ranks survivors by materiality x novelty x strength/10 against Calculate's anomaly
    table (PLAN.md §5.12.3). Not wired yet: a flat score so choose_discovery degrades to "first survivor
    found" rather than guessing at a ranking with data it does not have."""
    return 1.0


def build_falsification(
    hyp: Hypothesis, threshold: float, next_check: date, check_source: str, periods_required: int = 2
) -> Falsification:
    """Grammar: "<metric> <comparator> <threshold> for <n> consecutive periods (next check: <date>,
    source: <check_source>)". The comparator points at what would make us reconsider: if the hypothesis
    predicts the metric falls, the condition that breaks it is the metric climbing back to or past the
    pre-change level."""
    pred = hyp.predictions[0]
    if pred.direction == "down":
        comparator = ">="
    elif pred.direction == "up":
        comparator = "<="
    else:
        comparator = "=="
    statement = (
        f"{pred.metric_id} {comparator} {threshold} for {periods_required} consecutive periods "
        f"(next check: {next_check.isoformat()}, source: {check_source})"
    )
    return Falsification(
        statement=statement, metric_id=pred.metric_id, comparator=comparator, threshold=threshold,
        periods_required=periods_required, next_check=next_check, check_source=check_source,
    )


def default_falsification(ctx: RunContext, hyp: Hypothesis) -> Falsification:
    """Live wiring reads the pre-change segment mean off Calculate's change-point output and the next
    scheduled results date off NSE board-meeting filings. Not wired yet: falls back to a quarter-end plus
    45 days check date and a threshold of 0.0, which is honestly a placeholder, not a real-looking number
    (Prove's own guard would otherwise let a fabricated-looking value through silently)."""
    next_check = ctx.as_of.replace(day=1) + timedelta(days=135)
    f = build_falsification(hyp, threshold=0.0, next_check=next_check, check_source="next quarterly results")
    return f.model_copy(update={"plain": plain.falsification_plain(f, ctx.company)})


def _display(unit: str, value: float) -> str:
    """Indian-notation display string for a metric value, by unit family. Not exhaustive, covers the
    units the registry actually produces as of this writing (pct, pct_pts, days, ratio, count, beds);
    an unrecognised unit falls back to a plain number so a new metric never crashes Prove over display
    formatting, it just displays less prettily until this function is extended."""
    if unit in ("pct",):
        return f"{value * 100:.1f}%"
    if unit == "pct_pts":
        return f"{abs(value):.1f} points"
    if unit == "days":
        return f"{value:.0f} days"
    if unit in ("ratio", "count", "beds"):
        return f"{value:.2f}" if unit == "ratio" else f"{value:.0f}"
    return f"{value:.2f}"


def _metric_for_hyp(hyp: Hypothesis) -> Optional[str]:
    return hyp.predictions[0].metric_id if hyp.predictions else None


def build_evidence(ctx: RunContext, hyp: Hypothesis) -> list[EvidenceItem]:
    """One EvidenceItem per distinct Document backing a subject Fact for the hypothesis's predicted
    metric's own raw inputs (not just the metric name itself, since a derived metric like gross_margin
    has no Fact of its own; its supporting evidence is the Facts behind its inputs). Falls back to every
    document behind any of the subject's facts when the metric's own raw items cannot be matched (a
    computed ratio metric whose registry inputs are themselves derived, such as ccc), so a real discovery
    is never left with zero evidence purely because of a metric-to-raw-item naming gap."""
    from ..metrics.library import REGISTRY

    metric_id = _metric_for_hyp(hyp)
    raw_items: set[str] = set()
    if metric_id in REGISTRY:
        for name in REGISTRY[metric_id].inputs:
            for suffix in ("_t_minus_1q", "_t_minus_4q", "_t"):
                if name.endswith(suffix):
                    raw_items.add(name[: -len(suffix)])
                    break
            else:
                raw_items.add(name)

    doc_by_id = {d.doc_id: d for d in ctx.documents}
    matching_facts = [
        f for f in ctx.facts
        if f.entity == ctx.symbol and (not raw_items or f.metric in raw_items)
    ]
    seen_docs: dict[str, EvidenceItem] = {}
    for i, fact in enumerate(matching_facts):
        doc = doc_by_id.get(fact.anchor.doc_id)
        if doc is None or doc.doc_id in seen_docs:
            continue
        seen_docs[doc.doc_id] = EvidenceItem(
            ev_id=f"EV{len(seen_docs) + 1}", doc_id=doc.doc_id, title=doc.title, url=doc.url,
            publisher=doc.publisher, origin_class=doc.origin_class, reliability=doc.reliability,
            published_at=doc.published_at, supports=[hyp.hyp_id], contradicts=[], anchor=fact.anchor,
        )
    return list(seen_docs.values())[:8]


def build_numbers(ctx: RunContext, hyp: Hypothesis) -> list[NumberBlock]:
    """NumberBlocks for the predicted metric's latest value plus, when Calculate found an anomaly for it,
    the peer z-score and the change-point period as their own labelled numbers: these are exactly the
    figures the discovery sentence and why-it-matters bullets are allowed to cite (llm/guards.py reads
    them off this list), so the metric's own result must be here even before any narrative is written."""
    metric_id = _metric_for_hyp(hyp)
    if metric_id is None:
        return []
    series = sorted(
        (m for m in ctx.metrics if m.metric_id == metric_id), key=lambda m: period_sort_key(m.period)
    )
    if not series:
        return []
    latest = series[-1]
    numbers = [NumberBlock(
        number_id="N1", label=metric_id.replace("_", " "), value=latest.value, unit=latest.unit,
        period=latest.period, formula=latest.formula, inputs=latest.inputs,
        display=_display(latest.unit, latest.value),
    )]
    anomaly = next((a for a in ctx.anomalies if a.metric_id == metric_id), None)
    if anomaly is not None and anomaly.peer_z is not None:
        numbers.append(NumberBlock(
            number_id="N2", label=f"{metric_id.replace('_', ' ')}, peer z-score", value=anomaly.peer_z,
            unit="z_score", period=latest.period, formula="robust z-score against same-playbook peers",
            inputs=[], display=f"z = {anomaly.peer_z:.1f}",
        ))
    return numbers


def build_timeline(ctx: RunContext, hyp: Hypothesis) -> list[TimelinePoint]:
    """One TimelinePoint per quarter in the predicted metric's financial history, from the subject's own
    FinancialRows (already point-in-time filtered by Connect), with the change-point Calculate found for
    this metric (if any) marked. Kept to the metric's own value so the timeline reads as "what this
    number did each quarter", the minimum a Timeline needs before Connect's regulator/press events (not
    yet wired into ctx.events) can enrich it further."""
    metric_id = _metric_for_hyp(hyp)
    if metric_id is None:
        return []
    anomaly = next((a for a in ctx.anomalies if a.metric_id == metric_id), None)
    cp_period = anomaly.changepoint_period if anomaly else None
    points = []
    rows = sorted(ctx.financials, key=lambda r: r.period_end)
    # ctx.financials holds raw line items (revenue, cogs, ...), not computed metric values, so the
    # metric's own value for each period comes from ctx.metrics instead; financials only supplies the
    # calendar date (period_end) for each period label.
    metric_series = {m.period: m for m in ctx.metrics if m.metric_id == metric_id}
    for row in rows:
        mv = metric_series.get(row.period)
        if mv is None:
            continue
        points.append(TimelinePoint(
            date=row.period_end, label=f"{metric_id.replace('_', ' ')}: {_display(mv.unit, mv.value)}",
            kind="company_filing", event_id=None, is_changepoint=(row.period == cp_period),
        ))
    return points


def default_strength(ctx: RunContext, hyp: Hypothesis, evidence: Optional[list[EvidenceItem]] = None) -> StrengthBreakdown:
    """Real wiring: independent origins and source grades come from the hypothesis's own EvidenceItems
    (grading.independence counts distinct origins, collapsing multiple company filings into one "the
    company" origin per its own documented rule); tests_passed/applicable come from ctx.tests;
    persistent_periods counts how many periods after the metric's change-point kept the predicted
    direction, from the metric's own real series. corroborated_numbers stays 0 until a second, truly
    independent source for the same figure is wired (results-comparision cross-checking, not yet done),
    which is an honest gap, not a guess. single_document is true only when every evidence item traces to
    the same filing, which a real multi-quarter history makes genuinely rare."""
    evidence = evidence if evidence is not None else build_evidence(ctx, hyp)
    relevant_tests = [t for t in ctx.tests if t.hyp_id == hyp.hyp_id]
    tests_passed = sum(1 for t in relevant_tests if t.applicable and t.passed)
    tests_applicable = sum(1 for t in relevant_tests if t.applicable)

    metric_id = _metric_for_hyp(hyp)
    persistent_periods = 0
    sector_partial = False
    if metric_id is not None:
        series = sorted((m for m in ctx.metrics if m.metric_id == metric_id), key=lambda m: period_sort_key(m.period))
        anomaly = next((a for a in ctx.anomalies if a.metric_id == metric_id), None)
        direction = hyp.predictions[0].direction if hyp.predictions else None
        if anomaly is not None and anomaly.changepoint_period is not None and direction in ("up", "down"):
            idx = next((i for i, m in enumerate(series) if m.period == anomaly.changepoint_period), None)
            if idx is not None:
                pre_mean = sum(m.value for m in series[:idx]) / max(1, idx)
                post = series[idx:]
                persistent_periods = sum(1 for m in post if (m.value > pre_mean) == (direction == "up"))
        t1 = next((t for t in relevant_tests if t.test_id == "T1"), None)
        sector_partial = bool(t1 and t1.applicable and "sector-wide=True" in t1.detail)

    doc_ids = {e.doc_id for e in evidence}
    return strength(
        independent_origins=independent_origins(evidence),
        grades=[e.reliability for e in evidence],
        corroborated_numbers=0, total_numbers=max(1, len(evidence)),
        tests_passed=tests_passed, tests_applicable=tests_applicable,
        persistent_periods=persistent_periods, unresolved_contradictions=len(ctx.contradictions),
        sector_partial=sector_partial, single_document=len(doc_ids) <= 1,
    )


def default_novelty(ctx: RunContext, hyp: Hypothesis) -> float:
    """Live wiring calls grading/novelty.py with GDELT mainstream-hit counts and a measured lead time.
    Not wired yet: returns 0.5 (neutral), not a flattering 1.0, so an un-evaluated discovery never claims
    more novelty than it has actually demonstrated."""
    return 0.5


def deterministic_discovery_text(hyp: Hypothesis) -> DiscoveryText:
    """Template fallback used whenever the LLM writer is unavailable or its output fails guards."""
    why = [plain.scrub_identifiers(hyp.mechanism)]
    for pred in hyp.predictions:
        why.append(plain.scrub_identifiers(
            f"The hypothesis predicts that {plain.metric_phrase(pred.metric_id)} will move {pred.direction}; "
            f"this is checked in {pred.where_to_check}."
        ))
    for d in hyp.disconfirmers:
        why.append(plain.scrub_identifiers(f"It would be contradicted by {d}."))
    why = why[:5]
    while len(why) < 3:
        why.append("This hypothesis survived the falsification battery without being killed.")
    counter = (
        "The strongest alternative explanation was not ruled out with certainty; the checks applied to "
        "it are set out in the challenge section."
    )
    return DiscoveryText(
        sentence=plain.scrub_identifiers(hyp.statement[:360]), why_it_matters=why, claims=[], counterargument=counter,
    )


def _build_writer_message(ctx: RunContext, hyp: Hypothesis, partial: Discovery, rival: Optional[Hypothesis]) -> str:
    numbers_lines = "\n".join(f"- {n.label}: {n.display} ({n.period})" for n in partial.numbers) or "(none yet)"
    evidence_lines = "\n".join(
        f'- [{e.ev_id}] {e.publisher} ({e.origin_class}, grade {e.reliability}): "{e.anchor.quote}"'
        for e in partial.evidence
    ) or "(none yet)"
    timeline_lines = "\n".join(f"- {t.date.isoformat()}: {t.label}" for t in partial.timeline) or "(none yet)"
    rival_statement = rival.statement if rival is not None else "(no distinct rival hypothesis recorded for this run)"
    return (
        f"Company: {ctx.company} ({ctx.symbol})\n"
        f"Chosen hypothesis: {hyp.statement}\n"
        f"Mechanism: {hyp.mechanism}\n\n"
        f"Numbers (use these exact display strings):\n{numbers_lines}\n\n"
        f"Evidence (with quotes):\n{evidence_lines}\n\n"
        f"Timeline:\n{timeline_lines}\n\n"
        f"Strongest surviving rival hypothesis (for the counterargument): {rival_statement}\n\n"
        "Return a JSON object matching the DiscoveryText schema."
    )


async def default_writer(ctx: RunContext, hyp: Hypothesis, partial: Optional[Discovery] = None) -> Optional[DiscoveryText]:
    """Live wiring calls llm/prompts/write_discovery.md through llm/router.py, using the same shared
    httpx client and event bus singletons pipeline/reason.py's propose_hypotheses_llm() uses. `partial`
    carries the numbers/evidence/timeline computed so far (empty lists until Connect/Calculate populate
    ctx further); the rival hypothesis is the first recorded rival of `hyp` (ctx.ach's own ranking is not
    read here yet, since real ACH ranking needs real evidence to rank against). Degrades to None (never a
    crash) on any failure, same as reason.py's proposer, so run() falls back to the deterministic
    template."""
    if partial is None:
        return None
    rival = next((r for r in ctx.hypotheses if r.is_rival_of == hyp.hyp_id), None)
    messages = [
        {"role": "system", "content": _SYSTEM_PROMPT},
        {"role": "user", "content": _build_writer_message(ctx, hyp, partial, rival)},
    ]
    try:
        return await llm_json(get_client(), bus, ctx.run_id, "write_discovery", messages, DiscoveryText, effort="medium")
    except Exception:
        return None


def validate_text(text: DiscoveryText, partial: Discovery) -> list[str]:
    """Checks every number in the LLM-authored prose against the allowed set built from the
    already-computed parts of the Discovery (numbers, evidence, timeline, strength, falsification), plus
    dash/exclamation/investment-language copy issues. Returns an empty list when the text is clean."""
    allowed = guards.allowed_numbers_from_discovery(partial)
    issues = guards.stray_numbers(text.sentence, allowed)
    for bullet in text.why_it_matters:
        issues += guards.stray_numbers(bullet, allowed)
    for claim in text.claims:
        issues += guards.stray_numbers(claim.text, allowed)
    issues += guards.copy_issues(text.sentence)
    for bullet in text.why_it_matters:
        issues += guards.copy_issues(bullet)
    return sorted(set(issues))


async def run(
    ctx: RunContext,
    score_fn: Optional[ScoreFn] = None,
    strength_fn: Optional[StrengthFn] = None,
    falsification_builder: Optional[FalsificationBuilder] = None,
    novelty_fn: Optional[NoveltyFn] = None,
    writer: Optional[Writer] = None,
) -> None:
    hyp = choose_discovery(ctx.hypotheses, score_fn or default_score)
    if hyp is None:
        ctx.discovery = None
        ctx.trace.append({"stage": "prove", "discovery": None, "reason": "no hypothesis survived Challenge"})
        return
    ctx.chosen_hyp_id = hyp.hyp_id

    evidence = build_evidence(ctx, hyp)
    numbers = build_numbers(ctx, hyp)
    timeline = build_timeline(ctx, hyp)

    sb = (strength_fn or default_strength)(ctx, hyp, evidence)
    fals = (falsification_builder or default_falsification)(ctx, hyp)
    nov = (novelty_fn or default_novelty)(ctx, hyp)

    partial = Discovery(
        sentence="", why_it_matters=["placeholder", "placeholder", "placeholder"], evidence=evidence,
        timeline=timeline, numbers=numbers, counterargument="", falsification=fals, strength=sb, claims=[],
        novelty=nov, angle_id=hyp.angle_id, hyp_id=hyp.hyp_id,
    )

    text = await (writer or default_writer)(ctx, hyp, partial)
    used_fallback = text is None
    if text is not None:
        partial = partial.model_copy(update={"counterargument": text.counterargument})
        if validate_text(text, partial):
            used_fallback = True
    if used_fallback:
        text = deterministic_discovery_text(hyp)

    ctx.discovery = Discovery(
        sentence=text.sentence, why_it_matters=text.why_it_matters, evidence=evidence, timeline=timeline,
        numbers=numbers, counterargument=text.counterargument, counter_evidence_ids=[], falsification=fals,
        strength=sb, claims=text.claims, novelty=nov, angle_id=hyp.angle_id, hyp_id=hyp.hyp_id,
    )

    ctx.trace.append({
        "stage": "prove", "discovery": hyp.hyp_id, "strength": sb.label, "strength_total": sb.total,
        "used_fallback_writer": used_fallback,
    })
