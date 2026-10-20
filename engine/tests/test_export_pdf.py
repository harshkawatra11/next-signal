import shutil
from pathlib import Path

import pytest

from next_signal.export.pdf import print_html_to_pdf

CHROME_AVAILABLE = Path(r"C:\Program Files\Google\Chrome\Application\chrome.exe").exists() or shutil.which("chrome")


@pytest.mark.skipif(not CHROME_AVAILABLE, reason="Chrome not found on this machine")
def test_print_html_to_pdf_produces_a_real_pdf(tmp_path):
    html_path = tmp_path / "r.html"
    html_path.write_text("<!doctype html><html><body><h1>Test</h1></body></html>", encoding="utf-8")
    out = print_html_to_pdf(html_path, tmp_path / "r.pdf")
    assert out.exists()
    data = out.read_bytes()
    assert data[:5] == b"%PDF-"
    assert len(data) > 1000


def test_print_html_to_pdf_raises_clear_error_without_chrome(tmp_path, monkeypatch):
    import next_signal.export.pdf as pdf_module
    monkeypatch.setattr(pdf_module, "_find_chrome", lambda: (_ for _ in ()).throw(RuntimeError("Chrome or Edge not found; cannot render PDF export")))
    html_path = tmp_path / "r.html"
    html_path.write_text("<!doctype html><html><body>x</body></html>", encoding="utf-8")
    with pytest.raises(RuntimeError, match="Chrome or Edge not found"):
        print_html_to_pdf(html_path, tmp_path / "r.pdf")
