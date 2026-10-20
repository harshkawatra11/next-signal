import type { StrengthBreakdown } from "@/types/report";

const SEGMENTS: Array<{ key: keyof StrengthBreakdown; label: string; color: string }> = [
  { key: "independence", label: "Independence", color: "bg-ink" },
  { key: "reliability", label: "Reliability", color: "bg-ink-2" },
  { key: "corroboration", label: "Corroboration", color: "bg-ink-3" },
  { key: "survival", label: "Survival", color: "bg-signal" },
  { key: "persistence", label: "Persistence", color: "bg-signal-2" },
];

const MAX_SCALE = 10;

export function StrengthBar({ breakdown }: { breakdown: StrengthBreakdown }) {
  return (
    <div>
      <div className="relative h-7 w-full border-2 border-ink">
        <div className="flex h-full w-full">
          {SEGMENTS.map((seg) => {
            const value = Math.max(0, breakdown[seg.key] as number);
            const widthPct = (value / MAX_SCALE) * 100;
            return widthPct > 0 ? (
              <div
                key={seg.key}
                className={seg.color}
                style={{ width: `${widthPct}%` }}
                title={`${seg.label}: ${value}`}
              />
            ) : null;
          })}
        </div>
        {[4, 7].map((threshold) => (
          <div
            key={threshold}
            className="absolute top-0 h-full border-l-2 border-dashed border-ink-3"
            style={{ left: `${(threshold / MAX_SCALE) * 100}%` }}
          >
            <span className="absolute -bottom-5 left-0 -translate-x-1/2 font-mono text-[9px] text-ink-3">
              {threshold === 4 ? "Moderate" : "Strong"}
            </span>
          </div>
        ))}
      </div>
      <ul className="mt-7 space-y-0.5 text-[11px] text-ink-3">
        {breakdown.reasoning.map((r, i) => (
          <li key={i}>{r}</li>
        ))}
      </ul>
    </div>
  );
}
