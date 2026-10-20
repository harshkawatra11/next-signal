"""Pipeline orchestrator: resolves identity, then drives the six stages in sequence under a soft/hard
time budget, emitting bus events for SSE streaming and persisting to the run store (PLAN.md §5.13,
Appendix X.6). This is the one place the stub seams in discover/connect/reason/challenge/prove get wired
to real dependencies (a shared httpx client, the LLM router) once those exist; until then it drives the
same stages with their honest stubs, so a run always finishes with a schema-valid Report, never a crash.
"""
from __future__ import annotations

import asyncio
import time
from typing import Optional

from .. import plain, store
from ..config import settings
from ..events import bus
from ..http import fetch_listener
from ..sources.nse import NSE
from . import calculate, challenge, connect, discover, prove, reason, resolve
from .context import RunContext

STAGES = [
    ("Discover", discover.run, 50),
    ("Connect", connect.run, 120),
    ("Calculate", calculate.run, 15),
    ("Reason", reason.run, 40),
    ("Challenge", challenge.run, 110),
    ("Prove", prove.run, 40),
]


def _snapshot(ctx: RunContext) -> dict:
    return {
        "docs": len(ctx.documents), "facts": len(ctx.facts), "hyps": len(ctx.hypotheses),
        "tests": len(ctx.tests), "contras": len(ctx.contradictions),
    }


async def _emit_stage_outputs(ctx: RunContext, name: str, before: dict) -> None:
    """Turns what a stage just added to ctx into the SSE events the live run page renders. Runs after
    every stage, including one that timed out, so partial work still shows up. Never raises."""
    rid = ctx.run_id
    try:
        if name == "Discover":
            for a in ctx.angles_considered:
                await bus.emit(rid, "angle", {
                    "angle_id": a.get("angle_id"), "score": float(a.get("score") or 0.0),
                    "chosen": bool(a.get("chosen")), "reason": a.get("reason", ""),
                })
        elif name == "Connect":
            new_docs = len(ctx.documents) - before["docs"]
            if new_docs > 0:
                await bus.emit(rid, "doc_parsed", {"count": new_docs})
            new_facts = ctx.facts[before["facts"]:]
            if new_facts:
                verified = sum(1 for f in new_facts if getattr(getattr(f, "anchor", None), "verified", False))
                await bus.emit(rid, "fact", {"count": len(new_facts), "verified": verified})
        elif name == "Calculate":
            for an in ctx.anomalies:
                await bus.emit(rid, "anomaly", {**an.model_dump(mode="json"), "label": plain.metric_name(an.metric_id)})
        elif name == "Reason":
            for h in ctx.hypotheses[before["hyps"]:]:
                await bus.emit(rid, "hypothesis", {
                    "hyp_id": h.hyp_id, "statement": h.statement, "angle_id": h.angle_id,
                    "is_rival_of": h.is_rival_of,
                })
        elif name == "Challenge":
            for t in ctx.tests[before["tests"]:]:
                await bus.emit(rid, "test", {
                    "hyp_id": t.hyp_id, "test_id": t.test_id, "applicable": t.applicable,
                    "passed": t.passed, "detail": t.detail, "plain": t.plain,
                })
            for h in ctx.hypotheses:
                if h.is_rival_of is not None:
                    continue
                if h.status == "killed":
                    await bus.emit(rid, "kill", {"hyp_id": h.hyp_id, "reason": h.kill_reason or ""})
                else:
                    await bus.emit(rid, "hyp_status", {"hyp_id": h.hyp_id, "status": h.status})
            for c in ctx.contradictions[before["contras"]:]:
                await bus.emit(rid, "contradiction", {"type": c.type, "claim": c.claim})
        elif name == "Prove" and ctx.discovery is not None:
            await bus.emit(rid, "discovery", {
                "sentence": ctx.discovery.sentence, "label": ctx.discovery.strength.label,
                "hyp_id": ctx.discovery.hyp_id,
            })
    except Exception as e:
        ctx.trace.append({"stage": name, "emit_error": str(e)[:200]})


