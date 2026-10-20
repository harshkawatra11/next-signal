"use client";

import useSWR from "swr";
import Link from "next/link";
import { Topbar } from "@/components/layout/Topbar";
import { Footer } from "@/components/layout/Footer";
import { Skeleton } from "@/components/ui/skeleton";
import { Container, Kicker, KpiBand } from "@/components/system";
import { BarRanked, ChartCard, DataTable, type Column } from "@/components/viz";
import { getEvalCompanies, getEvalSummary, type EvalCompany } from "@/lib/api";
import { fmtDuration } from "@/lib/format";

export default function EvalPage() {
  const { data: summary, error, isLoading } = useSWR("/api/eval/summary", getEvalSummary);
  const { data: companies } = useSWR("/api/eval/companies", getEvalCompanies);

  const killRatePct = summary ? Math.round(summary.kill_rate * 100) : 0;
  const findingSharePct = summary ? Math.round(summary.share_with_discovery * 100) : 0;

  const columns: Column<EvalCompany>[] = [
    { key: "symbol", header: "Symbol", accessor: (c) => <Link href={`/report/${c.run_id}`} className="text-signal hover:underline">{c.symbol}</Link>, mono: true, width: "88px" },
    { key: "status", header: "Status", accessor: (c) => c.status, width: "88px" },
    { key: "documents", header: "Documents", accessor: (c) => String(c.documents), align: "right", mono: true },
    { key: "facts", header: "Facts", accessor: (c) => String(c.facts_count), align: "right", mono: true },
    { key: "anomalies", header: "Anomalies", accessor: (c) => String(c.anomalies), align: "right", mono: true },
    { key: "hypotheses", header: "Hypotheses", accessor: (c) => String(c.hypotheses_total), align: "right", mono: true },
    { key: "killed", header: "Killed", accessor: (c) => String(c.killed), align: "right", mono: true },
    { key: "finding", header: "Finding", accessor: (c) => c.discovery_label ?? "none", width: "100px" },
    { key: "strength", header: "Strength", accessor: (c) => (c.strength_total != null ? c.strength_total.toFixed(2) : "-"), align: "right", mono: true },
    { key: "runtime", header: "Runtime", accessor: (c) => fmtDuration(c.runtime_s), align: "right", mono: true },
  ];

  return (
    <>
      <Topbar />
      <main className="flex-1">
        <Container className="py-12">
          <Kicker>File 04 // Evaluation</Kicker>
          <h1 className="mt-3 max-w-3xl text-h1 font-serif leading-h1 text-ink">
            {summary
              ? `${summary.n_companies} companies, one codebase: ${killRatePct}% of hypotheses were killed and ${findingSharePct}% of runs ended with a reportable finding`
              : "The evaluation harness result for every company in the run set"}
          </h1>
          <p className="mt-4 max-w-2xl text-body leading-body text-ink-2">
            These numbers come only from the evaluation harness (
            <code className="font-mono text-small">engine/next_signal/eval/harness.py</code>), never
            typed by hand.
          </p>

          {isLoading && (
            <div className="mt-8 grid grid-cols-2 gap-6 md:grid-cols-4">
              {Array.from({ length: 4 }).map((_, i) => (
                <Skeleton key={i} className="h-16 w-full bg-paper-2" />
              ))}
            </div>
          )}

          {error && (
            <p className="mt-8 text-small text-ink-3">
              The evaluation has not run yet. Run{" "}
              <code className="font-mono text-small">python -m next_signal.eval --set N50,TB</code> from
              the engine folder.
            </p>
          )}

          {summary && (
            <>
              <KpiBand
                className="mt-8"
                items={[
                  { label: "Companies", value: String(summary.n_companies) },
                  { label: "Hypotheses", value: String(summary.hypotheses_total) },
                  { label: "Kill rate", value: `${killRatePct}%` },
                  { label: "With a finding", value: `${findingSharePct}%` },
                  { label: "Median runtime", value: fmtDuration(summary.median_runtime_s) },
                  { label: "p90 runtime", value: fmtDuration(summary.p90_runtime_s) },
                  { label: "Failed", value: String(summary.failed) },
                ]}
              />

              <div className="mt-10 grid gap-5 md:grid-cols-2">
                <ChartCard title="Runtime by company" source="eval/harness.py">
                  {companies && companies.length > 0 ? (
                    <BarRanked
                      data={companies.map((c) => ({ label: c.symbol, value: c.runtime_s }))}
                      formatValue={(v) => fmtDuration(v)}
                    />
                  ) : (
                    <p className="text-small text-ink-3">No company rows yet.</p>
                  )}
                </ChartCard>
                <ChartCard title="Discovery labels across the run set" source="eval/harness.py">
                  <BarRanked
                    data={Object.entries(summary.label_counts).map(([label, count]) => ({ label, value: count }))}
                  />
                </ChartCard>
              </div>

              {companies && companies.length > 0 && (
                <div className="mt-8 border border-rule p-5 md:p-6">
                  <h3 className="text-h3 font-sans font-semibold text-ink">Per-company result</h3>
                  <div className="mt-4">
                    <DataTable columns={columns} rows={companies} rowKey={(c) => c.run_id} dense />
                  </div>
                </div>
              )}
            </>
          )}
        </Container>
      </main>
      <Footer />
    </>
  );
}
