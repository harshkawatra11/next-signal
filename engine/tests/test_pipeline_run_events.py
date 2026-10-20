from datetime import date

import pytest

import next_signal.pipeline.run as run_module
from next_signal import http
from next_signal.pipeline.context import RunContext
from next_signal.schemas import Anomaly, Hypothesis


class FakeBus:
    def __init__(self):
        self.events: list[tuple[str, str, dict]] = []

    async def emit(self, run_id, type_, data):
        self.events.append((run_id, type_, data))
        return len(self.events)

    def emit_nowait(self, run_id, type_, data):
        self.events.append((run_id, type_, data))
        return len(self.events)


class FakeStore:
    def __init__(self):
        self.saved_report = None
        self.failed = None

    def create_run(self, ctx):
        pass

    def save_report(self, report):
        self.saved_report = report

    def mark_failed(self, run_id, message):
        self.failed = (run_id, message)


@pytest.fixture
def wired(monkeypatch):
    fake_bus = FakeBus()
    fake_store = FakeStore()
    monkeypatch.setattr(run_module, "bus", fake_bus)
    monkeypatch.setattr(run_module, "store", fake_store)
    return fake_bus, fake_store


async def _discover(ctx):
    ctx.angles_considered = [{"angle_id": "P1", "score": 0.7, "chosen": True, "reason": "r"}]


async def _noop(ctx, **kw):
    return None


async def _calculate(ctx):
    ctx.anomalies = [Anomaly(anomaly_id="anom-gm-Q1FY27", metric_id="gross_margin", description="d", score=0.5)]


async def _reason(ctx):
    ctx.hypotheses = [Hypothesis(hyp_id="H1", angle_id="P1", statement="s", mechanism="m", predictions=[], disconfirmers=[])]


async def test_drive_emits_stage_outputs(wired, monkeypatch):
    fake_bus, _ = wired
    monkeypatch.setattr(run_module, "STAGES", [
        ("Discover", _discover, 50), ("Connect", _noop, 120), ("Calculate", _calculate, 15),
        ("Reason", _reason, 40), ("Challenge", _noop, 110), ("Prove", _noop, 40),
    ])
    ctx = RunContext(run_id="ev1", symbol="X", company="X Ltd", sub_industry="pharma", as_of=date(2026, 10, 15))
    await run_module.drive(ctx)
    types = [e[1] for e in fake_bus.events]
    assert "angle" in types and "anomaly" in types and "hypothesis" in types
    assert types[-1] == "done"


def test_notify_fetch_calls_listener_set_in_context():
    captured = []
    token = http.fetch_listener.set(lambda ev: captured.append(ev))
    try:
        http.notify_fetch(http.FetchEvent("h", "u", 200, 5, False))
    finally:
        http.fetch_listener.reset(token)
    assert len(captured) == 1
    assert captured[0].host == "h"
