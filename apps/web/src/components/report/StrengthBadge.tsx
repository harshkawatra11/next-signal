import type { StrengthLabel } from "@/types/report";

const STYLES: Record<StrengthLabel, string> = {
  Strong: "bg-ink text-white border-ink",
  Moderate: "bg-white text-ink border-ink",
  Weak: "bg-white text-signal border-signal border-dashed",
};

export function StrengthBadge({ label, total }: { label: StrengthLabel; total: number }) {
  return (
    <span
      className={`inline-flex items-center gap-2 border-2 px-3 py-1 font-mono text-xs font-semibold uppercase tracking-[0.06em] ${STYLES[label]}`}
    >
      {label}
      <span className="font-tnum">{total.toFixed(1)}/10</span>
    </span>
  );
}
