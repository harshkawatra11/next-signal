"""Builds everything in the research paper that is not prose: the facts (plain sentence fragments
with citations), the figures (grayscale SVG), and the tables (booktabs-style), from a Report. The
writer (writer.py) turns these facts into paragraphs; it never computes or invents a number, it only
narrates the numbers this module already computed from the report's own fields.
"""
from __future__ import annotations

from dataclasses import dataclass, field

from .. import plain
from ..llm import guards
from ..schemas import Report
from . import figures
from .references import Reference, build_references

_SECTOR_WORDS = {
    "pharma": "pharmaceutical manufacturer",
    "hospital": "hospital operator",
    "diagnostics": "diagnostics provider",
}


@dataclass
class Fact:
    key: str
    text: str
    cite: list[int]


@dataclass
class Table:
    number: int
    caption: str
    columns: list[str]
    rows: list[list[str]]
    align: list[str]
    note: str = ""


@dataclass
class Figure:
    number: int
    caption: str
    svg: str
    note: str = ""


@dataclass
class PaperSpec:
    company: str
    symbol: str
    sector_phrase: str
    prepared: str
    as_of: str
    has_finding: bool
    facts: dict[str, list[Fact]]
    figures: list[Figure]
    tables: list[Table]
    references: list[Reference]
    allowed_numbers: set[str]
    keywords: list[str]
    n_quarters: int = 0
    n_peers: int = 0
    n_explanations: int = 0
    focus_metric: str = ""
    focus_metric_name: str = ""
    changepoint_quarter: str = ""


def _sector_phrase(report: Report) -> str:
    return _SECTOR_WORDS.get(report.meta.sub_industry, "listed company")


def _peer_name(report: Report, symbol: str) -> str:
    return report.peer_names.get(symbol, symbol) if report.peer_names else symbol


def _cite(doc_to_num: dict, doc_id: str) -> list[int]:
    n = doc_to_num.get(doc_id)
    return [n] if n else []


def _cites_str(nums: list[int]) -> str:
    nums = sorted(set(nums))
    if not nums:
        return ""
    return " ".join(f"[{n}]" for n in nums)


def _fin_rows_chrono(report: Report) -> list:
    """Table 1's 8 quarters, oldest first (chronological), for the table and Figure 1."""
    return list(reversed(report.financials[:8]))


def _margin(values: dict, numerator: str, denom: str = "revenue") -> float | None:
    rev = values.get(denom)
    num = values.get(numerator)
    if rev in (None, 0) or num is None:
        return None
    return num / rev


def _build_table1(report: Report, doc_to_num: dict) -> Table:
    rows_chrono = _fin_rows_chrono(report)
    rows_newest_first = list(reversed(rows_chrono))
    cols = ["Quarter", "Revenue", "Gross profit", "EBITDA", "Other income", "Profit before tax", "Net profit"]
    out_rows = []
    for r in rows_newest_first:
        v = r.values
        out_rows.append([
            plain.period_phrase(r.period),
            plain.indian_group(v["revenue"], 1) if v.get("revenue") is not None else "",
            plain.indian_group(v["gross_profit"], 1) if v.get("gross_profit") is not None else "",
            plain.indian_group(v["ebitda"], 1) if v.get("ebitda") is not None else "",
            plain.indian_group(v["other_income"], 1) if v.get("other_income") is not None else "",
            plain.indian_group(v["pbt"], 1) if v.get("pbt") is not None else "",
            plain.indian_group(v["pat"], 1) if v.get("pat") is not None else "",
        ])
    first_q, last_q = rows_chrono[0], rows_chrono[-1]
    caption = (
        f"Revenue from operations {'rose' if last_q.values.get('revenue', 0) >= first_q.values.get('revenue', 0) else 'fell'} "
        f"from Rs {plain.indian_group(first_q.values.get('revenue', 0), 1)} crore in {plain.period_phrase(first_q.period)} "
        f"to Rs {plain.indian_group(last_q.values.get('revenue', 0), 1)} crore in {plain.period_phrase(last_q.period)}."
    )
    doc_ids = [r.doc_id for r in rows_newest_first if r.doc_id]
    cite_nums = sorted({doc_to_num[d] for d in doc_ids if d in doc_to_num})
    if cite_nums:
        note = f"Source: the company's quarterly financial results filed with the National Stock Exchange of India [{cite_nums[0]}] to [{cite_nums[-1]}]." if len(cite_nums) > 1 else f"Source: the company's quarterly financial results filed with the National Stock Exchange of India [{cite_nums[0]}]."
    else:
        note = "Source: the company's quarterly financial results filed with the National Stock Exchange of India."
    return Table(number=1, caption=caption, columns=cols, rows=out_rows,
                 align=["l", "r", "r", "r", "r", "r", "r"], note=note)


