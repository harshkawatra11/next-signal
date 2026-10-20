"""Pure-Python SVG chart builders (no matplotlib). Palette: red/black/grey only, matching the UI tokens
(PLAN.md §6.2: --signal #C8102E, --ink #0B0B0C). Used both by the dashboard (for a pure-HTML export the
browser can render identically) and by the PDF export pipeline.
"""
from __future__ import annotations

import html

INK = "#0B0B0C"
SIGNAL = "#C8102E"
GREY = "#E2DFD9"
GREY_DARK = "#75716A"


def _esc(s: str) -> str:
    return html.escape(str(s), quote=True)


def _svg(width: int, height: int, body: str) -> str:
    return f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}">{body}</svg>'


def timeline_svg(points: list[dict], width: int = 900, height: int = 190) -> str:
    """points: [{date_frac: 0..1, label: str, kind: str, is_changepoint: bool}], date_frac already
    normalised to the plot's time range by the caller. Below-axis labels alternate between two rows
    so two points that land close together in date_frac do not render overlapping text."""
    if not points:
        return _svg(width, height, "")
    pad = 40
    axis_y = height - pad - 20
    parts = [f'<line x1="{pad}" y1="{axis_y}" x2="{width - pad}" y2="{axis_y}" stroke="{INK}" stroke-width="1.5"/>']
    span = width - 2 * pad
    below_i = 0
    for p in points:
        x = pad + p["date_frac"] * span
        color = SIGNAL if p.get("is_changepoint") else INK
        r = 7 if p.get("is_changepoint") else 5
        parts.append(f'<circle cx="{x:.1f}" cy="{axis_y}" r="{r}" fill="{color}" stroke="{INK}" stroke-width="1"/>')
        label = _esc(p.get("label", ""))[:28]
        if p.get("is_changepoint"):
            ly = axis_y - 14
        else:
            ly = axis_y + 18 + (below_i % 2) * 16
            below_i += 1
        parts.append(f'<text x="{x:.1f}" y="{ly}" font-size="11" text-anchor="middle" fill="{INK}">{label}</text>')
    return _svg(width, height, "".join(parts))


def line_svg(rows: list[dict], series: list[tuple[str, str]], width: int = 720, height: int = 220) -> str:
    """rows: [{"label": "Q1 FY26", "revenue": 1.0, ...}] oldest first. series: [(key, legend_label)].
    First series in SIGNAL, the rest in INK and GREY_DARK."""
    vals = [r[k] for r in rows for k, _ in series if r.get(k) is not None]
    if len(rows) < 2 or not vals:
        return _svg(width, 40, "")
    pad_l, pad_r, pad_t, pad_b = 70, 20, 16, 34
    lo, hi = min(0.0, min(vals)), max(vals)
    span = (hi - lo) or 1.0
    def x(i): return pad_l + i * (width - pad_l - pad_r) / (len(rows) - 1)
    def y(v): return pad_t + (height - pad_t - pad_b) * (1 - (v - lo) / span)
    colors = [SIGNAL, INK, GREY_DARK]
    parts = []
    for frac in (0, 0.5, 1):
        gv = lo + span * frac
        parts.append(f'<line x1="{pad_l}" y1="{y(gv):.1f}" x2="{width - pad_r}" y2="{y(gv):.1f}" stroke="{GREY}" stroke-dasharray="2,4"/>')
        parts.append(f'<text x="{pad_l - 6}" y="{y(gv) + 4:.1f}" font-size="10" text-anchor="end" fill="{GREY_DARK}">{gv:,.0f}</text>')
    for i, r in enumerate(rows):
        parts.append(f'<text x="{x(i):.1f}" y="{height - 12}" font-size="10" text-anchor="middle" fill="{GREY_DARK}">{_esc(r["label"])}</text>')
    for si, (key, label) in enumerate(series):
        pts = [(x(i), y(r[key])) for i, r in enumerate(rows) if r.get(key) is not None]
        if len(pts) < 2:
            continue
        c = colors[si % len(colors)]
        parts.append(f'<polyline fill="none" stroke="{c}" stroke-width="2" points="{" ".join(f"{a:.1f},{b:.1f}" for a, b in pts)}"/>')
        parts.append(f'<text x="{pad_l + 6 + si * 110}" y="{pad_t - 2}" font-size="11" fill="{c}">{_esc(label)}</text>')
    return _svg(width, height, "".join(parts))


