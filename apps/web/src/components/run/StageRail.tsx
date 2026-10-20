"use client";

import { motion } from "framer-motion";
import { STAGES, useRunStore } from "@/store/run";
import { fmtDuration } from "@/lib/format";

export function StageRail() {
  const stages = useRunStore((s) => s.stages);
  const doneCount = STAGES.filter((name) => stages[name].state === "done").length;
  const progress = doneCount / STAGES.length;

  return (
    <div className="border border-rule p-5">
      <div className="relative h-1 w-full bg-paper-2">
        <motion.div
          className="absolute inset-y-0 left-0 bg-signal"
          animate={{ width: `${progress * 100}%` }}
          transition={{ duration: 0.4, ease: [0.22, 1, 0.36, 1] }}
        />
      </div>
      <div className="mt-4 grid grid-cols-3 gap-4 sm:grid-cols-6">
        {STAGES.map((name) => {
          const st = stages[name];
          return (
            <div key={name} className="flex flex-col gap-1">
              <div
                className={`text-label font-mono font-semibold uppercase tracking-[0.08em] ${
                  st.state === "done"
                    ? "text-ink"
                    : st.state === "running"
                      ? "text-signal"
                      : st.state === "timeout"
                        ? "text-warn"
                        : "text-ink-3"
                }`}
              >
                {name}
              </div>
              <div className="font-mono font-tnum text-small text-ink-3">
                {st.state === "running" && "running"}
                {st.state === "done" && st.ms !== undefined && fmtDuration(st.ms / 1000)}
                {st.state === "timeout" && "timed out"}
                {st.state === "pending" && "pending"}
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}
