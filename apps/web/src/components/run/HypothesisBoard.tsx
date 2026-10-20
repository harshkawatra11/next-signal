"use client";

import { AnimatePresence, motion } from "framer-motion";
import { useRunStore } from "@/store/run";
import { Badge } from "@/components/system/Badge";
import type { HypothesisCardState } from "@/store/run";

const STATUS_TONE: Record<HypothesisCardState["status"], { tone: "signal" | "ink" | "warn" | "outline" }> = {
  killed: { tone: "signal" },
  survived: { tone: "ink" },
  downgraded: { tone: "warn" },
  proposed: { tone: "outline" },
};

export function HypothesisBoard() {
  const hypotheses = useRunStore((s) => s.hypotheses);
  const cards = Object.values(hypotheses);

  return (
    <div className="border border-rule p-5">
      <h3 className="text-label font-mono font-semibold uppercase tracking-[0.1em] text-ink-3">
        Hypotheses
      </h3>
      {cards.length === 0 && (
        <p className="mt-3 text-small text-ink-3">No hypotheses proposed yet.</p>
      )}
      <div className="mt-3 grid gap-3 sm:grid-cols-2">
        <AnimatePresence>
          {cards.map((card) => (
            <motion.div
              key={card.hyp_id}
              layout
              initial={{ opacity: 0, y: 6 }}
              animate={{ opacity: 1, y: 0 }}
              className="relative border border-rule p-3"
            >
              <div className="flex items-start justify-between gap-2">
                <p className="text-small leading-snug text-ink">{card.statement}</p>
                <Badge tone={STATUS_TONE[card.status].tone} className="flex-shrink-0">
                  {card.status}
                </Badge>
              </div>
              {card.kill_reason && (
                <p className="mt-1 text-label text-ink-3">{card.kill_reason}</p>
              )}
              <div className="mt-2 flex flex-wrap gap-1">
                {Object.entries(card.tests).map(([testId, passed]) => (
                  <span
                    key={testId}
                    className={`font-mono text-label font-semibold uppercase ${
                      passed === true
                        ? "text-ink"
                        : passed === false
                          ? "text-signal"
                          : "text-ink-3"
                    }`}
                  >
                    {testId}
                  </span>
                ))}
              </div>
            </motion.div>
          ))}
        </AnimatePresence>
      </div>
    </div>
  );
}
