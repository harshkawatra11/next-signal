"""RunContext: the mutable state one run accumulates across its six stages. Each stage module exposes
`async def run(ctx) -> None` and only appends to its own fields, never rewrites another stage's output.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime, timezone
from typing import Optional

from .. import plain
from ..schemas import (
    Anomaly,
    Contradiction,
    Discovery,
    Document,
    Event,
    Fact,
    FinancialRow,
    Hypothesis,
    MetricValue,
    Report,
    RunMeta,
    Series,
    TestResult,
)


@dataclass
class RunContext:
    run_id: str
    symbol: str
    company: str
    sub_industry: str  # playbook: pharma | hospital | diagnostics | generic
    as_of: date
    peers: list[str] = field(default_factory=list)
    started_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    partial: bool = False

    documents: list[Document] = field(default_factory=list)
    events: list[Event] = field(default_factory=list)
    facts: list[Fact] = field(default_factory=list)
    metrics: list[MetricValue] = field(default_factory=list)
    # {peer_symbol: {period: {metric_id: value}}}, computed by Calculate alongside the subject's own
    # ctx.metrics, and read by Challenge's T1 peer test (grading/falsify.t1_peer). Not part of the Report
    # contract (Report.series only carries what the dashboard displays); this is internal pipeline state.
    peer_metrics: dict = field(default_factory=dict)
    anomalies: list[Anomaly] = field(default_factory=list)
    angles_considered: list[dict] = field(default_factory=list)
    hypotheses: list[Hypothesis] = field(default_factory=list)
    tests: list[TestResult] = field(default_factory=list)
    ach: dict = field(default_factory=dict)
    contradictions: list[Contradiction] = field(default_factory=list)
    discovery: Optional[Discovery] = None
    chosen_hyp_id: Optional[str] = None
    trace: list[dict] = field(default_factory=list)
    financials: list[FinancialRow] = field(default_factory=list)
    series: list[Series] = field(default_factory=list)
    stage_ms: dict[str, int] = field(default_factory=dict)

    llm_calls: int = 0
    llm_provider_mix: dict[str, int] = field(default_factory=dict)

    def note_llm_call(self, provider: str) -> None:
        self.llm_calls += 1
        self.llm_provider_mix[provider] = self.llm_provider_mix.get(provider, 0) + 1

    def to_meta_dict(self) -> dict:
        return {
            "run_id": self.run_id,
            "symbol": self.symbol,
            "company": self.company,
            "sub_industry": self.sub_industry,
            "as_of": self.as_of.isoformat(),
            "started_at": self.started_at.isoformat(),
            "finished_at": None,
            "runtime_s": None,
            "llm_calls": self.llm_calls,
            "llm_provider_mix": self.llm_provider_mix,
            "sources_hit": len({d.publisher for d in self.documents}),
            "documents": len(self.documents),
            "status": "running",
        }

    def to_report(self, runtime_s: float) -> Report:
        # Runners-up are every main hypothesis (never a rival) that survived or was downgraded but was
        # not the one Prove chose, matched by hyp_id (not angle_id, which collided with multiple
        # hypotheses sharing an angle and silently left the chosen hypothesis in its own runners-up list).
        survived_or_downgraded = [
            h for h in self.hypotheses if h.is_rival_of is None and h.status in ("survived", "downgraded")
        ]
        runners_up = [h for h in survived_or_downgraded if h.hyp_id != self.chosen_hyp_id]
        killed = [h for h in self.hypotheses if h.is_rival_of is None and h.status == "killed"]

        metric_ids: set[str] = set()
        metric_ids.update(m.metric_id for m in self.metrics)
        metric_ids.update(a.metric_id for a in self.anomalies)
        metric_ids.update(s.metric_id for s in self.series)
        for h in self.hypotheses:
            metric_ids.update(p.metric_id for p in h.predictions)
        if self.discovery is not None and self.discovery.falsification is not None:
            metric_ids.add(self.discovery.falsification.metric_id)
        glossary = {mid: plain.metric_name(mid) for mid in metric_ids}

        meta = RunMeta(
            run_id=self.run_id,
            symbol=self.symbol,
            company=self.company,
            sub_industry=self.sub_industry,
            as_of=self.as_of,
            started_at=self.started_at,
            finished_at=datetime.now(timezone.utc),
            runtime_s=round(runtime_s, 1),
            llm_calls=self.llm_calls,
            llm_provider_mix=self.llm_provider_mix,
            sources_hit=len({d.publisher for d in self.documents}),
            documents=len(self.documents),
            status="partial" if self.partial else "done",
        )
        return Report(
            meta=meta,
            discovery=self.discovery,
            runners_up=runners_up,
            killed=killed,
            tests=self.tests,
            ach=self.ach,
            contradictions=self.contradictions,
            documents=self.documents,
            events=self.events,
            metrics=self.metrics,
            anomalies=self.anomalies,
            angles_considered=self.angles_considered,
            trace=self.trace,
            facts_count=len(self.facts),
            financials=self.financials,
            series=self.series,
            peers=self.peers,
            stage_ms=self.stage_ms,
            glossary=glossary,
            peer_names={},
        )
