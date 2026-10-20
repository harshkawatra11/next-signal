import { cn } from "@/lib/utils";

export interface KpiItem {
  label: string;
  value: string;
  sub?: string;
}

export function KpiBand({ items, className }: { items: KpiItem[]; className?: string }) {
  return (
    <div className={cn("grid grid-cols-2 gap-y-6 gap-x-6 md:grid-cols-4 lg:grid-cols-6", className)}>
      {items.map((item, i) => (
        <div
          key={item.label}
          className={cn(
            "flex flex-col gap-1 border-rule pl-4",
            i === 0 ? "border-l-0 pl-0" : "border-l"
          )}
        >
          <span className="font-mono text-label uppercase tracking-[0.12em] text-ink-3">{item.label}</span>
          <span className="font-mono text-2xl font-tnum font-semibold text-ink">{item.value}</span>
          {item.sub && <span className="text-small text-ink-3">{item.sub}</span>}
        </div>
      ))}
    </div>
  );
}
