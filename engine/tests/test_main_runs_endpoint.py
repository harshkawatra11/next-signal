from fastapi.testclient import TestClient

import next_signal.main as main_module
from next_signal import main


def test_create_run_requires_query():
    client = TestClient(main.app)
    r = client.post("/api/runs", json={})
    assert r.status_code == 422


def test_create_run_returns_run_id_on_success(monkeypatch):
    async def fake_start_run(query, as_of=None, disable_challenge=False):
        assert query == "CIPLA"
        return "CIPLA-20261015120000"

    monkeypatch.setattr(main_module, "start_run", fake_start_run)
    client = TestClient(main.app)
    r = client.post("/api/runs", json={"query": "CIPLA"})
    assert r.status_code == 200
    assert r.json() == {"run_id": "CIPLA-20261015120000"}


def test_create_run_returns_404_for_unresolvable_company(monkeypatch):
    async def fake_start_run(query, as_of=None, disable_challenge=False):
        raise ValueError(f"could not resolve '{query}' to a listed company")

    monkeypatch.setattr(main_module, "start_run", fake_start_run)
    client = TestClient(main.app)
    r = client.post("/api/runs", json={"query": "NOTACOMPANY"})
    assert r.status_code == 404


def test_get_run_404_when_missing(monkeypatch):
    monkeypatch.setattr(main_module.store, "get_run_meta", lambda run_id: None)
    client = TestClient(main.app)
    r = client.get("/api/runs/does-not-exist")
    assert r.status_code == 404
