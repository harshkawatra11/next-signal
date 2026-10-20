import { Badge, Section, SectionHeading } from "@/components/system";
import { challengeTitle, metricLabel } from "@/lib/headlines";
import type { Hypothesis, Prediction, Report } from "@/types/report";

const STATUS_TONE: Record<Hypothesis["status"], "ink" | "signal" | "warn" | "outline"> = {
  survived: "ink",
  downgraded: "warn",
  killed: "signal",
  proposed: "outline",
};

const DIRECTION_WORDS: Record<Prediction["direction"], string> = {
  up: "to rise",
  down: "to fall",
  flat: "to stay flat",
  present: "to appear",
  absent: "to disappear",
};

function HypothesisCard({ h, glossary }: { h: Hypothesis; glossary?: Record<string, string> }) {
  return (
    <div className="border border-rule p-5">
      <div className="flex items-center justify-between gap-3">
        <span className="font-mono text-label text-ink-3">{h.hyp_id}</span>
        <Badge tone={STATUS_TONE[h.status]}>{h.status}</Badge>
      </div>
      <p className="mt-3 text-body font-semibold text-ink">{h.statement}</p>
      <p className="mt-2 text-small text-ink-2">{h.mechanism}</p>
      {h.predictions.length > 0 && (
        <ul className="mt-3 space-y-1">
          {h.predictions.map((p, i) => (
            <li key={i} className="text-small text-ink-2">
              {metricLabel(p.metric_id, glossary)} expected {DIRECTION_WORDS[p.direction]}; check {p.where_to_check}
            </li>
          ))}
        </ul>
      )}
      {h.kill_reason && (
        <p className="mt-3 border-t border-rule pt-3 text-small text-signal">{h.kill_reason}</p>
      )}
    </div>
  );
}

export function HypothesesSection({ report }: { report: Report }) {
  const { runners_up: runnersUp, killed, glossary } = report;
  if (runnersUp.length === 0 && killed.length === 0) return null;

  return (
    <Section id="hypotheses">
      <SectionHeading index="08" kicker="Every hypothesis the run considered" title={challengeTitle(report)} />
      <div className="grid gap-4 md:grid-cols-2">
        {[...runnersUp, ...killed].map((h) => (
          <HypothesisCard key={h.hyp_id} h={h} glossary={glossary} />
        ))}
      </div>
    </Section>
  );
}
