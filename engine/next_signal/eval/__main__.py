"""CLI: runs the pipeline against a company set through the live engine's HTTP API, one company at a
time, and collects honest RunMetrics for each (did it find facts, did it compute anomalies, did a
hypothesis survive, which LLM provider answered). This module never imports pipeline internals: it
talks to an already-running engine exactly as the web app does, through POST /api/runs, GET
/api/runs/{id} and GET /api/runs/{id}/report, so a batch run exercises the real HTTP surface rather than
an in-process shortcut.

Usage (from engine/, with the engine already running on port 8080):
    .venv/Scripts/python.exe -m next_signal.eval --set N50,TB --tb-limit 10
    .venv/Scripts/python.exe -m next_signal.eval --symbols CIPLA,DIVISLAB --paper
    .venv/Scripts/python.exe -m next_signal.eval --set N50 --as-of 2025-12-31 --api http://localhost:8080

After every company, engine/eval/out/{companies.json,summary.json,runs.csv} are rewritten from the
results collected so far, so a long batch is inspectable (and usable) mid-run, not only at the end.
"""
from __future__ import annotations

import argparse
import asyncio
import csv
import json
from dataclasses import asdict, fields
from pathlib import Path
from typing import Optional

import httpx

from .harness import RunMetrics, _failed_metrics, company_set, metrics_from_report, summarize
from ..schemas import Report

OUT = Path(__file__).resolve().parent.parent.parent / "eval" / "out"
POLL_INTERVAL_S = 5.0
TIMEOUT_S = 720.0
_TERMINAL_STATUSES = ("done", "failed", "partial")


async def run_one_company(
    client: httpx.AsyncClient,
    api_base: str,
    symbol: str,
    as_of: Optional[str] = None,
    poll_interval: float = POLL_INTERVAL_S,
    timeout: float = TIMEOUT_S,
) -> RunMetrics:
    """Starts one run, polls its status until it leaves "running", then fetches the finished report and
    turns it into a RunMetrics row. Any failure along the way (the POST, a poll, the report fetch, or
    simply running out of time) becomes an honest status="failed" row via _failed_metrics rather than an
    exception that would abort the rest of the batch; one broken company must never block the others."""
    body: dict = {"query": symbol}
    if as_of:
        body["as_of"] = as_of
    try:
        resp = await client.post(f"{api_base}/api/runs", json=body)
        resp.raise_for_status()
        run_id = resp.json()["run_id"]
    except Exception:
        return _failed_metrics(symbol)

    status: Optional[str] = None
    elapsed = 0.0
    while elapsed < timeout:
        try:
            meta_resp = await client.get(f"{api_base}/api/runs/{run_id}")
            meta_resp.raise_for_status()
            status = meta_resp.json().get("status")
        except Exception:
            status = None
        if status in _TERMINAL_STATUSES:
            break
        await asyncio.sleep(poll_interval)
        elapsed += poll_interval
    else:
        # The for/while-else fires only when the loop ran out of time without a `break`.
        return _failed_metrics(symbol)

    if status != "done" and status != "partial":
        return _failed_metrics(symbol)

    try:
        report_resp = await client.get(f"{api_base}/api/runs/{run_id}/report")
        report_resp.raise_for_status()
        report = Report.model_validate(report_resp.json())
    except Exception:
        return _failed_metrics(symbol)

    return metrics_from_report(report)


async def fetch_paper(client: httpx.AsyncClient, api_base: str, run_id: str, symbol: str, out_dir: Path) -> None:
    """Best-effort: a failed paper download never fails the batch, since the paper is a nice-to-have
    artifact of the eval run, not the metric the harness exists to collect."""
    try:
        resp = await client.get(f"{api_base}/api/runs/{run_id}/export.pdf")
        resp.raise_for_status()
    except Exception:
        return
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / f"{symbol}.pdf").write_bytes(resp.content)


async def resolve_symbols(args: argparse.Namespace) -> list[str]:
    """--symbols, when given, is authoritative and overrides --set entirely. Otherwise builds the
    symbol list from the requested company sets (N50, TB, or both), deterministically from the live
    index CSVs via harness.company_set: no hand-picked list."""
    if args.symbols:
        return [s.strip().upper() for s in args.symbols.split(",") if s.strip()]
    sets = {s.strip().upper() for s in args.set.split(",") if s.strip()} if args.set else {"N50"}
    n50, tb = await company_set(tb_limit=args.tb_limit)
    symbols: list[str] = []
    if "N50" in sets:
        symbols.extend(r.symbol for r in n50)
    if "TB" in sets:
        symbols.extend(r.symbol for r in tb)
    return symbols


def write_outputs(results: list[RunMetrics]) -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "companies.json").write_text(
        json.dumps([asdict(r) for r in results], indent=2), encoding="utf-8"
    )
    (OUT / "summary.json").write_text(json.dumps(summarize(results), indent=2), encoding="utf-8")
    fieldnames = [f.name for f in fields(RunMetrics)]
    with (OUT / "runs.csv").open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for r in results:
            writer.writerow(asdict(r))


def parse_args(argv: Optional[list[str]] = None) -> argparse.Namespace:
    p = argparse.ArgumentParser(
        prog="python -m next_signal.eval",
        description="Run next_signal's research pipeline against a company set through the live engine's HTTP API.",
    )
    p.add_argument("--set", default="N50", help="Comma-separated company sets to include: N50, TB.")
    p.add_argument("--tb-limit", type=int, default=10, help="Tie-break list length when TB is included.")
    p.add_argument("--symbols", default=None, help="Comma-separated explicit symbol list; overrides --set.")
    p.add_argument("--api", default="http://localhost:8080", help="Base URL of the running engine.")
    p.add_argument("--as-of", default=None, help="ISO date (YYYY-MM-DD) to run every company as of.")
    p.add_argument("--paper", action="store_true", help="Also download each finished run's research paper PDF.")
    return p.parse_args(argv)


async def main_async(argv: Optional[list[str]] = None) -> list[RunMetrics]:
    args = parse_args(argv)
    symbols = await resolve_symbols(args)
    results: list[RunMetrics] = []
    paper_dir = OUT / "papers"
    async with httpx.AsyncClient(timeout=60) as client:
        for symbol in symbols:
            metrics = await run_one_company(client, args.api, symbol, args.as_of)
            results.append(metrics)
            if args.paper and metrics.status != "failed" and metrics.run_id:
                await fetch_paper(client, args.api, metrics.run_id, symbol, paper_dir)
            write_outputs(results)
            print(f"{symbol}: {metrics.status}")
    return results


def main() -> None:
    asyncio.run(main_async())


if __name__ == "__main__":
    main()
