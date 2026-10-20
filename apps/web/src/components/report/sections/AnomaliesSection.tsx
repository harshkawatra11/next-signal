import { Section, SectionHeading } from "@/components/system";
import { BarRanked, ChartCard, DataTable, type Column } from "@/components/viz";
import { fmtPeriod, fmtZ } from "@/lib/format";
import { anomaliesTitle, metricLabel } from "@/lib/headlines";
import type { Anomaly } from "@/types/report";

export function AnomaliesSection({
  anomalies,
  glossary,
}: {
  anomalies: Anomaly[];
  glossary?: Record<string, string>;
}) {
  if (anomalies.length === 0) return null;

  const barData = anomalies
    .slice()
    .sort((a, b) => b.score - a.score)
    .map((a) => ({ label: metricLabel(a.metric_id, glossary), value: a.score }));

  const columns: Column<Anomaly>[] = [
    { key: "metric", header: "Metric", accessor: (a) => metricLabel(a.metric_id, glossary), width: "160px" },
    {
      key: "peer_z",
      header: "Peer z",
      accessor: (a) => (a.peer_z !== null && a.peer_z !== undefined ? fmtZ(a.peer_z) : "-"),
      sortValue: (a) => Math.abs(a.peer_z ?? 0),
      align: "right",
      mono: true,
    },
    {
      key: "changepoint",
      header: "Change point",
      accessor: (a) => (a.changepoint_period ? fmtPeriod(a.changepoint_period) : "-"),
      align: "right",
      mono: true,
    },
    {
      key: "trend",
      header: "Trend t",
      accessor: (a) => (a.trend_t !== null && a.trend_t !== undefined ? a.trend_t.toFixed(1) : "-"),
      sortValue: (a) => Math.abs(a.trend_t ?? 0),
      align: "right",
      mono: true,
    },
    {
      key: "score",
      header: "Score",
      accessor: (a) => a.score.toFixed(2),
      sortValue: (a) => a.score,
      align: "right",
      mono: true,
    },
  ];

  return (
    <Section id="anomalies">
      <SectionHeading
        index="03"
        kicker="What changed"
        title={anomaliesTitle(anomalies, glossary)}
        lede="Every anomaly below is a metric whose peer-relative divergence, change-point strength or trend met the 0.30 score threshold, computed before the language model saw any of it."
      />
      <div className="grid gap-5 md:grid-cols-2">
        <ChartCard
          title="Anomaly scores, ranked"
          source="Calculate stage"
          soWhat="A score blends peer-relative divergence, change-point strength and trend significance; the highest-scoring metric is what Reason was asked to explain first."
        >
          <BarRanked data={barData} />
        </ChartCard>
        <div className="border border-rule p-5 md:p-6">
          <h3 className="text-h3 font-sans font-semibold text-ink">Anomaly detail</h3>
          <div className="mt-4">
            <DataTable columns={columns} rows={anomalies} rowKey={(a) => a.anomaly_id} dense />
          </div>
        </div>
      </div>
    </Section>
  );
}
