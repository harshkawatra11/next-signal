"use client";

import useSWR from "swr";
import { Topbar } from "@/components/layout/Topbar";
import { Footer } from "@/components/layout/Footer";
import { Tabs, TabsList, TabsTrigger, TabsContent } from "@/components/ui/tabs";
import { Skeleton } from "@/components/ui/skeleton";
import { Container, Kicker, KpiBand } from "@/components/system";
import { DiscoveryHero } from "@/components/report/DiscoveryHero";
import { WhyItMatters } from "@/components/report/WhyItMatters";
import { NumbersGrid } from "@/components/report/NumbersGrid";
import { TimelineChart } from "@/components/report/TimelineChart";
import { EvidenceTable } from "@/components/report/EvidenceTable";
import { ChallengeTab } from "@/components/report/ChallengeTab";
import { ExportPanel } from "@/components/report/ExportPanel";
import { EvidenceDrawer } from "@/components/report/EvidenceDrawer";
import { FinancialsSection } from "@/components/report/sections/FinancialsSection";
import { AnomaliesSection } from "@/components/report/sections/AnomaliesSection";
import { MethodSection } from "@/components/report/sections/MethodSection";
import { MetricHeatSection } from "@/components/report/sections/MetricHeatSection";
import { PeersSection } from "@/components/report/sections/PeersSection";
import { SourcesSection } from "@/components/report/sections/SourcesSection";
import { HypothesesSection } from "@/components/report/sections/HypothesesSection";
import { fmtDuration } from "@/lib/format";
import { getReport } from "@/lib/api";
import type { ACHMatrix as ACHMatrixType } from "@/types/report";

function asAch(value: unknown): ACHMatrixType | undefined {
  if (value && typeof value === "object" && "hypotheses" in value && "evidence" in value) {
    return value as ACHMatrixType;
  }
  return undefined;
}

export function ReportView({ runId }: { runId: string }) {
  const { data: report, error, isLoading } = useSWR(`/api/runs/${runId}/report`, () => getReport(runId));

  return (
    <>
      <Topbar />
      <main className="flex-1">
        {isLoading && (
          <Container className="space-y-4 py-10">
            <Skeleton className="h-10 w-1/3 bg-paper-2" />
            <Skeleton className="h-40 w-full bg-paper-2" />
            <Skeleton className="h-64 w-full bg-paper-2" />
          </Container>
        )}

        {error && (
          <Container className="py-10">
            <p className="text-sm text-ink-3">
              Could not load this report. The engine may not be running, or this run id does not exist.
            </p>
          </Container>
        )}

        {report && !report.discovery && (
          <>
            <Container className="py-16">
              <Kicker>Case file // No discovery survived</Kicker>
              <h1 className="mt-3 max-w-2xl text-h1 font-serif leading-h1 text-ink">
                Every hypothesis on {report.meta.company} was killed or downgraded below a reportable
                strength.
              </h1>
              <p className="mt-4 max-w-2xl text-body leading-body text-ink-2">
                The Challenge stage withholds a finding rather than report one that did not survive
                scrutiny. The financial base, anomaly scoring and method below ran in full regardless of
                the outcome, since the engine computes before it decides whether it has anything worth
                reporting.
              </p>
              <KpiBand
                className="mt-8"
                items={[
                  { label: "Runtime", value: report.meta.runtime_s ? fmtDuration(report.meta.runtime_s) : "-" },
                  { label: "Documents", value: String(report.meta.documents) },
                  { label: "Verified facts", value: String(report.facts_count) },
                  { label: "Anomalies", value: String(report.anomalies.length) },
                  { label: "Hypotheses", value: String(report.killed.length + report.runners_up.length) },
                  { label: "Killed", value: String(report.killed.length) },
                  { label: "LLM calls", value: String(report.meta.llm_calls) },
                ]}
              />
              {report.killed.length > 0 && (
                <div className="mt-8 border border-rule p-5">
                  <h3 className="text-h3 font-sans font-semibold text-ink">Kill log</h3>
                  <ul className="mt-3 space-y-2">
                    {report.killed.map((h) => (
                      <li key={h.hyp_id} className="text-small">
                        <span className="font-semibold text-ink">{h.statement}</span>
                        <span className="ml-2 text-ink-3">{h.kill_reason}</span>
                      </li>
                    ))}
                  </ul>
                </div>
              )}
            </Container>
            <Container>
              <FinancialsSection financials={report.financials} company={report.meta.company} />
              <AnomaliesSection anomalies={report.anomalies} glossary={report.glossary} />
              <MethodSection report={report} />
              <SourcesSection documents={report.documents} report={report} />
              <HypothesesSection report={report} />
              <ExportPanel runId={runId} />
            </Container>
          </>
        )}

        {report && report.discovery && (
          <>
            <DiscoveryHero meta={report.meta} discovery={report.discovery} />
            <Container className="py-8">
              <Tabs defaultValue="overview">
                <TabsList>
                  <TabsTrigger value="overview">Overview</TabsTrigger>
                  <TabsTrigger value="data">Data</TabsTrigger>
                  <TabsTrigger value="evidence">Evidence</TabsTrigger>
                  <TabsTrigger value="sources">Sources</TabsTrigger>
                  <TabsTrigger value="challenge">Challenge</TabsTrigger>
                  <TabsTrigger value="export">Export</TabsTrigger>
                </TabsList>

                <TabsContent value="overview" className="mt-4 grid gap-4">
                  <WhyItMatters bullets={report.discovery.why_it_matters} />
                  <NumbersGrid numbers={report.discovery.numbers} />
                  <TimelineChart points={report.discovery.timeline} />
                </TabsContent>

                <TabsContent value="data" className="mt-4">
                  <FinancialsSection financials={report.financials} company={report.meta.company} />
                  <MetricHeatSection series={report.series} subject={report.meta.symbol} glossary={report.glossary} />
                  <AnomaliesSection anomalies={report.anomalies} glossary={report.glossary} />
                  <PeersSection series={report.series} subject={report.meta.symbol} peers={report.peers} glossary={report.glossary} />
                  <MethodSection report={report} />
                </TabsContent>

                <TabsContent value="evidence" className="mt-4">
                  <EvidenceTable evidence={report.discovery.evidence} />
                </TabsContent>

                <TabsContent value="sources" className="mt-4">
                  <SourcesSection documents={report.documents} report={report} />
                </TabsContent>

                <TabsContent value="challenge" className="mt-4 grid gap-4">
                  <ChallengeTab
                    discovery={report.discovery}
                    tests={report.tests}
                    killed={report.killed}
                    ach={asAch(report.ach)}
                    contradictions={report.contradictions}
                  />
                  <HypothesesSection report={report} />
                </TabsContent>

                <TabsContent value="export" className="mt-4">
                  <ExportPanel runId={runId} />
                </TabsContent>
              </Tabs>
            </Container>
          </>
        )}
      </main>
      <Footer />
      <EvidenceDrawer />
    </>
  );
}
