"use client";

import { useMemo, useState } from "react";
import { scaleTime } from "d3-scale";
import { timeFormat } from "d3-time-format";
import { fmtDateIN } from "@/lib/format";
import type { TimelinePoint } from "@/types/report";

const LANES = [
  { kind: "regulatory_usfda", label: "Regulator" },
  { kind: "results", label: "Company filing" },
  { kind: "guidance", label: "Management said" },
  { kind: "price_move", label: "Market" },
  { kind: "news_first_seen", label: "Press" },
  { kind: "__other__", label: "Other" },
] as const;

function laneForKind(kind: string): number {
  const idx = LANES.findIndex((l) => l.kind === kind);
  return idx >= 0 ? idx : LANES.length - 1;
}

const tickFormat = timeFormat("%b %Y");

export function TimelineChart({ points }: { points: TimelinePoint[] }) {
  const [hovered, setHovered] = useState<string | null>(null);

  const width = 1080;
  const laneHeight = 48;
  const axisHeight = 24;
  const height = LANES.length * laneHeight + axisHeight;
  const labelW = 150;
  const plotW = width - labelW - 16;

  const { sorted, scale, changepoint, ticks } = useMemo(() => {
    const dated = points.map((p) => ({ ...p, t: new Date(p.date) }));
    dated.sort((a, b) => a.t.getTime() - b.t.getTime());
    const min = dated.length ? dated[0].t : new Date();
    const maxRaw = dated.length ? dated[dated.length - 1].t : new Date(min.getTime() + 86400000);
    const max = maxRaw.getTime() === min.getTime() ? new Date(min.getTime() + 86400000) : maxRaw;
    const d3Scale = scaleTime().domain([min, max]).range([labelW, labelW + plotW]);
    const cp = dated.find((p) => p.is_changepoint);
    return { sorted: dated, scale: d3Scale, changepoint: cp, ticks: d3Scale.ticks(5) };
  }, [points, plotW, labelW]);

  // Collision offsetting: events landing within 16px of each other on the same lane get staggered
  // vertically within the lane so their dots and labels do not overlap.
  const laidOut = useMemoLayout(sorted, scale);

  if (sorted.length === 0) {
    return (
      <div className="border border-rule p-5 text-small text-ink-3">
        This discovery has no dated events on its timeline.
      </div>
    );
  }

  const cpX = changepoint ? scale(changepoint.t) : null;

  return (
    <div className="border border-rule p-5">
      <h3 className="font-mono text-label font-semibold uppercase tracking-[0.1em] text-ink-3">
        When the story changed
      </h3>
      <svg viewBox={`0 0 ${width} ${height}`} className="mt-3 w-full" style={{ maxHeight: 420 }}>
        {LANES.map((lane, i) => (
          <g key={lane.kind}>
            <rect
              x={0}
              y={i * laneHeight}
              width={width}
              height={laneHeight}
              fill={i % 2 === 0 ? "var(--paper-2)" : "var(--paper)"}
            />
            <text x={8} y={i * laneHeight + laneHeight / 2 + 4} fontSize={11} fill="var(--ink)" fontFamily="var(--font-mono)">
              {lane.label}
            </text>
          </g>
        ))}

        {ticks.map((tick, i) => (
          <g key={i}>
            <line
              x1={scale(tick)}
              y1={LANES.length * laneHeight}
              x2={scale(tick)}
              y2={height}
              stroke="var(--chart-grid)"
              strokeWidth={1}
            />
            <text
              x={scale(tick)}
              y={LANES.length * laneHeight + axisHeight - 7}
              fontSize={10}
              fontFamily="var(--font-mono)"
              fill="var(--chart-axis)"
              textAnchor="middle"
            >
              {tickFormat(tick)}
            </text>
          </g>
        ))}

        {cpX !== null && (
          <>
            <line
              x1={cpX}
              y1={0}
              x2={cpX}
              y2={LANES.length * laneHeight}
              stroke="var(--signal)"
              strokeWidth={2}
              strokeDasharray="4,3"
            />
            <text x={cpX + 6} y={12} fontSize={10} fontWeight={600} fill="var(--signal)" fontFamily="var(--font-mono)">
              Change emerges: {changepoint?.label}
            </text>
          </>
        )}

        {laidOut.map((p) => {
          const key = `${p.date}-${p.label}`;
          const isHovered = hovered === key;
          return (
            <g
              key={key}
              onMouseEnter={() => setHovered(key)}
              onMouseLeave={() => setHovered((h) => (h === key ? null : h))}
              style={{ cursor: "pointer" }}
            >
              <circle
                cx={p.cx}
                cy={p.cy}
                r={p.is_changepoint ? 7 : 5}
                fill={p.is_changepoint ? "var(--signal)" : "var(--ink)"}
                stroke="var(--ink)"
                strokeWidth={1}
              />
              {(isHovered || p.is_changepoint) && (
                <text
                  x={p.cx + 9}
                  y={p.cy - 8}
                  fontSize={10}
                  fontFamily="var(--font-mono)"
                  fill="var(--ink)"
                  fontWeight={isHovered ? 600 : 400}
                >
                  {p.label}
                </text>
              )}
              {isHovered && (
                <text x={p.cx + 9} y={p.cy + 14} fontSize={9} fontFamily="var(--font-mono)" fill="var(--ink-3)">
                  {fmtDateIN(p.date)}
                </text>
              )}
            </g>
          );
        })}
      </svg>
    </div>
  );
}

function useMemoLayout(
  sorted: Array<TimelinePoint & { t: Date }>,
  scale: (d: Date) => number
) {
  return useMemo(() => {
    const laneHeight = 48;
    const slotsByLane = new Map<number, number[]>();
    return sorted.map((p) => {
      const lane = laneForKind(p.kind);
      const cx = scale(p.t);
      const used = slotsByLane.get(lane) ?? [];
      const nearby = used.filter((x) => Math.abs(x - cx) < 16).length;
      slotsByLane.set(lane, [...used, cx]);
      const cy = lane * laneHeight + laneHeight / 2 + (nearby % 2 === 0 ? 1 : -1) * Math.ceil(nearby / 2) * 10;
      return { ...p, cx, cy, lane };
    });
  }, [sorted, scale]);
}
