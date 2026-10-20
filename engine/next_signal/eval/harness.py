"""Evaluation harness: runs the pipeline against the Track D company set (NIFTY 50 + tie-break) and
collects per-run metrics, the only legitimate source for every evaluation number that appears anywhere in
the deck, the Round 1 PDF, or the research document's {{EVAL:...}} placeholders (PLAN.md §5.14). The
runner callable is injected so this module, and every number it produces, is testable without a live
engine run; `live_runner` wires a real one once the orchestrator's source/LLM dependencies are filled in
further.
"""
from __future__ import annotations

import statistics
from dataclasses import dataclass
from typing import Awaitable, Callable, Optional

from .. import universe
from ..pipeline.context import RunContext
from ..pipeline.resolve import run as resolve_run
from ..pipeline.run import drive
from ..schemas import Report


@dataclass
class RunMetrics:
    symbol: str
    company: str
    runtime_s: float
    status: str
    documents: int
    hypotheses_total: int
    killed: int
    survived: int
    discovery_label: Optional[str]
    strength_total: Optional[float]
    novelty: Optional[float]
    numbers_total: int
    contradictions_found: int
    angle_chosen: Optional[str]
    run_id: str = ""
    facts_count: int = 0
    anomalies: int = 0
    numbers_traced: int = 0
    llm_calls: int = 0
    llm_provider: str = ""


async def company_set(uni: Optional[dict] = None, tb_limit: int = 10) -> tuple[list, list]:
    """Returns (n50_rows, tiebreak_rows). Both lists are of universe.UniverseRow; callers typically only
    need their .symbol field. Deterministic given the live index CSVs: no hand-picked company list."""
    universe_data = uni if uni is not None else await universe.load_universe()
    n50 = universe.track_d_n50(universe_data)
    tb = universe.track_d_tiebreak(universe_data, limit=tb_limit)
    return n50, tb


def metrics_from_report(report: Report) -> RunMetrics:
    """hypotheses_total counts every hypothesis the run considered: the ones killed, the runners-up that
    survived but were not chosen, and the chosen discovery itself (not otherwise listed separately in
    Report, since `discovery` is prose built from the winning hypothesis, not the hypothesis object)."""
    hypotheses_total = len(report.killed) + len(report.runners_up) + (1 if report.discovery else 0)
    angle_chosen = next((a["angle_id"] for a in report.angles_considered if a.get("chosen")), None)
    if angle_chosen is None and report.angles_considered:
        angle_chosen = report.angles_considered[0]["angle_id"]
    numbers_traced = (
        sum(1 for n in report.discovery.numbers if n.inputs) if report.discovery else 0
    )
    provider_mix = report.meta.llm_provider_mix or {}
    llm_provider = max(provider_mix, key=provider_mix.get) if provider_mix else ""
    return RunMetrics(
        symbol=report.meta.symbol,
        company=report.meta.company,
        runtime_s=report.meta.runtime_s or 0.0,
        status=report.meta.status,
        documents=report.meta.documents,
        hypotheses_total=hypotheses_total,
        killed=len(report.killed),
        survived=len(report.runners_up) + (1 if report.discovery else 0),
        discovery_label=report.discovery.strength.label if report.discovery else None,
        strength_total=report.discovery.strength.total if report.discovery else None,
        novelty=report.discovery.novelty if report.discovery else None,
        numbers_total=len(report.discovery.numbers) if report.discovery else 0,
        contradictions_found=len(report.contradictions),
        angle_chosen=angle_chosen,
        run_id=report.meta.run_id,
        facts_count=report.facts_count,
        anomalies=len(report.anomalies),
        numbers_traced=numbers_traced,
        llm_calls=report.meta.llm_calls,
        llm_provider=llm_provider,
    )


def _failed_metrics(symbol: str) -> RunMetrics:
    return RunMetrics(
        symbol=symbol, company=symbol, runtime_s=0.0, status="failed", documents=0, hypotheses_total=0,
        killed=0, survived=0, discovery_label=None, strength_total=None, novelty=None, numbers_total=0,
        contradictions_found=0, angle_chosen=None,
        run_id="", facts_count=0, anomalies=0, numbers_traced=0, llm_calls=0, llm_provider="",
    )


Runner = Callable[[str, Optional[str]], Awaitable[Report]]


async def run_harness(symbols: list[str], runner: Runner, as_of: Optional[str] = None) -> list[RunMetrics]:
    """A symbol whose runner call raises becomes an honest status="failed" row rather than aborting the
    whole harness run: one broken company should never block the other N minus one results."""
    results = []
    for symbol in symbols:
        try:
            report = await runner(symbol, as_of)
            results.append(metrics_from_report(report))
        except Exception:
            results.append(_failed_metrics(symbol))
    return results


async def live_runner(symbol: str, as_of: Optional[str] = None) -> Report:
    """Wires a real run through resolve + drive. Not exercised by this module's own tests (it needs a
    live universe fetch and the engine's still-partial source/LLM wiring); `scripts/run_one.py` and
    `eval/summarize.py`'s CLI entry point are the intended callers once that wiring is further along."""
    ctx = await resolve_run(symbol, as_of)
    await drive(ctx)
    return ctx.to_report(runtime_s=0.0)


def summarize(results: list[RunMetrics]) -> dict:
    n = len(results)
    hyp_total = sum(r.hypotheses_total for r in results)
    killed_total = sum(r.killed for r in results)
    runtimes = [r.runtime_s for r in results]
    documents = [r.documents for r in results]
    facts = [r.facts_count for r in results]
    anomalies = [r.anomalies for r in results]
    numbers_total = sum(r.numbers_total for r in results)
    numbers_traced = sum(r.numbers_traced for r in results)
    label_counts: dict[str, int] = {}
    llm_provider_counts: dict[str, int] = {}
    for r in results:
        if r.discovery_label:
            label_counts[r.discovery_label] = label_counts.get(r.discovery_label, 0) + 1
        if r.llm_provider:
            llm_provider_counts[r.llm_provider] = llm_provider_counts.get(r.llm_provider, 0) + 1
    return {
        "n_companies": n,
        "hypotheses_total": hyp_total,
        "killed_total": killed_total,
        "kill_rate": round(killed_total / hyp_total, 3) if hyp_total else 0.0,
        "median_runtime_s": round(statistics.median(runtimes), 1) if runtimes else 0.0,
        "p90_runtime_s": round(_percentile(runtimes, 0.9), 1) if runtimes else 0.0,
        "share_with_discovery": round(sum(1 for r in results if r.discovery_label is not None) / n, 3) if n else 0.0,
        "label_counts": label_counts,
        "failed": sum(1 for r in results if r.status == "failed"),
        "documents_median": round(statistics.median(documents), 1) if documents else 0,
        "facts_median": round(statistics.median(facts), 1) if facts else 0,
        "anomalies_median": round(statistics.median(anomalies), 1) if anomalies else 0,
        "discoveries": sum(1 for r in results if r.discovery_label is not None),
        "numbers_traced_share": round(numbers_traced / numbers_total, 3) if numbers_total else 0.0,
        "llm_calls_total": sum(r.llm_calls for r in results),
        "llm_provider_counts": llm_provider_counts,
    }


def _percentile(values: list[float], p: float) -> float:
    if not values:
        return 0.0
    s = sorted(values)
    idx = min(len(s) - 1, max(0, round(p * (len(s) - 1))))
    return s[idx]
