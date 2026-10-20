"use client";

import useSWR from "swr";
import Link from "next/link";
import { Badge, Container, Section, SectionHeading } from "@/components/system";
import { DataTable, type Column } from "@/components/viz";
import { Skeleton } from "@/components/ui/skeleton";
import { getRecentRuns } from "@/lib/api";
import { fmtDateIN, fmtDuration } from "@/lib/format";
import type { RunMeta } from "@/types/report";

const STATUS_TONE: Record<RunMeta["status"], "ink" | "signal" | "warn" | "outline"> = {
  done: "ink",
  partial: "warn",
  failed: "signal",
  running: "outline",
};

export function RecentRuns() {
  const { data: recent, error, isLoading } = useSWR("recent", () => getRecentRuns(50));

  const columns: Column<RunMeta>[] = [
    { key: "company", header: "Company", accessor: (r) => r.company },
    { key: "symbol", header: "Symbol", accessor: (r) => r.symbol, mono: true, width: "96px" },
    { key: "as_of", header: "As of", accessor: (r) => fmtDateIN(r.as_of), mono: true, align: "right", width: "110px" },
    { key: "status", header: "Status", accessor: (r) => <Badge tone={STATUS_TONE[r.status]}>{r.status}</Badge>, width: "110px" },
    {
      key: "runtime",
      header: "Runtime",
      accessor: (r) => (r.runtime_s ? fmtDuration(r.runtime_s) : "-"),
      mono: true,
      align: "right",
      width: "100px",
    },
    {
      key: "open",
      header: "",
      accessor: (r) => (
        <Link
          href={r.status === "done" || r.status === "partial" ? `/report/${r.run_id}` : `/run/${r.run_id}`}
          className="text-signal hover:underline"
        >
          Open
        </Link>
      ),
      width: "72px",
      align: "right",
    },
  ];

  const latest = recent?.[0];
  const title = recent
    ? latest
      ? `${recent.length} runs on record; the latest is ${latest.company}, ${latest.status}`
      : "No runs on record yet"
    : "Recent runs";

  return (
    <Section>
      <Container>
        <SectionHeading index="02" kicker="Recent runs" title={title} />
        {isLoading && <Skeleton className="h-40 w-full bg-paper-2" />}
        {error && <p className="text-sm text-ink-3">The run log is not reachable right now.</p>}
        {recent && recent.length === 0 && <p className="text-sm text-ink-3">No runs yet. Start one above.</p>}
        {recent && recent.length > 0 && (
          <DataTable columns={columns} rows={recent} rowKey={(r) => r.run_id} dense />
        )}
      </Container>
    </Section>
  );
}