def _build_table2(report: Report) -> Table:
    rows_chrono = _fin_rows_chrono(report)
    rows_newest_first = list(reversed(rows_chrono))
    by_period = {r.period: r.values for r in report.financials}

    def _yoy(period: str, values: dict) -> float | None:
        # same quarter, prior fiscal year: "Q1FY27" -> "Q1FY26"
        import re
        m = re.match(r"^(Q\d)FY(\d+)$", period)
        if not m:
            return None
        prior = f"{m.group(1)}FY{int(m.group(2)) - 1}"
        prior_vals = by_period.get(prior)
        if not prior_vals or prior_vals.get("revenue") in (None, 0) or values.get("revenue") is None:
            return None
        return (values["revenue"] - prior_vals["revenue"]) / prior_vals["revenue"]

    out_rows = []
    for r in rows_newest_first:
        v = r.values
        gm = _margin(v, "gross_profit")
        em = _margin(v, "ebitda")
        pm = _margin(v, "pat")
        yoy = _yoy(r.period, v)
        out_rows.append([
            plain.period_phrase(r.period),
            f"{gm * 100:.1f}%" if gm is not None else "",
            f"{em * 100:.1f}%" if em is not None else "",
            f"{pm * 100:.1f}%" if pm is not None else "",
            f"{yoy * 100:.1f}%" if yoy is not None else "",
        ])
    return Table(
        number=2,
        caption="Margins and revenue growth, computed from Table 1.",
        columns=["Quarter", "Gross margin", "EBITDA margin", "Net profit margin", "Revenue growth on a year earlier"],
        rows=out_rows, align=["l", "r", "r", "r", "r"],
        note="Source: computed from Table 1.",
    )


_KILL_PREFIX = __import__("re").compile(r"^failed\s+[A-Z]{1,2}\d{1,2}\s*\([^)]*\):\s*", __import__("re").I)


def _plain_kill_reason(text: str) -> str:
    """kill_reason strings are written as technical labels ('failed T1 (peer test): ...'); the paper
    needs the plain English remainder. If TestResult.plain was not set for the deciding test, strip
    the technical prefix rather than print the internal test id."""
    if not text:
        return ""
    cleaned = _KILL_PREFIX.sub("", text)
    cleaned = cleaned[0].upper() + cleaned[1:] if cleaned else cleaned
    if not cleaned.endswith("."):
        cleaned += "."
    return cleaned


def _hyp_row(h, tests_by_hyp: dict, result: str) -> list[str]:
    tests = tests_by_hyp.get(h.hyp_id, [])
    applicable = [t for t in tests if t.applicable]
    checked = "; ".join(plain.test_question(t.test_id) for t in applicable) or "No applicable checks"
    if result == "Rejected":
        deciding = [t for t in applicable if t.passed is False]
    elif result == "Supported":
        deciding = [t for t in applicable if t.passed is True]
    else:
        deciding = applicable
    reason_sentences = [t.plain for t in deciding if t.plain][:2]
    reason = " ".join(reason_sentences) or _plain_kill_reason(h.kill_reason or "")
    if not reason:
        reason = "the checks applied to it were not conclusive either way."
    reason = plain.scrub_identifiers(reason)
    return [plain.scrub_identifiers(h.statement), checked, result, reason]


