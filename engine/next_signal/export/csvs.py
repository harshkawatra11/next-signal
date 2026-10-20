"""CSV export: one UTF-8-with-BOM file per table, zipped. BOM so Excel renders the rupee symbol and
Indian digit grouping correctly (pattern used in quiz-platform's apps/web/src/lib/export.ts).
"""
from __future__ import annotations

import csv
import io
import zipfile
from pathlib import Path

from ..schemas import Report

_TABLES = (
    "evidence", "numbers", "timeline", "hypotheses", "tests", "ach", "contradictions",
    "sources", "metrics", "anomalies",
)


def _write_csv_bom(rows: list[list[str]]) -> bytes:
    buf = io.StringIO()
    w = csv.writer(buf, lineterminator="\r\n")
    for row in rows:
        w.writerow(row)
    return ("﻿" + buf.getvalue()).encode("utf-8")


def table_rows(report: Report, table: str) -> list[list[str]]:
    d = report.discovery
    if table == "evidence":
        rows = [["ev_id", "title", "publisher", "origin_class", "reliability", "published_at", "url", "quote"]]
        if d:
            for e in d.evidence:
                rows.append([e.ev_id, e.title, e.publisher, e.origin_class, e.reliability,
                            str(e.published_at or ""), e.url, e.anchor.quote])
        return rows
    if table == "numbers":
        rows = [["number_id", "label", "display", "value", "unit", "period", "formula"]]
        if d:
            for n in d.numbers:
                rows.append([n.number_id, n.label, n.display, str(n.value), n.unit, n.period, n.formula])
        return rows
    if table == "timeline":
        rows = [["date", "label", "kind", "is_changepoint"]]
        if d:
            for t in d.timeline:
                rows.append([str(t.date), t.label, t.kind, str(t.is_changepoint)])
        return rows
    if table == "hypotheses":
        rows = [["hyp_id", "angle_id", "statement", "status", "kill_reason"]]
        for h in report.runners_up + report.killed:
            rows.append([h.hyp_id, h.angle_id, h.statement, h.status, h.kill_reason or ""])
        return rows
    if table == "tests":
        rows = [["hyp_id", "test_id", "applicable", "passed", "detail"]]
        for t in report.tests:
            rows.append([t.hyp_id, t.test_id, str(t.applicable), str(t.passed), t.detail])
        return rows
    if table == "ach":
        rows = [["evidence", *report.ach.get("hypotheses", [])]]
        for i, e in enumerate(report.ach.get("evidence", [])):
            cells = report.ach.get("cells", [])
            row_cells = cells[i] if i < len(cells) else []
            rows.append([e, *row_cells])
        return rows
    if table == "contradictions":
        rows = [["type", "claim", "side_a", "side_b", "ruling", "resolved"]]
        for c in report.contradictions:
            rows.append([c.type, c.claim, c.side_a, c.side_b, c.ruling, str(c.resolved)])
        return rows
    if table == "sources":
        rows = [["title", "publisher", "origin_class", "reliability", "url"]]
        for doc in report.documents:
            rows.append([doc.title, doc.publisher, doc.origin_class, doc.reliability, doc.url])
        return rows
    if table == "metrics":
        rows = [["metric_id", "period", "value", "unit", "formula"]]
        for m in report.metrics:
            rows.append([m.metric_id, m.period, str(m.value), m.unit, m.formula])
        return rows
    if table == "anomalies":
        rows = [["anomaly_id", "metric_id", "description", "score", "peer_z", "changepoint_period"]]
        for a in report.anomalies:
            rows.append([a.anomaly_id, a.metric_id, a.description, str(a.score), str(a.peer_z or ""), a.changepoint_period or ""])
        return rows
    raise ValueError(f"unknown table: {table}")


def build_zip(report: Report, out_path: Path) -> Path:
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(out_path, "w", zipfile.ZIP_DEFLATED) as zf:
        for table in _TABLES:
            zf.writestr(f"{table}.csv", _write_csv_bom(table_rows(report, table)))
    return out_path
