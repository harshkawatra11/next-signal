"use client";

import { exportUrl } from "@/lib/api";
import { toast } from "sonner";

const EXPORTS: Array<{ kind: "pdf" | "md" | "xlsx" | "zip"; label: string; note: string }> = [
  {
    kind: "pdf",
    label: "Research paper (PDF)",
    note: "A research note on the company, written from its filings, six to ten pages.",
  },
  { kind: "md", label: "Markdown", note: "Plain text, every link intact." },
  { kind: "xlsx", label: "Excel workbook", note: "Every table, one sheet each." },
  { kind: "zip", label: "CSV bundle", note: "Every table as a CSV, zipped." },
];

export function ExportPanel({ runId }: { runId: string }) {
  return (
    <div className="border border-rule p-5">
      <h3 className="text-label font-mono font-semibold uppercase tracking-[0.1em] text-ink-3">
        Export
      </h3>
      <div className="mt-4 grid grid-cols-2 gap-3 sm:grid-cols-4">
        {EXPORTS.map((e) => (
          <a
            key={e.kind}
            href={exportUrl(runId, e.kind)}
            download
            onClick={() =>
              toast(
                e.kind === "pdf"
                  ? "Preparing the research paper… the first export can take up to a minute while the text is written."
                  : `Preparing ${e.label}…`,
              )
            }
            className="flex flex-col items-start gap-1 border border-ink p-4 text-left hover:bg-signal-tint"
          >
            <span className="font-mono text-small font-semibold uppercase">{e.label}</span>
            <span className="text-label text-ink-3">{e.note}</span>
          </a>
        ))}
      </div>
    </div>
  );
}
