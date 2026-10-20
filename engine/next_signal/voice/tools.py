"""Voice tool schemas and handlers (PLAN.md §5.15 point 5). Replaces ai-healthcare platform's 13
health-domain tools (get_state_briefing, get_district_briefing, ...) with 10 report-domain tools, all
reading from a single in-memory Report object rather than live district services. Each handler returns
a ToolResult(llm, card): `llm` is the JSON payload fed back to the model, `card` is an optional
UI-renderable summary the frontend's FactCard components display.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Optional

from ..schemas import Report

TOOL_SCHEMAS: list[dict[str, Any]] = [
    {
        "type": "function",
        "function": {
            "name": "get_discovery",
            "description": "Get the report's main discovery sentence and its strength label.",
            "parameters": {"type": "object", "properties": {}},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_why_it_matters",
            "description": "Get the 3 to 5 bullets explaining why the discovery matters.",
            "parameters": {"type": "object", "properties": {}},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_numbers",
            "description": "Get the discovery's numbers, optionally filtered by a name fragment.",
            "parameters": {
                "type": "object",
                "properties": {"name": {"type": "string", "description": "optional label fragment to filter by"}},
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_evidence",
            "description": "Get evidence items, optionally filtered by publisher.",
            "parameters": {
                "type": "object",
                "properties": {"publisher": {"type": "string", "description": "optional publisher name to filter by"}},
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_timeline",
            "description": "Get the discovery's timeline of events.",
            "parameters": {"type": "object", "properties": {}},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_counterargument",
            "description": "Get the strongest alternative explanation the system considered.",
            "parameters": {"type": "object", "properties": {}},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_falsification",
            "description": "Get the condition that would make the system reconsider its conclusion.",
            "parameters": {"type": "object", "properties": {}},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_strength",
            "description": "Get the evidence strength score breakdown and its reasoning.",
            "parameters": {"type": "object", "properties": {}},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_killed_hypotheses",
            "description": "Get the hypotheses that were proposed and then killed, with the reason each was killed.",
            "parameters": {"type": "object", "properties": {}},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_method",
            "description": "Get a summary of the run: stages, runtime, documents and sources used.",
            "parameters": {"type": "object", "properties": {}},
        },
    },
]


@dataclass
class ToolResult:
    llm: dict[str, Any]
    card: Optional[dict[str, Any]] = None


def _trunc(obj: Any, limit: int = 600) -> Any:
    """History payloads are truncated to 600 chars per the ported session.py convention."""
    import json

    s = json.dumps(obj, ensure_ascii=False)
    return json.loads(s[:limit]) if len(s) <= limit else {"truncated": s[:limit]}


def build_tool_functions(report: Report) -> dict[str, Any]:
    d = report.discovery

    def get_discovery(**_: Any) -> ToolResult:
        if d is None:
            return ToolResult(llm={"discovery": None, "note": "no discovery survived the challenge stage"})
        return ToolResult(
            llm={"sentence": d.sentence, "strength": d.strength.label},
            card={"type": "discovery", "sentence": d.sentence, "label": d.strength.label},
        )

    def get_why_it_matters(**_: Any) -> ToolResult:
        if d is None:
            return ToolResult(llm={"why_it_matters": []})
        return ToolResult(llm={"why_it_matters": d.why_it_matters})

    def get_numbers(name: str = "", **_: Any) -> ToolResult:
        if d is None:
            return ToolResult(llm={"numbers": []})
        items = [n for n in d.numbers if name.lower() in n.label.lower()] if name else d.numbers
        payload = [{"label": n.label, "display": n.display, "period": n.period, "formula": n.formula} for n in items]
        return ToolResult(llm={"numbers": payload}, card={"type": "numbers", "items": payload})

    def get_evidence(publisher: str = "", **_: Any) -> ToolResult:
        if d is None:
            return ToolResult(llm={"evidence": []})
        items = [e for e in d.evidence if publisher.lower() in e.publisher.lower()] if publisher else d.evidence
        payload = [
            {"publisher": e.publisher, "origin": e.origin_class, "grade": e.reliability, "quote": e.anchor.quote, "url": e.url}
            for e in items
        ]
        return ToolResult(llm={"evidence": payload})

    def get_timeline(**_: Any) -> ToolResult:
        if d is None:
            return ToolResult(llm={"timeline": []})
        payload = [{"date": str(t.date), "label": t.label, "is_changepoint": t.is_changepoint} for t in d.timeline]
        return ToolResult(llm={"timeline": payload}, card={"type": "timeline", "items": payload})

    def get_counterargument(**_: Any) -> ToolResult:
        if d is None:
            return ToolResult(llm={"counterargument": None})
        return ToolResult(llm={"counterargument": d.counterargument})

    def get_falsification(**_: Any) -> ToolResult:
        if d is None:
            return ToolResult(llm={"falsification": None})
        f = d.falsification
        return ToolResult(llm={
            "statement": f.statement, "metric_id": f.metric_id, "comparator": f.comparator,
            "threshold": f.threshold, "next_check": str(f.next_check), "check_source": f.check_source,
        })

    def get_strength(**_: Any) -> ToolResult:
        if d is None:
            return ToolResult(llm={"strength": None})
        s = d.strength
        return ToolResult(llm={
            "label": s.label, "total": s.total, "independence": s.independence, "reliability": s.reliability,
            "corroboration": s.corroboration, "survival": s.survival, "persistence": s.persistence,
            "reasoning": s.reasoning,
        })

    def get_killed_hypotheses(**_: Any) -> ToolResult:
        payload = [{"statement": h.statement, "reason": h.kill_reason} for h in report.killed]
        return ToolResult(llm={"killed": payload})

    def get_method(**_: Any) -> ToolResult:
        m = report.meta
        return ToolResult(llm={
            "status": m.status, "runtime_s": m.runtime_s, "documents": m.documents,
            "sources_hit": m.sources_hit, "llm_calls": m.llm_calls,
        })

    return {
        "get_discovery": get_discovery,
        "get_why_it_matters": get_why_it_matters,
        "get_numbers": get_numbers,
        "get_evidence": get_evidence,
        "get_timeline": get_timeline,
        "get_counterargument": get_counterargument,
        "get_falsification": get_falsification,
        "get_strength": get_strength,
        "get_killed_hypotheses": get_killed_hypotheses,
        "get_method": get_method,
    }


def tool_label(name: str, args: dict[str, Any]) -> str:
    """Short human-readable label for the UI's tool-call trace (ported convention from session.py)."""
    labels = {
        "get_discovery": "Reading the discovery",
        "get_why_it_matters": "Reading why it matters",
        "get_numbers": "Looking up numbers",
        "get_evidence": "Checking evidence",
        "get_timeline": "Checking the timeline",
        "get_counterargument": "Checking the counterargument",
        "get_falsification": "Checking the falsification condition",
        "get_strength": "Checking the evidence strength",
        "get_killed_hypotheses": "Checking killed hypotheses",
        "get_method": "Checking the run method",
    }
    return labels.get(name, name)
