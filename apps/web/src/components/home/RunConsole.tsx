"use client";

import { useState } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";
import { toast } from "sonner";
import { startRun } from "@/lib/api";

export function RunConsole() {
  const router = useRouter();
  const searchParams = useSearchParams();
  // Lazy initializer, not an effect: the ?q= param (set when a UniverseGrid card is clicked) only
  // needs to seed the field once on mount, so this avoids the extra render an effect-driven
  // setState would cause.
  const [query, setQuery] = useState(() => searchParams.get("q") ?? "");
  const [asOfMode, setAsOfMode] = useState(false);
  const [asOf, setAsOf] = useState("");
  const [loading, setLoading] = useState(false);

  async function handleInvestigate() {
    if (!query.trim()) {
      toast.error("Enter a company name or NSE symbol first.");
      return;
    }
    setLoading(true);
    try {
      const { run_id } = await startRun(query.trim(), asOfMode && asOf ? asOf : undefined);
      router.push(`/run/${run_id}`);
    } catch (err) {
      toast.error(
        err instanceof Error
          ? `Could not start the run: ${err.message}`
          : "Could not start the run."
      );
      setLoading(false);
    }
  }

  return (
    <section id="investigate" className="border-b border-rule px-4 py-12">
      <div className="mx-auto max-w-6xl">
        <p className="font-mono text-[11px] font-semibold uppercase tracking-[0.16em] text-signal">
          File 01 // Investigate a company
        </p>
        <div className="mt-4 flex flex-col gap-3 md:flex-row md:items-center">
          <Input
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === "Enter") handleInvestigate();
            }}
            placeholder="Company name or NSE symbol, for example CIPLA"
            className="h-12 flex-1 border-rule text-base"
          />
          <Button
            onClick={handleInvestigate}
            disabled={loading}
            className="h-12 bg-signal px-8 text-base font-semibold text-white hover:bg-signal-deep"
          >
            {loading ? "Starting…" : "Investigate"}
          </Button>
        </div>
        <div className="mt-3 flex items-center gap-2">
          <input
            id="as-of-toggle"
            type="checkbox"
            checked={asOfMode}
            onChange={(e) => setAsOfMode(e.target.checked)}
            className="h-4 w-4 accent-signal"
          />
          <label htmlFor="as-of-toggle" className="text-sm text-ink-2">
            Run as of an earlier date
          </label>
          {asOfMode && (
            <input
              type="date"
              value={asOf}
              onChange={(e) => setAsOf(e.target.value)}
              className="ml-2 border border-rule px-2 py-1 text-sm"
            />
          )}
        </div>
      </div>
    </section>
  );
}