def bars_svg(numbers: list[dict], width: int = 700, height: int = 260) -> str:
    """numbers: [{label: str, value: float}]. Horizontal bars, red for the largest (the 'moneyshot'
    convention: strong colour on the headline value), ink for the rest."""
    if not numbers:
        return _svg(width, height, "")
    pad_left = 160
    pad_right_label = 50  # reserved so the value label after the longest bar never clips the viewBox
    row_h = height / len(numbers)
    max_v = max(abs(n["value"]) for n in numbers) or 1.0
    parts = []
    max_idx = max(range(len(numbers)), key=lambda i: abs(numbers[i]["value"]))
    for i, n in enumerate(numbers):
        y = i * row_h + row_h * 0.2
        bar_h = row_h * 0.6
        bar_w = (width - pad_left - pad_right_label) * abs(n["value"]) / max_v
        color = SIGNAL if i == max_idx else INK
        parts.append(f'<text x="{pad_left - 10}" y="{y + bar_h / 2 + 4}" font-size="12" text-anchor="end" fill="{INK}">{_esc(n["label"])}</text>')
        parts.append(f'<rect x="{pad_left}" y="{y:.1f}" width="{bar_w:.1f}" height="{bar_h:.1f}" fill="{color}"/>')
        parts.append(f'<text x="{pad_left + bar_w + 8:.1f}" y="{y + bar_h / 2 + 4}" font-size="12" fill="{INK}">{_esc(n["value"])}</text>')
    return _svg(width, height, "".join(parts))


def ach_heat_svg(matrix: dict, width: int = 760, cell: int = 56) -> str:
    """matrix: {"hypotheses": [...], "evidence": [...], "cells": [[glyph,...],...]}."""
    hyps = matrix.get("hypotheses", [])
    evs = matrix.get("evidence", [])
    cells = matrix.get("cells", [])
    if not hyps or not evs:
        return _svg(width, 100, "")
    label_w = 180
    # Header rotated -40deg so a hypothesis id longer than one cell's width (56px) reads on its own
    # diagonal line instead of overlapping the neighbouring column's header text.
    header_h = 90
    height = header_h + cell * len(evs)
    color_map = {"CC": INK, "C": GREY_DARK, "N": "#FFFFFF", "I": "#F19AA6", "II": SIGNAL}
    text_color_map = {"CC": "#FFFFFF", "C": "#FFFFFF", "N": INK, "I": INK, "II": "#FFFFFF"}
    parts = []
    for j, h in enumerate(hyps):
        x = label_w + j * cell
        tx, ty = x + cell / 2 + 4, header_h - 8
        parts.append(f'<text x="{tx}" y="{ty}" font-size="11" text-anchor="start" fill="{INK}" transform="rotate(-40 {tx} {ty})">{_esc(h)[:18]}</text>')
    for i, e in enumerate(evs):
        y = header_h + i * cell
        parts.append(f'<text x="{label_w - 8}" y="{y + cell / 2 + 4}" font-size="11" text-anchor="end" fill="{INK}">{_esc(e)[:22]}</text>')
        for j, h in enumerate(hyps):
            x = label_w + j * cell
            glyph = cells[i][j] if i < len(cells) and j < len(cells[i]) else "N"
            fill = color_map.get(glyph, "#FFFFFF")
            tcolor = text_color_map.get(glyph, INK)
            parts.append(f'<rect x="{x}" y="{y}" width="{cell}" height="{cell}" fill="{fill}" stroke="{INK}" stroke-width="1"/>')
            parts.append(f'<text x="{x + cell / 2}" y="{y + cell / 2 + 4}" font-size="12" text-anchor="middle" fill="{tcolor}">{_esc(glyph)}</text>')
    # Extra right margin so the last column's diagonal header (it projects up and to the right of its
    # cell) has room to finish inside the viewBox instead of being clipped at the SVG's right edge.
    return _svg(label_w + cell * len(hyps) + 70, height, "".join(parts))


def strength_bar_svg(breakdown: dict, width: int = 500, height: int = 70) -> str:
    """breakdown: {independence, reliability, corroboration, survival, persistence, total, label}.
    A single stacked horizontal bar with the Strong/Moderate thresholds marked (4 and 7)."""
    max_scale = 10.0
    segments = [
        ("independence", breakdown.get("independence", 0), "#0B0B0C"),
        ("reliability", breakdown.get("reliability", 0), "#3A3936"),
        ("corroboration", breakdown.get("corroboration", 0), "#75716A"),
        ("survival", breakdown.get("survival", 0), "#C8102E"),
        ("persistence", breakdown.get("persistence", 0), "#E23A50"),
    ]
    pad = 10
    bar_w = width - 2 * pad
    bar_h = 28
    y = 10
    parts = []
    x = pad
    for name, val, color in segments:
        seg_w = bar_w * max(0.0, val) / max_scale
        if seg_w > 0:
            parts.append(f'<rect x="{x:.1f}" y="{y}" width="{seg_w:.1f}" height="{bar_h}" fill="{color}"/>')
        x += seg_w
    for threshold, tlabel in ((4, "Moderate"), (7, "Strong")):
        tx = pad + bar_w * threshold / max_scale
        parts.append(f'<line x1="{tx:.1f}" y1="{y - 4}" x2="{tx:.1f}" y2="{y + bar_h + 4}" stroke="{INK}" stroke-width="1.5" stroke-dasharray="3,2"/>')
        parts.append(f'<text x="{tx:.1f}" y="{y + bar_h + 18}" font-size="10" text-anchor="middle" fill="{INK}">{tlabel}</text>')
    parts.append(f'<rect x="{pad}" y="{y}" width="{bar_w}" height="{bar_h}" fill="none" stroke="{INK}" stroke-width="1.5"/>')
    return _svg(width, height, "".join(parts))