async def start_run(query: str, as_of: Optional[str] = None, disable_challenge: bool = False) -> str:
    """Resolves the query to a company, persists the run shell, and starts the stage sequence as a
    background task. Returns the run_id immediately; callers poll /api/runs/{id} or subscribe to
    /api/runs/{id}/events for progress. This is the live entry point: it constructs a real `NSE()`
    client (lazily cookie-warmed on first real call, not at construction time) so Connect can fetch real
    announcements, unlike `drive()` called directly, which defaults to no client."""
    ctx = await resolve.run(query, as_of)
    store.create_run(ctx)
    asyncio.create_task(drive(ctx, disable_challenge, nse_client=NSE()))
    return ctx.run_id


async def drive(ctx: RunContext, disable_challenge: bool = False, nse_client=None) -> None:
    """Runs STAGES in order against an already-resolved ctx. Each stage gets at most
    min(2 x its soft budget, time remaining under the hard cap); a stage that times out sets
    ctx.partial and the sequence continues (Prove always runs on whatever exists rather than being
    skipped, so a run never ends without at least an honest "no discovery survived" result).
    `nse_client` is passed straight through to `connect.run()`. It defaults to `None`, which keeps
    `connect.run()`'s own honest empty-list degrade: `drive()` never constructs a live, network-calling
    client on its own, so calling it directly (as the unit tests in test_pipeline_run.py do) never risks
    an unwanted network call. `start_run()` is the one caller that passes a real `NSE()` instance, since
    it is the actual live-serving entry point behind `POST /api/runs`, not something a fast unit test
    exercises."""
    t0 = time.perf_counter()
    token = fetch_listener.set(lambda ev: bus.emit_nowait(ctx.run_id, "source_fetch", ev.as_dict()))
    try:
        try:
            for name, fn, budget in STAGES:
                if name == "Challenge" and disable_challenge:
                    continue
                elapsed = time.perf_counter() - t0
                reserve_for_prove = 40 if name != "Prove" else 0
                remaining = settings.run_hard_cap_s - elapsed - reserve_for_prove
                if remaining <= 5 and name != "Prove":
                    ctx.partial = True
                    continue
                await bus.emit(ctx.run_id, "stage", {"stage": name, "state": "start"})
                stage_t0 = time.perf_counter()
                before = _snapshot(ctx)
                stage_call = fn(ctx, nse_client=nse_client) if name == "Connect" else fn(ctx)
                try:
                    await asyncio.wait_for(stage_call, timeout=max(5, min(budget * 2, remaining)))
                except asyncio.TimeoutError:
                    ctx.partial = True
                    await bus.emit(ctx.run_id, "stage", {"stage": name, "state": "timeout"})
                await _emit_stage_outputs(ctx, name, before)
                ctx.stage_ms[name] = int((time.perf_counter() - stage_t0) * 1000)
                await bus.emit(
                    ctx.run_id, "stage",
                    {"stage": name, "state": "end", "ms": int((time.perf_counter() - stage_t0) * 1000)},
                )
            runtime_s = time.perf_counter() - t0
            try:
                llm_events = [e for e in store.events_after(ctx.run_id, 0) if e["type"] == "llm" and e["data"].get("ok", True)]
                ctx.llm_calls = len(llm_events)
                mix: dict[str, int] = {}
                for e in llm_events:
                    p = e["data"].get("provider", "unknown")
                    mix[p] = mix.get(p, 0) + 1
                ctx.llm_provider_mix = mix
            except Exception:
                pass
            report = ctx.to_report(runtime_s=runtime_s)
            store.save_report(report)
            try:
                from ..paper.writer import ensure_paper_text
                asyncio.create_task(ensure_paper_text(report))
            except Exception:
                pass
            await bus.emit(ctx.run_id, "done", {"run_id": ctx.run_id, "runtime_s": round(runtime_s, 1)})
        except Exception as e:  # a run must always resolve to done/run_error, never hang the UI
            store.mark_failed(ctx.run_id, str(e))
            # Named "run_error", not "error": EventSource fires its own built-in "error" event on
            # every connection close, including a normal close after "done". A server event literally
            # named "error" collides with that browser-native event and makes the frontend's listener
            # fire a false alarm on every clean disconnect.
            await bus.emit(ctx.run_id, "run_error", {"message": str(e)[:300]})
    finally:
        fetch_listener.reset(token)
