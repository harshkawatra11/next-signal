"""Calculate stage: turn verified Facts into MetricValues, peer z-scores, change-points and anomalies
(PLAN.md §5.9). Every number here traces to a Fact's quote-anchored source; the LLM is never involved.
"""
from __future__ import annotations

from collections import defaultdict

from ..metrics.changepoint import best_changepoint
from ..metrics.library import REGISTRY, compute
from ..metrics.peers import robust_z
from ..metrics.periods import period_sort_key
from ..metrics.series import resolve_inputs, with_derived_items
from ..schemas import Anomaly, Fact, MetricValue
from .context import RunContext


def facts_by_entity_period(facts: list[Fact]) -> dict[str, dict[str, dict[str, float]]]:
    """{entity: {period: {raw_item: value}}}. One value per (entity, period, raw_item); if a raw item has
    multiple facts for the same period (should not happen after Connect's dedup), the last one wins and
    this is intentionally permissive rather than crashing a run over a data-quality edge case."""
    out: dict[str, dict[str, dict[str, float]]] = defaultdict(lambda: defaultdict(dict))
    for f in facts:
        out[f.entity][f.period][f.metric] = f.value
    return out


def ordered_periods(period_values) -> list[str]:
    """Chronological sort over any iterable of period strings, via metrics.periods.period_sort_key."""
    return sorted(period_values, key=period_sort_key)


def compute_metric_series(raw_by_period: dict[str, dict[str, float]]) -> dict[str, dict[str, float]]:
    """raw_by_period: one entity's {period: {raw_item: value}}, as produced by facts_by_entity_period for
    that entity. Returns {period: {metric_id: value}}: every registry metric computed for every period it
    has enough resolved inputs for, including period-relative (lagged) ones, via metrics.series. This is
    the function both the subject and each peer are run through, so a peer's own computed values (not its
    raw facts looked up under a metric_id that was never actually assigned to them) back the z-score."""
    with_derived = with_derived_items(raw_by_period)
    out: dict[str, dict[str, float]] = defaultdict(dict)
    for period in with_derived:
        for metric_id, metric in REGISTRY.items():
            inputs = resolve_inputs(with_derived, period, metric.inputs)
            if inputs is None:
                continue
            value = compute(metric_id, inputs)
            if value is None:
                continue
            out[period][metric_id] = value
    return out


async def run(ctx: RunContext) -> None:
    grouped = facts_by_entity_period(_facts_from_trace(ctx))
    subject_raw = grouped.get(ctx.symbol, {})
    subject_metrics = compute_metric_series(subject_raw)

    peer_metrics: dict[str, dict[str, dict[str, float]]] = {
        peer: compute_metric_series(grouped.get(peer, {})) for peer in ctx.peers
    }

    metrics_out: list[MetricValue] = []
    with_derived_subject = with_derived_items(subject_raw)
    for period, by_metric in subject_metrics.items():
        for metric_id, value in by_metric.items():
            metric = REGISTRY[metric_id]
            inputs = resolve_inputs(with_derived_subject, period, metric.inputs) or {}
            metrics_out.append(MetricValue(
                metric_id=metric_id, period=period, value=value, unit=metric.unit,
                inputs=[f"{ctx.symbol}:{period}:{k}" for k in inputs], formula=metric.formula_text,
            ))
    ctx.metrics = metrics_out
    ctx.peer_metrics = peer_metrics

    anomalies: list[Anomaly] = []
    by_metric_series: dict[str, list[tuple[str, float]]] = defaultdict(list)
    for m in metrics_out:
        by_metric_series[m.metric_id].append((m.period, m.value))

    for metric_id, series in by_metric_series.items():
        if len(series) < 4:
            continue
        periods = ordered_periods([p for p, _ in series])
        value_by_period = dict(series)
        ordered_values = [value_by_period[p] for p in periods]
        latest_period = periods[-1]

        peer_values = [
            peer_metrics.get(peer_symbol, {}).get(latest_period, {}).get(metric_id)
            for peer_symbol in ctx.peers
        ]
        peer_values = [v for v in peer_values if v is not None]
        z = robust_z(ordered_values[-1], peer_values) if len(peer_values) >= 3 else None

        cp_idx, cp_strength = best_changepoint(ordered_values)
        cp_period = periods[cp_idx] if cp_idx is not None else None

        n = len(ordered_values)
        trend_t = None
        if n >= 4:
            import numpy as np

            x = np.arange(n, dtype=float)
            y = np.asarray(ordered_values, dtype=float)
            slope, intercept = np.polyfit(x, y, 1)
            resid = y - (slope * x + intercept)
            se = float(resid.std(ddof=2)) / (float(x.std()) * (n ** 0.5)) if n > 2 and x.std() > 0 else None
            trend_t = (slope / se) if se and se > 0 else None

        materiality_pct = _materiality_pct(metric_id, subject_raw.get(latest_period, {}), with_derived_subject.get(latest_period, {}))

        score = 0.4 * min(1.0, abs(z) / 3 if z is not None else 0.0)
        score += 0.35 * cp_strength
        score += 0.25 * min(1.0, abs(trend_t) / 4 if trend_t is not None else 0.0)

        if score >= 0.30:
            anomalies.append(Anomaly(
                anomaly_id=f"anom-{metric_id}-{latest_period}", metric_id=metric_id,
                description=f"{metric_id} shows a score of {score:.2f} (peer z={z}, change-point={cp_period}, trend t={trend_t})",
                peer_z=z, changepoint_period=cp_period, trend_t=trend_t, materiality_pct=materiality_pct,
                score=round(score, 3),
            ))

    anomalies.sort(key=lambda a: a.score, reverse=True)
    ctx.anomalies = anomalies[:12]
    ctx.trace.append({"stage": "calculate", "metrics_computed": len(metrics_out), "anomalies_found": len(anomalies)})


_MARGIN_METRICS = {"gross_margin", "ebitda_margin", "pat_margin", "etr"}


def _materiality_pct(metric_id: str, raw: dict[str, float], derived: dict[str, float]) -> float | None:
    """How much of the subject's business this metric's latest value touches, as a revenue-relative
    percentage: a margin metric already describes 100% of revenue by construction; a specific line item
    (other income, exceptional items) is sized against the same period's revenue. Returns None when
    revenue for the period is unknown, rather than guessing."""
    if metric_id in _MARGIN_METRICS:
        return 100.0
    revenue = raw.get("revenue") or derived.get("revenue")
    if not revenue:
        return None
    for item in ("other_income", "exceptional_items", "tax_expense"):
        if metric_id.startswith(item):
            value = raw.get(item)
            if value is not None:
                return round(abs(value) / revenue * 100.0, 1)
    return None


def _facts_from_trace(ctx: RunContext) -> list[Fact]:
    """ctx.facts is populated by Connect once sources/docs wiring runs; an empty list here means
    Calculate degrades to zero metrics rather than crashing, keeping the pipeline runnable end to end for
    testing the other stages."""
    return getattr(ctx, "facts", [])