def _build_table3(report: Report, tests_by_hyp: dict) -> Table:
    out_rows = []
    if report.discovery:
        chosen_tests = tests_by_hyp.get(report.discovery.hyp_id, [])
        applicable = [t for t in chosen_tests if t.applicable]
        checked = "; ".join(plain.test_question(t.test_id) for t in applicable) or "No applicable checks"
        passed_sentences = [t.plain for t in applicable if t.passed and t.plain][:2]
        reason = " ".join(passed_sentences) or "The checks in this section did not contradict it."
        out_rows.append([plain.scrub_identifiers(report.discovery.sentence), checked, "Supported", reason])
    for h in report.runners_up:
        out_rows.append(_hyp_row(h, tests_by_hyp, "Weakened"))
    for h in report.killed:
        out_rows.append(_hyp_row(h, tests_by_hyp, "Rejected"))
    caption = (
        "Every explanation we tested for the change was either rejected or weakened, so no finding survives."
        if not report.discovery
        else "The surviving explanation held against every check applied to its strongest rivals."
    )
    return Table(number=3, caption=caption,
                 columns=["Explanation", "What was checked", "Result", "Reason"],
                 rows=out_rows, align=["l", "l", "l", "l"],
                 note="Source: the checks set out in Section 4.")


def _focus_metric(report: Report) -> str | None:
    """The measure the paper centres on. schemas.Discovery does not carry its own Prediction list
    (only schemas.Hypothesis does, and the chosen hypothesis object is not retained on Report once
    it becomes a Discovery), so the discovery's focus metric is read off the top-scored anomaly
    instead, which is how Prove picks the discovery's angle in the first place."""
    if report.anomalies:
        return sorted(report.anomalies, key=lambda a: a.score, reverse=True)[0].metric_id
    if any(s.metric_id == "ebitda_margin" for s in report.series):
        return "ebitda_margin"
    return None


def _series_for(report: Report, entity: str, metric_id: str):
    return next((s for s in report.series if s.entity == entity and s.metric_id == metric_id), None)


def _build_table4(report: Report, focus_metric: str | None) -> Table | None:
    if len(report.peers) < 1:
        return None
    entities = [report.meta.symbol] + report.peers
    rows = []
    any_row = False
    for ent in entities:
        rev_s = _series_for(report, ent, "revenue")
        gm_s = _series_for(report, ent, "gross_margin")
        em_s = _series_for(report, ent, "ebitda_margin")
        yoy_s = _series_for(report, ent, "rev_yoy")
        name = report.meta.company if ent == report.meta.symbol else _peer_name(report, ent)

        def _latest(s):
            return s.points[-1].value if s and s.points else None

        rev, gm, em, yoy = _latest(rev_s), _latest(gm_s), _latest(em_s), _latest(yoy_s)
        if any(x is not None for x in (rev, gm, em, yoy)):
            any_row = True
        rows.append([
            name,
            plain.indian_group(rev, 1) if rev is not None else "",
            f"{gm * 100:.1f}%" if gm is not None else "",
            f"{em * 100:.1f}%" if em is not None else "",
            f"{yoy * 100:.1f}%" if yoy is not None else "",
        ])
    if not any_row:
        return None
    return Table(number=4, caption="Latest comparable quarter across the company and its listed peers.",
                 columns=["Company", "Revenue (Rs crore)", "Gross margin", "EBITDA margin", "Revenue growth on a year earlier"],
                 rows=rows, align=["l", "r", "r", "r", "r"],
                 note="Source: the company's and its peers' quarterly financial results.")


