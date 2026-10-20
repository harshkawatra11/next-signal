"""Tests for next_signal/eval/__main__.py, the batch CLI that drives an already-running engine over
HTTP. No test here starts a real engine: httpx calls are mocked with respx (the pattern tests/test_http.py
already uses for this codebase's httpx-based modules), and resolve_symbols/write_outputs are exercised
directly with fakes / tmp_path so the universe CSVs and the real engine/eval/out directory are never
touched."""
from __future__ import annotations

import csv
import json
from dataclasses import dataclass
from datetime import date

import httpx
import pytest
import respx

from next_signal.eval import __main__ as cli
from next_signal.eval.harness import RunMetrics
from next_signal.schemas import Report, RunMeta


def make_report_json(symbol: str, run_id: str) -> dict:
    report = Report(
        meta=RunMeta(
            run_id=run_id, symbol=symbol, company=f"{symbol} Ltd", sub_industry="pharma",
            as_of=date(2026, 10, 15), started_at="2026-10-15T00:00:00+00:00",
            runtime_s=42.0, documents=7, status="done", llm_calls=2, llm_provider_mix={"sarvam": 2},
        ),
        discovery=None, runners_up=[], killed=[], tests=[], ach={}, contradictions=[], documents=[],
        events=[], metrics=[], anomalies=[], angles_considered=[], trace=[], facts_count=90,
    )
    return json.loads(report.model_dump_json())


async def test_run_one_company_happy_path_returns_metrics_from_the_finished_report():
    api = "http://engine.test"
    with respx.mock(assert_all_called=True) as mock:
        mock.post(f"{api}/api/runs").mock(return_value=httpx.Response(200, json={"run_id": "CIPLA-run1"}))
        mock.get(f"{api}/api/runs/CIPLA-run1").mock(return_value=httpx.Response(200, json={"status": "done"}))
        mock.get(f"{api}/api/runs/CIPLA-run1/report").mock(
            return_value=httpx.Response(200, json=make_report_json("CIPLA", "CIPLA-run1"))
        )
        async with httpx.AsyncClient() as client:
            metrics = await cli.run_one_company(client, api, "CIPLA", poll_interval=0.01, timeout=1.0)
    assert metrics.symbol == "CIPLA"
    assert metrics.status == "done"
    assert metrics.run_id == "CIPLA-run1"
    assert metrics.facts_count == 90
    assert metrics.llm_provider == "sarvam"


async def test_run_one_company_polls_until_the_run_leaves_running():
    api = "http://engine.test"
    statuses = iter(["running", "running", "done"])
    with respx.mock(assert_all_called=False) as mock:
        mock.post(f"{api}/api/runs").mock(return_value=httpx.Response(200, json={"run_id": "R1"}))
        mock.get(f"{api}/api/runs/R1").mock(
            side_effect=lambda request: httpx.Response(200, json={"status": next(statuses)})
        )
        mock.get(f"{api}/api/runs/R1/report").mock(
            return_value=httpx.Response(200, json=make_report_json("DIVISLAB", "R1"))
        )
        async with httpx.AsyncClient() as client:
            metrics = await cli.run_one_company(client, api, "DIVISLAB", poll_interval=0.01, timeout=1.0)
    assert metrics.status == "done"
    assert metrics.symbol == "DIVISLAB"


async def test_run_one_company_the_engine_reports_failed_status():
    api = "http://engine.test"
    with respx.mock(assert_all_called=True) as mock:
        mock.post(f"{api}/api/runs").mock(return_value=httpx.Response(200, json={"run_id": "R2"}))
        mock.get(f"{api}/api/runs/R2").mock(return_value=httpx.Response(200, json={"status": "failed"}))
        async with httpx.AsyncClient() as client:
            metrics = await cli.run_one_company(client, api, "APOLLOHOSP", poll_interval=0.01, timeout=1.0)
    assert metrics.status == "failed"
    assert metrics.symbol == "APOLLOHOSP"


async def test_run_one_company_a_broken_post_becomes_a_failed_row_not_an_exception():
    api = "http://engine.test"
    with respx.mock(assert_all_called=True) as mock:
        mock.post(f"{api}/api/runs").mock(return_value=httpx.Response(500))
        async with httpx.AsyncClient() as client:
            metrics = await cli.run_one_company(client, api, "SUNPHARMA", poll_interval=0.01, timeout=1.0)
    assert metrics.status == "failed"
    assert metrics.symbol == "SUNPHARMA"


async def test_run_one_company_times_out_without_the_run_ever_finishing():
    api = "http://engine.test"
    with respx.mock(assert_all_called=False) as mock:
        mock.post(f"{api}/api/runs").mock(return_value=httpx.Response(200, json={"run_id": "R3"}))
        mock.get(f"{api}/api/runs/R3").mock(return_value=httpx.Response(200, json={"status": "running"}))
        async with httpx.AsyncClient() as client:
            metrics = await cli.run_one_company(client, api, "CIPLA", poll_interval=0.01, timeout=0.03)
    assert metrics.status == "failed"


async def test_fetch_paper_writes_the_pdf_bytes_to_the_symbol_named_file(tmp_path):
    api = "http://engine.test"
    with respx.mock(assert_all_called=True) as mock:
        mock.get(f"{api}/api/runs/R4/export.pdf").mock(
            return_value=httpx.Response(200, content=b"%PDF-1.4 fake", headers={"content-type": "application/pdf"})
        )
        async with httpx.AsyncClient() as client:
            await cli.fetch_paper(client, api, "R4", "CIPLA", tmp_path / "papers")
    out_file = tmp_path / "papers" / "CIPLA.pdf"
    assert out_file.exists()
    assert out_file.read_bytes() == b"%PDF-1.4 fake"


