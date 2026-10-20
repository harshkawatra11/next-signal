export function WhyItMatters({ bullets }: { bullets: string[] }) {
  return (
    <div className="border border-rule p-5">
      <h3 className="font-mono text-[11px] font-semibold uppercase tracking-[0.1em] text-ink-3">
        Why It Matters
      </h3>
      <ol className="mt-3 space-y-3">
        {bullets.map((b, i) => (
          <li key={i} className="flex gap-3">
            <span className="font-mono text-sm font-semibold text-signal">{i + 1}</span>
            <span className="text-[14px] leading-relaxed text-ink">{b}</span>
          </li>
        ))}
      </ol>
    </div>
  );
}
