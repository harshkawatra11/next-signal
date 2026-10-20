"""Markdown export: the brief's eight output elements in order, rendered from the Report model.
Section headings follow the brief's own wording (Discovery, Why It Matters, Evidence, Timeline, Numbers,
Counterargument, Falsification Condition, Evidence Strength) so a reader can check the output against the
brief line by line.
"""
from __future__ import annotations

from pathlib import Path

from jinja2 import Environment, FileSystemLoader, select_autoescape

from ..schemas import Report

_TEMPLATES_DIR = Path(__file__).parent / "templates"
_env = Environment(
    loader=FileSystemLoader(str(_TEMPLATES_DIR)),
    autoescape=select_autoescape(enabled_extensions=()),
    trim_blocks=True,
    lstrip_blocks=True,
)


def render_markdown(report: Report) -> str:
    template = _env.get_template("report.md.j2")
    return template.render(report=report, discovery=report.discovery)


def write_markdown(report: Report, out_path: Path) -> Path:
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(render_markdown(report), encoding="utf-8")
    return out_path