async def test_fetch_paper_a_failed_download_does_not_raise(tmp_path):
    api = "http://engine.test"
    with respx.mock(assert_all_called=True) as mock:
        mock.get(f"{api}/api/runs/R5/export.pdf").mock(return_value=httpx.Response(500))
        async with httpx.AsyncClient() as client:
            await cli.fetch_paper(client, api, "R5", "CIPLA", tmp_path / "papers")
    assert not (tmp_path / "papers" / "CIPLA.pdf").exists()


@dataclass
class _FakeRow:
    symbol: str


async def test_resolve_symbols_explicit_symbols_overrides_set(monkeypatch):
    async def fail_company_set(*args, **kwargs):
        raise AssertionError("company_set should not be called when --symbols is given")

    monkeypatch.setattr(cli, "company_set", fail_company_set)
    args = cli.parse_args(["--symbols", "cipla, divislab"])
    symbols = await cli.resolve_symbols(args)
    assert symbols == ["CIPLA", "DIVISLAB"]


async def test_resolve_symbols_builds_from_n50_and_tb_sets(monkeypatch):
    async def fake_company_set(tb_limit=10):
        return [_FakeRow("CIPLA"), _FakeRow("SUNPHARMA")], [_FakeRow("TIEBREAK1")]

    monkeypatch.setattr(cli, "company_set", fake_company_set)
    args = cli.parse_args(["--set", "N50,TB"])
    symbols = await cli.resolve_symbols(args)
    assert symbols == ["CIPLA", "SUNPHARMA", "TIEBREAK1"]


async def test_resolve_symbols_n50_only_excludes_tiebreak(monkeypatch):
    async def fake_company_set(tb_limit=10):
        return [_FakeRow("CIPLA")], [_FakeRow("TIEBREAK1")]

    monkeypatch.setattr(cli, "company_set", fake_company_set)
    args = cli.parse_args(["--set", "N50"])
    symbols = await cli.resolve_symbols(args)
    assert symbols == ["CIPLA"]


def test_write_outputs_writes_companies_summary_and_csv(tmp_path, monkeypatch):
    monkeypatch.setattr(cli, "OUT", tmp_path)
    results = [
        RunMetrics(symbol="CIPLA", company="Cipla Ltd", runtime_s=10.0, status="done", documents=5,
                   hypotheses_total=1, killed=0, survived=1, discovery_label="Moderate", strength_total=5.0,
                   novelty=0.5, numbers_total=2, contradictions_found=0, angle_chosen="P2", run_id="r1",
                   facts_count=90, anomalies=1, numbers_traced=1, llm_calls=2, llm_provider="sarvam"),
    ]
    cli.write_outputs(results)
    companies = json.loads((tmp_path / "companies.json").read_text(encoding="utf-8"))
    assert companies[0]["symbol"] == "CIPLA"
    assert companies[0]["llm_provider"] == "sarvam"
    summary = json.loads((tmp_path / "summary.json").read_text(encoding="utf-8"))
    assert summary["n_companies"] == 1
    with (tmp_path / "runs.csv").open(encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    assert rows[0]["symbol"] == "CIPLA"
    assert rows[0]["run_id"] == "r1"


def test_write_outputs_handles_an_empty_results_list(tmp_path, monkeypatch):
    monkeypatch.setattr(cli, "OUT", tmp_path)
    cli.write_outputs([])
    assert json.loads((tmp_path / "companies.json").read_text(encoding="utf-8")) == []
    summary = json.loads((tmp_path / "summary.json").read_text(encoding="utf-8"))
    assert summary["n_companies"] == 0
    with (tmp_path / "runs.csv").open(encoding="utf-8") as f:
        header = f.readline().strip()
    assert "symbol" in header


def test_parse_args_defaults():
    args = cli.parse_args([])
    assert args.set == "N50"
    assert args.tb_limit == 10
    assert args.symbols is None
    assert args.api == "http://localhost:8080"
    assert args.as_of is None
    assert args.paper is False


def test_parse_args_paper_and_api_override():
    args = cli.parse_args(["--symbols", "CIPLA", "--api", "http://example.com:9090", "--paper", "--as-of", "2025-12-31"])
    assert args.paper is True
    assert args.api == "http://example.com:9090"
    assert args.as_of == "2025-12-31"


async def test_main_async_runs_each_symbol_and_writes_outputs_after_each(tmp_path, monkeypatch):
    monkeypatch.setattr(cli, "OUT", tmp_path)
    api = "http://localhost:8080"
    with respx.mock(assert_all_called=True) as mock:
        mock.post(f"{api}/api/runs").mock(
            side_effect=lambda request: httpx.Response(200, json={"run_id": f"{json.loads(request.content)['query']}-run"})
        )
        mock.get(url__regex=rf"{api}/api/runs/[A-Z]+-run$").mock(return_value=httpx.Response(200, json={"status": "done"}))
        mock.get(url__regex=rf"{api}/api/runs/[A-Z]+-run/report$").mock(
            side_effect=lambda request: httpx.Response(
                200, json=make_report_json(request.url.path.split("/")[3].removesuffix("-run"), request.url.path.split("/")[3])
            )
        )
        results = await cli.main_async(["--symbols", "CIPLA,SUNPHARMA"])
    assert [r.symbol for r in results] == ["CIPLA", "SUNPHARMA"]
    assert all(r.status == "done" for r in results)
    summary = json.loads((tmp_path / "summary.json").read_text(encoding="utf-8"))
    assert summary["n_companies"] == 2
