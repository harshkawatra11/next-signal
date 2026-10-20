"""Reason stage: propose hypotheses that explain the anomalies Calculate found, each as a falsifiable
prediction, then attach the standard rival explanations deterministically so Challenge always has a full
set of alternatives to test against (PLAN.md §5.10). The LLM proposes the main hypotheses; rival generation
is template-based and never touches the LLM, so it is fully deterministic and auditable.
"""
from __future__ import annotations

from typing import Awaitable, Callable, Optional

from .. import plain
from ..events import bus
from ..http import get_client
from ..llm.router import llm_json
from ..schemas import Hypotheses, Hypothesis, Prediction
from .context import RunContext

_SYSTEM_PROMPT = (
    "Use only the data provided. Never compute new numbers; copy numbers exactly as given. Never give "
    "investment advice. Plain English, no dashes, no exclamation marks, no rhetorical questions.\n\n"
    "You are forming hypotheses about what a pattern in a company's disclosed numbers and public record "
    "means. You will be given: the company's identity and sub-industry playbook, the research angles "
    "chosen for this run with their questions, a table of the top statistical anomalies found, and a "
    "timeline of regulatory, filing, market and press events.\n\n"
    "Propose at most 6 hypotheses. Each hypothesis must:\n"
    "1. Explain at least one anomaly from the table using only the data given.\n"
    "2. State a plausible mechanism in one or two sentences, referencing specific metric ids, periods "
    "and events from the data provided, never inventing a new number.\n"
    "3. List 2 to 4 predictions, each naming a metric id, a direction (up, down, flat, present, absent), "
    "and where that prediction could be checked.\n"
    "4. List 2 to 3 disconfirmers: concrete, checkable observations that, if found, would mean this "
    "hypothesis is wrong.\n\n"
    "Do not propose a hypothesis that only restates an anomaly without a mechanism. Do not state any "
    "number that is not already in the anomaly table or timeline you were given."
)

RIVAL_KINDS = ("sector", "fx", "oneoff", "accounting", "seasonal")

_RIVAL_TEMPLATES = {
    "sector": "The move in {metric} is sector-wide: peers show the same change over the same periods, "
              "not something specific to {company}.",
    "fx": "The move in {metric} is a currency effect: once translated at a constant exchange rate, "
          "the change shrinks or disappears.",
    "oneoff": "The move in {metric} is driven by a disclosed one-time item (an exceptional item, "
              "acquisition or divestment), not an ongoing change.",
    "accounting": "The move in {metric} comes from a reclassification or restatement of reporting "
                  "segments or labels, not from an underlying business change.",
    "seasonal": "The move in {metric} is seasonal: the same-quarter year-on-year comparison does not "
                "support a change in trend.",
}


def generate_rivals(hyp: Hypothesis, company: str) -> list[Hypothesis]:
    """One standard rival per kind in RIVAL_KINDS, each pointing at `hyp` via is_rival_of. The metric used
    in the rival statement is the first prediction's metric_id, since that is the number Challenge's
    deterministic tests (T1 peer, T2 FX, T3 one-off, T4 reclassification, T5 seasonality) actually check."""
    if not hyp.predictions:
        return []
    kind_words = {
        "sector": "a sector-wide move", "fx": "currency movement", "oneoff": "a one-off item",
        "accounting": "an accounting reclassification", "seasonal": "seasonality",
    }
    metric = plain.metric_phrase(hyp.predictions[0].metric_id)
    rivals = []
    for kind in RIVAL_KINDS:
        rivals.append(Hypothesis(
            hyp_id=f"{hyp.hyp_id}-R-{kind}",
            angle_id=hyp.angle_id,
            statement=_RIVAL_TEMPLATES[kind].format(metric=metric, company=company),
            mechanism=f"Standard alternative explanation ({kind_words[kind]}).",
            predictions=[],
            disconfirmers=[],
            is_rival_of=hyp.hyp_id,
            status="proposed",
        ))
    return rivals


def _build_user_message(ctx: RunContext) -> str:
    chosen = [a for a in ctx.angles_considered if a.get("chosen")]
    angle_lines = "\n".join(f"- {a['angle_id']}: {a.get('reason', '')}" for a in chosen) or "(none recorded)"

    anomaly_header = "metric_id | periods | peer_z | changepoint_period | materiality_pct | score"
    anomaly_lines = "\n".join(
        f"{a.metric_id} | peer_z={a.peer_z} | changepoint={a.changepoint_period} | "
        f"materiality={a.materiality_pct} | score={a.score}"
        for a in ctx.anomalies
    ) or "(none)"

    timeline_lines = "\n".join(
        f"{e.date.isoformat()} | {e.kind} | {e.title} | {e.origin_class}" for e in ctx.events
    ) or "(none recorded)"

    return (
        f"Company: {ctx.company} ({ctx.symbol}), playbook: {ctx.sub_industry}\n\n"
        f"Angles chosen for this run:\n{angle_lines}\n\n"
        f"Top anomalies ({anomaly_header}):\n{anomaly_lines}\n\n"
        f"Timeline (chronological):\n{timeline_lines}\n\n"
        "Management narrative claims: (not yet extracted for this run)\n\n"
        "Peer values for the same metrics: (not yet collected for this run)\n\n"
        "Return a JSON object matching the Hypotheses schema."
    )


async def propose_hypotheses_llm(ctx: RunContext) -> list[Hypothesis]:
    """Live hypothesis generation via the LLM router (PLAN.md §5.10 step 1, prompt per
    llm/prompts/hypothesise.md). Uses the shared httpx client and event bus singletons (http.get_client(),
    events.bus), the same pattern sources/nse.py's NSE class uses, so this does not need
    pipeline/run.py to inject anything. Narrative claims and peer-metric tables are not yet collected into
    ctx, so those sections of the prompt are sent as explicit "not yet collected" rather than omitted
    silently or filled with placeholder data. Degrades to no proposed hypotheses (never a crash) when
    there is nothing to reason about, or the LLM call itself fails for any reason."""
    if not ctx.anomalies:
        return []
    messages = [
        {"role": "system", "content": _SYSTEM_PROMPT},
        {"role": "user", "content": _build_user_message(ctx)},
    ]
    try:
        result = await llm_json(get_client(), bus, ctx.run_id, "hypothesise", messages, Hypotheses, effort="medium")
    except Exception:
        return []
    return [
        h.model_copy(update={
            "statement": plain.scrub_identifiers(h.statement),
            "mechanism": plain.scrub_identifiers(h.mechanism),
        })
        for h in result.items
    ]


Proposer = Callable[[RunContext], Awaitable[list[Hypothesis]]]


async def run(ctx: RunContext, propose: Optional[Proposer] = None) -> None:
    propose = propose or propose_hypotheses_llm
    main_hyps = await propose(ctx)
    all_hyps: list[Hypothesis] = []
    for h in main_hyps:
        all_hyps.append(h)
        all_hyps.extend(generate_rivals(h, ctx.company))
    ctx.hypotheses.extend(all_hyps)
    ctx.trace.append({
        "stage": "reason",
        "main_hypotheses": len(main_hyps),
        "rivals_generated": len(all_hyps) - len(main_hyps),
    })