def _figure1(report: Report) -> Figure:
    rows_chrono = _fin_rows_chrono(report)
    labels = [plain.period_phrase(r.period) for r in rows_chrono]
    revenue = [r.values.get("revenue") for r in rows_chrono]
    ebitda = [r.values.get("ebitda") for r in rows_chrono]
    svg = figures.revenue_ebitda(labels, revenue, ebitda)
    first_q, last_q = labels[0], labels[-1]
    caption = f"Quarterly revenue and EBITDA, {first_q} to {last_q}, Rs crore."
    return Figure(number=1, caption=caption, svg=svg)


def _figure2(report: Report, focus_metric: str | None) -> Figure | None:
    if not focus_metric:
        return None
    subj = _series_for(report, report.meta.symbol, focus_metric)
    if not subj or not subj.points:
        return None
    peer_series = [_series_for(report, p, focus_metric) for p in report.peers]
    peer_series = [s for s in peer_series if s and s.points]
    labels = [plain.period_phrase(p.period) for p in subj.points]
    subject_vals = [p.value for p in subj.points]
    peer_median: list[float | None] = []
    peer_low: list[float | None] = []
    peer_high: list[float | None] = []
    for i, pt in enumerate(subj.points):
        vals = [s.points[i].value for s in peer_series if i < len(s.points)]
        if vals:
            vals_sorted = sorted(vals)
            mid = len(vals_sorted) // 2
            median = vals_sorted[mid] if len(vals_sorted) % 2 else (vals_sorted[mid - 1] + vals_sorted[mid]) / 2
            peer_median.append(median)
            peer_low.append(min(vals_sorted))
            peer_high.append(max(vals_sorted))
        else:
            peer_median.append(None)
            peer_low.append(None)
            peer_high.append(None)
    cp_period = subj.changepoint_period
    cp_index = next((i for i, p in enumerate(subj.points) if p.period == cp_period), None) if cp_period else None
    unit = subj.unit
    pct = unit == "pct"
    ylabel = plain.metric_name(focus_metric) + (" (per cent)" if pct else "")
    cp_label = f"Change point: {plain.period_phrase(cp_period)}" if cp_period else ""
    svg = figures.metric_vs_peers(labels, subject_vals, peer_median, peer_low, peer_high,
                                  report.meta.company, ylabel, cp_index, cp_label, pct)
    last_subj = subject_vals[-1]
    last_peer = peer_high[-1] if peer_high and peer_high[-1] is not None else None
    last_peer_lo = peer_low[-1] if peer_low and peer_low[-1] is not None else None
    cp_phrase = f" from {plain.period_phrase(cp_period)}" if cp_period else ""
    if last_peer is None and last_peer_lo is None:
        trend = "rose" if len(subject_vals) > 1 and subject_vals[-1] >= subject_vals[0] else "fell"
        caption = f"{plain.metric_name(focus_metric)} at {report.meta.company} {trend} over the quarters examined{cp_phrase}."
    else:
        position = "within the range of"
        if last_peer is not None and last_subj is not None and last_subj > last_peer:
            position = "above the range of"
        elif last_peer_lo is not None and last_subj is not None and last_subj < last_peer_lo:
            position = "below the range of"
        caption = f"{plain.metric_name(focus_metric)} at {report.meta.company} moved {position} its peers{cp_phrase}."
    return Figure(number=2, caption=caption, svg=svg)


def _figure3(report: Report, focus_metric: str | None) -> Figure | None:
    if not focus_metric or len(report.peers) < 3:
        return None
    entities = [report.meta.symbol] + report.peers
    names, values = [], []
    for ent in entities:
        s = _series_for(report, ent, focus_metric)
        if s and s.points:
            names.append(report.meta.company if ent == report.meta.symbol else _peer_name(report, ent))
            values.append(s.points[-1].value)
    if len(values) < 3:
        return None
    unit = next((s.unit for s in report.series if s.metric_id == focus_metric), "")
    pct = unit == "pct"
    svg = figures.peer_bars(names, values, 0, plain.metric_name(focus_metric), pct)
    caption = f"{plain.metric_name(focus_metric)}, latest quarter, {report.meta.company} against its listed peers."
    return Figure(number=3, caption=caption, svg=svg)


