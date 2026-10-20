from datetime import date

import pytest

import next_signal.pipeline.run as run_module
from next_signal.pipeline.context import RunContext


class FakeBus:
    def __init__(self):
        self.events: list[tuple[str, str, dict]] = []

    async def emit(self, run_id, type_, data):
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


def make_ctx(run_id="r1"):
    return RunContext(run_id=run_id, symbol="CIPLA", company="Cipla Limited", sub_industry="pharma", as_of=date(2026, 10, 15))


async def test_drive_runs_all_six_stages_in_order(wired):
    fake_bus, fake_store = wired
    ctx = make_ctx()
    await run_module.drive(ctx)
    starts = [e[2]["stage"] for e in fake_bus.events if e[1] == "stage" and e[2]["state"] == "start"]
    assert starts == ["Discover", "Connect", "Calculate", "Reason", "Challenge", "Prove"]
    assert fake_bus.events[-1][1] == "done"
    assert fake_store.saved_report is not None
    assert fake_store.saved_report.meta.run_id == "r1"


async def test_drive_produces_schema_valid_report_with_no_discovery(wired):
    fake_bus, fake_store = wired
    ctx = make_ctx("r2")
    await run_module.drive(ctx)
    report = fake_store.saved_report
    assert report.discovery is None  # honest: nothing to reason about without real source data
    assert report.meta.status == "done"


async def test_drive_can_disable_challenge_stage(wired):
    fake_bus, fake_store = wired
    ctx = make_ctx("r3")
    await run_module.drive(ctx, disable_challenge=True)
    starts = [e[2]["stage"] for e in fake_bus.events if e[1] == "stage" and e[2]["state"] == "start"]
    assert "Challenge" not in starts
    assert fake_bus.events[-1][1] == "done"


async def test_drive_marks_failed_and_emits_error_on_stage_exception(wired, monkeypatch):
    fake_bus, fake_store = wired
    ctx = make_ctx("r4")

    async def boom(c):
        raise RuntimeError("synthetic failure")

    monkeypatch.setattr(run_module, "STAGES", [("Discover", boom, 50)] + run_module.STAGES[1:])
    await run_module.drive(ctx)
    assert fake_store.failed is not None
    assert fake_store.failed[0] == "r4"
    assert "synthetic failure" in fake_store.failed[1]
    assert fake_bus.events[-1][1] == "run_error"


async def test_drive_times_out_a_slow_stage_and_marks_partial(wired, monkeypatch):
    fake_bus, fake_store = wired
    ctx = make_ctx("r5")

    async def slow(c):
        import asyncio
        await asyncio.sleep(10)

    monkeypatch.setattr(run_module, "STAGES", [("Discover", slow, 0)] + run_module.STAGES[1:])
    await run_module.drive(ctx)
    assert ctx.partial is True
    timeouts = [e for e in fake_bus.events if e[1] == "stage" and e[2]["state"] == "timeout"]
    assert len(timeouts) == 1
    assert fake_store.saved_report.meta.status == "partial"


async def test_drive_passes_nse_client_through_to_connect_stage(wired, monkeypatch):
    fake_bus, fake_store = wired
    ctx = make_ctx("r6")
    received = {}

    async def fake_connect_run(c, nse_client=None):
        received["nse_client"] = nse_client

    monkeypatch.setattr(run_module, "STAGES", [
        ("Discover", run_module.discover.run, 50), ("Connect", fake_connect_run, 120),
    ] + run_module.STAGES[2:])
    sentinel = object()
    await run_module.drive(ctx, nse_client=sentinel)
    assert received["nse_client"] is sentinel


async def test_drive_defaults_to_no_nse_client_so_connect_stays_offline(wired):
    fake_bus, fake_store = wired
    ctx = make_ctx("r7")
    await run_module.drive(ctx)  # no nse_client passed
    assert ctx.documents == []  # connect.run's own honest degrade, confirming no live client was used


async def test_start_run_constructs_a_real_nse_client_and_passes_it_to_drive(monkeypatch):
    calls = {}

    async def fake_resolve(query, as_of=None):
        return make_ctx("r8")

    async def fake_drive(ctx, disable_challenge=False, nse_client=None):
        calls["nse_client"] = nse_client

    class FakeNSE:
        pass

    monkeypatch.setattr(run_module.resolve, "run", fake_resolve)
    monkeypatch.setattr(run_module, "drive", fake_drive)
    monkeypatch.setattr(run_module, "NSE", FakeNSE)
    monkeypatch.setattr(run_module.store, "create_run", lambda ctx: None)

    run_id = await run_module.start_run("CIPLA")
    assert run_id == "r8"
    # asyncio.create_task schedules fake_drive; let the event loop run it before asserting
    import asyncio
    await asyncio.sleep(0)
    assert isinstance(calls["nse_client"], FakeNSE)
