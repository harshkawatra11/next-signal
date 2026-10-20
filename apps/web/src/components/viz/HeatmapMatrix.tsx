"use client";

import { Fragment } from "react";
import { cn } from "@/lib/utils";
import { heatColor } from "./chart-theme";

export interface HeatCell {
  value: number | null;
  bin: number | null;
  display: string;
}

// A metrics-by-periods (or peers-by-metrics, or evidence-by-hypothesis) heat matrix, built as a CSS
// grid rather than an HTML table: a table forces every cell to the same text-driven width, where a
// grid can give the row-label column real estate and every data column a fixed, legible square.
export function HeatmapMatrix({
  rowLabels,
  colLabels,
  cells,
  labelWidth = 160,
  cellWidth = 72,
  onCellClick,
}: {
  rowLabels: string[];
  colLabels: string[];
  cells: HeatCell[][];
  labelWidth?: number;
  cellWidth?: number;
  onCellClick?: (rowIndex: number, colIndex: number) => void;
}) {
  return (
    <div
      className="inline-grid gap-px bg-rule"
      style={{ gridTemplateColumns: `${labelWidth}px repeat(${colLabels.length}, ${cellWidth}px)` }}
    >
      <div className="bg-paper" />
      {colLabels.map((label) => (
        <div
          key={label}
          className="flex items-center justify-center bg-paper-2 px-1 py-2 text-center font-mono text-label font-semibold uppercase tracking-[0.08em] text-ink-3"
        >
          {label}
        </div>
      ))}
      {rowLabels.map((rowLabel, ri) => (
        <Fragment key={rowLabel}>
          <div className="flex items-center truncate bg-paper px-2 py-2 font-mono text-small text-ink-2" title={rowLabel}>
            {rowLabel}
          </div>
          {colLabels.map((_, ci) => {
            const cell = cells[ri]?.[ci];
            const bin = cell?.bin ?? null;
            return (
              <button
                key={`${rowLabel}-${ci}`}
                type="button"
                onClick={onCellClick ? () => onCellClick(ri, ci) : undefined}
                className={cn(
                  "flex items-center justify-center py-2 font-mono text-[11px] font-tnum text-ink",
                  onCellClick && "cursor-pointer hover:outline hover:outline-1 hover:outline-ink"
                )}
                style={{ background: heatColor(bin), color: bin !== null && bin >= 3 ? "var(--color-paper)" : "var(--color-ink)" }}
                title={cell?.display ?? ""}
              >
                {cell?.display ?? ""}
              </button>
            );
          })}
        </Fragment>
      ))}
    </div>
  );
}
