"use client";

import { useRunStore } from "@/store/run";

function pathTail(url: string): string {
  try {
    const path = new URL(url).pathname;
    return path.length > 48 ? path.slice(-48) : path;
  } catch {
    return url.length > 48 ? url.slice(-48) : url;
  }
}

export function SourceTicker() {
  const sourceLog = useRunStore((s) => s.sourceLog);
  const documentsCount = useRunStore((s) => s.documentsCount);
  const factsCount = useRunStore((s) => s.factsCount);

  return (
    <div className="border border-rule p-5">
      <div className="flex items-center justify-between">
        <h3 className="text-label font-mono font-semibold uppercase tracking-[0.1em] text-ink-3">
          Source feed
        </h3>
        <div className="font-mono font-tnum text-small text-ink-3">
          {documentsCount} documents · {factsCount} verified facts
        </div>
      </div>
      <div className="mt-3 space-y-1.5">
        {sourceLog.length === 0 && (
          <p className="text-small text-ink-3">Waiting for the first fetch.</p>
        )}
        {sourceLog.map((entry, i) => (
          <div
            key={`${entry.url}-${i}`}
            className="flex items-center justify-between gap-3 font-mono text-small"
          >
            <span className="truncate text-ink-2">{entry.host}</span>
            <span className="truncate text-ink-3">{pathTail(entry.url)}</span>
            <span className="flex-shrink-0 text-ink-3">
              {entry.cached ? "cached" : `${entry.ms}ms`} ·{" "}
              <span className={entry.status >= 400 ? "text-signal" : "text-ink-3"}>
                {entry.status}
              </span>
            </span>
          </div>
        ))}
      </div>
    </div>
  );
}
