import json
import re
from pathlib import Path

import fitz
import pytest

import next_signal.paper.render as render_module
from next_signal.paper import fallback
from next_signal.paper.spec import build_spec
from next_signal.paper.writer import PaperText
from next_signal.schemas import Report

FIXTURE_FULL = Path(__file__).parent / "fixtures" / "report_full.json"

_IDENT_RE = re.compile(r"\b[a-z][a-z0-9]*(?:_[a-z0-9]+)+\b")
_OPERATOR_RE = re.compile(r"(<=|>=|==|\s[<>]\s)")
_INTERNAL_ID_RE = re.compile(r"\b(?:H|P|T|EV|N|C|D)\d{1,2}\b")


def _report():
    return Report.model_validate(json.loads(FIXTURE_FULL.read_text(encoding="utf-8")))


def _fallback_text(spec) -> PaperText:
    return PaperText(
        title=fallback.title(spec),
        abstract=fallback.abstract(spec),
        introduction=fallback.introduction(spec),
        company_and_data=fallback.company_and_data(spec),
        findings=fallback.findings(spec),
        explanations=fallback.explanations(spec),
        outlook=fallback.outlook(spec),
        conclusion=fallback.conclusion(spec),
    )


def _fake_print(html_path: Path, pdf_path: Path, timeout: int = 120) -> Path:
    doc = fitz.open()
    doc.new_page()
    pdf_path.parent.mkdir(parents=True, exist_ok=True)
    doc.save(pdf_path)
    doc.close()
    return pdf_path


@pytest.mark.asyncio
async def test_build_paper_pdf_is_stamped_with_metadata(tmp_path, monkeypatch):
    report = _report()
    spec = build_spec(report)
    text = _fallback_text(spec)

    async def fake_ensure_paper_text(r):
        return text

    monkeypatch.setattr(render_module, "ensure_paper_text", fake_ensure_paper_text)
    monkeypatch.setattr(render_module, "print_html_to_pdf", _fake_print)

    out_path = tmp_path / "paper.pdf"
    result = await render_module.build_paper_pdf(report, out_path)
    assert result == out_path
    assert out_path.exists()

    doc = fitz.open(out_path)
    assert doc.metadata.get("author") == "Next Signal Research"
    doc.close()


def test_rendered_html_has_required_markers_and_no_leaked_identifiers(tmp_path):
    report = _report()
    spec = build_spec(report)
    text = _fallback_text(spec)
    html = render_module._render_html(report, text, spec)

    assert "Abstract." in html
    assert "Table 1." in html
    assert "Figure 1." in html
    assert "References" in html

    # Scan only the reader-facing body text: strip <style> (the font-face src paths legitimately
    # contain underscores, e.g. .../next_signal/export/fonts/...) and every <svg>...</svg> block
    # (matplotlib's own generated element ids, e.g. "m1234567890", can collide with the identifier
    # regex).
    body = html[html.find("<body>"):]
    without_svg = re.sub(r"<svg.*?</svg>", "", body, flags=re.S)
    without_style = re.sub(r"<style>.*?</style>", "", without_svg, flags=re.S)
    # The references list legitimately carries raw source URLs, which may contain underscores or
    # angle-bracket-like path segments (e.g. a regulator's own "cms_ia/form483/..." URL); those are
    # citation data, not prose, so they are excluded from the banned-pattern scan below.
    without_refs = re.sub(r'<ol class="refs">.*?</ol>', "", without_style, flags=re.S)
    assert not _IDENT_RE.search(without_refs)
    assert not _OPERATOR_RE.search(without_refs)
    assert not _INTERNAL_ID_RE.search(without_refs)
