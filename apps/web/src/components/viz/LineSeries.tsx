"use client";

import {
  CartesianGrid,
  Line,
  LineChart,
  ReferenceLine,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import { AXIS_TICK, CHART_MARGIN, CURSOR_LINE, GRID_PROPS, seriesColor } from "./chart-theme";

export interface LineSeriesDatum {
  period: string;
  [seriesKey: string]: number | string;
}

export interface LineSeriesLine {
  key: string;
  label: string;
}

function ChartTooltip({ active, payload, label }: { active?: boolean; payload?: Array<{ name?: string; value?: number; color?: string }>; label?: string }) {
  if (!active || !payload?.length) return null;
  return (
    <div className="border border-ink bg-ink px-3 py-2 font-mono text-[11px] text-paper">
      <div className="mb-1 text-ink-3">{label}</div>
      {payload.map((p) => (
        <div key={p.name} className="flex items-center gap-2">
          <span className="inline-block h-2 w-2" style={{ background: p.color }} />
          <span>{p.name}</span>
          <span className="ml-auto pl-3 font-tnum">{typeof p.value === "number" ? p.value.toFixed(2) : p.value}</span>
        </div>
      ))}
    </div>
  );
}

export function LineSeries({
  data,
  lines,
  height = 240,
  changepointPeriod,
  changepointLabel,
  unit,
}: {
  data: LineSeriesDatum[];
  lines: LineSeriesLine[];
  height?: number;
  changepointPeriod?: string | null;
  changepointLabel?: string;
  unit?: (v: number) => string;
}) {
  return (
    <ResponsiveContainer width="100%" height={height} initialDimension={{ width: 600, height }}>
      <LineChart data={data} margin={CHART_MARGIN}>
        <CartesianGrid {...GRID_PROPS} />
        <XAxis dataKey="period" tick={AXIS_TICK} tickLine={false} axisLine={{ stroke: "var(--chart-grid)" }} minTickGap={16} />
        <YAxis
          tick={AXIS_TICK}
          tickLine={false}
          axisLine={false}
          width={48}
          tickFormatter={(v: number) => (unit ? unit(v) : String(v))}
        />
        <Tooltip content={<ChartTooltip />} cursor={CURSOR_LINE} />
        {changepointPeriod && (
          <ReferenceLine
            x={changepointPeriod}
            stroke="var(--color-signal)"
            strokeDasharray="4 4"
            strokeWidth={1.5}
            label={{
              value: changepointLabel ?? "Change point",
              position: "insideTopRight",
              fontSize: 10,
              fontFamily: "var(--font-mono)",
              fill: "var(--color-signal)",
            }}
          />
        )}
        {lines.map((line, i) => (
          <Line
            key={line.key}
            type="monotone"
            dataKey={line.key}
            name={line.label}
            stroke={seriesColor(i)}
            strokeWidth={2}
            dot={false}
            activeDot={{ r: 4, stroke: "var(--color-paper)", strokeWidth: 2 }}
            isAnimationActive={false}
          />
        ))}
      </LineChart>
    </ResponsiveContainer>
  );
}
