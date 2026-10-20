"use client";

import {
  Tooltip,
  TooltipContent,
  TooltipTrigger,
} from "@/components/ui/tooltip";
import type { NumberBlock } from "@/types/report";

export function NumbersGrid({ numbers }: { numbers: NumberBlock[] }) {
  return (
    <div className="border border-rule p-5">
      <h3 className="font-mono text-[11px] font-semibold uppercase tracking-[0.1em] text-ink-3">
        Numbers
      </h3>
      <div className="mt-3 grid grid-cols-2 gap-px bg-rule sm:grid-cols-3">
        {numbers.map((n) => (
          <Tooltip key={n.number_id}>
            <TooltipTrigger className="cursor-help bg-background p-4 text-left">
              <div className="font-mono text-2xl font-semibold text-ink">{n.display}</div>
              <div className="mt-1 text-[11px] text-ink-3">{n.label}</div>
              <div className="mt-1 font-mono text-[10px] text-ink-3">{n.period}</div>
            </TooltipTrigger>
            <TooltipContent className="max-w-xs">
              <p className="font-mono text-xs">{n.formula}</p>
            </TooltipContent>
          </Tooltip>
        ))}
      </div>
    </div>
  );
}
