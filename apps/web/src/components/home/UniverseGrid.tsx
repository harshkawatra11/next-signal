"use client";

import useSWR from "swr";
import Link from "next/link";
import { getUniverse } from "@/lib/api";
import { Skeleton } from "@/components/ui/skeleton";
import type { UniverseRow } from "@/types/report";

const PLAYBOOK_LABEL: Record<string, string> = {
  pharma: "Pharma",
  hospital: "Hospital",
  diagnostics: "Diagnostics",
  generic: "Generic",
};

function Grid({ rows, title, note }: { rows: UniverseRow[]; title: string; note?: string }) {
  if (rows.length === 0) return null;
  return (
    <div className="mt-8">
      <h3 className="font-mono text-[11px] font-semibold uppercase tracking-[0.1em] text-ink-3">
        {title}
      </h3>
      {note && <p className="mt-1 text-xs text-ink-3">{note}</p>}
      <div className="mt-3 grid grid-cols-2 gap-px bg-rule sm:grid-cols-3 md:grid-cols-5">
        {rows.map((r) => (
          <Link
            key={r.symbol}
            href={`/?q=${encodeURIComponent(r.symbol)}#investigate`}
            className="group flex flex-col justify-between bg-background p-4 transition-colors hover:bg-signal-tint"
          >
            <div className="font-mono text-sm font-semibold text-ink group-hover:text-signal">
              {r.symbol}
            </div>
            <div className="mt-2 text-xs text-ink-3">{r.name}</div>
            <div className="mt-2 font-mono text-[10px] uppercase tracking-[0.08em] text-ink-3">
              {PLAYBOOK_LABEL[r.playbook] ?? r.playbook}
            </div>
          </Link>
        ))}
      </div>
    </div>
  );
}

export function UniverseGrid() {
  const { data, error, isLoading } = useSWR("/api/universe", () => getUniverse("D"));

  return (
    <section className="border-b border-rule px-4 py-12">
      <div className="mx-auto max-w-6xl">
        <p className="font-mono text-[11px] font-semibold uppercase tracking-[0.16em] text-signal">
          File 03 // The universe this agent covers
        </p>

        {isLoading && (
          <div className="mt-6 grid grid-cols-2 gap-px bg-rule sm:grid-cols-3 md:grid-cols-5">
            {Array.from({ length: 5 }).map((_, i) => (
              <Skeleton key={i} className="h-28 w-full bg-paper-2" />
            ))}
          </div>
        )}

        {error && (
          <p className="mt-6 text-sm text-ink-3">
            The universe loader is not reachable right now. Start the engine (see the README) to see
            the live NIFTY 50 and tie-break lists here.
          </p>
        )}

        {data && (
          <>
            <Grid rows={data.filter((r) => r.in_nifty50)} title="NIFTY 50 Track D companies" />
            <Grid
              rows={data.filter((r) => !r.in_nifty50)}
              title="Tie-break universe: Nifty Pharma and Nifty Healthcare"
              note="Judges may run the agent on any of these in a tie-break, including companies outside the NIFTY 50."
            />
          </>
        )}
      </div>
    </section>
  );
}
