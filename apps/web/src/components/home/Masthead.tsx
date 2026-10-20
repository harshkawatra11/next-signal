"use client";

import useSWR from "swr";
import { motion } from "framer-motion";
import { Reveal } from "@/components/ui/reveal";
import { getEvalSummary, getRecentRuns, getUniverse } from "@/lib/api";
import { fmtDuration } from "@/lib/format";

const LOADING = "…";

export function Masthead() {
  const { data: universe } = useSWR("universe", () => getUniverse());
  const { data: recent } = useSWR("recent", () => getRecentRuns(50));
  const { data: evalSummary, error: evalError, isLoading: evalLoading } = useSWR("eval", getEvalSummary);

  const stats = [
    { label: "Companies in Track D", value: universe ? String(universe.length) : LOADING },
    {
      label: "Runs completed",
      value: recent ? String(recent.filter((r) => r.status === "done").length) : LOADING,
    },
    {
      label: "Companies evaluated",
      value: evalLoading ? LOADING : evalError ? "Not yet run" : String(evalSummary!.n_companies),
    },
    {
      label: "Median runtime",
      value: evalLoading ? LOADING : evalError ? "-" : fmtDuration(evalSummary!.median_runtime_s),
    },
  ];

  return (
    <section className="border-b border-rule px-4 py-16 md:py-24">
      <div className="mx-auto max-w-6xl">
        <Reveal>
          <p className="font-mono text-[11px] font-semibold uppercase tracking-[0.16em] text-signal">
            ATMOS 2026 // Finding the Next Signal // Track D
          </p>
        </Reveal>
        <Reveal delay={0.05}>
          <h1 className="mt-4 max-w-3xl font-serif text-[2.6rem] leading-[1.05] md:text-[4.2rem]">
            Next Signal reads the filings, checks the regulators, and tries to prove itself{" "}
            <em>wrong</em>.
          </h1>
        </Reveal>
        <Reveal delay={0.1}>
          <p className="mt-6 max-w-2xl text-[15px] leading-relaxed text-ink-2">
            Give it any listed pharma or healthcare company. It collects public evidence from the
            exchanges, the USFDA, peers and the market, computes what changed and when, tests every
            hypothesis against its strongest alternative, and reports only what survives, with a link
            behind every number.
          </p>
        </Reveal>

        <motion.div
          className="mt-10 h-px bg-signal"
          initial={{ scaleX: 0 }}
          animate={{ scaleX: 1 }}
          transition={{ duration: 0.6, ease: [0.22, 1, 0.36, 1] }}
          style={{ transformOrigin: "left" }}
        />

        <div className="mt-8 grid grid-cols-2 gap-6 md:grid-cols-4">
          {stats.map((stat, i) => (
            <div
              key={stat.label}
              className={`font-tnum ${i > 0 ? "border-l border-rule pl-6" : ""}`}
            >
              <div className="font-mono text-2xl font-semibold text-ink">{stat.value}</div>
              <div className="mt-1 font-mono text-[10px] uppercase tracking-[0.1em] text-ink-3">
                {stat.label}
              </div>
            </div>
          ))}
        </div>
      </div>
    </section>
  );
}
