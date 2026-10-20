"""Renders the research paper's HTML (paper.html.j2) and prints it to PDF with headless Chrome, then
stamps page numbers, a running header and PDF metadata with PyMuPDF (Chrome's own margin boxes are
not reliable from the command line, so --no-pdf-header-footer is used and the running header/footer
is added here instead).
"""
from __future__ import annotations

import asyncio
import os
from pathlib import Path

import fitz
from jinja2 import Environment, FileSystemLoader, select_autoescape

from ..export.pdf import print_html_to_pdf
from ..schemas import Report
from .spec import build_spec
from .writer import ensure_paper_text

_TEMPLATES_DIR = Path(__file__).resolve().parents[1] / "export" / "templates"
_FONTS_DIR = Path(__file__).resolve().parents[1] / "export" / "fonts"
_env = Environment(loader=FileSystemLoader(str(_TEMPLATES_DIR)), autoescape=select_autoescape(["html", "j2"]))
_env.globals["zip"] = zip


def render_paper_html(report: Report) -> tuple[str, "object"]:
    """Returns (html, spec); split out so tests can render without a live LLM call."""
    spec = build_spec(report)
    return spec


def _tables_by_number(spec):
    return {t.number: t for t in spec.tables}


def _figures_by_number(spec):
    return {f.number: f for f in spec.figures}


def _render_html(report: Report, text, spec) -> str:
    tables = _tables_by_number(spec)
    figures = _figures_by_number(spec)
    ctx = {
        "text": text, "spec": spec,
        "table1": tables.get(1), "table2": tables.get(2), "table3": tables.get(3), "table4": tables.get(4),
        "figure1": figures.get(1), "figure2": figures.get(2), "figure3": figures.get(3), "figure4": figures.get(4),
        "fonts": _FONTS_DIR.resolve().as_uri(),
    }
    return _env.get_template("paper.html.j2").render(**ctx)


def stamp(pdf_path, company: str, prepared: str, title: str) -> None:
    doc = fitz.open(pdf_path)
    n = doc.page_count
    left = 25 * 72 / 25.4
    for i, page in enumerate(doc):
        w, h = page.rect.width, page.rect.height
        if i > 0:
            page.insert_text((left, 44), company, fontname="tiro", fontsize=8.5)
            right = f"Research note, {prepared}"
            page.insert_text((w - left - fitz.get_text_length(right, fontname="tiro", fontsize=8.5), 44), right, fontname="tiro", fontsize=8.5)
            page.draw_line((left, 49), (w - left, 49), color=(0, 0, 0), width=0.4)
        foot = f"{i + 1} of {n}"
        page.insert_text(((w - fitz.get_text_length(foot, fontname="tiro", fontsize=9)) / 2, h - 40), foot, fontname="tiro", fontsize=9)
    doc.set_metadata({"title": title, "author": "Next Signal Research", "subject": f"Research note on {company}", "creator": "Next Signal"})
    tmp = str(pdf_path) + ".tmp"
    doc.save(tmp, garbage=3, deflate=True)
    doc.close()
    os.replace(tmp, pdf_path)


async def build_paper_pdf(report: Report, out_path: Path) -> Path:
    text = await ensure_paper_text(report)
    spec = build_spec(report)
    html = _render_html(report, text, spec)
    html_path = out_path.with_suffix(".html")
    html_path.parent.mkdir(parents=True, exist_ok=True)
    html_path.write_text(html, encoding="utf-8")
    await asyncio.to_thread(print_html_to_pdf, html_path, out_path)
    stamp(out_path, report.meta.company, spec.prepared, text.title)
    return out_path
