"use client";

import { cn } from "@/lib/utils";

export interface BarRankedDatum {
  label: string;
  value: number;
  highlight?: boolean;
}

// Horizontal ranked bars, built as plain divs rather than a recharts BarChart: a ranked list of
// named items (angles considered, anomaly scores) reads better as a compact label-plus-bar row than
// as a chart with a categorical axis, and this form makes the "highlighted" (chosen) row trivial to
// pick out in signal red against the rest in ink.
export function BarRanked({ data, formatValue, height = 28 }: { data: BarRankedDatum[]; formatValue?: (v: number) => string; height?: number }) {
  const max = Math.max(...data.map((d) => Math.abs(d.value)), 0.0001);
  return (
    <div className="space-y-2">
      {data.map((d) => {
        const pct = (Math.abs(d.value) / max) * 100;
        return (
          <div key={d.label} className="flex items-center gap-3">
            <span className="w-36 shrink-0 truncate font-mono text-small text-ink-2" title={d.label}>
              {d.label}
            </span>
            <div className="relative flex-1 bg-paper-2" style={{ height }}>
              <div
                className={cn("absolute inset-y-0 left-0", d.highlight ? "bg-signal" : "bg-ink")}
                style={{ width: `${pct}%` }}
              />
            </div>
            <span className="w-16 shrink-0 text-right font-mono text-small font-tnum text-ink">
              {formatValue ? formatValue(d.value) : d.value.toFixed(2)}
            </span>
          </div>
        );
      })}
    </div>
  );
}
