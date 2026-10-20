import { Section, SectionHeading } from "@/components/system";
import { ChartCard, HeatmapMatrix, Z_SCORE_THRESHOLDS, heatBin, type HeatCell } from "@/components/viz";
import { fmtNumber, fmtPct, fmtPeriod } from "@/lib/format";
import { metricLabel } from "@/lib/headlines";
import type { Series } from "@/types/report";

function periodKey(p: string): number {
  const m = p.match(/^Q(\d)FY(\d+)$/);
  if (!m) return 0;
  return Number(m[2]) * 4 + Number(m[1]);
}

function mean(xs: number[]): number {
  return xs.reduce((s, x) => s + x, 0) / xs.length;
}

function populationStd(xs: number[], m: number): number {
  return Math.sqrt(xs.reduce((s, x) => s + (x - m) ** 2, 0) / xs.length);
}

function displayValue(value: number, unit: string): string {
  if (unit === "pct" && Math.abs(value) < 1.5) return fmtPct(value);
  return fmtNumber(value, 1);
}

export function MetricHeatSection({
  series,
  subject,
  glossary,
}: {
  series: Series[];
  subject: string;
  glossary?: Record<string, string>;
}) {
  const subjectSeries = series.filter((s) => s.entity === subject);
  if (subjectSeries.length === 0) return null;

  const allPeriods = Array.from(new Set(subjectSeries.flatMap((s) => s.points.map((p) => p.period))));
  allPeriods.sort((a, b) => periodKey(a) - periodKey(b));
  const columns = allPeriods.slice(-8);

  let maxAbsZ = -Infinity;
  let maxCellMetric = "";
  let maxCellPeriod = "";
  let maxCellZ = 0;

  const rows = subjectSeries.map((s) => {
    const values = s.points.map((p) => p.value);
    const m = mean(values);
    const sd = populationStd(values, m);
    const cells: HeatCell[] = columns.map((period) => {
      const point = s.points.find((p) => p.period === period);
      if (!point) return { value: null, bin: null, display: "" };
      const z = sd > 0 ? (point.value - m) / sd : 0;
      if (Math.abs(z) > maxAbsZ) {
        maxAbsZ = Math.abs(z);
        maxCellMetric = s.metric_id;
        maxCellPeriod = period;
        maxCellZ = z;
      }
      return { value: z, bin: heatBin(z, Z_SCORE_THRESHOLDS), display: displayValue(point.value, s.unit) };
    });
    return { metric_id: s.metric_id, cells };
  });

  const title =
    maxCellMetric !== ""
      ? `${metricLabel(maxCellMetric, glossary)} moved furthest from its own history in ${fmtPeriod(maxCellPeriod)}: z = ${maxCellZ.toFixed(1)}`
      : "No metric history was available to score";

  return (
    <Section id="metric-heat">
      <SectionHeading index="04" kicker="Against its own history" title={title} />
      <ChartCard
        title="Metric z-scores against their own history"
        source="Calculate stage"
        soWhat="Each cell compares a quarter with the same metric's own average across the quarters shown; darker red means further from normal."
      >
        <HeatmapMatrix
          rowLabels={rows.map((r) => metricLabel(r.metric_id, glossary))}
          colLabels={columns.map((p) => fmtPeriod(p))}
          cells={rows.map((r) => r.cells)}
        />
      </ChartCard>
    </Section>
  );
}
