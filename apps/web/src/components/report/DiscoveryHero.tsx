"use client";

import type { Discovery, RunMeta } from "@/types/report";
import { StrengthBadge } from "./StrengthBadge";
import { StrengthBar } from "./StrengthBar";
import { useEvidenceDrawer } from "@/store/drawer";

const ORIGIN_LABEL: Record<string, string> = {
  company_filing: "Company",
  company_ir: "Company",
  exchange: "Exchange",
  regulator_us: "Regulator",
  regulator_in: "Regulator",
  sec: "SEC",
  rating_agency: "Rating agency",
  industry_body: "Industry body",
  market_data: "Market",
  press: "Press",
  aggregator: "Aggregator",
  peer_filing: "Peer",
};

function independentOrigins(discovery: Discovery): string[] {
  const seen = new Set<string>();
  for (const e of discovery.evidence) {
    const key = e.origin_class === "company_filing" || e.origin_class === "company_ir" ? "company" : e.origin_class;
    seen.add(key);
  }
  return Array.from(seen);
}

export function DiscoveryHero({ meta, discovery }: { meta: RunMeta; discovery: Discovery }) {
  const show = useEvidenceDrawer((s) => s.show);
  const origins = independentOrigins(discovery);

  // Underline every numeric token in the sentence and make it clickable to the first evidence item
  // whose quote contains that same number (the brief's own "click through from each claim to its
  // source" requirement, applied at the sentence level, not just the Numbers table).
  const parts = discovery.sentence.split(/(\d[\d,.]*%?)/);

  function findEvidenceFor(numberText: string) {
    const digits = numberText.replace(/[,%]/g, "");
    return discovery.evidence.find((e) => e.anchor.quote.replace(/[,%]/g, "").includes(digits));
  }

  return (
    <section className="border-b-2 border-ink px-4 py-10">
      <div className="mx-auto max-w-6xl">
        <p className="font-mono text-[11px] font-semibold uppercase tracking-[0.16em] text-signal">
          File 01 // The Discovery
        </p>
        <div className="mt-2 flex flex-wrap items-baseline gap-3">
          <h2 className="font-serif text-2xl">{meta.company}</h2>
          <span className="font-mono text-sm text-ink-3">
            {meta.symbol} · {meta.sub_industry} · as of {meta.as_of}
          </span>
        </div>

        <div className="mt-6 grid gap-8 md:grid-cols-[1fr_320px]">
          <p className="font-serif text-[1.6rem] leading-snug md:text-[2rem]">
            {parts.map((part, i) => {
              if (!/^\d/.test(part)) return <span key={i}>{part}</span>;
              const ev = findEvidenceFor(part);
              if (!ev) return <span key={i}>{part}</span>;
              return (
                <button
                  key={i}
                  onClick={() => show(ev, discovery.evidence.filter((e) => e.ev_id !== ev.ev_id))}
                  className="underline decoration-signal decoration-2 underline-offset-2 hover:text-signal"
                >
                  {part}
                </button>
              );
            })}
          </p>

          <div>
            <StrengthBadge label={discovery.strength.label} total={discovery.strength.total} />
            <div className="mt-4">
              <StrengthBar breakdown={discovery.strength} />
            </div>
            <div className="mt-8">
              <div className="font-mono text-[10px] uppercase tracking-[0.08em] text-ink-3">
                Novelty
              </div>
              <div className="mt-1 h-1.5 w-full bg-paper-2">
                <div
                  className="h-full bg-signal"
                  style={{ width: `${discovery.novelty * 100}%` }}
                />
              </div>
            </div>
            <div className="mt-4 font-mono text-[10px] uppercase tracking-[0.08em] text-ink-3">
              Independent origins: {origins.length}
            </div>
            <div className="mt-1 flex flex-wrap gap-1.5">
              {origins.map((o) => (
                <span key={o} className="border border-rule px-1.5 py-0.5 text-[10px] text-ink-2">
                  {ORIGIN_LABEL[o] ?? o}
                </span>
              ))}
            </div>
          </div>
        </div>
      </div>
    </section>
  );
}
