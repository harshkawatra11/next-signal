"""FastAPI app: REST + SSE endpoints per PLAN.md §5.13. POST /api/runs starts a real run through
pipeline/run.py's six-stage orchestrator; the individual stages still have honest stubs where a live
source client or the LLM router is not wired yet, so a run always finishes with a schema-valid Report
(typically with no documents and no discovery until sources/* and llm/* are filled in further).
"""
from __future__ import annotations

import asyncio
import json
import time
from pathlib import Path

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from sse_starlette.sse import EventSourceResponse

from . import store, universe
from .config import settings
from .events import bus
from .export.csvs import build_zip
from .export.md import write_markdown
from .export.xlsx import build_workbook
from .paper.render import build_paper_pdf
from .pipeline.run import start_run
from .schemas import Report, RunMeta
from .voice.ws import router as voice_router

app = FastAPI(title="Next Signal engine")

app.add_middleware(
    CORSMiddleware,
    allow_origins=[settings.web_origin, "http://localhost:3000"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(voice_router)


@app.get("/api/health")
async def health():
    from .llm import router as R

    return {
        "ok": True,
        "llm_provider": settings.llm_provider,
        "sarvam": bool(settings.sarvam_api_key),
        "gemini": bool(settings.gemini_api_key),
        "prices_chain": ["nse_mcp", "angel", "upstox", "nse_bhavcopy"],
        "llm_order": ["sarvam", "gemini"] if settings.llm_provider == "sarvam" else ["gemini", "sarvam"],
        "llm_recent": list(R.RECENT)[-5:],
    }


@app.get("/api/llm/selftest")
async def llm_selftest():
    from pydantic import BaseModel

    from .http import get_client
    from .llm import router as R

    class Probe(BaseModel):
        company: str
        quarters: int

    t0 = time.perf_counter()
    try:
        out = await R.llm_json(
            get_client(), None, "selftest", "selftest",
            [
                {"role": "system", "content": "Return only JSON."},
                {"role": "user", "content": 'Return {"company": "Example Industries Limited", "quarters": 8}.'},
            ],
            Probe, effort="low",
        )
        last = next((a for a in reversed(R.RECENT) if a.get("ok")), {})
        return {
            "ok": True,
            "provider": last.get("provider"),
            "model": settings.sarvam_research_model if last.get("provider") == "sarvam" else settings.gemini_model,
            "ms": int((time.perf_counter() - t0) * 1000),
            "answer": out.model_dump(),
            "attempts": list(R.RECENT)[-4:],
        }
    except Exception as e:
        return {"ok": False, "error": str(e)[:300], "attempts": list(R.RECENT)[-4:]}


@app.get("/api/universe")
async def get_universe(track: str = "D"):
    # Known, documented limitation (not a bug): the "playbook" field here is cosmetic for the
    # homepage grid, computed from the index CSV's coarse "Industry" column ("Healthcare" for every
    # Track D name), so it will show "generic" rather than "pharma"/"hospital" until each row gets a
    # live NSE quote-equity enrichment call for its finer industryInfo.basicIndustry field (PLAN.md
    # §5.7). Deliberately NOT hard-coding a company->playbook lookup table here even though we know
    # the answer from the research dossiers: that would violate the no-hard-coding rule the same way
    # for the universe listing as it would for the actual run pipeline. The real per-company routing
    # that matters (pipeline/resolve.py, used when a run actually starts) always calls the live NSE
    # API, so playbook selection for an actual investigation is unaffected by this endpoint's display
    # simplification.
    uni = await universe.load_universe()
    n50 = universe.track_d_n50(uni)
    tiebreak = universe.track_d_tiebreak(uni)
    rows = []
    for r in n50:
        rows.append({
            "symbol": r.symbol, "name": r.company_name, "industry": r.industry,
            "basic_industry": r.industry, "playbook": universe.playbook_for(r.industry),
            "in_nifty50": True, "weight": None,
        })
    for r in tiebreak:
        rows.append({
            "symbol": r.symbol, "name": r.company_name, "industry": r.industry,
            "basic_industry": r.industry, "playbook": universe.playbook_for(r.industry),
            "in_nifty50": False, "weight": None,
        })
    return rows


@app.get("/api/resolve")
async def resolve(q: str):
    uni = await universe.load_universe()
    ident = universe.resolve_offline(q, uni)
    if ident is None:
        from .sources.nse import resolve_live
        ident = await resolve_live(q)
    if ident is None:
        raise HTTPException(status_code=404, detail=f"could not resolve '{q}'")
    return {
        "symbol": ident.symbol, "company_name": ident.company_name, "industry": ident.industry,
        "playbook": ident.playbook, "in_nifty50": ident.in_nifty50, "isin": ident.isin,
    }


@app.post("/api/runs")
async def create_run(body: dict):
    query = body.get("query")
    if not query:
        raise HTTPException(status_code=422, detail="body must include a non-empty 'query'")
    try:
        run_id = await start_run(
            query, as_of=body.get("as_of"), disable_challenge=bool(body.get("disable_challenge", False))
        )
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    return {"run_id": run_id}


@app.get("/api/runs/{run_id}")
async def get_run(run_id: str) -> RunMeta:
    meta = store.get_run_meta(run_id)
    if meta is None:
        raise HTTPException(status_code=404, detail="run not found")
    return RunMeta.model_validate(meta)


_EXPORT_MEDIA = {
    "pdf": "application/pdf",
    "md": "text/markdown; charset=utf-8",
    "xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    "zip": "application/zip",
}
_EXPORT_WRITERS = {"md": write_markdown, "xlsx": build_workbook, "zip": build_zip}
_ENGINE_DIR = Path(__file__).resolve().parent.parent
_FIXTURE_REPORT = _ENGINE_DIR / "tests" / "fixtures" / "report_full.json"


def _load_report(run_id: str) -> Report:
    if run_id == "fixture":
        return Report.model_validate_json(_FIXTURE_REPORT.read_text(encoding="utf-8"))
    report_json = store.get_report_json(run_id)
    if report_json is None:
        raise HTTPException(status_code=404, detail="report not found (run may still be in progress)")
    return Report.model_validate_json(report_json)


@app.get("/api/runs/{run_id}/report")
async def get_report(run_id: str):
    if run_id == "fixture":
        return json.loads(_FIXTURE_REPORT.read_text(encoding="utf-8"))
    report_json = store.get_report_json(run_id)
    if report_json is None:
        raise HTTPException(status_code=404, detail="report not found (run may still be in progress)")
    return json.loads(report_json)


@app.get("/api/runs/{run_id}/export.{kind}")
async def export_run(run_id: str, kind: str):
    if kind != "pdf" and kind not in _EXPORT_WRITERS:
        raise HTTPException(status_code=404, detail=f"unknown export kind '{kind}'")
    report = _load_report(run_id)
    out_path = settings.db_path.parent / "exports" / run_id / f"next-signal-{report.meta.symbol}-{run_id}.{kind}"
    try:
        if kind == "pdf":
            await build_paper_pdf(report, out_path)
        else:
            await asyncio.to_thread(_EXPORT_WRITERS[kind], report, out_path)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"{kind} export failed: {str(e)[:300]}")
    return FileResponse(out_path, media_type=_EXPORT_MEDIA[kind], filename=out_path.name)


_EVAL_OUT = _ENGINE_DIR / "eval" / "out"


@app.get("/api/eval/summary")
async def eval_summary():
    p = _EVAL_OUT / "summary.json"
    if not p.exists():
        raise HTTPException(status_code=404, detail="evaluation has not been run")
    return json.loads(p.read_text(encoding="utf-8"))


@app.get("/api/eval/companies")
async def eval_companies():
    p = _EVAL_OUT / "companies.json"
    if not p.exists():
        raise HTTPException(status_code=404, detail="evaluation has not been run")
    return json.loads(p.read_text(encoding="utf-8"))


@app.get("/api/runs")
async def recent_runs(limit: int = 20):
    return store.recent_runs(limit)


@app.get("/api/runs/{run_id}/events")
async def run_events(run_id: str, request: Request, after: int = 0):
    # The browser sends Last-Event-ID automatically on reconnect; honor it alongside the
    # explicit `after` query param (whichever is further along wins), so a client that
    # reconnects without passing `after` still resumes from where it left off.
    last_event_id_header = request.headers.get("last-event-id")
    last_event_id_from_header = int(last_event_id_header) if last_event_id_header else 0
    effective_after = max(after, last_event_id_from_header)

    async def gen():
        # Subscribe to the live bus BEFORE replaying from the store. Replaying first and
        # subscribing after leaves a window where an event emitted between the two steps is
        # never seen by this stream. Subscribing first means any event emitted during replay
        # queues up on `q` and gets correctly skipped (by seq) when we drain it afterward.
        q = bus.subscribe(run_id)
        try:
            last_sent_seq = effective_after
            for ev in store.events_after(run_id, effective_after):
                last_sent_seq = ev["seq"]
                yield {"event": ev["type"], "id": str(ev["seq"]), "data": json.dumps(ev["data"]), "retry": 3000}
                if ev["type"] in ("done", "run_error"):
                    return
            while True:
                ev = await q.get()
                if ev["seq"] <= last_sent_seq:
                    continue
                last_sent_seq = ev["seq"]
                yield {"event": ev["type"], "id": str(ev["seq"]), "data": json.dumps(ev["data"]), "retry": 3000}
                if ev["type"] in ("done", "run_error"):
                    return
        finally:
            bus.unsubscribe(run_id, q)

    return EventSourceResponse(gen(), ping=15)
