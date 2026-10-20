"use client";

import { useState } from "react";
import { Table, TableHeader, TableBody, TableRow, TableHead, TableCell } from "@/components/ui/table";
import type { EvidenceItem, OriginClass } from "@/types/report";
import { useEvidenceDrawer } from "@/store/drawer";
import { fmtDateIN } from "@/lib/format";

const ORIGIN_LABEL: Record<OriginClass, string> = {
  company_filing: "Company filing",
  company_ir: "Company IR",
  exchange: "Exchange",
  regulator_us: "US regulator",
  regulator_in: "India regulator",
  sec: "SEC",
  rating_agency: "Rating agency",
  industry_body: "Industry body",
  market_data: "Market data",
  press: "Press",
  aggregator: "Aggregator",
  peer_filing: "Peer filing",
};

export function EvidenceTable({ evidence }: { evidence: EvidenceItem[] }) {
  const [filter, setFilter] = useState<string | null>(null);
  const show = useEvidenceDrawer((s) => s.show);
  const origins = Array.from(new Set(evidence.map((e) => e.origin_class)));
  const rows = filter ? evidence.filter((e) => e.origin_class === filter) : evidence;

  return (
    <div className="border border-rule p-5">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <h3 className="font-mono text-[11px] font-semibold uppercase tracking-[0.1em] text-ink-3">
          Evidence
        </h3>
        <div className="flex flex-wrap gap-1.5">
          <button
            onClick={() => setFilter(null)}
            className={`border px-2 py-0.5 font-mono text-[10px] uppercase ${
              filter === null ? "border-ink bg-ink text-white" : "border-rule text-ink-3"
            }`}
          >
            All
          </button>
          {origins.map((o) => (
            <button
              key={o}
              onClick={() => setFilter(o)}
              className={`border px-2 py-0.5 font-mono text-[10px] uppercase ${
                filter === o ? "border-ink bg-ink text-white" : "border-rule text-ink-3"
              }`}
            >
              {ORIGIN_LABEL[o]}
            </button>
          ))}
        </div>
      </div>

      <Table className="mt-4">
        <TableHeader>
          <TableRow>
            <TableHead>Claim</TableHead>
            <TableHead>Publisher</TableHead>
            <TableHead>Origin</TableHead>
            <TableHead>Grade</TableHead>
            <TableHead>Date</TableHead>
          </TableRow>
        </TableHeader>
        <TableBody>
          {rows.map((e) => (
            <TableRow
              key={e.ev_id}
              className="cursor-pointer"
              onClick={() =>
                show(
                  e,
                  evidence.filter(
                    (x) =>
                      x.ev_id !== e.ev_id &&
                      (x.supports.some((s) => e.supports.includes(s)) ||
                        x.contradicts.some((s) => e.contradicts.includes(s)))
                  )
                )
              }
            >
              <TableCell className="max-w-xs truncate">{e.anchor.quote}</TableCell>
              <TableCell>{e.publisher}</TableCell>
              <TableCell className="text-ink-3">{ORIGIN_LABEL[e.origin_class]}</TableCell>
              <TableCell className="font-mono">{e.reliability}</TableCell>
              <TableCell className="font-tnum text-ink-3">
                {e.published_at ? fmtDateIN(e.published_at) : ""}
              </TableCell>
            </TableRow>
          ))}
        </TableBody>
      </Table>
    </div>
  );
}
