// Action titles computed from report data, never typed by hand. Mirrors
// engine/next_signal/export/narrative.py (same functions, same wording) so the web report and the PDF
// case file never disagree about what happened in a run. Every string below has to read as a
// declarative finding with a number in it, not a topic label (case-competition-deck skill, §3 of the
// project plan: action titles carry the finding, the kicker carries the topic).
import type { Anomaly, FinancialRow, Report } from "@/types/report";
import { fmtCrore, fmtPeriod } from "@/lib/format";

const METRIC_LABELS: Record<string, string> = {
  gross_margin: "Gross margin", ebitda_margin: "EBITDA margin", rev_yoy: "Revenue growth",
  revenue_yoy: "Revenue growth", pat_margin: "PAT margin", other_income_share: "Other income share",
  employee_pct: "Employee cost share", dna_pct: "Depreciation share", finance_cost_pct: "Finance cost share",
};

export function metricLabel(id: string, glossary?: Record<string, string>): string {
  return glossary?.[id] ?? METRIC_LABELS[id] ?? id.replace(/_/g, " ").replace(/^./, (c) => c.toUpperCase());
}

function priorYearSameQuarter(p: string): string | null {
  const m = p.match(/^(Q\d)FY(\d+)$/);
  return m ? `${m[1]}FY${String(Number(m[2]) - 1).padStart(2, "0")}` : null;
}

export function financialsTitle(fin: FinancialRow[], company: string): string {
  if (fin.length === 0) return "No quarterly filings were parsed for this run";
  const latest = fin[0];
  const rev = latest.values.revenue;
  const prior = fin.find((r) => r.period === priorYearSameQuarter(latest.period));
  if (rev !== undefined && prior?.values.revenue) {
    const chg = (rev / prior.values.revenue - 1) * 100;
    return `${company} reported revenue of ${fmtCrore(rev)} in ${fmtPeriod(latest.period)}, ${chg >= 0 ? "up" : "down"} ${Math.abs(chg).toFixed(1)}% on the same quarter last year`;
  }
  if (rev !== undefined) return `${company} reported revenue of ${fmtCrore(rev)} in ${fmtPeriod(latest.period)} across ${fin.length} filed quarters`;
  return `${fin.length} quarters of filed results were parsed for ${company}`;
}

export function anomaliesTitle(anomalies: Anomaly[], glossary?: Record<string, string>): string {
  if (anomalies.length === 0) return "No metric crossed the 0.30 anomaly threshold";
  const top = [...anomalies].sort((a, b) => b.score - a.score)[0];
  const bits = [`score ${top.score.toFixed(2)}`];
  if (top.peer_z != null) bits.push(`peer z ${top.peer_z.toFixed(1)}`);
  if (top.changepoint_period) bits.push(`change point ${fmtPeriod(top.changepoint_period)}`);
  return `${metricLabel(top.metric_id, glossary)} is the sharpest break of ${anomalies.length} flagged metrics: ${bits.join(", ")}`;
}

export function anglesTitle(angles: Report["angles_considered"]): string {
  if (angles.length === 0) return "No investigation angle was scored";
  const top = [...angles].sort((a, b) => b.score - a.score)[0];
  return `Angle ${top.angle_id} scored ${top.score.toFixed(2)} and led a field of ${angles.length}`;
}

export function challengeTitle(r: Report): string {
  const total = r.killed.length + r.runners_up.length + (r.discovery ? 1 : 0);
  const applied = r.tests.filter((t) => t.applicable).length;
  return `${r.killed.length} of ${total} hypotheses were killed after ${applied} applicable falsification tests`;
}

export function methodTitle(r: Report): string {
  const entries = Object.entries(r.stage_ms ?? {});
  const runtime = Math.round(r.meta.runtime_s ?? 0);
  if (entries.length === 0) return `The run read ${r.meta.documents} documents in ${runtime} sec`;
  const [slowStage, slowMs] = entries.reduce((a, b) => (b[1] > a[1] ? b : a));
  const share = Math.round((100 * slowMs) / Math.max(1, entries.reduce((s, [, v]) => s + v, 0)));
  return `The run read ${r.meta.documents} documents in ${runtime} sec; ${slowStage} took ${share}% of the time`;
}

export function sourcesTitle(r: Report): string {
  const own = r.documents.filter((d) => d.origin_class === "company_filing" || d.origin_class === "exchange").length;
  return `${r.documents.length} documents read, ${own} of them from the exchange or the company's own filings`;
}
