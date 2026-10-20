"""Discover stage: pick the playbook's angles worth investigating for this company, using a quick,
cheap first pass of data (not the full Connect fetch) to estimate data availability and anomaly signal
before committing to the expensive per-angle document fetch (PLAN.md §5.7).
"""
from __future__ import annotations

from .. import plain
from ..playbooks.angles import PLAYBOOKS
from ..playbooks.select import score_angle, select_angles
from .context import RunContext


async def quickpass_metrics(ctx: RunContext) -> dict[str, list[float]]:
    """Cheap first-pass data: screener ratios + results-comparison, already period-indexed.
    Returns {metric_id: [period values, oldest to newest]}. Stubbed to an empty dict until
    sources/screener.py is wired; callers must handle missing keys gracefully (angle scoring already
    does, via a 0.0 data_availability default).
    """
    return {}


def angle_data_availability(angle_metrics: tuple[str, ...], series: dict[str, list[float]]) -> float:
    if not angle_metrics:
        return 0.5  # an angle with no numeric metrics (narrative-only) gets a neutral default
    have = sum(1 for m in angle_metrics if len(series.get(m, [])) >= 6)
    return have / len(angle_metrics)


def angle_anomaly_signal(angle_metrics: tuple[str, ...], series: dict[str, list[float]]) -> float:
    """Placeholder until metrics/changepoint.py and metrics/peers.py are wired against real per-period
    data here; returns 0.0 (no signal) rather than fabricating a score. Once Calculate has run, this
    should read anomalies already computed into ctx.anomalies instead of recomputing."""
    return 0.0


def angle_novelty_prior(angle_id: str, mainstream_hits_90d: int) -> float:
    return max(0.0, 1.0 - min(1.0, mainstream_hits_90d / 20))


def angle_reason_plain(angle_metrics: tuple[str, ...], series: dict[str, list[float]], ctx: RunContext) -> str:
    """Plain-language reason for why this angle was or was not chosen, read by the paper and the web UI
    in place of the raw data-availability/anomaly-signal/novelty-prior breakdown. Never mentions a
    metric id, a score, or the word "angle" itself."""
    need = len(angle_metrics)
    if need == 0:
        return "This question is narrative rather than numeric, so no measure count applies."
    have = sum(1 for m in angle_metrics if len(series.get(m, [])) >= 8)
    text = f"{have} of the {need} measures this question needs have at least eight quarters of data."
    for m in angle_metrics:
        an = next((a for a in ctx.anomalies if a.metric_id == m and a.changepoint_period), None)
        if an is not None:
            text += f" The clearest break is in {plain.metric_phrase(m)}, in {plain.period_phrase(an.changepoint_period)}."
            break
    return text


async def run(ctx: RunContext) -> None:
    angles = PLAYBOOKS.get(ctx.sub_industry, PLAYBOOKS["generic"])
    series = await quickpass_metrics(ctx)

    scores = {}
    for angle in angles:
        da = angle_data_availability(angle.metrics, series)
        anom = angle_anomaly_signal(angle.metrics, series)
        novelty = angle_novelty_prior(angle.angle_id, mainstream_hits_90d=0)  # GDELT wiring comes with Connect
        scores[angle.angle_id] = score_angle(angle, da, anom, novelty)

    chosen = select_angles(ctx.sub_industry, list(angles), scores, top_n=4)
    angle_by_id = {a.angle_id: a for a in angles}
    ctx.angles_considered = [
        {
            "angle_id": s.angle_id, "score": round(s.score, 3),
            "reason": angle_reason_plain(angle_by_id[s.angle_id].metrics, series, ctx),
            "chosen": s in chosen,
        }
        for s in scores.values()
    ]
    ctx.trace.append({"stage": "discover", "chosen_angles": [c.angle_id for c in chosen]})
