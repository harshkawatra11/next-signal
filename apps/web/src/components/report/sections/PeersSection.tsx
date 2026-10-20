import { Section, SectionHeading } from "@/components/system";
import { ChartCard, DataTable, HeatmapMatrix, Z_SCORE_THRESHOLDS, heatBin, type Column, type HeatCell } from "@/components/viz";
import { fmtNumber, fmtZ } from "@/lib/format";
import { metricLabel } from "@/lib/headlines";
import type { Series } from "@/types/report";

function median(xs: number[]): number {
  const s = [...xs].sort((a, b) => a - b);
  const m = Math.floor(s.length / 2);
  return s.length % 2 ? s[m] : (s[m - 1] + s[m]) / 2;
}

function robustZ(x: number, xs: number[]): number {
  const med = median(xs);
  const mad = median(xs.map((v) => Math.abs(v - med))) * 1.4826;
  return mad > 0 ? (x - med) / mad : 0;
}

function periodKey(p: string): number {
  const m = p.match(/^Q(\d)FY(\d+)$/);
  if (!m) return 0;
  return Number(m[2]) * 4 + Number(m[1]);
}

function latestValue(series: Series): number | null {
  if (series.points.length === 0) return null;
  const sorted = [...series.points].sort((a, b) => periodKey(a.period) - periodKey(b.period));
  return sorted[sorted.length - 1].value;
}

export function PeersSection({
  series,
  subject,
  peers,
  glossary,
}: {
  series: Series[];
  subject: string;
  peers: string[];
  glossary?: Record<string, string>;
}) {
  if (peers.length === 0) return null;

  const subjectSeries = series.filter((s) => s.entity === subject);
  if (subjectSeries.length === 0) return null;

  const metricIds = Array.from(new Set(subjectSeries.map((s) => s.metric_id)));
  const entities = [subject, ...peers];

  // entityValue[entity][metric_id] = latest raw value, only populated when that entity has the series.
  const entityValue = new Map<string, Map<string, number>>();
  for (const entity of entities) {
    const row = new Map<string, number>();
    for (const metricId of metricIds) {
      const s = series.find((x) => x.entity === entity && x.metric_id === metricId);
      const v = s ? latestValue(s) : null;
      if (v !== null) row.set(metricId, v);
    }
    entityValue.set(entity, row);
  }

  let maxAbsZ = -Infinity;
  let maxCellMetric = "";
  let maxCellZ = 0;

  const cells: HeatCell[][] = entities.map((entity) => {
    const row = entityValue.get(entity)!;
    return metricIds.map((metricId) => {
      const value = row.get(metricId);
      if (value === undefined) return { value: null, bin: null, display: "" };
      const peerValues = entities
        .map((e) => entityValue.get(e)!.get(metricId))
        .filter((v): v is number => v !== undefined);
      const z = robustZ(value, peerValues);
      if (entity === subject && Math.abs(z) > maxAbsZ) {
        maxAbsZ = Math.abs(z);
        maxCellMetric = metricId;
        maxCellZ = z;
      }
      return { value: z, bin: heatBin(z, Z_SCORE_THRESHOLDS), display: fmtZ(z) };
    });
  });

  const title =
    maxCellMetric !== ""
      ? `${subject} sits furthest from peers on ${metricLabel(maxCellMetric, glossary)}: robust z = ${maxCellZ.toFixed(1)}`
      : "No peer-comparable metric was available for this run";

  const tableColumns: Column<string>[] = [
    { key: "entity", header: "Entity", accessor: (e) => e, mono: true, width: "120px" },
    ...metricIds.map((metricId) => ({
      key: metricId,
      header: metricLabel(metricId, glossary),
      accessor: (e: string) => {
        const v = entityValue.get(e)!.get(metricId);
        return v !== undefined ? fmtNumber(v, 2) : "-";
      },
      align: "right" as const,
      mono: true,
    })),
  ];

  return (
    <Section id="peers">
      <SectionHeading index="05" kicker="Against the peer set" title={title} />
      <div className="grid gap-5 md:grid-cols-2">
        <ChartCard
          title="Robust z against peers, latest quarter"
          source="Calculate stage, peer filings"
          soWhat="Robust z uses the peer set's median and median absolute deviation, so one outlier peer cannot distort the comparison the way a mean-and-standard-deviation z-score would."
        >
          <HeatmapMatrix rowLabels={entities} colLabels={metricIds.map((m) => metricLabel(m, glossary))} cells={cells} />
        </ChartCard>
        <div className="border border-rule p-5 md:p-6">
          <h3 className="text-h3 font-sans font-semibold text-ink">Latest quarter, raw values</h3>
          <div className="mt-4">
            <DataTable columns={tableColumns} rows={entities} rowKey={(e) => e} dense />
          </div>
        </div>
      </div>
    </Section>
  );
}
