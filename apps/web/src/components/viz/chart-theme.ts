// Shared recharts configuration for every chart in the app, so a line chart, a bar chart and a
// scatter plot all read as one visual system rather than three different defaults bolted together.

export const AXIS_TICK = { fontSize: 10, fontFamily: "var(--font-mono)", fill: "var(--chart-axis)" };

export const GRID_PROPS = { stroke: "var(--chart-grid)", strokeDasharray: "2 4", vertical: false };

export const CHART_MARGIN = { top: 8, right: 8, bottom: 0, left: 0 };

export const CURSOR_LINE = { stroke: "var(--rule-strong)", strokeWidth: 1 };

// The heat ramp as a plain array, for code that needs to pick a step directly (e.g. a legend) rather
// than reference the CSS variable through a className.
export const HEAT_SCALE = ["var(--color-heat-0)", "var(--color-heat-1)", "var(--color-heat-2)", "var(--color-heat-3)", "var(--color-heat-4)"];
export const INK_RAMP_SCALE = ["var(--color-ink-ramp-1)", "var(--color-ink-ramp-2)", "var(--color-ink-ramp-3)", "var(--color-ink-ramp-4)", "var(--color-ink-ramp-5)"];

/**
 * Bins a value into one of 5 heat steps (0 = quietest, 4 = most extreme), given one or more
 * thresholds. `higherIsWorse` controls which direction is "more extreme": true for something like a
 * peer z-score's magnitude where a bigger absolute deviation is a stronger signal regardless of sign.
 * Returns null when `value` is null/undefined, so an absent data point renders as an empty cell, not a
 * false "quietest" reading.
 */
export function heatBin(value: number | null | undefined, thresholds: [number, number, number, number]): number | null {
  if (value === null || value === undefined || Number.isNaN(value)) return null;
  const abs = Math.abs(value);
  if (abs < thresholds[0]) return 0;
  if (abs < thresholds[1]) return 1;
  if (abs < thresholds[2]) return 2;
  if (abs < thresholds[3]) return 3;
  return 4;
}

export function heatColor(bin: number | null): string {
  if (bin === null) return "var(--paper-2)";
  return HEAT_SCALE[Math.max(0, Math.min(4, bin))];
}

// Default thresholds for a z-score-shaped value (peer divergence, trend t-stat): quiet below 0.5,
// mild below 1, notable below 2, strong below 3, extreme at or above 3.
export const Z_SCORE_THRESHOLDS: [number, number, number, number] = [0.5, 1, 2, 3];

// Cycles through the ink/signal family for a multi-series chart (line overlays, grouped bars), so a
// series never needs an unrelated hue: the signal red is reserved for the single most important
// series (usually the subject itself), with the ink ramp for everything else (peers, comparisons).
const SERIES_COLORS = [
  "var(--color-signal)",
  "var(--color-ink)",
  "var(--color-ink-3)",
  "var(--color-signal-2)",
  "var(--color-ink-ramp-2)",
  "var(--color-ink-ramp-4)",
];

export function seriesColor(index: number): string {
  return SERIES_COLORS[index % SERIES_COLORS.length];
}
