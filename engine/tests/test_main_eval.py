import json

import pytest
from fastapi.testclient import TestClient

import next_signal.main as main_module


@pytest.fixture
def client():
    return TestClient(main_module.app)


def test_eval_summary_404_then_200(client, tmp_path, monkeypatch):
    monkeypatch.setattr(main_module, "_EVAL_OUT", tmp_path)
    assert client.get("/api/eval/summary").status_code == 404
    (tmp_path / "summary.json").write_text(json.dumps({"companies": 3}), encoding="utf-8")
    r = client.get("/api/eval/summary")
    assert r.status_code == 200
    assert r.json() == {"companies": 3}


def test_eval_companies_404_then_200(client, tmp_path, monkeypatch):
    monkeypatch.setattr(main_module, "_EVAL_OUT", tmp_path)
    assert client.get("/api/eval/companies").status_code == 404
    (tmp_path / "companies.json").write_text(json.dumps([{"symbol": "CIPLA"}]), encoding="utf-8")
    r = client.get("/api/eval/companies")
    assert r.status_code == 200
    assert r.json() == [{"symbol": "CIPLA"}]
