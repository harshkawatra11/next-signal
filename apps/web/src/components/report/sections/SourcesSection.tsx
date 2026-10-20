"use client";

import { useState } from "react";
import { Section, SectionHeading } from "@/components/system";
import { BarRanked, ChartCard, DataTable, type Column } from "@/components/viz";
import { fmtDateIN } from "@/lib/format";
import { sourcesTitle } from "@/lib/headlines";
import type { Document, Report } from "@/types/report";

export function SourcesSection({ documents, report }: { documents: Document[]; report: Report }) {
  const [showAll, setShowAll] = useState(false);
  if (documents.length === 0) return null;

  const sorted = [...documents].sort((a, b) => (b.published_at ?? "").localeCompare(a.published_at ?? ""));
  const visible = showAll ? sorted : sorted.slice(0, 25);

  const kindCounts = new Map<string, number>();
  for (const d of documents) kindCounts.set(d.kind, (kindCounts.get(d.kind) ?? 0) + 1);
  const barData = Array.from(kindCounts.entries())
    .sort((a, b) => b[1] - a[1])
    .map(([kind, count]) => ({ label: kind.replace(/_/g, " "), value: count }));

  const columns: Column<Document>[] = [
    { key: "date", header: "Date", accessor: (d) => (d.published_at ? fmtDateIN(d.published_at) : "-"), mono: true, width: "110px" },
    { key: "kind", header: "Kind", accessor: (d) => d.kind.replace(/_/g, " "), width: "140px" },
    {
      key: "title",
      header: "Title",
      accessor: (d) => (
        <a href={d.url} target="_blank" rel="noreferrer" className="text-signal hover:underline">
          {d.title}
        </a>
      ),
    },
    { key: "publisher", header: "Publisher", accessor: (d) => d.publisher },
    { key: "grade", header: "Grade", accessor: (d) => d.reliability, mono: true, align: "right", width: "72px" },
  ];

  return (
    <Section id="sources">
      <SectionHeading index="07" kicker="Sources" title={sourcesTitle(report)} />
      <div className="grid gap-5">
        <ChartCard title="Documents by kind" source="Connect stage">
          <BarRanked data={barData} />
        </ChartCard>
        <div className="border border-rule p-5 md:p-6">
          <div className="flex items-center justify-between">
            <h3 className="text-h3 font-sans font-semibold text-ink">Document register</h3>
            {sorted.length > 25 && (
              <button
                type="button"
                onClick={() => setShowAll((v) => !v)}
                className="font-mono text-label uppercase tracking-[0.1em] text-signal hover:underline"
              >
                {showAll ? "Show first 25" : `Show all ${sorted.length}`}
              </button>
            )}
          </div>
          <div className="mt-4">
            <DataTable columns={columns} rows={visible} rowKey={(d) => d.doc_id} dense />
          </div>
        </div>
      </div>
    </Section>
  );
}
