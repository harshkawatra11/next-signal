import pytest
from fastapi.testclient import TestClient
import next_signal.main as main_module


@pytest.fixture
def client():
    return TestClient(main_module.app)


@pytest.mark.parametrize("kind,ctype", [("md", "text/markdown"), ("xlsx", "spreadsheetml"), ("zip", "application/zip")])
def test_fixture_exports_download(client, kind, ctype):
    r = client.get(f"/api/runs/fixture/export.{kind}")
    assert r.status_code == 200
    assert ctype in r.headers["content-type"]
    assert "attachment" in r.headers["content-disposition"]
    assert len(r.content) > 200


def test_pdf_export_uses_writer(client, monkeypatch):
    async def fake_pdf(report, out_path):
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_bytes(b"%PDF-1.4" + b"0" * 2000)
        return out_path
    monkeypatch.setattr(main_module, "build_paper_pdf", fake_pdf)
    r = client.get("/api/runs/fixture/export.pdf")
    assert r.status_code == 200 and r.content.startswith(b"%PDF")


def test_unknown_kind_404(client):
    assert client.get("/api/runs/fixture/export.docx").status_code == 404


def test_missing_run_404(client):
    assert client.get("/api/runs/NOPE-1/export.md").status_code == 404
