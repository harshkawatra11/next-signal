import { KpiBand, Section, SectionHeading } from "@/components/system";
import { BarRanked, ChartCard } from "@/components/viz";
import { fmtDuration } from "@/lib/format";
import { methodTitle } from "@/lib/headlines";
import type { Report } from "@/types/report";

export function MethodSection({ report }: { report: Report }) {
  const { meta, stage_ms: stageMs, angles_considered: anglesConsidered, facts_count: factsCount } = report;
  const stageEntries = Object.entries(stageMs);
  const kpis = [
    { label: "Runtime", value: meta.runtime_s ? fmtDuration(meta.runtime_s) : "-" },
    { label: "Documents", value: String(meta.documents) },
    { label: "Verified facts", value: String(factsCount) },
    { label: "LLM calls", value: String(meta.llm_calls) },
    { label: "Sources hit", value: String(meta.sources_hit) },
    { label: "Status", value: meta.status },
  ];

  return (
    <Section id="method">
      <SectionHeading
        index="06"
        kicker="Method"
        title={methodTitle(report)}
        lede="The deterministic stages (Discover, Connect, Calculate, Challenge) do the counting and testing; the language model is only called inside Reason and Prove, and only to explain what the arithmetic already found."
      />
      <KpiBand items={kpis} className="mb-6" />
      <div className="grid gap-5 md:grid-cols-2">
        {stageEntries.length > 0 && (
          <ChartCard title="Stage duration" source="pipeline/run.py" soWhat="Connect and Challenge are usually the slowest stages: Connect fetches and parses filings, Challenge runs the falsification battery.">
            <BarRanked data={stageEntries.map(([stage, ms]) => ({ label: stage, value: ms }))} formatValue={(v) => `${(v / 1000).toFixed(1)}s`} />
          </ChartCard>
        )}
        {anglesConsidered.length > 0 && (
          <ChartCard title="Angles considered" source="Discover stage" soWhat="The highest-scoring angle (data availability times anomaly signal times novelty) is the one Reason investigates first.">
            <BarRanked
              data={anglesConsidered
                .slice()
                .sort((a, b) => b.score - a.score)
                .map((a) => ({ label: a.angle_id, value: a.score }))}
            />
          </ChartCard>
        )}
      </div>
    </Section>
  );
}