def _figure4(report: Report) -> Figure | None:
    if not report.discovery or len(report.discovery.timeline) < 2:
        return None
    pts = report.discovery.timeline
    dates = [p.date for p in pts]
    labels = [p.label for p in pts]
    cp_date = next((p.date for p in pts if p.is_changepoint), None)
    svg = figures.event_timeline(dates, labels, cp_date)
    return Figure(number=4, caption="The sequence of dated events behind the finding.", svg=svg)


def build_spec(report: Report) -> PaperSpec:
    company = report.meta.company
    symbol = report.meta.symbol
    sector_phrase = _sector_phrase(report)
    references, doc_to_num = build_references(report)
    tests_by_hyp: dict[str, list] = {}
    for t in report.tests:
        tests_by_hyp.setdefault(t.hyp_id, []).append(t)

    has_finding = report.discovery is not None
    focus_metric = _focus_metric(report)

    table1 = _build_table1(report, doc_to_num)
    table2 = _build_table2(report)
    table3 = _build_table3(report, tests_by_hyp)
    table4 = _build_table4(report, focus_metric)
    tables = [table1, table2, table3] + ([table4] if table4 else [])

    figure1 = _figure1(report)
    figure2 = _figure2(report, focus_metric)
    figure3 = _figure3(report, focus_metric)
    figure4 = _figure4(report)
    figures_list = [figure1] + [f for f in (figure2, figure3, figure4) if f]
    # renumber in document order
    for i, f in enumerate(figures_list, start=1):
        f.number = i

    rows_chrono = _fin_rows_chrono(report)
    latest_row = rows_chrono[-1]
    prior_year_row = next((r for r in report.financials if r.period == _prior_year_period(latest_row.period)), None)

    facts: dict[str, list[Fact]] = {"intro": [], "company": [], "findings": [], "explanations": [], "outlook": []}

    facts["intro"].append(Fact("as_of", f"{company} is a {sector_phrase} listed on the National Stock Exchange of India, as of {plain.date_long(report.meta.as_of)}", []))
    if focus_metric:
        facts["intro"].append(Fact("focus", f"this note focuses on {plain.metric_phrase(focus_metric)}, compared against {len(report.peers)} listed peers", []))

    facts["company"].append(Fact(
        "latest_revenue",
        f"Revenue from operations in {plain.period_phrase(latest_row.period)} was Rs {plain.indian_group(latest_row.values.get('revenue', 0), 1)} crore",
        _cite(doc_to_num, latest_row.doc_id),
    ))
    if prior_year_row:
        facts["company"].append(Fact(
            "revenue_year_earlier",
            f"a year earlier, in {plain.period_phrase(prior_year_row.period)}, it was Rs {plain.indian_group(prior_year_row.values.get('revenue', 0), 1)} crore",
            _cite(doc_to_num, prior_year_row.doc_id),
        ))
    em_latest = _margin(latest_row.values, "ebitda")
    if em_latest is not None:
        facts["company"].append(Fact("ebitda_margin_latest", f"EBITDA margin was {em_latest * 100:.1f} per cent in {plain.period_phrase(latest_row.period)}", []))
    facts["company"].append(Fact("n_quarters", f"we examined {len(report.financials)} quarters of filed results", []))

    if focus_metric:
        subj = _series_for(report, symbol, focus_metric)
        if subj and subj.points:
            latest_point = subj.points[-1]
            unit = subj.unit
            facts["findings"].append(Fact(
                "focus_latest",
                f"{plain.metric_phrase(focus_metric)} stood at {plain.value_phrase(focus_metric, latest_point.value)} in {plain.period_phrase(latest_point.period)}",
                [],
            ))
            cp = subj.changepoint_period
            if cp:
                pre_points = [p.value for p in subj.points if p.period < cp]
                if pre_points:
                    pre_mean = sum(pre_points) / len(pre_points)
                    facts["findings"].append(Fact(
                        "focus_pre_change",
                        f"before {plain.period_phrase(cp)} it had averaged {plain.value_phrase(focus_metric, pre_mean)}",
                        [],
                    ))
                facts["findings"].append(Fact("changepoint", f"the clearest break is in {plain.period_phrase(cp)}", []))
            peer_series = [_series_for(report, p, focus_metric) for p in report.peers]
            peer_series = [s for s in peer_series if s and s.points]
            if peer_series:
                last_vals = sorted(s.points[-1].value for s in peer_series)
                mid = len(last_vals) // 2
                median = last_vals[mid] if len(last_vals) % 2 else (last_vals[mid - 1] + last_vals[mid]) / 2
                facts["findings"].append(Fact("peer_median", f"the peer median was {plain.value_phrase(focus_metric, median)} over the same quarter", []))
        t1 = next((t for t in report.tests if t.test_id == "T1" and t.applicable and t.plain), None)
        if t1:
            facts["findings"].append(Fact("t1_plain", t1.plain, []))

    for row in table3.rows:
        statement, _checked, result, reason = row
        facts["explanations"].append(Fact("row", f"{statement}: {result.lower()}. {reason}", []))

    if report.discovery and report.discovery.falsification.plain:
        facts["outlook"].append(Fact("falsification", report.discovery.falsification.plain, []))
    elif focus_metric:
        facts["outlook"].append(Fact("watch", f"the measure to watch is {plain.metric_phrase(focus_metric)} in the next results", []))

    allowed = set()
    for group in facts.values():
        for f in group:
            allowed |= guards.numbers_in(f.text)
    for t in tables:
        for row in t.rows:
            for cell in row:
                allowed |= guards.numbers_in(cell)
        allowed |= guards.numbers_in(t.caption)
    for fig in figures_list:
        allowed |= guards.numbers_in(fig.caption)
    allowed |= {str(i) for i in range(1, 13)}
    allowed |= {str(r.number) for r in references}
    allowed |= {str(y) for y in range(2015, 2036)}
    allowed |= {str(len(report.financials)), str(len(report.peers)), str(len(table3.rows))}
    import re as _re
    for row in table1.rows:
        q = row[0]
        for m in _re.findall(r"\d+", q):
            allowed.add(m)

    keywords = [sector_phrase]
    if focus_metric:
        keywords.append(plain.metric_name(focus_metric))
    keywords += ["India", "quarterly results", "peer comparison"]

    changepoint_quarter = ""
    if focus_metric:
        subj = _series_for(report, symbol, focus_metric)
        if subj and subj.changepoint_period:
            changepoint_quarter = plain.period_phrase(subj.changepoint_period)

    return PaperSpec(
        company=company, symbol=symbol, sector_phrase=sector_phrase,
        prepared=plain.date_long(__import__("datetime").date.today()),
        as_of=plain.date_long(report.meta.as_of),
        has_finding=has_finding, facts=facts, figures=figures_list, tables=tables,
        references=references, allowed_numbers=allowed, keywords=keywords,
        n_quarters=len(report.financials), n_peers=len(report.peers),
        n_explanations=len(table3.rows), focus_metric=focus_metric or "",
        focus_metric_name=plain.metric_name(focus_metric) if focus_metric else "",
        changepoint_quarter=changepoint_quarter,
    )


def _prior_year_period(period: str) -> str:
    import re
    m = re.match(r"^(Q\d)FY(\d+)$", period)
    if not m:
        return ""
    return f"{m.group(1)}FY{int(m.group(2)) - 1}"
